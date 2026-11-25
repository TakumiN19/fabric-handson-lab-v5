# 仕様: nb_02_prepare_trips（乗車データの取り込みと加工）

共通の約束は [README.md](README.md) を参照。生成先: `work/notebooks/nb_02_prepare_trips.ipynb`

## 目的

`Files/raw` の乗車データ（Bronze）を読み、クレンジングと派生列の追加をして Delta テーブル（Silver）に保存する。

## 入力

| 種類 | 場所 | 内容 |
|---|---|---|
| Parquet | `Files/raw/green_tripdata_2026-04.parquet` | NYC グリーンタクシー 2026 年 4 月。44,238 行 / 21 列 |

元の 21 列: `VendorID`, `lpep_pickup_datetime`, `lpep_dropoff_datetime`, `store_and_fwd_flag`, `RatecodeID`,
`PULocationID`, `DOLocationID`, `passenger_count`, `trip_distance`, `fare_amount`, `extra`, `mta_tax`, `tip_amount`,
`tolls_amount`, `ehail_fee`, `improvement_surcharge`, `total_amount`, `payment_type`, `trip_type`,
`congestion_surcharge`, `cbd_congestion_fee`

## 出力

| テーブル | 書き方 |
|---|---|
| `green_tripdata_2026`（Delta、既定 Lakehouse） | `mode("overwrite")` + `overwriteSchema`。27 列、先頭列は `trip_id` |

## 加工ルール

| 対象 | ルール |
|---|---|
| `ehail_fee` | 列を削除する |
| 除外する行 | `passenger_count` が null の行だけ。重複排除やその他の行削除はしない |
| `lpep_pickup_datetime` / `lpep_dropoff_datetime` | セッションのタイムゾーンを UTC にしたうえで `timestamp` 型にキャストする（Warehouse で日時を扱うため） |
| `trip_id`（long） | 次の 8 列の昇順で並べた 1 始まりの連番（`row_number()`）: `lpep_pickup_datetime`, `lpep_dropoff_datetime`, `VendorID`, `PULocationID`, `DOLocationID`, `trip_distance`, `fare_amount`, `total_amount`。並べる前に、この 8 列に null がないことを確認し、あれば例外にする |
| `pickup_date`（date） | 乗車日時の日付 |
| `pickup_hour`（int） | 乗車日時の時（0〜23） |
| `pickup_month`（string） | 乗車日時の `yyyy-MM` |
| `trip_duration_minutes`（double） | （降車 − 乗車）の秒 ÷ 60 を小数 2 桁に丸める。秒が負または欠損なら null |
| `fare_per_mile`（double） | `fare_amount / trip_distance` を小数 2 桁に丸める。距離が 0 以下・欠損、または運賃が欠損なら null |
| `passenger_group`（string） | `passenger_count` が 1 → `single`、2 以上 → `group`、それ以外 → `unknown` |

## 自己チェックと結果

`save_result("nb_02_prepare_trips", ...)` に次を含める。

- `source`: 入力の行数・列数
- `removedNullPassengerCount`: 除外した行数
- `saved`: `{"table": "green_tripdata_2026", "rows": ..., "columns": ...}`（保存後に `spark.table` で読み直した値）
- `passed`: 保存後の行数が「入力行数 − 除外行数」と等しく、列数が 27 なら `true`

> 期待値との答え合わせ（固定レコード・集計）は、教材提供の `nb_02_validate_trips` で行う。この Notebook では行わない。

## 目安

入力 44,238 行 → 除外 6,290 行 → 保存 37,948 行 / 27 列
