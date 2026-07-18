"""Run this after download_data.py to see the real column names/dtypes
before trusting the alias mapping in clean.py."""
import pandas as pd

from config import RAW_DIR


def inspect() -> None:
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in {RAW_DIR}. Run download_data.py first.")

    for path in csv_files:
        df = pd.read_csv(path, nrows=500)
        print(f"\n=== {path.name} ===")
        print(f"sampled shape: {df.shape}")
        print("\ncolumns + dtypes:")
        for col in df.columns:
            print(f"  {col!r}: {df[col].dtype}")
        print("\nfirst row:")
        print(df.iloc[0].to_dict())


if __name__ == "__main__":
    inspect()
