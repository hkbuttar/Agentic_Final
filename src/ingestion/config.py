import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

KAGGLE_DATASET = "promptcloud/amazon-product-dataset-2020"

PRODUCTS_PARQUET = PROCESSED_DIR / "products.parquet"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Matched against the top-level segment of the pipe-delimited Category
# breadcrumb (e.g. "Home & Kitchen | Bedding | ..."). Exact top-level match,
# not a keyword-in-text search: the raw dataset's product descriptions use
# words like "clean" so loosely ("wipe clean", "easy to clean") that a
# keyword search over title/description pulls in unrelated products.
CATEGORY_TOP_LEVEL = os.getenv("CATEGORY_TOP_LEVEL", "Home & Kitchen")

CHROMA_DIR = PROJECT_ROOT / os.getenv("CHROMA_DIR", "data/chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "amazon_products_home_kitchen")

for d in (RAW_DIR, PROCESSED_DIR):
    d.mkdir(parents=True, exist_ok=True)
