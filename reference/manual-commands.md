# Copilot が実行するコマンド一覧（参考）

本文では、受講者は日本語の作業指示だけを入力します。このページは、裏側で Copilot が実行するコマンドを
確認したい人や、講師が切り分けをするときのための参考です。**受講者が手で入力する必要はありません。**

すべてのコマンドは、Azure CLI のサインインと参加者設定（`.github/student.local.md`）が一致していることを最初に確認し、
一致しない場合は何も変更せずに止まります。トークンは表示・保存しません。

## Lab ごとのコマンド

| Lab | コマンド | 内容 |
|---|---|---|
| 00 | `python3 scripts/doctor.py` | 環境の読み取り専用診断 |
| 01 | `az login --tenant <tenantId> --allow-no-subscriptions --use-device-code` | Azure CLI のサインイン |
| 01 | `python3 scripts/lab.py check --save` | アカウント・テナント・ワークスペースの照合、Workspace ID の保存 |
| 02 | `python3 scripts/lab.py ensure-lakehouse` | Lakehouse の作成（既存なら再利用） |
| 02 | `python3 scripts/lab.py upload-sample` | サンプルを OneLake にアップロードし、サイズを照合 |
| 02〜08 | `python3 scripts/lab.py notebook check <名前>` | Copilot が生成した `work/notebooks/` の Notebook を配置前にオフラインで確認 |
| 02〜08 | `python3 scripts/lab.py notebook deploy-run <名前> --reference` | 生成がうまくいかない場合に模範解答（`reference/notebooks/`）で配置・実行 |
| 02 | `python3 scripts/lab.py notebook deploy-run nb_02_prepare_trips` | Copilot が生成した加工 Notebook の配置・実行 |
| 02 | `python3 scripts/lab.py notebook deploy-run nb_02_validate_trips` | 検証 Notebook の配置・実行 |
| 03 | `python3 scripts/lab.py shortcut` | 共有接続でショートカットを作成 |
| 03 | `python3 scripts/lab.py notebook deploy-run nb_03_prepare_dimensions` | マスター整備（生成した Notebook） |
| 03 | `python3 scripts/lab.py notebook deploy-run nb_03_validate_dimensions` | マスター・結合の検証 |
| 04 | `python3 scripts/lab.py ensure-warehouse` | Warehouse の作成（既存なら再利用） |
| 04 | `python3 scripts/lab.py refresh-sql-endpoint` | SQL 分析エンドポイントのメタデータ更新 |
| 04 | `python3 scripts/lab.py notebook deploy-run nb_04_build_warehouse` | 生成した T-SQL Notebook の配置・実行 |
| 04 | `python3 scripts/lab.py notebook deploy-run nb_04_validate_warehouse` | Warehouse の検証 |
| 05 | `python3 scripts/lab.py semantic-model [--apply]` | モデル定義の生成（`--apply` で作成・更新・更新処理） |
| 05 | `python3 scripts/lab.py model-check` | DAX で主要な数値を期待値と照合 |
| 07 | `python3 scripts/lab.py notebook deploy-run nb_07_prepare_ontology` | Ontology 用テーブルの準備（生成した Notebook） |
| 07 | `python3 scripts/lab.py ontology [--apply]` | Ontology 定義の生成（`--apply` で作成・更新・読み戻し） |
| 08 | `python3 scripts/lab.py notebook deploy-run nb_08_create_agents` | Data Agent 2 つの作成・公開（生成した Notebook） |
| 08 | `python3 scripts/lab.py agent-compare` | 2 つの Agent に同じ質問を送り比較 |
| 08 | `python3 scripts/lab.py agent-ask <agent> "<質問>"` | 1 つの Agent に質問 |
| 09 | `python3 ../../scripts/rayfin_az.py <rayfin のサブコマンド>` | Azure CLI のサインインで Rayfin を実行 |

Notebook には次の操作もあります。

| コマンド | 内容 |
|---|---|
| `python3 scripts/lab.py notebook deploy <名前>` | 配置のみ |
| `python3 scripts/lab.py notebook run <名前>` | 実行のみ（実行中のジョブがあれば重複実行しない） |
| `python3 scripts/lab.py notebook result <名前>` | 最後の実行結果（`Files/lab_results/<名前>.json`）を表示 |

## Copilot CLI のスラッシュコマンド（参考）

本文では使いませんが、Copilot の中で次のコマンドも使えます。

| コマンド | 内容 |
|---|---|
| `/plugin list` | 導入済みのプラグイン |
| `/mcp` | MCP サーバーの状態 |
| `/instructions` | 読み込まれている指示ファイル |
| `/model` | 使用するモデルの選択 |
| `/exit` | Copilot の終了 |

## 生成物の確認

`semantic-model`・`ontology` は、API に送る定義を `.lab/semantic-model/`・`.lab/ontology/` に TMDL として保存します。
内容を確認してから `--apply` を実行できます。`.lab/` は Git の管理対象外です。
