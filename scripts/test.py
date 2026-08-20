import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Same fix as ingest_to_db.py: load .env relative to this script's
# location, not the process's current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def main():

    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
            
        )

        cursor = connection.cursor()

        cursor.execute("SELECT version();")

        version = cursor.fetchone()[0]

        print("PostgreSQL connection successful!")
        print()
        print(version)

        cursor.close()
        connection.close()

    except Exception as error:

        print("PostgreSQL connection FAILED")
        print()
        print(error)


if __name__ == "__main__":
    main()