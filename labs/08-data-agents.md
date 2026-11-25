# Lab 08 — Data Agent の比較（セマンティックモデル vs Ontology）

所要時間: 約 30 分　／　前提: [Lab 05](05-semantic-model.md) と [Lab 07](07-ontology.md) 完了

このラボでは、**同じ業務定義（指示）**で、**接続先だけが異なる** 2 つの Data Agent を、Copilot が書いた Notebook で作成・公開し、
同じ質問を送って回答を比べます。

| Agent | 接続先 | 質問の解き方 |
|---|---|---|
| `taxi_metrics_agent` | セマンティックモデル `sm_taxi` | DAX でメジャーと表を集計する |
| `taxi_ontology_agent` | Ontology `onto_taxi` | エンティティと名前付きの関係をたどる（GQL など） |

2 つのデータソースを 1 つの Agent に入れると、どちらを使って答えたか分からなくなるため、Agent を分けて比較します。
指示は [`config/agents.json`](../config/agents.json) で、売上・乗車地・降車地の定義を両方そろえています。

---

## 8-1. Data Agent 作成 Notebook を Copilot に書かせて実行する

🤖 **Copilot に入力**

```text
notebooks/specs の nb_08_create_agents の仕様を読んで、fabric-data-agent-sdk で Data Agent を作る Notebook を
work/notebooks/nb_08_create_agents.ipynb に生成して。チェックを通して Fabric に配置・実行して。
sm_taxi に接続する taxi_metrics_agent と、onto_taxi に接続する taxi_ontology_agent を作成して公開して。
指示は教材の設定ファイルのものを使って、完了したら作成された Agent と接続先、Agent ごとの成否を教えて。
```

🤖 **Copilot の動き**

- 仕様書 [`notebooks/specs/nb_08_create_agents.md`](../notebooks/specs/nb_08_create_agents.md) から Notebook を生成します。
  - Agent 名・指示は書かず、`{{AGENT_CONFIG_B64}}`（配置時に `config/agents.json` が埋め込まれる）から読む
  - 追加直後のデータソースが一覧に出るまで待つ・Agent ごとに失敗を分ける、といった堅牢化も仕様書どおりに入れる
- `python3 scripts/lab.py notebook check nb_08_create_agents` で約束を確認してから、`python3 scripts/lab.py notebook deploy-run nb_08_create_agents` で配置・実行します。
- 失敗したら `result.error` とセル出力から原因を説明し、生成した Notebook を直して再実行します（模範解答は `--reference`）。
- Notebook 内では `fabric-data-agent-sdk` を使い、次を順に実行します（何度実行しても同じ構成になる）

    | 処理 | SDK のメソッド |
    |---|---|
    | Agent の作成（既存なら再利用） | `create_data_agent` |
    | 指示の設定 | `update_settings(ai_instructions=...)` |
    | セマンティックモデルの追加・全要素の選択 | `add_staging_datasource` / `update_element` |
    | Ontology の追加・全エンティティの選択 | `add_staging_ontology` / `select_entities` |
    | 公開（説明文は MCP ツールの説明になる） | `publish_staging` |

✅ **期待する結果**: `passed: true`、`agents` の 2 つの Agent が `published: true`。
片方だけ失敗した場合は、`agents.<名前>.error` に理由が入ります（もう片方は作成・公開されます）。

🌐 **ブラウザ**（任意）: ワークスペースで 2 つの Data Agent を開き、データソースと指示を確認します。

