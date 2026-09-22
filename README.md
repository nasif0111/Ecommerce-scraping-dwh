# Jumia Products ETL Pipeline

مشروع ETL لمعالجة بيانات منتجات Jumia: التحقق من ملف Excel، تنظيفه، رفعه إلى SQL Server، ثم الاحتفاظ بتاريخ تغيّرات المنتجات باستخدام **SCD Type 2**.

## Pipeline

```text
Raw Excel
   ↓
Validation → valid_data.xlsx / not_valid_data.xlsx
   ↓
Cleaning → cleaned_valid_data.xlsx
   ↓
SQL Server Staging → stg.JumiaProducts
   ↓
SCD Type 2 → dbo.JumiaProducts
   ↓
Export current products → Excel
```

## Features

- التحقق من الحقول الأساسية: `SKU` و`Current Price` و`Old Price`.
- فصل الصفوف الصحيحة والخاطئة في ملفين Excel.
- تنظيف المسافات وقيم `Discount` و`Rating` و`Reviews Count`.
- رفع البيانات إلى Staging Area قبل إدخالها للجدول الأساسي.
- استخدام `SKU` كمفتاح للمنتج.
- تتبع تغيّرات المنتج باستخدام SCD Type 2.

## SQL Server tables

| Table | Purpose |
| --- | --- |
| `stg.JumiaProducts` | يحتفظ بكل Batch يصل من Python قبل المعالجة. |
| `dbo.JumiaProducts` | يحتوي على بيانات المنتج الحالية وتاريخ النسخ القديمة. |

أهم أعمدة SCD في الجدول الأساسي:

- `st_date`: بداية صلاحية النسخة.
- `end_date`: نهاية صلاحية النسخة القديمة.
- `iscurrent`: `1` للنسخة الحالية و`0` للنسخ السابقة.
- `RowHash`: بصمة للصف تكشف تغيّر بيانات المنتج.

## SCD Type 2 behavior

| حالة البيانات الواردة | الإجراء |
| --- | --- |
| `SKU` جديد | إضافة منتج جديد. |
| نفس `SKU` ونفس البيانات | لا تغيير. |
| نفس `SKU` وبيانات مختلفة | إغلاق النسخة القديمة وإضافة نسخة جديدة. |

## Installation

Requirements: Python 3.10+, SQL Server, and ODBC Driver 18 for SQL Server.

```bash
pip install pandas openpyxl pydantic pyodbc
```

حدّث إعدادات SQL Server ومسار ملف Excel في ملفات Python قبل التشغيل.

## Run the project

```bash
python validate_data.py
python clean_valid_data.py
python load_to_sql_server.py
python export_from_sql.py
```

## Useful query

لعرض المنتجات الحالية فقط:

```sql
SELECT *
FROM dbo.JumiaProducts
WHERE iscurrent = 1;
```

## Tech stack

- Python, Pandas, Pydantic
- SQL Server, PyODBC
- Excel, OpenPyXL
