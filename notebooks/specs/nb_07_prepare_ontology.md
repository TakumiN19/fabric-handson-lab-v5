# 仕様: nb_07_prepare_ontology（Ontology 用テーブルの整備）

共通の約束は [README.md](README.md) を参照。生成先: `work/notebooks/nb_07_prepare_ontology.ipynb`

## 目的

Ontology `onto_taxi` のエンティティ（Trip・Zone・Vendor）にバインドするテーブルを、加工済みデータから作る。
`onto_trips` は 1 トリップ 1 行のまま、支払方法・乗車種別の名前を付ける。件数・金額は変えない。

## 入力（既定 Lakehouse のテーブル）

`green_tripdata_2026`（Lab 02）、`taxi_zone_lookup` / `vendor_lookup` / `payment_type_lookup` / `trip_type_lookup`（Lab 03）

## 出力（すべて Delta、`mode("overwrite")` + `overwriteSchema`）

Ontology の生成（`scripts/lab.py ontology`）がこの列名・型を前提にしているため、**列名と型を正確に**そろえる。

| テーブル（エンティティ / キー） | 列（型） |
|---|---|
| `onto_trips`（Trip / `trip_id`） | `trip_id`（long）, `VendorID`（long）, `PULocationID`（long）, `DOLocationID`（long）, `lpep_pickup_datetime`（timestamp）, `pickup_date`（timestamp、date をキャスト）, `pickup_hour`（long）, `passenger_count`（long）, `passenger_group`（string）, `trip_distance`（double）, `trip_duration_minutes`（double）, `fare_amount`（double）, `tip_amount`（double）, `total_amount`（double）, `payment_type_name`（string）, `trip_type_name`（string） |
| `onto_zones`（Zone / `LocationID`） | `LocationID`（long）, `Borough`, `Zone`, `service_zone`（string） |
| `onto_vendors`（Vendor / `VendorID`） | `VendorID`（long）, `vendor_name`（string） |

| ルール | 内容 |
|---|---|
| 名前の付与 | `payment_type` → `payment_type_lookup`、`trip_type` → `trip_type_lookup` を **left join**（行を増減させない） |
| 列の順序 | 上の表の順 |

## 自己チェックと結果

保存後に読み直して、次を `checks` に記録し、`save_result("nb_07_prepare_ontology", {"passed": ..., "checks": ...})` で保存する。

| チェック | 期待 |
|---|---|
| `onto_trips` / `onto_zones` / `onto_vendors` の行数 | 37,948 / 265 / 2 |
| 各テーブルのキーの一意性 | 行数 = キーの distinct 数 |
| `onto_trips` の `total_amount` 合計（小数 2 桁） | `green_tripdata_2026` と一致（許容誤差 0.005） |
| 名前の解決 | `payment_type_name` または `trip_type_name` が null の行が 0 |
