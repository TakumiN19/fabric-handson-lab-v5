# 講師ガイド 00 — 全体像と準備スケジュール

このフォルダーは、開催前の準備から当日運用、片付けまでを講師・テナント管理者向けにまとめたものです。
受講者の手順（`labs/`）は、ここに書いた準備が完了している前提で書かれています。

## 役割分担

| 役割 | 主な作業 | 必要な権限 |
|---|---|---|
| テナント管理者 | Fabric テナント設定、ユーザー・グループ、ライセンス | Fabric 管理者、Entra のユーザー管理 |
| 容量管理者 | 有料 Fabric 容量の稼働・割り当て | 容量管理者 |
| Azure 管理者 | 共有 ADLS Gen2、サービスプリンシパル | サブスクリプションの共同作成者以上 |
| 講師 | 受講者ワークスペース、共有接続、リハーサル、当日運用 | 各ワークスペースの Admin |
| 受講者 | 自分のワークスペースでの作業 | 自分のワークスペースの Member 以上 |

## 準備スケジュール

| 時期 | 作業 | 手順 |
|---|---|---|
| 2 週間前 | 容量・テナント設定・ユーザー・ライセンスを確定 | [01](01-tenant-capacity-and-identities.md) |
| 1 週間前 | 共有 ADLS・共有接続・受講者ワークスペースを作成 | [01](01-tenant-capacity-and-identities.md)、[02](02-shared-data-and-connections.md) |
| 1 週間前 | アプリと Data Agent の権限・同意を確認 | [03](03-app-and-agent-auth.md) |
| 3 日前 | **技術 Gate を含む通しリハーサル**（テスト受講者 2 名） | [04](04-rehearsal-and-runbook.md) |
| 前日 | 容量の稼働、受講者アカウントのサインイン可否、配布物 | [04](04-rehearsal-and-runbook.md) |
| 当日 | 受付・進行・障害対応 | [04](04-rehearsal-and-runbook.md) |
| 終了後 | 費用停止とリソース削除 | [05](05-cleanup.md) |

## 技術 Gate（リハーサルで必ず確認）

以下は公式ドキュメントと SDK のソースで仕様を確認済みですが、**対象テナントでの成立は未確認**です。
リハーサルで通常の受講者アカウントを使って確認し、結果を記録してください。
失敗した Gate は、表の「代替」を当日の手順として受講者に案内します。

| Gate | 確認内容 | 確認方法 | 代替（失敗時） |
|---|---|---|---|
| G1 認証 | Codespaces で Copilot・Azure CLI がデバイスコードでサインインできる | Lab 00〜01 | [reference/auth-troubleshooting.md](../reference/auth-troubleshooting.md) |
| G2 Notebook 実行 | API で配置した PySpark Notebook が受講者の権限で実行できる | Lab 02 | ポータルで Notebook を開いて「すべて実行」 |
| G2b Notebook 生成 | 受講者の Copilot が `notebooks/specs/` から生成した Notebook が `notebook check` を通り、検証 Notebook で `passed: true` | Lab 02〜04・07・08 | `notebook deploy-run <名前> --reference`（模範解答）で進め、差分を後で解説 |
| G3 T-SQL Notebook | `nb_04_build_warehouse` が API 実行で完了する | Lab 04 | ポータルで開いて「すべて実行」（生成した Notebook は配置済み） |
| G4 Direct Lake | `sm_taxi` が Warehouse の OneLake データで表示できる | Lab 05〜06 | ポータルでモデルの「更新」 |
| G5 Ontology | `onto_taxi` が API で作成され、定義を読み戻せる | Lab 07 | 講師が作成済み定義を確認し、エラーを `instructor/` に記録 |
| G6 Data Agent | `nb_08_create_agents` で 2 Agent が作成・公開される | Lab 08 | [03](03-app-and-agent-auth.md) のポータル手順 |
| G7 Agent の MCP | `agent-compare` で両 Agent から回答が返る | Lab 08 | ポータルの Agent チャットで同じ質問 |
| G8 Rayfin | `rayfin_az.py up` でデプロイでき、別ブラウザの受講者でダッシュボード・入力・チャットが動く | Lab 09 | [03](03-app-and-agent-auth.md) の確認項目で切り分け |

> [!IMPORTANT]
> Gate を管理者アカウントで通しただけでは不十分です。受講者と同じ権限のテストアカウントで確認してください。
> 管理者で成功し受講者で失敗する場合、多くは権限・テナント設定の対象グループが原因です。

## 配布物

| 配布物 | 受講者に渡す方法 |
|---|---|
| student 番号とパスワード | 個別に配布（メール・チャットに平文で残さない） |
| リポジトリ URL | `https://github.com/TakumiN19/fabric-handson-lab-v4` |
| 開催設定 | 既定は `config/workshop.json`。別テナントで開催する場合は `config/workshop.local.json` を配布 |
| 講師への連絡方法 | Teams など |

`config/workshop.json` に書けるのは秘密でない値だけです。パスワード、クライアントシークレット、
トークンを設定ファイル・リポジトリ・チャットに記載しないでください。
