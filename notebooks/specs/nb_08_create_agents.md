# 仕様: nb_08_create_agents（2 つの Data Agent を作成・公開）

共通の約束は [README.md](README.md) を参照。生成先: `work/notebooks/nb_08_create_agents.ipynb`

## 目的

同じ業務定義（指示）で、データソースだけが異なる 2 つの Data Agent を作成・公開する。何度実行しても同じ構成になること。

| 設定キー | Agent | データソース |
|---|---|---|
| `metricsAgent` | `taxi_metrics_agent` | セマンティックモデル `sm_taxi` |
| `ontologyAgent` | `taxi_ontology_agent` | Ontology `onto_taxi` |

## 入力

- 設定: `config/agents.json`。Notebook では **`{{AGENT_CONFIG_B64}}` を Base64 デコードした JSON** として読む
  （`lab.py` が配置時に埋め込む。Agent 名・指示・説明文を Notebook に直書きしない）。
  各 Agent の設定は `name`, `source`（`type` と `item`）, `description`, `instructions`（文字列の配列）を持つ。
- パッケージ: 最初のコードセルで `%pip install -q "fabric-data-agent-sdk==0.1.36a0"`（この Notebook だけ許可。バージョン固定）

## 使う SDK（`from fabric.dataagent.client import create_data_agent`）

| 処理 | メソッド |
|---|---|
| Agent の作成（既存なら同じ名前のものを返す） | `create_data_agent(name)` |
| 指示の設定 | `agent.update_settings(ai_instructions="\n".join(instructions))` |
| データソース一覧 / 追加 | `agent.list_datasources()` / `agent.add_staging_datasource(item, type=source["type"])` |
| 名前の確認 | `datasource.get_configuration().get("displayName")` |
| 要素（表・列・メジャー）の取得 / 選択 | `datasource.get_elements(root_id=..., continuation_token=...)`（`value` と `continuationToken` を返す） / `datasource.update_element(id, is_selected=True)` |
| データソースの説明 | `datasource.update_configuration(description=...)` |
| Ontology 一覧 / 追加 / 全エンティティ選択 | `agent.list_ontologies()` / `agent.add_staging_ontology(item)` / `ontology.select_entities()` |
| 公開（説明文は MCP ツールの説明になる） | `agent.publish_staging(description=config["description"])` |

## 処理ルール

| ルール | 内容 |
|---|---|
| 冪等 | データソース・Ontology は、同じ `displayName` がすでに付いていれば追加しない |
| 全要素の選択 | `get_elements` を `continuationToken` がなくなるまでページングし、子（`hasChildren` / `children`）を再帰的にたどって、`isSelected` が `False` の要素を選択する |
| 反映待ち | 追加直後のデータソースは一覧にすぐ出ないことがある。一覧で見つかるまで **10 秒間隔で最大 6 回** 再取得し、出なければ例外にする（`list[0]` をいきなり参照しない） |
| 失敗の分離 | Agent ごとに `try` / `except` で囲み、片方が失敗しても、もう片方の作成・公開は続ける |

## 結果

`save_result("nb_08_create_agents", ...)` に次を含める。

- `agents`: Agent 名ごとに `{"source": ..., "published": true/false, "error": "<例外クラス>: <メッセージ>"（失敗時のみ、500 文字まで）}`
- `passed`: 2 つとも公開できたら `true`

> 回答の比較は `python3 scripts/lab.py agent-compare` で行う（この Notebook では質問しない）。
