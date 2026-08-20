from pathlib import Path
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = Path("data")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def inspect_file(file_path):
    print_section(f"FILE: {file_path.name}")

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"ERROR reading file: {e}")
        return

    # --------------------------------------------------------
    # BASIC INFORMATION
    # --------------------------------------------------------

    print_section("1. BASIC INFORMATION")

    print(f"File name       : {file_path.name}")
    print(f"Rows            : {len(df)}")
    print(f"Columns         : {len(df.columns)}")
    print(f"Memory usage    : {df.memory_usage(deep=True).sum() / 1024:.2f} KB")

    # --------------------------------------------------------
    # COLUMN INFORMATION
    # --------------------------------------------------------

    print_section("2. COLUMNS")

    for i, column in enumerate(df.columns, start=1):

        print(
            f"{i:2}. {column}"
        )

    # --------------------------------------------------------
    # DATA TYPES
    # --------------------------------------------------------

    print_section("3. DATA TYPES")

    print(df.dtypes.to_string())

    # --------------------------------------------------------
    # MISSING VALUES
    # --------------------------------------------------------

    print_section("4. MISSING VALUES")

    missing = df.isnull().sum()

    missing_percentage = (
        df.isnull().mean() * 100
    )

    missing_report = pd.DataFrame({
        "missing_count": missing,
        "missing_percentage": missing_percentage.round(2)
    })

    missing_report = missing_report[
        missing_report["missing_count"] > 0
    ]

    if missing_report.empty:

        print("No missing values found.")

    else:

        print(
            missing_report.to_string()
        )

    # --------------------------------------------------------
    # EXACT DUPLICATE ROWS
    # --------------------------------------------------------

    print_section("5. EXACT DUPLICATE ROWS")

    duplicate_count = df.duplicated().sum()

    print(
        f"Duplicate rows: {duplicate_count}"
    )

    if duplicate_count > 0:

        print("\nSample duplicate rows:")

        duplicates = df[
            df.duplicated(keep=False)
        ]

        print(
            duplicates.head(10).to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # UNIQUE VALUES
    # --------------------------------------------------------

    print_section("6. UNIQUE VALUES PER COLUMN")

    for column in df.columns:

        unique_count = df[column].nunique(
            dropna=True
        )

        print(
            f"{column:30} "
            f"{unique_count} unique values"
        )

    # --------------------------------------------------------
    # SAMPLE DATA
    # --------------------------------------------------------

    print_section("7. FIRST 5 ROWS")

    print(
        df.head().to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # LAST 5 ROWS
    # --------------------------------------------------------

    print_section("8. LAST 5 ROWS")

    print(
        df.tail().to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # POTENTIAL NAME / EMAIL / PHONE COLUMNS
    # --------------------------------------------------------

    print_section("9. POTENTIAL PERSON IDENTIFIER COLUMNS")

    possible_name_columns = [
        "name",
        "full_name",
        "fullname",
        "candidate_name",
        "worker_name",
        "person_name",
        "first_name",
        "last_name"
    ]

    possible_email_columns = [
        "email",
        "email_address",
        "email_id",
        "mail"
    ]

    possible_phone_columns = [
        "phone",
        "phone_number",
        "mobile",
        "mobile_number",
        "contact",
        "contact_number"
    ]

    columns_lower = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    # Name
    found_names = [
        columns_lower[column]
        for column in possible_name_columns
        if column in columns_lower
    ]

    # Email
    found_emails = [
        columns_lower[column]
        for column in possible_email_columns
        if column in columns_lower
    ]

    # Phone
    found_phones = [
        columns_lower[column]
        for column in possible_phone_columns
        if column in columns_lower
    ]

    print(
        f"Name columns  : {found_names}"
    )

    print(
        f"Email columns : {found_emails}"
    )

    print(
        f"Phone columns : {found_phones}"
    )

    # --------------------------------------------------------
    # DUPLICATES IN POTENTIAL IDENTIFIER COLUMNS
    # --------------------------------------------------------

    print_section(
        "10. DUPLICATES IN IDENTIFIER COLUMNS"
    )

    identifier_columns = (
        found_names
        + found_emails
        + found_phones
    )

    if not identifier_columns:

        print(
            "No obvious name/email/phone columns found."
        )

    else:

        for column in identifier_columns:

            duplicate_values = (
                df[column]
                .dropna()
                .value_counts()
            )

            duplicate_values = duplicate_values[
                duplicate_values > 1
            ]

            print(
                f"\nColumn: {column}"
            )

            if duplicate_values.empty:

                print(
                    "  No duplicate values."
                )

            else:

                print(
                    duplicate_values
                    .head(20)
                    .to_string()
                )

    # --------------------------------------------------------
    # EMPTY STRING CHECK
    # --------------------------------------------------------

    print_section("11. EMPTY STRING VALUES")

    for column in df.columns:

        if df[column].dtype == "object":

            empty_count = (
                df[column]
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )

            if empty_count > 0:

                print(
                    f"{column}: "
                    f"{empty_count} empty strings"
                )

    # --------------------------------------------------------
    # WHITESPACE ISSUES
    # --------------------------------------------------------

    print_section("12. WHITESPACE ISSUES")

    for column in df.columns:

        if df[column].dtype == "object":

            values = df[column].dropna().astype(str)

            leading_spaces = (
                values.str.startswith(" ")
                .sum()
            )

            trailing_spaces = (
                values.str.endswith(" ")
                .sum()
            )

            if leading_spaces or trailing_spaces:

                print(
                    f"{column}: "
                    f"{leading_spaces} leading-space values, "
                    f"{trailing_spaces} trailing-space values"
                )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_section("13. SUMMARY")

    print(f"Total rows              : {len(df)}")
    print(f"Total columns           : {len(df.columns)}")
    print(f"Exact duplicate rows    : {duplicate_count}")
    print(
        f"Columns with missing data: "
        f"{(df.isnull().sum() > 0).sum()}"
    )

    print("\nInspection completed.")


# ============================================================
# MAIN
# ============================================================

def main():

    if not DATA_DIR.exists():

        print(
            f"ERROR: Directory '{DATA_DIR}' does not exist."
        )

        return

    # Only inspect raw CSV files directly inside data/
    csv_files = list(
        DATA_DIR.glob("*.csv")
    )

    if not csv_files:

        print(
            "No CSV files found in data/."
        )

        return

    print(
        f"Found {len(csv_files)} CSV files."
    )

    for file_path in csv_files:

        inspect_file(file_path)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()