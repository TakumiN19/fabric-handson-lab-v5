# 仕様: nb_03_prepare_dimensions（ゾーンとコードのマスター整備）

共通の約束は [README.md](README.md) を参照。生成先: `work/notebooks/nb_03_prepare_dimensions.ipynb`

## 目的

OneLake ショートカット先のゾーン CSV（共有 ADLS Gen2 に置いたまま）と、TLC のデータ辞書にあるコード表を、
Lakehouse の Delta テーブル（マスター）として保存する。

## 入力

| 種類 | 場所 | 内容 |
|---|---|---|
| CSV（ヘッダーあり） | `Files/taxi_zone/Taxi_zone_lookup.csv`（Lab 03-1 のショートカット） | 列 `LocationID`, `Borough`, `Zone`, `service_zone`。265 行 |

## 出力（すべて Delta、`mode("overwrite")` + `overwriteSchema`）

| テーブル | 列（型） | 行 |
|---|---|---|
| `taxi_zone_lookup` | `LocationID`（int）, `Borough`, `Zone`, `service_zone`（string、前後の空白を除去） | 265 |
| `vendor_lookup` | `VendorID`（int）, `vendor_name`（string） | 2 |
| `ratecode_lookup` | `RatecodeID`（int）, `ratecode_name`（string） | 6 |
| `payment_type_lookup` | `payment_type`（int）, `payment_type_name`（string） | 6 |
| `trip_type_lookup` | `trip_type`（int）, `trip_type_name`（string） | 2 |

コード表の値（名前は Data Agent や Ontology の回答にそのまま出るため、この表記どおりにする）:

| テーブル | コード → 名前 |
|---|---|
| `vendor_lookup` | 1 → `Creative Mobile Technologies, LLC`、2 → `VeriFone Inc.` |
| `ratecode_lookup` | 1 → `Standard rate`、2 → `JFK`、3 → `Newark`、4 → `Nassau or Westchester`、5 → `Negotiated fare`、6 → `Group ride` |
| `payment_type_lookup` | 1 → `Credit card`、2 → `Cash`、3 → `No charge`、4 → `Dispute`、5 → `Unknown`、6 → `Voided trip` |
| `trip_type_lookup` | 1 → `Street-hail`、2 → `Dispatch` |

コード列は null 不可のスキーマ（`StructField(..., IntegerType(), False)`）で作る。

## 自己チェックと結果

`save_result("nb_03_prepare_dimensions", ...)` に次を含める。

- `source`: 読み込んだ CSV のパス
- `saved`: 5 テーブルそれぞれの保存後の行数（`spark.table` で読み直した値）
- `passed`: 上の表の行数とすべて一致し、`taxi_zone_lookup.LocationID` に重複・null がなければ `true`

> 乗車地・降車地での結合や区ごとの件数の答え合わせは、教材提供の `nb_03_validate_dimensions` で行う。
