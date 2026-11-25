# Microsoft Fabric × GitHub Copilot CLI ハンズオン Lab V4

GitHub Copilot CLI に日本語で指示し、Microsoft Fabric のデータ基盤から Ontology、Data Agent、
Fabric App（Rayfin）までを構築するハンズオンです。

V3 からの主な変更点は次のとおりです。

| 変更点 | 内容 |
|---|---|
| 講師準備を独立 | [`instructor/`](instructor/00-overview.md) に準備・リハーサル・当日運用・片付けを手順化 |
| 入力先を明示 | 各手順に「🤖 Copilot に入力」「⌨️ ターミナル」「🌐 ブラウザ」のどれか 1 つだけを表示 |
| Notebook も Copilot が書く | 加工・Warehouse 作成・Agent 作成の Notebook は、仕様書から GitHub Copilot がコードを生成し、Fabric の Notebook アイテムとして配置・実行（答え合わせは教材提供の検証 Notebook） |
| Ontology を追加 | セマンティックモデルとの違いを学び、Ontology（新しい体験）を API で作成 |
| Data Agent を比較 | 同じ指示で接続先だけ異なる 2 つの Agent を Notebook で作り、同じ質問で比較 |
| Rayfin の認証を修正 | Codespaces でも止まらない認証ラッパーと、プロキシ不要の Data Agent チャット |
| 期待値を一本化 | [`tests/expected/expected.json`](tests/expected/expected.json) に全 Lab の検証値を集約 |

## 🧭 全体像

```text
Lab 00 準備 → 01 サインイン → 02 Notebook で加工 → 03 ショートカット → 04 Warehouse
      → 05 セマンティックモデル → 06 Power BI → 07 Ontology → 08 Data Agent 比較 → 09 Fabric App
                                                           └─ 任意 B: Foundry から Ontology を再利用
```

| # | ラボ | Fabric に残る成果物 | 目安 |
|---|---|---|---|
| — | [講師の事前準備](instructor/00-overview.md) | 容量・権限・共有接続・リハーサル結果 | 開催前 |
| 00 | [環境の準備と参加者登録](labs/00-setup.md) | （ローカル設定） | 15 分 |
| 01 | [サインインと接続確認](labs/01-sign-in.md) | — | 15 分 |
| 02 | [Notebook で取り込み・加工・検証](labs/02-notebook-ingest-transform.md) | Lakehouse、Copilot が生成した Notebook、検証 Notebook、Delta 表 | 40 分 |
| 03 | [ショートカットとマスター整備](labs/03-shortcut-dimensions.md) | Shortcut、Copilot が生成した Notebook、検証 Notebook、マスター 5 表 | 20 分 |
| 04 | [Warehouse（T-SQL Notebook）](labs/04-warehouse-tsql-notebook.md) | Warehouse、T-SQL Notebook、検証 Notebook | 25 分 |
| 05 | [セマンティックモデル](labs/05-semantic-model.md) | Direct Lake モデル `sm_taxi` | 20 分 |
| 06 | [Power BI レポート](labs/06-powerbi-report.md) | レポート `rpt_taxi_analysis` | 20 分 |
| 07 | [Ontology](labs/07-ontology.md) | Ontology `onto_taxi`、準備 Notebook | 25 分 |
| 08 | [Data Agent の比較](labs/08-data-agents.md) | Data Agent 2 つ、作成 Notebook | 30 分 |
| 09 | [Fabric App（Rayfin）](labs/09-rayfin-app.md) | Fabric App `taxi-insights` | 35 分 |
| 任意 A | [レポート／アプリの UX 改善](labs/optional-a-ux.md) | 改善版のレポート・アプリ | 20〜30 分 |
| 任意 B | [Microsoft Foundry から Ontology を再利用](labs/optional-b-foundry-ontology.md) | Foundry Agent（別ワークショップ） | 30〜60 分 |
| 📖 | [用語集](labs/glossary.md) | — | — |

所要時間は暫定です（休憩・待ち時間を除き約 4 時間）。リハーサル結果で更新してください。

## 🚀 はじめかた（受講者）

