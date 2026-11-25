# 用語集（Glossary）

このハンズオンに登場する用語を、**定義**と **本ハンズオンでの使われ方** で整理します。

## Fabric の基本

| 用語 | 定義 | 本ハンズオンでの使われ方 |
|---|---|---|
| ワークスペース | Fabric のアイテムをまとめる作業場所。権限の単位 | `student<番号>`。全 Lab の成果物をここに作る |
| 容量（Capacity） | Fabric の計算資源。ワークスペースを割り当てて使う | 講師が用意した有料 F 容量。Data Agent は試用容量では使えない |
| OneLake | Fabric 全体で 1 つのデータレイク。各アイテムのデータは Delta/Parquet で保存 | Lakehouse・Warehouse のデータの実体 |
| Lakehouse | ファイル（`Files`）とテーブル（`Tables`）を扱うアイテム。SQL 分析エンドポイントが付く | `taxi_lakehouse`（Lab 02〜03・07） |
| Warehouse | T-SQL で読み書きできるデータウェアハウス | `taxi_warehouse`（Lab 04） |
| SQL 分析エンドポイント | Lakehouse のテーブルを T-SQL で読み取り専用に参照する入口 | Lab 04 で Warehouse から 3 部構成名で参照 |
| Delta テーブル | Parquet にトランザクションログを加えた表形式 | 加工結果の保存形式 |
| ショートカット | データをコピーせず外部ストレージを OneLake に見せる仕組み | Lab 03 で共有 ADLS Gen2 の CSV を参照 |
| 接続（Connection） | 外部データへの到達情報と資格情報をまとめた Fabric の設定 | 講師が作成・共有した ADLS 接続 |

## データ加工

| 用語 | 定義 | 本ハンズオンでの使われ方 |
|---|---|---|
| Notebook | コード・説明・実行結果をまとめた Fabric アイテム。ジョブとして実行できる | Lab 02〜04・07・08 の加工・検証・Agent 作成 |
| Notebook 仕様書 | 入力・出力・加工ルール・結果の約束だけを書いた設計書。GitHub Copilot がこれを読んで Notebook のコードを書く | `notebooks/specs/` → `work/notebooks/` |
| 検証 Notebook | 教材が用意した読み取り専用の採点役。生成した Notebook の結果を期待値と照合する | `nb_0x_validate_*` |
| T-SQL Notebook | Warehouse に接続して T-SQL を実行する Notebook | `nb_04_build_warehouse`（Copilot が生成） |
| 既定の Lakehouse | Notebook が `Tables`・`Files` の相対パスで参照する Lakehouse | `scripts/lab.py` が `taxi_lakehouse` を設定 |
| メダリオンアーキテクチャ | 生データ（Bronze）→ 整備（Silver）→ 分析用（Gold）と段階的に整える設計 | Lab 02〜05 の流れ |
| CTAS | `CREATE TABLE AS SELECT`。クエリ結果から表を作る | Lab 04 の Warehouse の表 |
| スター スキーマ | ファクト（出来事）とディメンション（属性）に分ける設計 | `fact_trips` と `dim_*` |
| ロールプレイング ディメンション | 同じマスターを異なる役割で使うこと | 乗車地・降車地のゾーン |
| 固定レコード検証 | 条件で特定したレコードを期待値と照合する検証 | `trip_id` 1 と 4 |

## 分析とセマンティック

| 用語 | 定義 | 本ハンズオンでの使われ方 |
|---|---|---|
| セマンティックモデル | 表・関係・メジャーを定義した Power BI の分析モデル | `sm_taxi`（Lab 05） |
| Direct Lake | OneLake の Delta を直接読む接続モード。コピーや資格情報の設定が不要 | `sm_taxi` の接続モード |
| メジャー | DAX で書いた集計の定義 | `Trips`、`Total Amount` など |
| DAX | セマンティックモデルのクエリ・計算言語 | `model-check`、ダッシュボード |
| TMDL | セマンティックモデルや Ontology の定義を書くテキスト形式 | `lab.py` が生成し、API で配置 |
| Ontology | 業務のエンティティ・プロパティ・関係・ルールを定義し、データにバインドする Fabric IQ のアイテム | `onto_taxi`（Lab 07） |
| エンティティ型 | 業務の概念（例: Trip、Zone）の定義 | `Trip`・`Zone`・`Vendor` |
| バインディング | Ontology の定義を実データの列に対応付けること | Lakehouse の `onto_*` 表 |

## AI とアプリ

| 用語 | 定義 | 本ハンズオンでの使われ方 |
|---|---|---|
| Data Agent | 接続したデータに自然言語で質問できる Fabric のアイテム | `taxi_metrics_agent` と `taxi_ontology_agent`（Lab 08） |
| MCP | AI が外部のツールやデータに接続するための標準プロトコル | 公開済み Data Agent に質問するときの接続方式 |
| Fabric Apps / Rayfin | Fabric 上でホストするアプリとその開発 CLI・SDK | `taxi-insights`（Lab 09） |
| Rayfin Functions | アプリのサーバー側で動く関数 | Data Agent の MCP をトークンを隠したまま呼ぶ |
| デバイスコード認証 | 表示されたコードを別のブラウザで入力して認証する方式 | Codespaces での Copilot・Azure CLI のサインイン |
| Microsoft Foundry | 独自の AI エージェントを開発・運用する Azure のプラットフォーム | 任意 B で Ontology を知識源として再利用 |

## 公式ドキュメント

- [Microsoft Fabric のドキュメント](https://learn.microsoft.com/fabric/)
- [Ontology の概要](https://learn.microsoft.com/fabric/iq/ontology/overview)
- [Data Agent の MCP サーバー](https://learn.microsoft.com/fabric/data-science/data-agent-mcp-server)
- [Fabric Apps の CLI リファレンス](https://learn.microsoft.com/fabric/apps/cli-reference)
