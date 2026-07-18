# Data Ingestion — Amazon Product Dataset 2020

Ingestion pipeline for the voice-to-voice product discovery assistant. Turns the
raw Kaggle dump into a Chroma vector index that the `rag.search` MCP tool queries.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # defaults to local embeddings, no API key needed
```

Requires a Kaggle API token at `~/.kaggle/kaggle.json` (from kaggle.com/settings → API → Create New Token).

## Pipeline

Run in order (or step through `notebooks/01_data_ingestion.ipynb`):

```bash
cd src/ingestion
python download_data.py    # kagglehub -> data/raw/*.csv
python inspect_schema.py   # confirm real column names before trusting clean.py
python clean.py            # data/raw -> data/processed/products.parquet
python build_index.py      # products.parquet -> data/chroma_db/ (Chroma collection)
python retriever.py        # sanity-check query
```

| Stage | Input | Output | What it does |
|---|---|---|---|
| `download_data.py` | Kaggle | `data/raw/*.csv` | Fetches `promptcloud/amazon-product-dataset-2020` via kagglehub |
| `inspect_schema.py` | `data/raw/*.csv` | stdout | Prints real column names/dtypes — PromptCloud's schema varies by revision |
| `clean.py` | `data/raw/*.csv` | `data/processed/products.parquet` | Resolves fields via alias matching, parses price/rating, filters to the category slice, derives `price_per_unit` |
| `build_index.py` | `products.parquet` | `data/chroma_db/` | Embeds `title + features + ingredients`, upserts into a persistent Chroma collection (cosine distance) with filterable metadata |
| `retriever.py` | `data/chroma_db/` | — | `RagRetriever.search(query, k, where)` — the function the `rag.search` MCP tool should import directly |

Verified end-to-end against the real download: 10,002 raw rows → 708 products in the `Home & Kitchen` slice → indexed and queryable (see [Known data-quality limitations](#known-data-quality-limitations)).

## Schema

`products.parquet` columns: `id, title, brand, category, price, rating, ingredients, features, unit_qty, unit, price_per_unit, url, doc_id`.

`doc_id` is the stable citation key used by the Answerer agent and surfaced in the UI's citation panel.

## Category slice

`CATEGORY_TOP_LEVEL` in `.env` (default `Home & Kitchen`) is matched exactly against the top-level segment of each product's `|`-delimited `Category` breadcrumb — e.g. the `Home & Kitchen` in `Home & Kitchen | Bedding | ...`.

**Why not Household Cleaning, per the spec's suggestion?** The actual `promptcloud/amazon-product-dataset-2020` file kagglehub returns (`marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv`, 10,002 rows) is a general marketplace sample dominated by Toys & Games (6,662 rows). Only 23 rows fall under `Health & Household` at all, and just 7 have "cleaning" anywhere in their category breadcrumb — too thin for a meaningful comparison demo. `Home & Kitchen` (708 rows: Home Décor, Furniture, Bedding, Event & Party Supplies, Kitchen & Dining) is the closest well-populated category to the spec's product-discovery use case. Swap `CATEGORY_TOP_LEVEL` back to `Health & Household` (or any other top-level category) if the team decides a thinner, on-spec slice is preferable — the pipeline doesn't care which one you pick.

An earlier version of this filter matched the keyword "clean" against title/description text directly, which pulled in unrelated products (plush toys, blankets) because their marketing copy says things like "wipe clean" or "easy to clean." Matching only the structured category breadcrumb's top-level segment avoids that false-positive problem regardless of which category is chosen.

## Known data-quality limitations

Confirmed against the real downloaded file — worth stating explicitly in the writeup/safety notes:

- **`Brand Name` and `Ingredients` are 100% empty** across all 10,002 raw rows, not just this slice. The Answerer agent should not claim brand or ingredient facts for these products; `retriever.py` already returns `None` for both rather than fabricating a value.
- **No rating/review-count column exists** in this file at all (`clean.py` logs a warning and leaves `rating` as `None`). If the team wants ratings for the demo, either source a `reviews.parquet` from a different PromptCloud file or drop rating-based comparisons from the example queries.
- **`price_per_unit`** is only derived when a quantity+unit (oz, lb, ct, etc.) is parseable from the title/weight/description text — 622 of 708 rows (88%) in the current slice. `price` itself is populated for 695/708.

## Embedding backend (model-agnostic)

Set `EMBEDDING_PROVIDER` in `.env`:
- `local` (default) — `sentence-transformers/all-MiniLM-L6-v2`, no API key, runs offline.
- `openai` — `text-embedding-3-small`, requires `OPENAI_API_KEY`.

Both implement the same `EmbeddingProvider.embed(texts) -> list[list[float]]` interface in `embeddings.py`, so swapping providers doesn't touch `build_index.py` or `retriever.py`.

## Handing off to the MCP layer

`rag.search` should be a thin wrapper:

```python
from retriever import RagRetriever, build_where

retriever = RagRetriever()
retriever.search(query, k=5, where=build_where(max_price=15, min_rating=4.0, brand="Method"))
```

Returned dicts already match the `{sku, title, price, rating, brand, ingredients, doc_id}` contract from the project spec.
