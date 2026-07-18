"""Download the Amazon Product Dataset 2020 via kagglehub and stage the
CSV file(s) into data/raw/. Requires a Kaggle API token at ~/.kaggle/kaggle.json.
"""
import shutil
from pathlib import Path

import kagglehub

from config import KAGGLE_DATASET, RAW_DIR


def download() -> list[Path]:
    cache_path = Path(kagglehub.dataset_download(KAGGLE_DATASET))
    print(f"kagglehub cached dataset at: {cache_path}")

    csv_files = sorted(cache_path.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found under {cache_path}")

    staged = []
    for src in csv_files:
        dst = RAW_DIR / src.name
        shutil.copy2(src, dst)
        staged.append(dst)
        print(f"staged: {dst} ({dst.stat().st_size / 1e6:.1f} MB)")

    return staged


if __name__ == "__main__":
    download()
