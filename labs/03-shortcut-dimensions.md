# Lab 03 — ショートカットとマスター整備

所要時間: 約 20 分　／　前提: [Lab 02](02-notebook-ingest-transform.md) 完了

このラボでは、講師が用意した共有 ADLS Gen2 の CSV を、**コピーせずに** OneLake ショートカットで参照し、
GitHub Copilot が仕様書から書いた Notebook で、ゾーンマスターとコード表を整備します。

```text
（講師が準備済み）                         （あなたが実施）
ADLS Gen2 の CSV + 共有接続  ──▶  Shortcut Files/taxi_zone ──▶ nb_03_prepare_dimensions ──▶ マスター 5 表
```

| 取り込み方 | データの場所 | 例 |
|---|---|---|
| アップロード（Lab 02） | OneLake にコピー | `Files/raw` の Parquet |
| ショートカット（Lab 03） | 元のストレージに残したまま参照 | `Files/taxi_zone` の CSV |

ショートカットの参照先は ADLS Gen2 のほか、Amazon S3、Google Cloud Storage、別の OneLake なども指定できます。
このラボでは Azure の権限は不要です。講師が共有した接続を使います。

---

## 3-1. 共有接続でショートカットを作成する

🤖 **Copilot に入力**

```text
講師が共有した ADLS Gen2 の接続を使って、taxi_lakehouse の Files に taxi_zone というショートカットを作って。
接続名や URL は教材の設定から読み取って。作成後にショートカットの一覧を表示して。
```

🤖 **Copilot の動き**

- `python3 scripts/lab.py shortcut` を実行します。
  - 接続名（`config/workshop.json` の `sharedAdls.connectionName`）から接続 ID を API で特定
  - 既に同じショートカットがあれば作り直さない

✅ **期待する結果**

```json
[ { "name": "taxi_zone", "path": "/Files", "type": "AdlsGen2" } ]
```

---

## 3-2. マスター整備 Notebook を Copilot に書かせて実行する

🤖 **Copilot に入力**

```text
notebooks/specs の nb_03_prepare_dimensions の仕様を読んで、マスター整備の PySpark Notebook を
work/notebooks/nb_03_prepare_dimensions.ipynb に生成して。セルの構成を説明してから、チェックを通して Fabric に配置・実行して。
ショートカットのゾーン CSV と、ベンダー・料金コード・支払方法・乗車種別のコード表を Delta テーブルに保存して、
保存したテーブルと件数を教えて。失敗したら原因を説明して Notebook を直して。答え合わせはまだしないで。
```

🤖 **Copilot の動き**

- 仕様書 [`notebooks/specs/nb_03_prepare_dimensions.md`](../notebooks/specs/nb_03_prepare_dimensions.md) から Notebook を生成します（コード表の値も仕様書のとおり）。
- `python3 scripts/lab.py notebook check nb_03_prepare_dimensions` で約束を確認してから、`python3 scripts/lab.py notebook deploy-run nb_03_prepare_dimensions` で配置・実行します。
- 失敗したら `result.error` とセル出力から原因を説明し、生成した Notebook を直して再実行します（模範解答は `--reference`）。

✅ **期待する結果**

| テーブル | 件数 |
|---|---|
| `taxi_zone_lookup` | 265 |
| `vendor_lookup` | 2 |
| `ratecode_lookup` | 6 |
| `payment_type_lookup` | 6 |
| `trip_type_lookup` | 2 |

---

## 3-3. マスターと結合結果を検証する

乗車地（`PULocationID`）と降車地（`DOLocationID`）は、どちらも同じゾーンマスターを参照します。
**同じマスターを 2 つの役割で結合する** ことが、Lab 05 のモデルと Lab 07 の Ontology の設計につながります。

🤖 **Copilot に入力**

```text
ゾーンマスターのキー品質と、乗車地・降車地それぞれで結合した結果を、検証 Notebook を Fabric で実行して確認して。
固定レコードのゾーン名、区ごとの件数、Manhattan から Brooklyn への件数を期待値と比べて。データは変更しないで。
```

🤖 **Copilot の動き**: `python3 scripts/lab.py notebook deploy-run nb_03_validate_dimensions`

✅ **期待する結果**: `passed: true`

| 検証項目 | 期待値 |
|---|---|
| ゾーン | 265 行、`LocationID` の重複・欠損 0 件 |
| 結合後の件数 | 37,948（欠落・増加なし） |
| 乗車区の件数 | Queens 9,957 / Manhattan 9,937 / Brooklyn 8,702 / Bronx 6,151 / Staten Island 2,800 / EWR 135 / その他 266 |
| Manhattan → Brooklyn | 2,340 件 / $42,944.85 |

| trip_id | 乗車ゾーン（区） | 降車ゾーン（区） |
|---|---|---|
| 1 | Washington Heights North（Manhattan） | Gravesend（Brooklyn） |
| 4 | Saint George/New Brighton（Staten Island） | Flatbush/Ditmas Park（Brooklyn） |

---

## ✅ チェックポイント

- [ ] ショートカット `taxi_zone` が作成された
- [ ] Copilot が生成した `nb_03_prepare_dimensions` が Completed、マスター 5 表が保存された
- [ ] `nb_03_validate_dimensions` の結果が `passed: true`

## 🧹 トラブルシュート

| 症状 | 対処 |
|---|---|
| 共有接続が見つからない | 🤖「アクセスできる接続を一覧して」。表示されなければ講師に接続の共有（User 権限）を依頼 |
| ショートカット作成で 403 | 講師対応（サービスプリンシパルの権限またはネットワーク）。[講師ガイド 02](../instructor/02-shared-data-and-connections.md) |
| CSV が見つからない | 🤖「taxi_lakehouse の Files/taxi_zone の中身を一覧して」 |
| 「その他」の件数が 266 と異なる | 共有 CSV の版の違い。講師に確認（データは変更しない） |

次は **[Lab 04 — Warehouse（T-SQL Notebook）](04-warehouse-tsql-notebook.md)** です。
