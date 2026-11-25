# 仕様: nb_04_build_warehouse（Warehouse のディメンションとファクト、T-SQL Notebook）

共通の約束のうち、結果ファイル以外は [README.md](README.md) と同じ。生成先: `work/notebooks/nb_04_build_warehouse.sql`

## 目的

Lakehouse `taxi_lakehouse` の加工済みテーブルを 3 部構成名（`taxi_lakehouse.dbo.<表>`）で参照し、
CTAS（`CREATE TABLE ... AS SELECT`）で Warehouse `taxi_warehouse` に 7 表を作る（Gold）。

## ファイル形式（Fabric の T-SQL Notebook = `notebook-content.sql`）

`.ipynb` ではなく、Fabric の T-SQL Notebook のソース形式で書く。`{{WAREHOUSE_ID}}` は `lab.py` が配置時に
`taxi_warehouse` の ID に置き換える（ID を直書きしない）。

```sql
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

-- # 見出し（Markdown セルは各行を "-- " で始める）

-- CELL ********************

SELECT 1;

-- METADATA ********************

-- META {
-- META   "language": "sql",
-- META   "language_group": "sqldatawarehouse"
-- META }
```

コードセルは `-- CELL ********************` で始め、各コードセルの後ろに上の `-- METADATA` ブロックを付ける。

## 出力（`dbo` スキーマ）

再実行できるよう、各表の前に `DROP TABLE IF EXISTS dbo.<表>;` を置き、`CREATE TABLE dbo.<表> AS SELECT ...` で作る。
セマンティックモデル（Lab 05）がこの列名を前提にしているため、**列名を正確に**そろえる。

| 表 | 元の表（`taxi_lakehouse.dbo.`） | 列（型） |
|---|---|---|
| `dim_vendor` | `vendor_lookup` | `VendorID` INT, `vendor_name` VARCHAR(100) |
| `dim_ratecode` | `ratecode_lookup` | `RatecodeID` INT, `ratecode_name` VARCHAR(100) |
| `dim_payment_type` | `payment_type_lookup` | `payment_type` INT, `payment_type_name` VARCHAR(100) |
| `dim_trip_type` | `trip_type_lookup` | `trip_type` INT, `trip_type_name` VARCHAR(100) |
| `dim_pickup_zone` | `taxi_zone_lookup` | `LocationID` INT, `pickup_borough` VARCHAR(50), `pickup_zone` VARCHAR(100), `pickup_service_zone` VARCHAR(50) |
| `dim_dropoff_zone` | `taxi_zone_lookup` | `LocationID` INT, `dropoff_borough` VARCHAR(50), `dropoff_zone` VARCHAR(100), `dropoff_service_zone` VARCHAR(50) |
| `fact_trips` | `green_tripdata_2026` | 下の表 |

乗車地と降車地は、同じゾーンマスターから **役割の異なる 2 つのディメンション** として作る（列名に `pickup_` / `dropoff_` を付ける）。

`fact_trips`（1 トリップ 1 行。行の削除・結合による増減をしない）:

| 列 | 型・ルール |
|---|---|
| `trip_id` | BIGINT |
| `VendorID`, `RatecodeID`, `PULocationID`, `DOLocationID`, `payment_type` | INT |
| `trip_type` | INT。null は 0 にする（`COALESCE(trip_type, 0)`） |
| `lpep_pickup_datetime`, `lpep_dropoff_datetime` | DATETIME2(6) |
| `pickup_date` | DATE |
| `pickup_hour` | INT |
| `pickup_month` | VARCHAR(7) |
| `passenger_count` | INT |
| `passenger_group` | VARCHAR(10) |
| `trip_distance`, `trip_duration_minutes`, `fare_amount`, `tip_amount`, `tolls_amount`, `total_amount`, `fare_per_mile` | 元の型のまま |

## 最後のセル（結果）

T-SQL Notebook は結果ファイルを書けないため、最後のセルで 7 表の件数を `UNION ALL` で 1 つの結果にまとめて表示する
（列 `table_name`, `row_count`、`table_name` 順）。答え合わせは教材提供の `nb_04_validate_warehouse` で行う。

## 目安

`fact_trips` 37,948 / `dim_vendor` 2 / `dim_ratecode` 6 / `dim_payment_type` 6 / `dim_trip_type` 2 / `dim_pickup_zone` 265 / `dim_dropoff_zone` 265
