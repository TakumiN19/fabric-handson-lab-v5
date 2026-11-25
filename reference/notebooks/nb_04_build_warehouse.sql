-- Fabric notebook source

-- METADATA ********************

-- META {
-- META   "kernel_info": {
-- META     "name": "sqldatawarehouse"
-- META   },
-- META   "dependencies": {
-- META     "warehouse": {
-- META       "default_warehouse": "{{WAREHOUSE_ID}}",
-- META       "known_warehouses": [
-- META         {
-- META           "id": "{{WAREHOUSE_ID}}",
-- META           "type": "Datawarehouse"
-- META         }
-- META       ]
-- META     }
-- META   }
-- META }

-- MARKDOWN ********************

-- # Lab 04 — Warehouse のディメンションとファクトを作成（T-SQL Notebook）
--
-- Lakehouse `taxi_lakehouse` の加工済みテーブルを 3 部構成名で参照し、CTAS で Warehouse に書き込みます。
-- 再実行すると同じ 7 テーブルだけを作り直します。

-- CELL ********************

DROP TABLE IF EXISTS dbo.dim_vendor;
CREATE TABLE dbo.dim_vendor AS
SELECT CAST(VendorID AS INT) AS VendorID, CAST(vendor_name AS VARCHAR(100)) AS vendor_name
FROM taxi_lakehouse.dbo.vendor_lookup;

DROP TABLE IF EXISTS dbo.dim_ratecode;
CREATE TABLE dbo.dim_ratecode AS
SELECT CAST(RatecodeID AS INT) AS RatecodeID, CAST(ratecode_name AS VARCHAR(100)) AS ratecode_name
FROM taxi_lakehouse.dbo.ratecode_lookup;

DROP TABLE IF EXISTS dbo.dim_payment_type;
CREATE TABLE dbo.dim_payment_type AS
SELECT CAST(payment_type AS INT) AS payment_type, CAST(payment_type_name AS VARCHAR(100)) AS payment_type_name
FROM taxi_lakehouse.dbo.payment_type_lookup;

DROP TABLE IF EXISTS dbo.dim_trip_type;
CREATE TABLE dbo.dim_trip_type AS
SELECT CAST(trip_type AS INT) AS trip_type, CAST(trip_type_name AS VARCHAR(100)) AS trip_type_name
FROM taxi_lakehouse.dbo.trip_type_lookup;

-- METADATA ********************

-- META {
-- META   "language": "sql",
-- META   "language_group": "sqldatawarehouse"
-- META }

-- MARKDOWN ********************

-- ## 乗車地と降車地は役割の異なる 2 つのディメンションにする

-- CELL ********************

DROP TABLE IF EXISTS dbo.dim_pickup_zone;
CREATE TABLE dbo.dim_pickup_zone AS
SELECT CAST(LocationID AS INT) AS LocationID,
       CAST(Borough AS VARCHAR(50)) AS pickup_borough,
       CAST(Zone AS VARCHAR(100)) AS pickup_zone,
       CAST(service_zone AS VARCHAR(50)) AS pickup_service_zone
FROM taxi_lakehouse.dbo.taxi_zone_lookup;

DROP TABLE IF EXISTS dbo.dim_dropoff_zone;
CREATE TABLE dbo.dim_dropoff_zone AS
SELECT CAST(LocationID AS INT) AS LocationID,
       CAST(Borough AS VARCHAR(50)) AS dropoff_borough,
       CAST(Zone AS VARCHAR(100)) AS dropoff_zone,
       CAST(service_zone AS VARCHAR(50)) AS dropoff_service_zone
FROM taxi_lakehouse.dbo.taxi_zone_lookup;

-- METADATA ********************

-- META {
-- META   "language": "sql",
-- META   "language_group": "sqldatawarehouse"
-- META }

-- MARKDOWN ********************

-- ## ファクト（1 トリップ 1 行・乗車日時を保持）

-- CELL ********************

DROP TABLE IF EXISTS dbo.fact_trips;
CREATE TABLE dbo.fact_trips AS
SELECT
    CAST(trip_id AS BIGINT) AS trip_id,
    CAST(VendorID AS INT) AS VendorID,
    CAST(RatecodeID AS INT) AS RatecodeID,
    CAST(PULocationID AS INT) AS PULocationID,
    CAST(DOLocationID AS INT) AS DOLocationID,
    CAST(payment_type AS INT) AS payment_type,
    CAST(COALESCE(trip_type, 0) AS INT) AS trip_type,
    CAST(lpep_pickup_datetime AS DATETIME2(6)) AS lpep_pickup_datetime,
    CAST(lpep_dropoff_datetime AS DATETIME2(6)) AS lpep_dropoff_datetime,
    CAST(pickup_date AS DATE) AS pickup_date,
    CAST(pickup_hour AS INT) AS pickup_hour,
    CAST(pickup_month AS VARCHAR(7)) AS pickup_month,
    CAST(passenger_count AS INT) AS passenger_count,
    CAST(passenger_group AS VARCHAR(10)) AS passenger_group,
    trip_distance,
    trip_duration_minutes,
    fare_amount,
    tip_amount,
    tolls_amount,
    total_amount,
    fare_per_mile
FROM taxi_lakehouse.dbo.green_tripdata_2026;

-- METADATA ********************

-- META {
-- META   "language": "sql",
-- META   "language_group": "sqldatawarehouse"
-- META }

-- CELL ********************

SELECT 'fact_trips' AS table_name, COUNT_BIG(*) AS row_count FROM dbo.fact_trips
UNION ALL SELECT 'dim_vendor', COUNT_BIG(*) FROM dbo.dim_vendor
UNION ALL SELECT 'dim_ratecode', COUNT_BIG(*) FROM dbo.dim_ratecode
UNION ALL SELECT 'dim_payment_type', COUNT_BIG(*) FROM dbo.dim_payment_type
UNION ALL SELECT 'dim_trip_type', COUNT_BIG(*) FROM dbo.dim_trip_type
UNION ALL SELECT 'dim_pickup_zone', COUNT_BIG(*) FROM dbo.dim_pickup_zone
UNION ALL SELECT 'dim_dropoff_zone', COUNT_BIG(*) FROM dbo.dim_dropoff_zone
ORDER BY table_name;

-- METADATA ********************

-- META {
-- META   "language": "sql",
-- META   "language_group": "sqldatawarehouse"
-- META }
