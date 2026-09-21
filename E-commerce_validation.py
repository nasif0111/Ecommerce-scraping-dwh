from pathlib import Path
from decimal import Decimal, InvalidOperation
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


INPUT_FILE = Path(r"G:\data clean\scrabing\jumia_products_pages_1_to_10.xlsx")
VALID_FILE = INPUT_FILE.with_name("valid_data.xlsx")
NOT_VALID_FILE = INPUT_FILE.with_name("not_valid_data.xlsx")


class ProductValidation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str = Field(min_length=1)
    current_price: Decimal
    old_price: Decimal

    @field_validator("sku", mode="before")
    @classmethod
    def validate_sku(cls, value):
        if value is None or pd.isna(value) or not str(value).strip():
            raise ValueError("SKU is required")
        return str(value).strip()

    @field_validator("current_price", "old_price", mode="before")
    @classmethod
    def validate_price(cls, value):
        if value is None or pd.isna(value):
            raise ValueError("Price is required")

        try:
            price = Decimal(str(value))

            if not price.is_finite():
                raise ValueError("Price must be a valid number")

            if price < 0:
                raise ValueError("Price cannot be negative")

            return price

        except (InvalidOperation, ValueError):
            raise ValueError("Price must be an integer or decimal number")


def validate_row(row: pd.Series) -> tuple[bool, dict]:
    row_data = row.to_dict()

    try:
        product = ProductValidation.model_validate(
            {
                "sku": row_data.get("SKU"),
                "current_price": row_data.get("Current Price"),
                "old_price": row_data.get("Old Price"),
            }
        )

        row_data["SKU"] = product.sku

        # نحولها إلى float حتى تُحفظ كرقم في Excel
        row_data["Current Price"] = float(product.current_price)
        row_data["Old Price"] = float(product.old_price)

        return True, row_data

    except ValidationError as exc:
        row_data["validation_errors"] = " | ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors()
        )
        return False, row_data


def main():
    df = pd.read_excel(INPUT_FILE, sheet_name="Jumia Products")

    valid_rows = []
    invalid_rows = []

    for _, row in df.iterrows():
        is_valid, result = validate_row(row)

        if is_valid:
            valid_rows.append(result)
        else:
            invalid_rows.append(result)

    pd.DataFrame(valid_rows).to_excel(VALID_FILE, index=False)
    pd.DataFrame(invalid_rows).to_excel(NOT_VALID_FILE, index=False)

    print(f"Valid rows: {len(valid_rows)}")
    print(f"Invalid rows: {len(invalid_rows)}")


if __name__ == "__main__":
    main()