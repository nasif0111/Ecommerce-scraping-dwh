from pathlib import Path
import pandas as pd


# ملف البيانات الصحيحة الناتج من مرحلة الـ Validation
INPUT_FILE = Path(r"G:\data clean\scrabing\valid_data.xlsx")

# ملف البيانات بعد مرحلة الـ Cleaning
OUTPUT_FILE = INPUT_FILE.with_name("cleaned_valid_data.xlsx")


def clean_text_value(value):
    """إزالة المسافات من بداية ونهاية أي قيمة نصية فقط."""
    if isinstance(value, str):
        return value.strip()

    return value


def clean_discount(value):
    """
    تنظيف قيمة الخصم:
    - إزالة المسافات الخارجية فقط.
    - الإبقاء على % إن كانت موجودة.
    - إضافة % إن لم تكن موجودة.
    """
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()

    if not value:
        return pd.NA

    if value.endswith("%"):
        return value

    return f"{value}%"


def main():
    # 1) تحويل ملف valid_data إلى DataFrame
    df = pd.read_excel(INPUT_FILE)

    if df.empty:
        raise ValueError("ملف valid_data.xlsx فارغ.")

    # 2) Cleaning لأسماء الأعمدة:
    # إزالة المسافات في البداية والنهاية فقط
    # حذف علامة % من اسم العمود فقط
    # بدون lower وبدون استبدال المسافات الداخلية بـ _
    df.columns = (
        df.columns
        .str.strip()
        .str.replace("%", "", regex=False)
        .str.strip()
    )

    print("Column names after cleaning:")
    print(df.columns.tolist())

    # 3) إزالة المسافات من بداية ونهاية القيم النصية في كل الصفوف
    df = df.apply(
        lambda column: column.map(clean_text_value)
    )

    # 4) تنظيف قيم عمود Discount وإضافة % عند الحاجة
    if "Discount" in df.columns:
        df["Discount"] = df["Discount"].map(clean_discount)
    else:
        print("Column 'Discount' was not found.")

    # 5) تحويل Rating إلى String
    # واستبدال القيم الفارغة بـ no rating yet
    if "Rating" in df.columns:
        df["Rating"] = df["Rating"].astype("string").str.strip()
        df["Rating"] = df["Rating"].replace("", pd.NA)
        df["Rating"] = df["Rating"].fillna("no rating yet")
    else:
        print("Column 'Rating' was not found.")

    # 6) تحويل Reviews Count إلى String
    # واستبدال القيم الفارغة بـ no reviews yet
    if "Reviews Count" in df.columns:
        df["Reviews Count"] = (
            df["Reviews Count"]
            .astype("string")
            .str.strip()
        )

        df["Reviews Count"] = df["Reviews Count"].replace("", pd.NA)
        df["Reviews Count"] = df["Reviews Count"].fillna(
            "no reviews yet"
        )
    else:
        print("Column 'Reviews Count' was not found.")

    # 7) عرض عدد القيم المختلفة
    if "Rating" in df.columns:
        print("\nUnique values in Rating:")
        print(df["Rating"].nunique())

    if "Reviews Count" in df.columns:
        print("\nUnique values in Reviews Count:")
        print(df["Reviews Count"].nunique())

    # 8) حفظ البيانات المنظفة في ملف جديد
    df.to_excel(OUTPUT_FILE, index=False)

    print("\nCleaning completed successfully.")
    print(f"Saved file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()