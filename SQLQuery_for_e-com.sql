select * from stg.JumiaProducts
select * from dbo.JumiaProducts

BEGIN TRANSACTION;

-- حذف الداتا لانه معتمد و مش هننعرف اننا نعمل ريسيت للid staging
DELETE FROM dbo.JumiaProducts;

--  delete staging data
DELETE FROM stg.JumiaProducts;

-- نصفر الid
DBCC CHECKIDENT ('dbo.JumiaProducts', RESEED, 0);
DBCC CHECKIDENT ('stg.JumiaProducts', RESEED, 0);

COMMIT TRANSACTION;
GO



USE E_commerce_scrabingproj;
GO

---- هنبدا نضيف و نعدل اسماء اعمده scd

-- EffectiveFrom تصبح st_date
IF COL_LENGTH('dbo.JumiaProducts', 'EffectiveFrom') IS NOT NULL
   AND COL_LENGTH('dbo.JumiaProducts', 'st_date') IS NULL
BEGIN
    EXEC sp_rename
        'dbo.JumiaProducts.EffectiveFrom',
        'st_date',
        'COLUMN';
END;
GO


-- EffectiveTo تصبح end_date
IF COL_LENGTH('dbo.JumiaProducts', 'EffectiveTo') IS NOT NULL
   AND COL_LENGTH('dbo.JumiaProducts', 'end_date') IS NULL
BEGIN
    EXEC sp_rename
        'dbo.JumiaProducts.EffectiveTo',
        'end_date',
        'COLUMN';
END;
GO


-- في حال لم تكن أعمدة SCD موجودة من الأساس
IF COL_LENGTH('dbo.JumiaProducts', 'st_date') IS NULL
BEGIN
    ALTER TABLE dbo.JumiaProducts
    ADD st_date DATETIME2 NULL;
END;
GO

IF COL_LENGTH('dbo.JumiaProducts', 'end_date') IS NULL
BEGIN
    ALTER TABLE dbo.JumiaProducts
    ADD end_date DATETIME2 NULL;
END;
GO

IF COL_LENGTH('dbo.JumiaProducts', 'iscurrent') IS NULL
BEGIN
    ALTER TABLE dbo.JumiaProducts
    ADD iscurrent BIT NULL;
END;
GO


---- لو فرضنا ان فيه اعمده بس القيم مش مجوده هنضيفها عشان هنحتاجها في التحميل للداتا الجديده 

UPDATE dbo.JumiaProducts
SET
    st_date = COALESCE(st_date, CreatedAt),
    end_date = NULL,
    iscurrent = COALESCE(iscurrent, 1);
GO


----- بنعمل بصمه للبيانات المهمه عشان نستعين بيها في scd 
------ هتكون عبارة عن بعض الاعمده المهمه و هنحتاجها في الاستورد و أحنا بنقارن الداتا 

UPDATE dbo.JumiaProducts
SET RowHash = HASHBYTES(
    'SHA2_256',
    CONCAT(
        COALESCE(ProductName, ''), '|',
        COALESCE(ImageURL, ''), '|',
        COALESCE(ProductURL, ''), '|',
        COALESCE(CONVERT(NVARCHAR(50), CurrentPrice), ''), '|',
        COALESCE(CONVERT(NVARCHAR(50), OldPrice), ''), '|',
        COALESCE(CONVERT(NVARCHAR(50), DiscountPercent), ''), '|',
        COALESCE(CONVERT(NVARCHAR(50), Rating), ''), '|',
        COALESCE(CONVERT(NVARCHAR(50), ReviewsCount), '')
    )
)
WHERE RowHash IS NULL;
GO


----- هنعمل عمليه upsert و احنا شغالين  , 
-----  بننقل الداتا من stg  لل main table

