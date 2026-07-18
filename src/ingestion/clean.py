"""Raw Amazon 2020 CSV -> data/processed/products.parquet.

Column names in PromptCloud's Amazon exports vary slightly between dataset
revisions, so target fields are resolved via an alias list rather than a
fixed name. Run inspect_schema.py first and extend COLUMN_ALIASES below if a
field comes back empty for your copy of the file.
"""
import re
from typing import Optional

import pandas as pd

from config import CATEGORY_TOP_LEVEL, PRODUCTS_PARQUET, RAW_DIR

COLUMN_ALIASES: dict[str, list[str]] = {
    "id": ["Uniq Id", "uniq_id", "Asin", "asin"],
    "title": ["Product Name", "product_name", "title"],
    "brand": ["Brand Name", "brand", "Manufacturer", "manufacturer"],
    "category": ["Category", "category", "Amazon Category And Sub Category"],
    "list_price": ["List Price", "list_price"],
    "price": ["Selling Price", "selling_price", "Discounted Price", "price"],
    "rating": ["Average Review Rating", "average_review_rating", "Rating", "rating"],
    "num_reviews": ["Number Of Reviews", "number_of_reviews"],
    "about": ["About Product", "about_product", "Product Description", "product_description"],
    "spec": ["Product Specification", "product_specification", "Technical Details", "technical_details"],
    "ingredients": ["Ingredients", "ingredients"],
    "weight": ["Shipping Weight", "shipping_weight", "Item Weight", "item_weight"],
    "url": ["Product Url", "product_url", "url"],
}

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


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df


def _find_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def _resolve_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    resolved = {field: _find_column(df, aliases) for field, aliases in COLUMN_ALIASES.items()}
    missing = [f for f, c in resolved.items() if c is None]
    if missing:
        print(f"warning: no source column found for fields {missing} "
              f"(run inspect_schema.py and extend COLUMN_ALIASES if these matter)")
    return resolved


def _parse_price(value) -> Optional[float]:
    if pd.isna(value):
        return None
    match = re.search(r"[\d,]+\.?\d*", str(value))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def _parse_rating(value) -> Optional[float]:
    price = _parse_price(value)
    if price is None:
        return None
    return price if price <= 5 else None


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


def _matches_category(category_breadcrumb: str) -> bool:
    top_level = category_breadcrumb.split("|")[0].strip().lower()
    return top_level == CATEGORY_TOP_LEVEL.lower()


def clean() -> pd.DataFrame:
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in {RAW_DIR}. Run download_data.py first.")

    frames = [_normalize_columns(pd.read_csv(path, low_memory=False)) for path in csv_files]
    raw = pd.concat(frames, ignore_index=True)
    cols = _resolve_columns(raw)

    out = pd.DataFrame()
    out["id"] = raw[cols["id"]] if cols["id"] else raw.index.astype(str)
    out["title"] = raw[cols["title"]] if cols["title"] else None
    out["brand"] = raw[cols["brand"]] if cols["brand"] else None
    out["category"] = raw[cols["category"]] if cols["category"] else None
    out["price"] = raw[cols["price"]].map(_parse_price) if cols["price"] else None
    out["rating"] = raw[cols["rating"]].map(_parse_rating) if cols["rating"] else None
    out["about"] = raw[cols["about"]] if cols["about"] else None
    out["spec"] = raw[cols["spec"]] if cols["spec"] else None
    out["ingredients"] = raw[cols["ingredients"]] if cols["ingredients"] else None
    weight_col = raw[cols["weight"]] if cols["weight"] else pd.Series([None] * len(raw))
    out["url"] = raw[cols["url"]] if cols["url"] else None

    out["title"] = out["title"].fillna("").astype(str)
    out["category"] = out["category"].fillna("").astype(str)
    out["about"] = out["about"].fillna("").astype(str)

    out = out[out["category"].map(_matches_category)].reset_index(drop=True)

    units = [
        _parse_unit(title, weight, about)
        for title, weight, about in zip(out["title"], weight_col.reindex(out.index), out["about"])
    ]
    out["unit_qty"] = [u[0] for u in units]
    out["unit"] = [u[1] for u in units]
    out["price_per_unit"] = out.apply(
        lambda r: round(r["price"] / r["unit_qty"], 4)
        if pd.notna(r["price"]) and pd.notna(r["unit_qty"]) and r["unit_qty"] > 0
        else None,
        axis=1,
    )

    out["features"] = (out["about"].fillna("") + " " + out["spec"].fillna("")).str.strip()
    out = out.drop(columns=["about", "spec"])

    out = out.dropna(subset=["title"])
    out = out[out["title"].str.len() > 0]
    out = out.drop_duplicates(subset=["id"]).reset_index(drop=True)
    out["doc_id"] = out["id"]

    PRODUCTS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PRODUCTS_PARQUET, index=False)
    print(f"wrote {len(out)} products to {PRODUCTS_PARQUET}")
    return out


if __name__ == "__main__":
    clean()