> 🛟 **Gate G6**: Notebook 内のパッケージ導入が禁止されている環境では失敗します。その場合は講師の案内
> （[講師ガイド 03](../instructor/03-app-and-agent-auth.md#data-agentlab-08)）に従ってください。

---

## 8-2. 同じ質問を 2 つの Agent に送る

🤖 **Copilot に入力**

```text
2 つの Data Agent に教材の比較用の質問を同じ順番で送って、回答を表にまとめて。
期待値と一致しているか、どのデータソース・業務用語・関係を使って答えたかを、回答から読み取れる範囲で説明して。
実行したクエリなど取得できない情報は、推測せず「取得できない」と書いて。
```

🤖 **Copilot の動き**

- `python3 scripts/lab.py agent-compare` を実行します。
  - 公開済み Agent の MCP エンドポイント（`/v1/mcp/workspaces/{ws}/dataagents/{id}/agent`）に、あなたの Azure CLI のサインインで問い合わせ
  - 結果を `.lab/agent-comparison.json` に保存
- 回答を期待値と照合して表にします。

📋 **比較用の質問**（[`tests/expected/agent_questions.json`](../tests/expected/agent_questions.json)）

| ID | 質問 | 期待値 | 見どころ |
|---|---|---|---|
| Q1 | 総トリップ数と売上合計は？ | 37,948 件 / $687,602.60 | 数値の正確さ |
| Q2 | Manhattan で乗車し Brooklyn で降車したトリップは？ | 2,340 件 / $42,944.85 | 乗車地と降車地の区別 |
| Q3 | Q2 をベンダー別に | Creative Mobile 1,166 / VeriFone 1,174 | 3 つのエンティティをまたぐ関係 |
| Q4 | 「売上」と「乗車地」は何を指す？ | `total_amount`（USD）／`PULocationID` のゾーン | 業務用語の定義 |
| Q5 | 料金コードが JFK のトリップは？ | モデル 4,823 件／Ontology は「データにない」 | 定義に含まれる範囲の違い |
| Q6 | 雨の日のトリップは？ | どちらも「データにない」 | 推測せずに答えられないと言えるか |

---

## 8-3. 違いを考察する

結果の表をもとに、次の観点で話し合ってみましょう（正解は 1 つではありません）。

| 観点 | 確認すること |
|---|---|
| 数値 | 両 Agent とも期待値と一致したか。一致しない場合、どの定義の解釈が違ったか |
| 関係 | 乗車地と降車地を取り違えなかったか。関係の名前が回答や推論に現れたか |
| 用語 | 「売上」の定義を説明できたか。指示に書いた定義と一致したか |
| 範囲外 | データにない情報を推測で答えず、「分からない」と言えたか |
| 再利用 | 同じ定義を別のツール（Foundry など）で使うとき、どちらが移しやすいか |

> [!IMPORTANT]
> 回答の文面が違うだけで「良い・悪い」は判断しません。期待値・使われたエンティティ・参照先で評価してください。
> 生成 AI の回答は実行ごとに変わることがあります。気になる質問は 2〜3 回送って傾向を見ます。

1 件だけ質問したい場合は、次のように指示できます。

🤖 **Copilot に入力**

```text
taxi_ontology_agent に「Brooklyn で降車したトリップが最も多い乗車ゾーン トップ 3 は？」と質問して、回答を見せて。
```

---

## ✅ チェックポイント

- [ ] Copilot が生成した `nb_08_create_agents` で 2 つの Agent が作成・公開された
- [ ] `agent-compare` で両 Agent から回答が得られた
- [ ] Q1〜Q6 の回答を期待値と比べ、違いを説明できた

## 🧹 トラブルシュート

| 症状 | 🤖 Copilot に入力 |
|---|---|
| `IndexError` / データソースが見つからない | 追加直後の反映待ちが不足。「仕様書の反映待ちのルールどおりに Notebook を直して再実行して」 |
| `HTTP 403` / `404`（MCP） | 「Agent が公開済みか確認して。公開されていなければ nb_08_create_agents を再実行して」 |
| 回答が「データがない」 | 公開直後は数分かかることがある。数分待って再質問 |
| Copilot のテナント設定エラー | 講師に連絡（テナント設定の反映に最大 1 時間） |
| 数値が大きくずれる | 「taxi_metrics_agent の回答に使われたメジャーを確認して、model-check の結果と比べて」 |

次は **[Lab 09 — Fabric App（Rayfin）](09-rayfin-app.md)** です。
発展として、[任意 B](optional-b-foundry-ontology.md) で同じ Ontology を Microsoft Foundry の Agent から再利用できます。
