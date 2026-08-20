import pandas as pd
from pathlib import Path


DATA_DIR = Path("data")


def inspect_csv(file_path):
    print("\n" + "=" * 80)
    print(f"FILE: {file_path.name}")
    print("=" * 80)

    df = pd.read_csv(file_path)

    print(f"\nRows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\nColumns:")
    for column in df.columns:
        print(f"  - {column}")

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nDuplicate rows:")
    print(df.duplicated().sum())

    print("\nFirst 5 rows:")
    print(df.head().to_string())

    print("\nUnique values:")
    for column in df.columns:
        print(f"\n{column}: {df[column].nunique()} unique values")


def main():
    csv_files = list(DATA_DIR.glob("*.csv"))

    if not csv_files:
        print("No CSV files found in the data/ directory.")
        return

    print(f"Found {len(csv_files)} CSV files.")

    for file_path in csv_files:
        try:
            inspect_csv(file_path)
        except Exception as e:
            print(f"\nERROR reading {file_path.name}: {e}")


if __name__ == "__main__":
    main()