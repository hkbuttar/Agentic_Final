# Ingestion Pipeline

Turns the raw Kaggle Amazon Product Dataset 2020 dump into the Chroma
vector index that the [`rag.search` MCP tool](../mcp_server/README.md)
queries — see the top-level README's
[Retrieval Corpus](../../README.md#retrieval-corpus) for where this fits
in the overall architecture.

## Setup

```bash
pip install -r ../../requirements.txt   # from src/ingestion/, or -r requirements.txt from repo root
cp ../../.env.example ../../.env        # embeddings run fully local, no API key needed
```

Requires a Kaggle API token (from kaggle.com/settings → API → Create New
Token) — either the classic `~/.kaggle/kaggle.json`, or the newer
`~/.kaggle/access_token` file format.

## Pipeline

Run in order (or step through
[notebooks/00_eda.ipynb](../../notebooks/00_eda.ipynb) then
[notebooks/01_data_ingestion.ipynb](../../notebooks/01_data_ingestion.ipynb)):

```bash
cd src/ingestion
python download_data.py    # kagglehub -> data/raw/*.csv
python inspect_schema.py   # confirm real column names (see notebooks/00_eda.ipynb for the full analysis)
python clean.py            # data/raw -> data/processed/products.parquet
python build_index.py      # products.parquet -> data/chroma_db/ (Chroma collection)
python retriever.py        # sanity-check query
```

| Stage | Input | Output | What it does |
|---|---|---|---|
| `download_data.py` | Kaggle | `data/raw/*.csv` | Fetches `promptcloud/amazon-product-dataset-2020` via `kagglehub` |
| `inspect_schema.py` | `data/raw/*.csv` | stdout | Prints real column names/dtypes |
| `clean.py` | `data/raw/*.csv` | `data/processed/products.parquet` | Reads the known columns directly (see [Column names](#column-names)), parses price, strips boilerplate text, extracts `category_top_level`, derives `price_per_unit` |
| `build_index.py` | `products.parquet` | `data/chroma_db/` | Embeds `title + features + ingredients` with `all-MiniLM-L6-v2`, upserts into a persistent Chroma collection (cosine distance) with filterable metadata |
| `retriever.py` | `data/chroma_db/` | — | `RagRetriever.search(query, k, where)` — the function the `rag.search` MCP tool should import directly |

[notebooks/00_eda.ipynb](../../notebooks/00_eda.ipynb) is the exploratory
pass that justifies every choice below (column completeness, category
distribution, price distribution) — run it first if you want the
reasoning, not just the conclusions.

Verified end-to-end against the real download: 10,002 raw rows → 10,002
products (every row keeps a non-empty title and a unique `Uniq Id`, so
nothing gets dropped) → indexed and queryable across all categories (see
[Known data-quality limitations](#known-data-quality-limitations)).

**Deploying:** `data/chroma_db/` is gitignored, not committed (at 10,002
rows the built index is ~128MB, over GitHub's 100MB file limit) —
`data/processed/products.parquet` (7.3MB) is committed instead, and the
deploy host rebuilds the index from it at build time (`python build_index.py`,
~25s). See [src/api/README.md](../api/README.md) if you're setting that up.

## Schema

`products.parquet` columns: `id, title, brand, brand_inferred, category, category_top_level, price, rating, ingredients, model_number, features, unit_qty, unit, price_per_unit, url, doc_id`.

`doc_id` is the stable citation key used by the Answerer agent and surfaced in the UI's citation panel.

## Column names

`clean.py` reads these raw CSV columns directly by name — no alias/fuzzy matching, since this file's schema is fixed and already confirmed via `inspect_schema.py`:

| target field | raw column |
|---|---|
| `id` | `Uniq Id` |
| `title` | `Product Name` |
| `brand` | `Brand Name` (always empty — see below) |
| `brand_inferred` | derived from `Product Name`'s first word — a heuristic guess, not real data (see [Brand inference](#brand-inference)) |
| `category` | `Category` (full `|`-delimited breadcrumb, kept as-is) |
| `category_top_level` | derived from `Category` — just the first breadcrumb segment (see [Category organization](#category-organization)) |
| `price` | `Selling Price` ($-anchored parse — see below) |
| `ingredients` | `Ingredients` (always empty — see below) |
| `model_number` | `Model Number` (82% populated, not embedded, kept as a lookup/citation aid) |
| `url` | `Product Url` |
| `features` | `About Product` + `Technical Details`, boilerplate-stripped (see below) |
| `unit_qty` / `unit` | parsed from `Product Name` / `Shipping Weight` / `About Product` |
| `rating` | none — no such column exists in this file, hardcoded to `None` |

If the team swaps in a different PromptCloud CSV with a different schema, update the `COL_*` constants at the top of `clean.py` — run `inspect_schema.py` against the new file first.

**Why `Technical Details` instead of `Product Specification`?** `Product Specification` looked useful at first glance but turned out to be ~100% boilerplate — every populated row is just `Shipping Weight: X (View shipping rates and policies)|ASIN: Y|#rank in Z` with the words run together (no spaces: `ProductDimensions:5.7x4.9x1.2inches`), which adds noise, not signal, to an embedding. `Technical Details` (92% populated) has genuine free-text product descriptions instead, so it's what actually goes into `features`.

## Category organization

The pipeline indexes every row — it no longer filters down to one category at ingestion time. `category_top_level` (the first segment of each product's `|`-delimited `Category` breadcrumb, e.g. the `Home & Kitchen` in `Home & Kitchen | Bedding | ...`) is stored as filterable Chroma metadata instead, so `rag.search` can scope a query to a category (`build_where(category="Home & Kitchen")`) or search across all of them by omitting it.

**Do products carry multiple categories?** Checked directly in `notebooks/00_eda.ipynb`: no. Every `Category` value in this file is a single hierarchical breadcrumb (top → leaf, 1–6 levels deep, `|`-delimited) — there's no second delimiter (`;`, `||`, newline) joining independent category assignments, no row repeats a top-level segment, and every `Uniq Id` appears exactly once. Taking the top-level breadcrumb segment is therefore a correct 1:1 label for this file, not a lossy approximation of a many-to-many relationship. (Caveat: a product can still be topically relevant to a category while filed under a different top-level, e.g. a kids' play-kitchen set under Toys & Games — that's a taxonomy/relevance tradeoff, not a parsing bug.)

**Real distribution**, confirmed against the full indexed set (10,002 rows): dominated by Toys & Games (6,662), followed by Clothing/Shoes/Jewelry (630), Sports & Outdoors (540), Home & Kitchen (708: Home Décor, Furniture, Bedding, Event & Party Supplies, Kitchen & Dining), Baby Products (214), and a long tail down to Health & Household (23). 830 rows have no `Category` value at all (`category_top_level` is `""` for those — `rag.search`'s category filter simply won't match them, they're still searchable unfiltered).

*(Earlier iterations of this project pre-filtered to a single category at ingestion time — first considered "Household Cleaning" per the original spec, rejected since only 23 rows fall under Health & Household at all and just 7 mention "cleaning" anywhere in their breadcrumb, then settled on Home & Kitchen as the best-populated fit. Indexing everything and filtering at query time instead makes that tradeoff moot — every category is available, and a query can still scope to Home & Kitchen via `category="Home & Kitchen"` if that's what's relevant.)*

## Brand inference

`Brand Name` is 100% empty in the raw file (see
[Known data-quality limitations](#known-data-quality-limitations)), but
many titles *do* start with the actual brand ("Melissa & Doug Wooden
Jigsaw Puzzle...", "KidKusion Gummi Teething Necklace..."). `_infer_brand`
in `clean.py` takes a conservative guess: the title's first word, unless
it looks like a number or a generic descriptor (`the`, `new`, `kids`,
etc.), in which case it returns `None` rather than guess.

**Deliberately single-word, even for real multi-word brands** ("Melissa &
Doug" → `"Melissa"`, "Achim Home Furnishings" → `"Achim"`). Tested a
2-3 word version first — it reliably grabbed unrelated descriptive words
for single-word brands ("Ceaco Perfect Piece Count Puzzle" →
`"Ceaco Perfect Piece"`, "AMSCAN Inmate Convict Prisoner..." →
`"AMSCAN Inmate Convict"`), which is a worse failure mode than
under-extracting: a truncated-but-correct guess is more useful than a
confidently wrong longer one.

**Kept as a separate `brand_inferred` field, never merged into `brand`.**
`brand` stays `None`/empty exactly as it is in the source data. Every
layer downstream — `rag.search`'s output, the Answerer's prompt, the
frontend's comparison table — treats `brand_inferred` as a labeled guess,
never as verified data. This isn't optional polish: presenting a guess as
a confirmed brand is exactly the kind of fabrication the top-level
README's Safety Notes are about avoiding.

## Known data-quality limitations

Confirmed against the real downloaded file — worth stating explicitly in the writeup/safety notes:

- **Brand Name and Ingredients are 100% empty** across all 10,002 rows. The Answerer agent should not claim brand or ingredient facts for these products; `retriever.py` already returns `None` for both rather than fabricating a value. (`brand_inferred` is a heuristic guess derived from the title, kept as a separate field — see [Brand inference](#brand-inference) — not a fix for this.)
- **No rating/review-count column exists** in this file at all (`clean.py` leaves `rating` as `None`), and unlike brand there's no title-text heuristic that could stand in for it — a rating isn't embedded in a product's name the way a brand sometimes is. If the team wants ratings for the demo, either source a `reviews.parquet` from a different PromptCloud file or drop rating-based comparisons from the example queries.
- **Selling Price has ~4% garbage values** dataset-wide ("from 2 sellers", "Total price:", free-text shipping blurbs, "$8.25 - $31.95" ranges). `_parse_price` requires the value to start with `$` before extracting a number — this matters: an earlier, unanchored version of the parser mis-read "from 2 sellers" as $2.00 and pulled a random $5 out of an unrelated shipping-policy sentence. For genuine ranges ("$8.25 - $31.95"), the low end is used as the representative price.
- **`price_per_unit` is only derived when a quantity+unit** (oz, lb, ct, etc.) is parseable from the title/weight/description text — 8,838 of 10,002 rows (88%). `price` itself is populated for 9,839/10,002 (98%).
- **`category_top_level` is empty for 830 rows** (8%) where the raw `Category` value is blank — those rows are still embedded and searchable, they just won't match a `category` filter.
- **`About Product` / `Technical Details` contain recurring boilerplate** ("Make sure this fits by entering your model number." in most rows, a return-policy blurb in a large share of `Technical Details` rows) that `clean.py` strips before building `features`, so it doesn't dilute the embedding for every product identically.
- **`Is Amazon Seller`** (Y/N, 100% populated) isn't currently surfaced — could be worth exposing as a trust signal if the Answerer agent wants to flag third-party vs. Amazon-fulfilled listings.

## Embedding backend

`all-MiniLM-L6-v2` via `sentence-transformers` (`embeddings.py`), runs fully local (CPU/MPS/CUDA) — no API key, no external calls. 22M params, 384-dim vectors, embeds the full 10,002-product dataset in well under a minute (~25s on Apple Silicon CPU/MPS). Override the model name with `EMBEDDING_MODEL` in `.env` if the team wants something different; `build_index.py`/`retriever.py` only depend on the `.embed(texts) -> list[list[float]]` interface, not on this model specifically.

**Why not Qwen?** Qwen's embedding line (Qwen3-Embedding) only ships in 0.6B/4B/8B — there's no smaller Qwen option, and 0.6B is ~30x the parameter count of MiniLM for no meaningful accuracy benefit at this dataset size. MiniLM is fast enough to rebuild the index from scratch in under a minute during dev, which matters far more than marginal retrieval-quality gains here.

## Handing off to the MCP layer

`rag.search` should be a thin wrapper:

```python
from retriever import RagRetriever, build_where

retriever = RagRetriever()
retriever.search(query, k=5, where=build_where(max_price=15, min_rating=4.0, brand="Method", category="Home & Kitchen"))
```

Returned dicts already match the `{sku, title, price, rating, brand, ingredients, doc_id}` contract from the project spec (plus `category`, `category_top_level`, `model_number`, and `url` as extra fields).

## Files

| file | role |
|---|---|
| `download_data.py` | Kaggle → `data/raw/*.csv` |
| `inspect_schema.py` | prints real raw column names/dtypes |
| `clean.py` | `data/raw` → `data/processed/products.parquet` |
| `build_index.py` | `products.parquet` → `data/chroma_db/` |
| `embeddings.py` | `sentence-transformers` wrapper (`all-MiniLM-L6-v2`) |
| `retriever.py` | `RagRetriever.search()` — imported directly by `rag.search` |
| `config.py` | env/config (`CHROMA_DIR`, `CHROMA_COLLECTION`, `EMBEDDING_MODEL`, ...) |
