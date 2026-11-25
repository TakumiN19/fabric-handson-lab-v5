# Lab 07 — Ontology

所要時間: 約 25 分　／　前提: [Lab 03](03-shortcut-dimensions.md) 完了（Lab 05・06 の後に実施すると比較しやすい）

このラボでは、Fabric IQ の **Ontology（新しい体験）** を API で作成し、同じタクシーデータを
「分析用の表とメジャー」ではなく「業務の実体（エンティティ）とその関係」として表現します。

## セマンティックモデルとの違い

| 観点 | セマンティックモデル（Lab 05） | Ontology（Lab 07） |
|---|---|---|
| 何を表すか | 分析用の表・関係・メジャー | 業務のエンティティ・プロパティ・関係・ルール |
| 主な単位 | `fact_trips` と `dim_*` | `Trip`・`Zone`・`Vendor` |
| 関係の表し方 | 列と列の結合（`PULocationID → LocationID`） | 意味のある名前（`Trip` **pickedUpIn** `Zone`） |
| 主な利用者 | Power BI、DAX、モデル接続の Data Agent | Ontology に接続した Data Agent、Ontology Agent、Foundry など |
| 計算の所有 | DAX メジャーとして定義 | データは元のソースに残す（Ontology はコピーを持たない） |

どちらが優れているかではなく、**同じデータの異なる表現**です。セマンティックモデルにも関係と意味はあります。
Ontology の価値は、業務用語と関係を名前付きで定義し、複数の AI エージェントやツールで**同じ定義を再利用できる**点です。

## このラボで作る Ontology

```text
             pickedUpIn
   Trip ─────────────────▶ Zone（LocationID, Borough, Zone）
 （trip_id）  droppedOffIn
     │   ─────────────────▶ Zone
     │      recordedBy
     └────────────────────▶ Vendor（VendorID, vendor_name）
```

- `Trip` は 1 トリップ 1 件（キー `trip_id`、Lab 02 で付与した再現可能な連番）。
- 乗車地と降車地は、**同じ `Zone` への役割の異なる 2 つの関係**です。
- バインド先は Lakehouse の Delta 表です（`onto_trips`・`onto_zones`・`onto_vendors`）。

> [!NOTE]
> 公式ドキュメントには「セマンティックモデルにバインドした Ontology は Data Agent で動作しない」という既知の問題があります。
> そのため、この Ontology はセマンティックモデルではなく、同じ加工済みデータを持つ Lakehouse の表にバインドします。

---

## 7-1. Ontology 用のテーブルを準備する Notebook を Copilot に書かせる

🤖 **Copilot に入力**

```text
notebooks/specs の nb_07_prepare_ontology の仕様を読んで、Ontology 用テーブルを作る PySpark Notebook を
work/notebooks/nb_07_prepare_ontology.ipynb に生成して。チェックを通して Fabric に配置・実行して。
Trip・Zone・Vendor の各テーブルの件数とキーの一意性、合計金額が変わっていないことを教えて。
失敗したら原因を説明して Notebook を直して。
```

🤖 **Copilot の動き**

- 仕様書 [`notebooks/specs/nb_07_prepare_ontology.md`](../notebooks/specs/nb_07_prepare_ontology.md) から、列名・型を Ontology の定義に合わせて生成します（自己チェック付き）。
- `python3 scripts/lab.py notebook check nb_07_prepare_ontology` で約束を確認してから、`python3 scripts/lab.py notebook deploy-run nb_07_prepare_ontology` で配置・実行します。
- 失敗したら `result.error` とセル出力から原因を説明し、生成した Notebook を直して再実行します（模範解答は `--reference`）。

✅ **期待する結果**: `passed: true`（`onto_trips` 37,948 件 / `onto_zones` 265 件 / `onto_vendors` 2 件、キー重複 0、合計金額不変）

---

## 7-2. Ontology の定義を確認してから作成する

🤖 **Copilot に入力**

```text
Lab 07 の Ontology onto_taxi の定義を生成して、エンティティ・プロパティ・関係を図か表で説明して。
問題がなければ REST API で自分のワークスペースに作成して、定義を読み戻して作成できたことを確認して。
```

🤖 **Copilot の動き**

1. `python3 scripts/lab.py ontology` で新しい体験の定義（TMDL）を生成し、`.lab/ontology/` に保存して説明します。
   - `tables/`（バインド先の表）、`entities/`（Trip・Zone・Vendor）、`relationships.tmdl`、`entityRelationships.tmdl`
   - 降車地の関係は表どうしの結合が 2 本目になるため、非アクティブな関係として定義し、エンティティの関係に名前を付けます。
2. `python3 scripts/lab.py ontology --apply` で作成（既にあれば更新）し、`getDefinition` で読み戻します。

✅ **期待する結果**

```json
{
  "ontology": "onto_taxi",
  "returnedParts": [".platform", "database.tmdl", "entities/Trip.tmdl", "entities/Vendor.tmdl", "entities/Zone.tmdl",
                    "entityRelationships.tmdl", "expressions.tmdl", "model.tmdl", "namespaces/default.tmdl", "relationships.tmdl", "..."]
}
```

🌐 **ブラウザ**: Copilot が表示したリンクから `onto_taxi` を開き、エンティティと関係の図を確認します。

> 🛟 **Gate G5**: 作成が API で拒否された場合は、エラー内容を Copilot に要約させて講師に共有してください。

---

## 7-3. Ontology に質問してみる

🤖 **Copilot に入力**

```text
onto_taxi に「Manhattan で乗車して Brooklyn で降車したトリップは何件？」と質問して、
回答と、使われたエンティティ・関係を教えて。期待値と比べて。
```

🤖 **Copilot の動き**: `fabric-skills` の `ontology-cli` スキルで、新しい体験の Ontology Agent（`ask_ontology`）に問い合わせます。

✅ **期待する結果**: **2,340 件**。回答に `Trip`・`Zone` と、`pickedUpIn`／`droppedOffIn` の 2 つの関係が使われていること。

> Ontology の初回の問い合わせは準備に数分かかることがあります。「データがない」と返った場合は数分待って再質問します。

---

## ✅ チェックポイント

- [ ] Copilot が生成した `nb_07_prepare_ontology` が `passed: true`
- [ ] `onto_taxi` が作成され、定義を読み戻せた
- [ ] Ontology への質問で 2,340 件が返った

## 🧹 トラブルシュート

| 症状 | 🤖 Copilot に入力 |
|---|---|
| Ontology の作成が拒否される | 「エラー内容を要約して。テナント設定とバインド先のテーブルを確認して」→ 講師に連絡 |
| 質問に「データがない」 | 数分待ってから同じ質問を再送 |
| 乗車地と降車地を取り違える | 「pickedUpIn と droppedOffIn を区別して答え直して」。定義の説明文も確認 |

次は **[Lab 08 — Data Agent の比較](08-data-agents.md)** です。
