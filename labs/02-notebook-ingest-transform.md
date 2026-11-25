# Lab 02 — Notebook で取り込み・加工・検証

所要時間: 約 40 分　／　前提: [Lab 01](01-sign-in.md) 完了

このラボでは、サンプルデータを Lakehouse に取り込み、**GitHub Copilot が仕様書から書いた Notebook** を
Fabric の Notebook アイテムとして配置して加工し、教材提供の検証 Notebook で答え合わせをします。
V3 では一時的な Spark セッションで処理していたため、処理内容が Fabric に残りませんでした。
V4 では、Notebook のコード・実行履歴・出力をポータルで確認できます。

```text
data/*.parquet ──アップロード──▶ Lakehouse Files/raw
                                     │
   仕様書 ─Copilot が生成─▶ nb_02_prepare_trips（加工・保存）──▶ Delta 表 green_tripdata_2026
                                     │
                     nb_02_validate_trips（読み取りのみ）──▶ 検証結果
```

> 📖 用語は [用語集](glossary.md) を参照してください（Lakehouse・Delta・Notebook・メダリオン など）。

## 📐 なぜ加工するのか

実データには欠損や不要な列があり、そのままでは分析しにくいため、段階的に整えます（メダリオンアーキテクチャの考え方）。

![メダリオンアーキテクチャ](images/medallion-architecture.png)

| 段階 | このハンズオンでの対応 |
|---|---|
| Bronze（生データ） | `Files/raw` の Parquet（変更しない） |
| Silver（整えたデータ） | `green_tripdata_2026`（Lab 02）とマスター（Lab 03） |
| Gold（分析用） | Warehouse のファクト・ディメンション（Lab 04）とモデル（Lab 05） |

---

## 2-1. Lakehouse を準備し、サンプルを取り込む

🤖 **Copilot に入力**

```text
自分のワークスペースに taxi_lakehouse を準備して、
data/green_tripdata_2026-04.parquet を Files/raw にアップロードして。
アップロード後のサイズがローカルと一致するか確認して。
```

🤖 **Copilot の動き**

- `python3 scripts/lab.py ensure-lakehouse`（既にあれば再利用し、SQL 分析エンドポイントの準備完了を待つ）
- `python3 scripts/lab.py upload-sample`（OneLake へアップロードし、サイズを照合）

✅ **期待する結果**

```json
{ "uploaded": "Files/raw/green_tripdata_2026-04.parquet", "bytes": 1316650 }
```

---

## 2-2. 加工 Notebook を GitHub Copilot に書かせる

このラボの加工 Notebook は、教材に完成品がありません。**仕様書を渡して、GitHub Copilot に Notebook のコードを書かせます。**
仕様書は「何を入力し、どのルールで加工し、何を出力するか」だけを書いた設計書です。

| ファイル | 役割 |
|---|---|
| [`notebooks/specs/nb_02_prepare_trips.md`](../notebooks/specs/nb_02_prepare_trips.md) | 加工の仕様（入力・出力・加工ルール） |
| [`notebooks/specs/README.md`](../notebooks/specs/README.md) | すべての Notebook に共通の約束（形式・結果ファイル・禁止事項） |
| `work/notebooks/nb_02_prepare_trips.ipynb` | **Copilot が生成する Notebook**（あなた専用。Git には含めない） |

🤖 **Copilot に入力**

```text
notebooks/specs の共通の約束と nb_02_prepare_trips の仕様を読んで、
Fabric の PySpark Notebook を work/notebooks/nb_02_prepare_trips.ipynb に生成して。
生成したら、セルごとに何をしているかを表で説明して、配置前のチェックを通して。まだ Fabric には配置しないで。
```

🤖 **Copilot の動き**

- 仕様書を読み、Markdown セル（目的）→ 結果の保存関数 → 読み込み → 加工 → 保存と自己チェック の順で Notebook を書きます。
- `python3 scripts/lab.py notebook check nb_02_prepare_trips` で、配置前に約束（形式・カーネル・結果ファイル・
  ID やトークンの直書きがないこと・出力テーブル）をオフラインで確認し、`problems` があれば自分で直します。

### 加工ルール（仕様書から抜粋）

| 対象 | ルール |
|---|---|
| `ehail_fee` | 削除 |
| 除外する行 | `passenger_count` が null の行だけ。重複排除や追加の削除はしない |
| 乗車・降車日時 | タイムゾーンなしの値を UTC の timestamp として保存（Warehouse で日時を扱うため） |
| `pickup_date` / `pickup_hour` / `pickup_month` | 乗車日時の日付 / 0〜23 時 / `yyyy-MM` |
| `trip_duration_minutes` | 降車 − 乗車（分・小数 2 桁）。欠損や負の値は null |
| `fare_per_mile` | `fare_amount / trip_distance`（小数 2 桁）。距離が 0 以下なら null |
| `passenger_group` | 1 人 `single`／2 人以上 `group`／0 以下 `unknown` |
| `trip_id` | 欠損のない 8 列で並べた連番。再実行しても同じ値（Lab 07 の Ontology のキー） |

✅ **期待する結果**: `work/notebooks/nb_02_prepare_trips.ipynb` ができ、`notebook check` が `passed: true`。

> 💡 生成されたコードは受講者ごとに少しずつ違って構いません。正しいかどうかは、2-5 の教材提供の検証 Notebook が判定します。

---

## 2-3. 生成した Notebook を Fabric に配置して実行する

🤖 **Copilot に入力**

```text
生成した nb_02_prepare_trips を Fabric のアイテムとして配置して、taxi_lakehouse で実行して。
ローカルでのデータ加工や、一時的な Spark セッションだけで済ませないで。
失敗したら、エラーの原因を説明してから生成した Notebook を直して、成功するまでやり直して。
完了したら Notebook のリンク、実行状態、保存したテーブルと件数を教えて。答え合わせはまだしないで。
```

