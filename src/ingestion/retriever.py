"""Query interface over the Chroma index. This is what the rag.search MCP
tool should import and call directly — its return shape matches the
{sku, title, price, rating, brand, ingredients, doc_id} contract the
Retriever/Answerer agents expect for citations.
"""
from typing import Optional

import chromadb

from config import CHROMA_COLLECTION, CHROMA_DIR
from embeddings import get_embedder


def build_where(
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    brand: Optional[str] = None,
) -> Optional[dict]:
    clauses = []
    if max_price is not None:
        clauses.append({"price": {"$lte": max_price}})
    if min_rating is not None:
        clauses.append({"rating": {"$gte": min_rating}})
    if brand is not None:
        clauses.append({"brand": brand})
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
                "ingredients": meta["ingredients"] or None,
                "doc_id": meta["doc_id"],
                "score": 1 - distance,
            })
        return hits


if __name__ == "__main__":
    retriever = RagRetriever()
    for hit in retriever.search("eco-friendly stainless steel cleaner", k=5, where=build_where(max_price=15)):
        print(hit)
