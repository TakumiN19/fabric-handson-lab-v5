# Lab 04 — Warehouse のディメンションとファクト（T-SQL Notebook）

所要時間: 約 25 分　／　前提: [Lab 03](03-shortcut-dimensions.md) 完了

このラボでは Fabric Data Warehouse を作成し、**T-SQL Notebook** で Lakehouse の加工済みデータから
スター スキーマ（ファクト 1 表 + ディメンション 6 表）を作ります。

```text
taxi_lakehouse（Delta）                    taxi_warehouse
  green_tripdata_2026  ──CTAS──▶  fact_trips
  vendor_lookup など   ──CTAS──▶  dim_vendor / dim_ratecode / dim_payment_type / dim_trip_type
  taxi_zone_lookup     ──CTAS──▶  dim_pickup_zone / dim_dropoff_zone（同じマスターを 2 つの役割で）
```

> 💡 V3 では Warehouse に日時が入らず、レポート用に別の日付テーブルを作っていました。
> V4 では Lab 02 で日時を UTC の timestamp として保存しているため、`fact_trips` に乗車日時をそのまま保持できます。

---

## 4-1. Warehouse を準備する

🤖 **Copilot に入力**

```text
自分のワークスペースに taxi_warehouse を準備して、接続先のサーバー名を教えて。
あわせて taxi_lakehouse の SQL 分析エンドポイントのメタデータを最新にして、テーブルが見えるか確認して。
```

🤖 **Copilot の動き**

- `python3 scripts/lab.py ensure-warehouse`
- `python3 scripts/lab.py refresh-sql-endpoint`（Lab 02・03 で作ったテーブルを SQL から参照できるようにする）

✅ **期待する結果**: Warehouse の ID とサーバー名、SQL 分析エンドポイントで `green_tripdata_2026` などのテーブルが同期済み。

---

## 4-2. T-SQL Notebook を Copilot に書かせて Warehouse のテーブルを作成する

🤖 **Copilot に入力**

```text
notebooks/specs の nb_04_build_warehouse の仕様を読んで、Fabric の T-SQL Notebook を
work/notebooks/nb_04_build_warehouse.sql に生成して。ディメンションとファクトの CTAS を表ごとに説明してから、
チェックを通して taxi_warehouse に接続して配置・実行して。
完了したら Notebook のリンクと実行状態を教えて。失敗したら原因を説明して Notebook を直して。答え合わせはまだしないで。
```

🤖 **Copilot の動き**

- 仕様書 [`notebooks/specs/nb_04_build_warehouse.md`](../notebooks/specs/nb_04_build_warehouse.md) から、Fabric の T-SQL Notebook 形式（`notebook-content.sql`）で生成します。
  - CTAS（`CREATE TABLE AS SELECT`）で、Lakehouse を 3 部構成名（`taxi_lakehouse.dbo.<表>`）で参照して 7 表を作成
  - Warehouse の ID は書かず、`{{WAREHOUSE_ID}}` にしておく（配置時に `lab.py` が置き換える）
- `python3 scripts/lab.py notebook check nb_04_build_warehouse` で約束を確認してから、`python3 scripts/lab.py notebook deploy-run nb_04_build_warehouse` で配置・実行します。
- 失敗したら `result.error` とセル出力から原因を説明し、生成した Notebook を直して再実行します（模範解答は `--reference`）。

> 🛟 **Gate G3**: T-SQL Notebook の API 実行がテナントで許可されていない場合、実行は失敗します。
> その場合は 🌐 Notebook のリンクを開き、**すべて実行** を選んでください（Copilot が生成したコードは配置済み）。

🌐 **ブラウザ**（任意）: Notebook を開き、各セルの SQL と、最後のセルの件数表を確認します。

---

## 4-3. Warehouse を検証する

🤖 **Copilot に入力**

```text
taxi_warehouse のテーブルを検証 Notebook で確認して。
件数、キーの重複と参照切れ、合計金額が Lakehouse と一致するか、Manhattan から Brooklyn の件数を期待値と比べて。
データは変更しないで。
```

🤖 **Copilot の動き**: `python3 scripts/lab.py notebook deploy-run nb_04_validate_warehouse`
（Spark の Warehouse コネクタで読み取り専用に確認します）

✅ **期待する結果**: `passed: true`

| テーブル | 件数 | 検証 |
|---|---|---|
| `fact_trips` | 37,948 | 合計金額 $687,602.60（Lakehouse と一致）、乗車日時あり |
| `dim_vendor` / `dim_trip_type` | 2 / 2 | キー重複 0、参照切れ 0 |
| `dim_ratecode` / `dim_payment_type` | 6 / 6 | 同上 |
| `dim_pickup_zone` / `dim_dropoff_zone` | 265 / 265 | 同上 |

---

## ✅ チェックポイント

- [ ] `taxi_warehouse` に 7 表が作成された
- [ ] Copilot が生成した T-SQL Notebook `nb_04_build_warehouse` が Fabric にある
- [ ] `nb_04_validate_warehouse` の結果が `passed: true`

## 🧹 トラブルシュート

| 症状 | 🤖 Copilot に入力 |
|---|---|
| `Invalid object name 'taxi_lakehouse.dbo...'` | 「taxi_lakehouse の SQL 分析エンドポイントのメタデータを更新して、もう一度 nb_04_build_warehouse を実行して」 |
| T-SQL Notebook の実行が失敗 | 「失敗理由を表示して」。API 実行が許可されていなければ 🌐 Notebook で「すべて実行」 |
| 検証で `orphan keys` が 0 でない | 「どのキーが参照切れか教えて。データは変更しないで」→ 講師に連絡 |

次は **[Lab 05 — セマンティックモデル](05-semantic-model.md)** です。