CREATE OR ALTER PROCEDURE dbo.usp_MoveJumiaFromStaging
    @LoadBatchID UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @ChangeTime DATETIME2 = SYSDATETIME();

    BEGIN TRY
        BEGIN TRANSACTION;

    

        DECLARE @Source TABLE (
            StageID INT PRIMARY KEY,
            SKU NVARCHAR(100),
            ProductName NVARCHAR(MAX),
            ImageURL NVARCHAR(MAX),
            ProductURL NVARCHAR(MAX),
            CurrentPrice DECIMAL(18,2),
            OldPrice DECIMAL(18,2),
            DiscountPercent DECIMAL(8,2),
            Rating DECIMAL(4,2),
            ReviewsCount INT,
            RowHash VARBINARY(32)
        );

        INSERT INTO @Source (
            StageID,
            SKU,
            ProductName,
            ImageURL,
            ProductURL,
            CurrentPrice,
            OldPrice,
            DiscountPercent,
            Rating,
            ReviewsCount,
            RowHash
        )
        SELECT
            x.StageID,
            x.SKU,
            x.ProductName,
            x.ImageURL,
            x.ProductURL,
            x.CurrentPrice,
            x.OldPrice,
            x.DiscountPercent,
            x.Rating,
            x.ReviewsCount,

            HASHBYTES(
                'SHA2_256',
                CONCAT(
                    COALESCE(x.ProductName, ''), '|',
                    COALESCE(x.ImageURL, ''), '|',
                    COALESCE(x.ProductURL, ''), '|',
                    COALESCE(CONVERT(NVARCHAR(50), x.CurrentPrice), ''), '|',
                    COALESCE(CONVERT(NVARCHAR(50), x.OldPrice), ''), '|',
                    COALESCE(CONVERT(NVARCHAR(50), x.DiscountPercent), ''), '|',
                    COALESCE(CONVERT(NVARCHAR(50), x.Rating), ''), '|',
                    COALESCE(CONVERT(NVARCHAR(50), x.ReviewsCount), '')
                )
            ) AS RowHash

        FROM (
            SELECT
                s.StageID,
                s.SKU,
                s.ProductName,
                s.ImageURL,
                s.ProductURL,
                s.CurrentPrice,
                s.OldPrice,

                TRY_CONVERT(
                    DECIMAL(8,2),
                    REPLACE(s.Discount, '%', '')
                ) AS DiscountPercent,

                TRY_CONVERT(
                    DECIMAL(4,2),
                    s.Rating
                ) AS Rating,

                TRY_CONVERT(
                    INT,
                    TRY_CONVERT(
                        DECIMAL(18,2),
                        REPLACE(s.ReviewsCount, ',', '')
                    )
                ) AS ReviewsCount,

                ROW_NUMBER() OVER (
                    PARTITION BY s.SKU
                    ORDER BY s.StageID DESC
                ) AS RowNumber

            FROM stg.JumiaProducts AS s
            WHERE
                s.LoadBatchID = @LoadBatchID
                AND s.SKU IS NOT NULL
                AND LTRIM(RTRIM(s.SKU)) <> ''
                AND s.CurrentPrice IS NOT NULL
                AND s.OldPrice IS NOT NULL
        ) AS x
        WHERE x.RowNumber = 1;


        --- تغيير القميه القديمة من iscurrent = 0 
        ---  و هنخلي الجديد ب 1

        UPDATE target
        SET
            target.iscurrent = 0,
            target.end_date = @ChangeTime
        FROM dbo.JumiaProducts AS target
        INNER JOIN @Source AS source
            ON target.SKU = source.SKU
        WHERE
            target.iscurrent = 1
            AND target.RowHash <> source.RowHash;


        -------ادخال المنتج لل main table 
        ---  بعد ما حفظنا المنتج في متغير في شكل جدول عشان اعمل المقارنات 
        ---- بتاعي قبل ما ابدا اعمل الinsert

        INSERT INTO dbo.JumiaProducts (
            StageID,
            SKU,
            ProductName,
            ImageURL,
            ProductURL,
            CurrentPrice,
            OldPrice,
            DiscountPercent,
            Rating,
            ReviewsCount,
            CreatedAt,
            st_date,
            end_date,
            iscurrent,
            RowHash
        )
        SELECT
            source.StageID,
            source.SKU,
            source.ProductName,
            source.ImageURL,
            source.ProductURL,
            source.CurrentPrice,
            source.OldPrice,
            source.DiscountPercent,
            source.Rating,
            source.ReviewsCount,
            @ChangeTime,
            @ChangeTime,
            NULL,
            1,
            source.RowHash
        FROM @Source AS source
        LEFT JOIN dbo.JumiaProducts AS target
            ON target.SKU = source.SKU
            AND target.iscurrent = 1
        WHERE target.ProductID IS NULL;


        DECLARE @RowsInserted INT = @@ROWCOUNT;

        COMMIT TRANSACTION;

        SELECT @RowsInserted AS RowsInserted;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH
END;
GO