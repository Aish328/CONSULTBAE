import re
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIG
# ============================================================

INPUT_DIR = Path(r"C:\Users\Lenovo\Desktop\consultbae_updated\consultbae\data")
OUTPUT_DIR = Path(r"C:\Users\Lenovo\Desktop\consultbae_updated\consultbae\data\cleaned")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_string(value):
    """
    Remove leading/trailing whitespace and
    collapse multiple spaces.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    value = re.sub(r"\s+", " ", value)

    return value


# ============================================================
# NAME NORMALIZATION
# ============================================================

def normalize_name(value):
    """
    Example:

        '  JOHN   SMITH  '
                ↓
        'john smith'
    """

    value = clean_string(value)

    if value is None:
        return None

    return value.lower()


# ============================================================
# EMAIL NORMALIZATION
# ============================================================

def normalize_email(value):
    """
    Normalize email for matching.
    """

    value = clean_string(value)

    if value is None:
        return None

    return value.lower()


# ============================================================
# PHONE NORMALIZATION
# ============================================================

def normalize_phone(value):
    """
    Keep only digits.

    Examples:

        +91-98765-43210
                ↓
        9876543210

        +91 9876543210
                ↓
        9876543210
    """

    value = clean_string(value)

    if value is None:
        return None

    digits = re.sub(r"\D", "", value)

    if not digits:
        return None

    # Handle Indian numbers.
    # Keep the last 10 digits.
    if len(digits) > 10:
        digits = digits[-10:]

    return digits

def normalize_city(value):
    value = clean_string(value)

    if value is None:
        return None

    return value.lower()

def normalize_boolean(value):

    value = clean_string(value)

    if value is None:
        return None

    value = value.lower()

    if value in ["y", "yes", "true", "1"]:
        return True

    if value in ["n", "no", "false", "0"]:
        return False

    return None

# ============================================================
# FIND COLUMNS
# ============================================================

def find_column(df, possible_names):
    """
    Find a column using possible variations of its name.
    """

    columns = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:

        if name.lower() in columns:
            return columns[name.lower()]

    return None


# ============================================================
# CLEAN ONE CSV
# ============================================================

def clean_file(file_path):

    print("\n" + "=" * 70)
    print(f"PROCESSING: {file_path.name}")
    print("=" * 70)

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = pd.read_csv(file_path)

    original_rows = len(df)

    print(f"Original rows: {original_rows}")

    print("\nOriginal columns:")
    print(list(df.columns))

    # --------------------------------------------------------
    # Remove planted structural problems BEFORE anything else:
    # a repeated CSV header embedded mid-file, and rows whose
    # fields got shifted one column to the left/right.
    # --------------------------------------------------------

    df = remove_repeated_header_rows(df)

    df = remove_malformed_shifted_rows(df)

    # --------------------------------------------------------
    # Standardize column names
    # --------------------------------------------------------

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )

    # --------------------------------------------------------
    # Remove completely empty rows
    # --------------------------------------------------------

    before = len(df)

    df = df.dropna(how="all")

    empty_rows_removed = before - len(df)

    # --------------------------------------------------------
    # Remove exact duplicate rows
    # --------------------------------------------------------

    before = len(df)

    df = df.drop_duplicates()

    exact_duplicates_removed = before - len(df)

    # --------------------------------------------------------
    # Detect important columns
    # --------------------------------------------------------

    name_col = find_column(
        df,
        [
            "name",
            "full_name",
            "fullname",
            "candidate_name",
            "worker_name",
            "person_name"
        ]
    )

    email_col = find_column(
        df,
        [
            "email",
            "email_address",
            "email_id",
            "mail"
            
        ]
    )

    phone_col = find_column(
        df,
        [
            "phone",
            "phone_number",
            "mobile",
            "mobile_number",
            "contact",
            "contact_number"
        ]
    )

    city_col = find_column(
    df,
    [
        "city",
        "location"
    ]
)

    verified_col = find_column(
    df,
    [
        "verified"
    ]
)

    # --------------------------------------------------------
    # Print detected columns
    # --------------------------------------------------------

    print("\nDetected columns:")

    print(f"Name  : {name_col}")
    print(f"Email : {email_col}")
    print(f"Phone : {phone_col}")

    # --------------------------------------------------------
    # Normalize NAME
    # --------------------------------------------------------

    if name_col:

        df["name_normalized"] = df[name_col].apply(
            normalize_name
        )

    # --------------------------------------------------------
    # Normalize EMAIL
    # --------------------------------------------------------

    if email_col:

        df["email_normalized"] = df[email_col].apply(
            normalize_email
        )

    # --------------------------------------------------------
    # Normalize PHONE
    # --------------------------------------------------------

    if phone_col:

        df["phone_normalized"] = df[phone_col].apply(
            normalize_phone
        )
    if city_col:
        df["city_normalized"] = df[city_col].apply(
        normalize_city
    )
    verified_col = find_column(
    df,
    [
        "verified"
    ]
)

    if verified_col:
        df["verified_normalized"] = df[
            verified_col
        ].apply(normalize_boolean)
    # --------------------------------------------------------
    # Clean other text columns
    # --------------------------------------------------------

    for column in df.select_dtypes(
        include=["object"]
    ).columns:

        # Don't modify normalized columns.
        if column.endswith("_normalized"):
            continue

        df[column] = df[column].apply(
            clean_string
        )

    # --------------------------------------------------------
    # Add source information
    # --------------------------------------------------------

    df["source_system"] = file_path.stem

    # Preserve original source row information.
    #
    # This is useful when investigating data problems.
    df["source_row_number"] = range(
        2,
        len(df) + 2
    )

    # --------------------------------------------------------
    # DATA QUALITY REPORT
    # --------------------------------------------------------

    print("\nData quality summary:")

    print(
        f"Rows after cleaning: {len(df)}"
    )

    print(
        f"Empty rows removed: {empty_rows_removed}"
    )

    print(
        f"Exact duplicates removed: "
        f"{exact_duplicates_removed}"
    )

    if name_col:

        print(
            f"Missing names: "
            f"{df['name_normalized'].isna().sum()}"
        )

    if email_col:

        print(
            f"Missing emails: "
            f"{df['email_normalized'].isna().sum()}"
        )

    if phone_col:

        print(
            f"Missing phones: "
            f"{df['phone_normalized'].isna().sum()}"
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output_file = OUTPUT_DIR / file_path.name

    df.to_csv(
        output_file,
        index=False
    )

    print(
        f"\nSaved cleaned file:"
    )

    print(output_file)

    return df

def remove_repeated_header_rows(df):
    """
    Remove rows that repeat the CSV header.
    """

    normalized_columns = [
        str(col).strip().lower()
        for col in df.columns
    ]

    rows_to_remove = []

    for index, row in df.iterrows():

        row_values = [
            str(value).strip().lower()
            if not pd.isna(value)
            else ""
            for value in row.tolist()
        ]

        if row_values == normalized_columns:
            rows_to_remove.append(index)

    if rows_to_remove:

        print(
            f"Repeated header rows removed: "
            f"{len(rows_to_remove)}"
        )

        df = df.drop(
            index=rows_to_remove
        )

    return df
def remove_malformed_shifted_rows(df):
    """
    Detect rows where fields appear shifted.

    For the Gig Workers dataset, a valid row should have:
        email_id -> looks like email
        worker_name -> looks like a person's name
        rate -> contains /hr or /month
        location -> city/location
        status -> status value
        skill_tags -> skill list
    """

    rows_to_remove = []

    columns = list(df.columns)

    # Only apply this logic to the Gig Workers structure
    required_columns = {
        "email_id",
        "worker_name",
        "rate",
        "location",
        "status",
        "skill_tags"
    }

    if not required_columns.issubset(set(columns)):
        return df

    for index, row in df.iterrows():

        email_value = str(
            row["email_id"]
        ).strip()

        worker_name = str(
            row["worker_name"]
        ).strip()

        rate = str(
            row["rate"]
        ).strip()

        location = str(
            row["location"]
        ).strip()

        status = str(
            row["status"]
        ).strip()

        skill_tags = str(
            row["skill_tags"]
        ).strip()

        # Detect shifted row:
        # skills are in email column
        # email is in worker_name column
        # name is in rate column
        # rate is in location column
        # city is in status column

        looks_shifted = (
            "," in email_value
            and "@" in worker_name
            and (
                rate.lower().count(" ") >= 0
                and not rate.lower().endswith(
                    ("/hr", "/month")
                )
            )
            and (
                "/hr" in location.lower()
                or "/month" in location.lower()
            )
        )

        if looks_shifted:
            rows_to_remove.append(index)

    if rows_to_remove:

        print(
            f"Malformed shifted rows removed: "
            f"{len(rows_to_remove)}"
        )

        df = df.drop(
            index=rows_to_remove
        )

    return df
# ============================================================
# MAIN
# ============================================================

def main():

    csv_files = list(
        INPUT_DIR.glob("*.csv")
    )

    # Prevent processing files that are already
    # inside a cleaned directory.
    csv_files = [
        file
        for file in csv_files
        if "clean" not in file.stem.lower()
    ]

    if not csv_files:

        print(
            "No CSV files found in the data directory."
        )

        return

    print(
        f"Found {len(csv_files)} CSV files."
    )

    for file_path in csv_files:

        try:

            clean_file(file_path)

        except Exception as error:

            print(
                f"\nERROR processing "
                f"{file_path.name}:"
            )

            print(error)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()