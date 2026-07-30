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

CHROMA_DIR = PROJECT_ROOT / os.getenv("CHROMA_DIR", "data/chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "amazon_products")

for d in (RAW_DIR, PROCESSED_DIR):
    d.mkdir(parents=True, exist_ok=True)
