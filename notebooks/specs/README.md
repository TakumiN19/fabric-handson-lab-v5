# Notebook 仕様書（GitHub Copilot が Notebook を生成するための設計書）

このフォルダーの仕様書を GitHub Copilot に渡すと、Copilot が **Notebook のコードを書き**、
`work/notebooks/` に保存します。保存した Notebook は `scripts/lab.py` が Fabric のアイテムとして配置・実行します。

```text
notebooks/specs/<名前>.md ──Copilot が生成──▶ work/notebooks/<名前>.ipynb（.sql）
                                                  │ python3 scripts/lab.py notebook check <名前>
                                                  │ python3 scripts/lab.py notebook deploy-run <名前>
                                                  ▼
                                    Fabric の Notebook アイテム ──▶ Files/lab_results/<名前>.json
                                                  │
                    教材提供の検証 Notebook（notebooks/*_validate_*）で答え合わせ
```

| 仕様書 | 生成する Notebook | Lab | 答え合わせ |
|---|---|---|---|
| [nb_02_prepare_trips.md](nb_02_prepare_trips.md) | `work/notebooks/nb_02_prepare_trips.ipynb` | 02 | `nb_02_validate_trips` |
| [nb_03_prepare_dimensions.md](nb_03_prepare_dimensions.md) | `work/notebooks/nb_03_prepare_dimensions.ipynb` | 03 | `nb_03_validate_dimensions` |
| [nb_04_build_warehouse.md](nb_04_build_warehouse.md) | `work/notebooks/nb_04_build_warehouse.sql` | 04 | `nb_04_validate_warehouse` |
| [nb_07_prepare_ontology.md](nb_07_prepare_ontology.md) | `work/notebooks/nb_07_prepare_ontology.ipynb` | 07 | Notebook 内の自己チェック |
| [nb_08_create_agents.md](nb_08_create_agents.md) | `work/notebooks/nb_08_create_agents.ipynb` | 08 | `agent-compare` |

> 生成がうまくいかない場合の模範解答は `reference/notebooks/` にあります（`--reference` で配置）。
> 受講中は、まず自分（Copilot）が生成したコードで動かすことを目指してください。

## すべての PySpark Notebook に共通の約束

`python3 scripts/lab.py notebook check <名前>` がこの約束をオフラインで確認し、満たさない Notebook は配置しません。

| 項目 | 約束 |
|---|---|
| 形式 | Jupyter Notebook（`nbformat` 4）。`metadata.kernelspec.name` と `metadata.kernel_info.name` は `synapse_pyspark`、`language_info.name` は `python` |
| セル | 先頭は目的を説明する Markdown セル。コードセルは `outputs: []`、`execution_count: null` |
| 既定 Lakehouse | `taxi_lakehouse`。配置時に `lab.py` が設定するので、Notebook に ID やパスを書かない（`Files/...` と表名だけで参照） |
| ID・資格情報 | GUID、トークン、パスワード、接続文字列を書かない |
| プレースホルダー | `lab.py` が配置時に置き換える次の 2 つだけを使える: `{{WORKSHOP_CONFIG_B64}}`（`config/workshop.json` の Base64）、`{{AGENT_CONFIG_B64}}`（`config/agents.json` の Base64） |
| パッケージ | `%pip install` は仕様書で許可された Notebook（nb_08）だけ。`!` のシェルコマンドは使わない |
| 書き込み | 仕様書の「出力」に書かれたテーブルと、結果ファイルだけ。元ファイル（`Files/raw` など）は変更しない |
| 再実行 | 何度実行しても同じ結果（`mode("overwrite")` と `option("overwriteSchema", "true")`、既存アイテムの再利用） |
| 時刻 | `spark.conf.set("spark.sql.session.timeZone", "UTC")` を最初に設定する |

### 結果ファイルの約束

`lab.py` は実行後に `Files/lab_results/<名前>.json` を読み、受講者に結果を表示します。次の関数をそのまま定義して使ってください。

```python
import json
from datetime import datetime, timezone

def save_result(name, payload):
    payload = {"notebook": name, "finishedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    notebookutils.fs.put(f"Files/lab_results/{name}.json", json.dumps(payload, ensure_ascii=False, default=str), True)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
```

| キー | 内容 |
|---|---|
| `passed` | 自己チェックがすべて成功なら `true`。1 つでも失敗、または例外なら `false` |
| `checks` | 自己チェックの一覧（`check`・`expected`・`actual`・`passed`） |
| `saved` | 保存したテーブルと件数（例: `{"green_tripdata_2026": 37948}`） |
| `error` | 例外時だけ。`"<例外クラス>: <メッセージ>"`（500 文字まで） |

**例外時も結果を書く**: 加工本体を `try` で囲み、`except` で `save_result(name, {"passed": False, "error": ...})` を書いてから
例外を再送出（`raise`）してください。こうすると、Notebook が失敗したときに Copilot が `result.error` を読んで
コードを直せます（`lab.py` は今回の実行より前の古い結果ファイルを表示しません）。

## Copilot が生成後に行うこと

1. 生成したセルの構成（Markdown の見出しと各コードセルの役割）を受講者に要約する。
2. `python3 scripts/lab.py notebook check <名前>` で約束を確認し、`problems` があれば直す。
3. `python3 scripts/lab.py notebook deploy-run <名前>` で Fabric に配置・実行する。
4. 失敗したら `result.error` とポータルのセル出力から原因を説明し、**生成した Notebook を直して** 2 から繰り返す。
   検証 Notebook・期待値（`tests/expected/`）・`scripts/lab.py` を書き換えて通そうとしない。