1. 講師から student 番号とパスワードを受け取ります。
2. 下のボタンから Codespace を作成し、セットアップ完了まで待ちます（推奨）。

   [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/TakumiN19/fabric-handson-lab-v4?quickstart=1)

3. [Lab 00](labs/00-setup.md) から順に進めます。

ローカル PC で進める場合は [reference/local-setup.md](reference/local-setup.md) を参照してください。

## 📖 手順書の読み方

各ステップは、入力先を 1 つに限定して記載しています。

| 表示 | 入力先 | 例 |
|---|---|---|
| 🤖 **Copilot に入力** | 起動済みの Copilot CLI のプロンプト | 日本語の作業指示 |
| ⌨️ **ターミナル** | VS Code のターミナル（Copilot を起動する前） | `copilot` の起動、初回ログイン |
| 🌐 **ブラウザ** | ブラウザ | サインイン、コード入力、作成物の確認 |
| 🙋 **あなたの操作** | 本人しかできない操作 | パスワード・MFA、アカウント選択、承認 |

本文のプロンプトはそのまま貼り付けて使えます。student 番号の入力は Lab 00 の 1 回だけです。
Copilot が裏側で実行するコマンドは [reference/manual-commands.md](reference/manual-commands.md) にまとめています。

## 🧰 必要なもの

| 必要なもの | 用意する人 | 備考 |
|---|---|---|
| GitHub アカウントと Copilot ライセンス | 受講者（または講師が付与） | 組織で Copilot CLI が許可されていること |
| 配布された Fabric アカウント | 講師 | 有料 Fabric 容量上の個人ワークスペース |
| ブラウザ（Edge / Chrome） | 受講者 | Codespaces 利用時もサインインに使用 |
| Power BI Pro / PPU 相当 | 講師または受講者のトライアル | Lab 05・06 |

Codespace では次のツールが検証済みバージョンで自動導入されます（[`config/versions.env`](config/versions.env)）。

| ツール | バージョン |
|---|---|
| Python / Node.js / npm | 3.12.11 / 22.22.0 / 10.9.4 |
| Azure CLI | 2.89.1 |
| GitHub Copilot CLI | 1.0.114 |
| Rayfin CLI | 2.0.1 |
| Power BI レポート作成 CLI | 0.5.0 |
| go-sqlcmd | 1.10.0 |
| Copilot プラグイン | `fabric-skills` / `powerbi-authoring` v0.3.23、`rayfin` |

## 🧑‍🏫 講師の方へ

開催前に [instructor/00-overview.md](instructor/00-overview.md) の手順と **技術 Gate** を完了してください。
テナント設定・容量・共有接続・権限は自動では作成されません。

## 🗂️ リポジトリ構成

| パス | 内容 |
|---|---|
| `labs/` | 受講者向け手順書 |
| `instructor/` | 講師向けの準備・運用手順 |
| `reference/` | 手動コマンド、ローカル環境、認証トラブルシュート |
| `notebooks/specs/` | Copilot が Notebook を生成するための仕様書（受講者は `work/notebooks/` に生成。Git 対象外） |
| `notebooks/` | 教材提供の検証 Notebook（読み取り専用の採点役） |
| `reference/notebooks/` | 生成対象 Notebook の模範解答（`--reference` で配置。いずれも `scripts/dev/build_notebooks.py` から生成） |
| `scripts/lab.py` | Copilot が使う Fabric 操作コマンド（確認・配置・実行・検証） |
| `scripts/rayfin_az.py` | Codespaces でも使える Rayfin の認証ラッパー |
| `scripts/doctor.py` | 読み取り専用の環境診断 |
| `config/` | 開催設定（秘密情報なし）、Agent 定義、検証済みバージョン |
| `samples/rayfin/` | Data Agent を呼ぶ Rayfin Function の参照実装 |
| `tests/` | 期待値とリポジトリ検証 |

## ✅ リポジトリの検証

```bash
python3 tests/validate_repo.py
```

Notebook の構造、生成物の一致、TMDL の生成、期待値とサンプルデータの一致、Markdown のリンクを検証します。
GitHub Actions でも同じ検証を実行します。