🤖 **Copilot の動き**

- `python3 scripts/lab.py notebook deploy-run nb_02_prepare_trips` を実行します。
  - `work/notebooks/nb_02_prepare_trips.ipynb` をもう一度チェックし、`taxi_lakehouse` を既定 Lakehouse にして配置
  - Fabric のジョブとして実行し、完了まで待機（Spark の起動を含め 3〜5 分程度）
  - Notebook が OneLake に書いた実行結果（`Files/lab_results/nb_02_prepare_trips.json`）を読み取り
- 失敗した場合は、`result.error`（Notebook が書いたエラー）を読んで原因を説明し、Notebook を直して再実行します。
  検証 Notebook や期待値を書き換えて通すことはしません。

✅ **期待する結果**

```text
Notebook: nb_02_prepare_trips（リンク）  実行状態: Completed
Source: 44,238 rows / 21 columns
Removed null passenger_count: 6,290 rows
Saved: green_tripdata_2026 — 37,948 rows / 27 columns
```

---

## 2-4. ポータルで Notebook を確認する

🌐 **ブラウザ**

1. Copilot が表示した Notebook のリンクを開きます。説明欄が「GitHub Copilot が生成」になっています。
2. セルの順に、読み込み → 加工ルール → 保存 の流れになっていることを確認します。**このコードは Copilot が書いたものです。**
3. 上部の **実行** › **最近の実行** で、今回のジョブが成功していることを確認します。

> 💡 Notebook はコードの「置き場所」と「実行記録」を兼ねたアイテムです。後から同じ処理を再実行したり、
> パイプラインやスケジュールで定期実行したりできます。

---

## 2-5. 検証 Notebook で答え合わせをする

🤖 **Copilot に入力**

```text
保存した green_tripdata_2026 が正しく加工できたか、検証 Notebook を Fabric で実行して確認して。
件数・列・欠損・派生列の計算・固定レコード・集計を期待値と比べて、不一致があれば差分を教えて。
確認だけで、データは変更しないで。
```

🤖 **Copilot の動き**

- `python3 scripts/lab.py notebook deploy-run nb_02_validate_trips` を実行します。
- 検証 Notebook（`notebooks/nb_02_validate_trips.ipynb`）は教材が用意した **採点役** です。読み取りだけを行い、すべての検証項目を `checks` として返します。
- 不一致がある場合は `passed: false` となり、Copilot はデータを修正せずに差分を報告します。
  原因が生成した加工ロジックにあれば、仕様書と照らして Notebook を直し、2-3 からやり直します。

✅ **期待する結果**: `passed: true`（23 項目すべて一致）

| 主な検証項目 | 期待値 |
|---|---|
| 行数 / 列数 | 37,948 / 27 |
| `trip_id` | 1〜37,948 で重複なし |
| 欠損・範囲外 | `passenger_count` の null 0 件、`pickup_hour` の範囲外 0 件、`pickup_month` は全件 `2026-04` |
| 合計金額 / 平均運賃 | $687,602.60 / $11.92 |
| 乗客区分 | `single` 6,257 件 / `group` 31,691 件 |
| 0 時台 | 1,615 件 / 平均運賃 $11.94 |

固定レコードは WHERE 条件（2026-04-01 0 時台、VendorID・乗車地・降車地）で特定し、各 1 件であることも確認します。

| trip_id | VendorID | 乗車地 → 降車地 | 乗客 | 距離 | 運賃 | 乗車時間（分） | 料金/マイル | 区分 |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 243 → 108 | 5 | 6.64 | 23.07 | 34.00 | 3.47 | group |
| 4 | 1 | 206 → 89 | 1 | 5.94 | 15.83 | 36.00 | 2.66 | single |

期待値の一覧は [`tests/expected/expected.json`](../tests/expected/expected.json) にあります。

---

## ✅ チェックポイント

- [ ] `taxi_lakehouse` の `Files/raw` にサンプルがある
- [ ] Copilot が生成した `work/notebooks/nb_02_prepare_trips.ipynb` が `notebook check` を通過
- [ ] Notebook `nb_02_prepare_trips` が Fabric にあり、実行が Completed
- [ ] Notebook `nb_02_validate_trips` の結果が `passed: true`

## 🧹 トラブルシュート

| 症状 | 🤖 Copilot に入力 |
|---|---|
| Notebook が NotStarted のまま | 「nb_02_prepare_trips の実行状態を確認して」。容量が混雑している場合は数分待つ |
| `notebook check` が失敗 | 「problems を 1 つずつ説明して、仕様書に合わせて Notebook を直して」 |
| 実行が Failed | 「nb_02_prepare_trips の失敗理由を result.error とセル出力から説明して、生成した Notebook を直して再実行して」 |
| 何度直しても通らない | 「模範解答と自分の Notebook の違いを説明して」→ 先に進む場合は「模範解答（--reference）で配置して実行して」 |
| 「すでに実行中」と表示される | 「実行中のジョブが終わったら結果だけを表示して」（重複実行はしない） |
| 検証で不一致 | 「不一致の項目について、期待値・実測値・考えられる原因を教えて。データは変更しないで」 |
| サインインの期限切れ | 「Azure CLI のサインイン状態を確認して、必要ならデバイスコード方式でサインインし直して」 |

> 🛟 API での実行がテナントの制限で失敗する場合は、🌐 Notebook を開いて **すべて実行** を選んでも同じ結果になります（Notebook は配置済み）。

次は **[Lab 03 — ショートカットとマスター整備](03-shortcut-dimensions.md)** です。
