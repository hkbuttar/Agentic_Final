"""Raw Amazon 2020 CSV -> data/processed/products.parquet.

Column names below are the real headers in
marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv
(confirmed via inspect_schema.py / notebooks/00_eda.ipynb). `Brand Name` and
`Ingredients` are read but are 100% empty in this file; there is no rating
column at all, so `rating` is left as None. `brand_inferred` is a
best-effort heuristic guess derived from the title (see `_infer_brand`),
kept as a separate column from `brand` — never a substitute for it.
"""
import re
from typing import Optional

import pandas as pd

from config import PRODUCTS_PARQUET, RAW_DIR

COL_ID = "Uniq Id"
COL_TITLE = "Product Name"
COL_BRAND = "Brand Name"
COL_CATEGORY = "Category"
COL_PRICE = "Selling Price"
COL_ABOUT = "About Product"
COL_TECH = "Technical Details"
COL_MODEL = "Model Number"
COL_INGREDIENTS = "Ingredients"
COL_WEIGHT = "Shipping Weight"
COL_URL = "Product Url"

UNIT_PATTERN = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>fl\s?oz|fl\.\s?oz|oz|ounce|ounces|lb|lbs|pound|pounds|"
    r"ct|count|pack|gal|gallon|l|liter|litre|ml)\b",
    re.IGNORECASE,
)

_UNIT_NORMALIZE = {
    "fl oz": "oz", "fl. oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "count": "ct", "pack": "ct",
    "gallon": "gal", "liter": "l", "litre": "l",
}

# Recur across most rows in About Product / Technical Details and add no
# product-specific signal to the embedding text.
_BOILERPLATE = [
    "Make sure this fits by entering your model number.",
    "Go to your orders and start the return Select the ship method Ship it!",
]

_BRAND_STOPWORDS = {
    "the", "new", "set", "pack", "a", "an", "kids", "baby", "womens",
    "mens", "boys", "girls",
}


def _infer_brand(title: str) -> Optional[str]:
    """Best-effort single-word brand guess from the title's first word,
    since the real `Brand Name` column is 100% empty (see README's Known
    data-quality limitations). Deliberately conservative: returns None
    rather than guessing when the first word looks like a number or a
    generic descriptor, and never extends past one word even for real
    multi-word brands ("Melissa & Doug" -> "Melissa") — a short, correct-
    as-far-as-it-goes guess is less misleading than a confidently wrong
    longer one built by grabbing more words. Kept as a separate
    `brand_inferred` column, never merged into `brand`, so nothing
    downstream can present a guess as verified data."""
    if not title:
        return None
    first = title.split()[0].strip(".,'\"")
    if not first or any(ch.isdigit() for ch in first) or first.lower() in _BRAND_STOPWORDS:
        return None
    return first


def _parse_price(value) -> Optional[float]:
    """Selling Price is normally "$12.99". A handful of rows hold garbage
    like "from 2 sellers" or free-text shipping blurbs — requiring the `$`
    anchor keeps those out instead of grabbing an unrelated digit."""
    if pd.isna(value):
        return None
    match = re.match(r"\s*\$\s*([\d,]+\.?\d*)", str(value))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("|", ". ")
    for phrase in _BOILERPLATE:
        text = text.replace(phrase, "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(\.\s*)+", "", text)
    return re.sub(r"(\.\s*){2,}", ". ", text).strip()


def _parse_unit(*text_fields: str) -> tuple[Optional[float], Optional[str]]:
    for text in text_fields:
        if not text or pd.isna(text):
            continue
        match = UNIT_PATTERN.search(str(text))
        if match:
            qty = float(match.group("qty"))
            unit = match.group("unit").lower()
            unit = _UNIT_NORMALIZE.get(unit, unit)
            return qty, unit
    return None, None


def _category_top_level(category_breadcrumb: str) -> str:
    """Category is a single `|`-delimited breadcrumb per row (top -> leaf),
    not multiple category assignments — confirmed in notebooks/00_eda.ipynb
    (no row uses a second delimiter like ';', '||', or repeats a top-level
    segment; every Uniq Id appears exactly once). Extracting the top-level
    segment gives a clean, filterable category field without losing the
    full breadcrumb (kept separately in `category`)."""
    if not category_breadcrumb:
        return ""
    return category_breadcrumb.split("|")[0].strip()


def clean() -> pd.DataFrame:
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in {RAW_DIR}. Run download_data.py first.")

    raw = pd.concat([pd.read_csv(path, low_memory=False) for path in csv_files], ignore_index=True)

    out = pd.DataFrame()
    out["id"] = raw[COL_ID]
    out["title"] = raw[COL_TITLE].fillna("").astype(str)
    out["brand"] = raw[COL_BRAND]
    out["brand_inferred"] = out["title"].map(_infer_brand)
    out["category"] = raw[COL_CATEGORY].fillna("").astype(str)
    out["category_top_level"] = out["category"].map(_category_top_level)
    out["price"] = raw[COL_PRICE].map(_parse_price)
    out["rating"] = None
    out["ingredients"] = raw[COL_INGREDIENTS]
    out["model_number"] = raw[COL_MODEL]
    out["url"] = raw[COL_URL]

    about = raw[COL_ABOUT].fillna("").astype(str)
    tech = raw[COL_TECH].fillna("").astype(str)
    weight = raw[COL_WEIGHT]

    units = [_parse_unit(title, w, a) for title, w, a in zip(out["title"], weight, about)]
    out["unit_qty"] = [u[0] for u in units]
    out["unit"] = [u[1] for u in units]
    out["price_per_unit"] = out.apply(
        lambda r: round(r["price"] / r["unit_qty"], 4)
        if pd.notna(r["price"]) and pd.notna(r["unit_qty"]) and r["unit_qty"] > 0
        else None,
        axis=1,
    )

    out["features"] = [_clean_text(a + ". " + t) for a, t in zip(about, tech)]

    out = out[out["title"].str.len() > 0]
    out = out.drop_duplicates(subset=["id"]).reset_index(drop=True)
    out["doc_id"] = out["id"]

    PRODUCTS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PRODUCTS_PARQUET, index=False)
    print(f"wrote {len(out)} products to {PRODUCTS_PARQUET}")
    return out


if __name__ == "__main__":
    clean()
