"""products.parquet -> persistent Chroma collection.

Embedding text = title + features + ingredients (semantic signal).
Metadata = price/rating/brand/ingredients/doc_id, kept alongside so
rag.search can combine vector similarity with metadata filters.
"""
import math

import chromadb
import pandas as pd
from tqdm import tqdm

from config import CHROMA_COLLECTION, CHROMA_DIR, PRODUCTS_PARQUET
from embeddings import get_embedder

BATCH_SIZE = 64


def _embedding_text(row: pd.Series) -> str:
    parts = [row["title"], row.get("features", ""), row.get("ingredients", "") or ""]
    return " ".join(str(p) for p in parts if p and not pd.isna(p)).strip()


def _clean_metadata(row: pd.Series) -> dict:
    meta = {
        "sku": str(row["id"]),
        "doc_id": str(row["doc_id"]),
        "title": str(row["title"]),
        "brand": str(row["brand"]) if pd.notna(row.get("brand")) else "",
        "category": str(row["category"]) if pd.notna(row.get("category")) else "",
        "ingredients": str(row["ingredients"]) if pd.notna(row.get("ingredients")) else "",
        "url": str(row["url"]) if pd.notna(row.get("url")) else "",
    }
    price = row.get("price")
    meta["price"] = float(price) if price is not None and not (isinstance(price, float) and math.isnan(price)) else -1.0
    rating = row.get("rating")
    meta["rating"] = float(rating) if rating is not None and not (isinstance(rating, float) and math.isnan(rating)) else -1.0
    price_per_unit = row.get("price_per_unit")
    meta["price_per_unit"] = (
        float(price_per_unit)
        if price_per_unit is not None and not (isinstance(price_per_unit, float) and math.isnan(price_per_unit))
        else -1.0
    )
    return meta


def build_index() -> None:
    df = pd.read_parquet(PRODUCTS_PARQUET)
    embedder = get_embedder()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    client.delete_collection(CHROMA_COLLECTION) if CHROMA_COLLECTION in [c.name for c in client.list_collections()] else None
    collection = client.create_collection(CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})

    for start in tqdm(range(0, len(df), BATCH_SIZE), desc="embedding + indexing"):
        batch = df.iloc[start:start + BATCH_SIZE]
        texts = [_embedding_text(row) for _, row in batch.iterrows()]
        vectors = embedder.embed(texts)
        collection.add(
            ids=[str(x) for x in batch["doc_id"].tolist()],
            embeddings=vectors,
            documents=texts,
            metadatas=[_clean_metadata(row) for _, row in batch.iterrows()],
        )

    print(f"indexed {len(df)} products into collection {CHROMA_COLLECTION!r} at {CHROMA_DIR}")


if __name__ == "__main__":
    build_index()
