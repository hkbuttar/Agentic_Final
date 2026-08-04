"""Query interface over the Chroma index. This is what the rag.search MCP
tool should import and call directly — its return shape matches the
{sku, title, price, rating, brand, ingredients, doc_id} contract the
Retriever/Answerer agents expect for citations, plus category/
category_top_level so results can be organized/filtered by category over
the full (unfiltered-at-ingestion) product set, brand_inferred — a
heuristic guess, never to be treated the same as the (always-empty) real
`brand` field (see clean.py's _infer_brand) — and price_per_unit/unit, the
normalized price that makes differently-sized listings comparable.
"""
from typing import Optional

import chromadb

from config import CHROMA_COLLECTION, CHROMA_DIR
from embeddings import get_embedder


def build_where(
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
) -> Optional[dict]:
    clauses = []
    if max_price is not None:
        clauses.append({"price": {"$lte": max_price}})
    if min_rating is not None:
        clauses.append({"rating": {"$gte": min_rating}})
    if brand is not None:
        clauses.append({"brand": brand})
    if category is not None:
        clauses.append({"category_top_level": category})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class RagRetriever:
    def __init__(self):
        self._embedder = get_embedder()
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._collection = client.get_collection(CHROMA_COLLECTION)

    def search(self, query: str, k: int = 5, where: Optional[dict] = None) -> list[dict]:
        vector = self._embedder.embed([query])[0]
        result = self._collection.query(query_embeddings=[vector], n_results=k, where=where)

        hits = []
        for meta, distance in zip(result["metadatas"][0], result["distances"][0]):
            hits.append({
                "sku": meta["sku"],
                "title": meta["title"],
                "price": meta["price"] if meta["price"] >= 0 else None,
                "rating": meta["rating"] if meta["rating"] >= 0 else None,
                "brand": meta["brand"] or None,
                "brand_inferred": meta["brand_inferred"] or None,
                "category": meta["category"] or None,
                "category_top_level": meta["category_top_level"] or None,
                "ingredients": meta["ingredients"] or None,
                "model_number": meta["model_number"] or None,
                # Normalized price, for fair comparison between differently-
                # sized listings ("$0.42/oz" vs "$0.61/oz"). Always paired
                # with `unit` — the number alone can't be compared, since
                # one row's unit is ounces and the next row's is count.
                # Derived from `Shipping Weight`, which is unreliable at the
                # low end (see src/ingestion/README.md#known-data-quality-
                # limitations), so this is supporting detail, not a ranking
                # key: rows whose weight is a placeholder produce a wildly
                # inflated per-unit price.
                "price_per_unit": meta["price_per_unit"] if meta["price_per_unit"] >= 0 else None,
                "unit": meta["unit"] or None,
                "url": meta["url"] or None,
                "doc_id": meta["doc_id"],
                "score": 1 - distance,
            })
        return hits


if __name__ == "__main__":
    retriever = RagRetriever()
    where = build_where(max_price=15, category="Home & Kitchen")
    for hit in retriever.search("eco-friendly stainless steel cleaner", k=5, where=where):
        print(hit)
