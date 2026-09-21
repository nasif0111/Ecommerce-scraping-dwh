from pathlib import Path
from uuid import uuid4

import pandas as pd
import pyodbc


# ==================================
# Excel and SQL Server configuration
# ==================================

INPUT_FILE = Path(
    r"G:\data clean\scrabing\cleaned_valid_data.xlsx"
)

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    r"SERVER=.\SQLEXPRESS;"
    "DATABASE=E_commerce_scrabingproj;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def get_connection():
    connection = pyodbc.connect(CONNECTION_STRING)
    connection.timeout = 60
    return connection


def read_excel_file():
    df = pd.read_excel(INPUT_FILE)

    if df.empty:
        raise ValueError("cleaned_valid_data.xlsx is empty.")

    required_columns = [
        "SKU",
        "Product Name",
        "Image URL",
        "Product URL",
        "Current Price",
        "Old Price",
        "Discount",
        "Rating",
        "Reviews Count",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Columns not found: {missing_columns}"
        )

    return df[required_columns].copy()


def upload_to_staging(connection, df, batch_id):
    insert_sql = """
    INSERT INTO stg.JumiaProducts (
        LoadBatchID,
        SourceFile,
        SKU,
        ProductName,
        ImageURL,
        ProductURL,
        CurrentPrice,
        OldPrice,
        Discount,
        Rating,
        ReviewsCount
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    # تحويل NaN و<NA> إلى NULL في SQL Server
    df = df.astype(object).where(pd.notna(df), None)

    rows = [
        (
            batch_id,
            INPUT_FILE.name,
            *row
        )
        for row in df.itertuples(index=False, name=None)
    ]

    cursor = connection.cursor()
    cursor.fast_executemany = True
    cursor.executemany(insert_sql, rows)

    return len(rows)


def move_from_staging_to_main(connection, batch_id):
    cursor = connection.cursor()

    cursor.execute(
        "EXEC dbo.usp_MoveJumiaFromStaging @LoadBatchID = ?",
        batch_id
    )

    result = cursor.fetchone()

    # الـ Stored Procedure ترجع RowsInserted
    # نستخدم رقم العمود بدل اسمه لتجنب مشكلة RowsMoved / RowsInserted
    if result is None:
        return 0

    return int(result[0])


def main():
    try:
        print("1. Starting load process...")

        if not INPUT_FILE.exists():
            raise FileNotFoundError(
                f"Excel file not found: {INPUT_FILE}"
            )

        print("2. Reading Excel file...")
        df = read_excel_file()

        print(f"3. Rows found in Excel: {len(df)}")

        batch_id = str(uuid4())
        print(f"4. Batch ID: {batch_id}")

        with get_connection() as connection:
            print("5. Uploading data to staging table...")

            staged_rows = upload_to_staging(
                connection=connection,
                df=df,
                batch_id=batch_id
            )
            connection.commit()

            print(
                f"6. Rows uploaded to stg.JumiaProducts: "
                f"{staged_rows}"
            )

            print("7. Running SCD Stored Procedure...")

            inserted_rows = move_from_staging_to_main(
                connection=connection,
                batch_id=batch_id
            )
            connection.commit()

        print("8. Process completed successfully.")
        print(f"Batch ID: {batch_id}")
        print(f"Rows uploaded to staging: {staged_rows}")
        print(f"New rows inserted into main table: {inserted_rows}")

    except Exception as error:
        print("\nERROR:")
        print(error)


if __name__ == "__main__":
    main()