# Fabric ハンズオン Lab V4 — Copilot への共通指示

この教材では、受講者は日本語で作業内容だけを伝える。Copilot は教材の手順と、
`scripts/` の補助コマンドを使って Microsoft Fabric を操作する。教材の各 Lab に
「Copilot の動き」として書かれたコマンドを優先し、独自の手順に置き換えない。

## 参加者設定（Lab 00 で一度だけ登録）

ユーザーが student 番号を伝えて登録・記憶を依頼したら、`config/workshop.json` の値から次を生成し、
教材ルートの `.github/student.local.md` に **この形式のまま** 保存する。

```markdown
# 参加者設定
- student 番号: <番号>
- アカウント: <accountPrefix><番号>@<accountDomain>
- ワークスペース名: <workspacePrefix><番号>
- テナント ID: <tenantId>
```

- 番号は数字のみ。先頭の 0 を含め、入力された表記を保持する。不正なら保存せず再入力を求める。
- アカウント名・ワークスペース名をユーザーに入力・置換させない。
- 番号が同じなら確認済みの `- Workspace ID:` 行を残す。番号を変えたら Workspace ID 行を削除する。
- 保存後に読み直し、番号・アカウント・ワークスペース名・テナント ID を表示する。
- 登録の依頼だけでは Azure / Fabric へのサインインやリソース作成をしない。
- パスワード、MFA コード、アクセストークン、シークレットは保存・表示しない。
- `.github/student.local.md` はコミット・共有・アップロードしない。

Azure / Fabric を操作する前に、必ずこのファイルを読む。ファイルがない、番号が不正、内容が矛盾する場合は
操作を止め、Lab 00 の登録を案内する。student 番号、Workspace ID、アイテム ID を推測しない。

## 接続先の特定

- すべての Fabric 操作の前に `python3 scripts/lab.py check` を実行し、サインイン中のアカウント・テナント・
  ワークスペースが参加者設定と一致することを確認する。不一致なら止めて理由を伝える。
- 初回接続で Workspace ID を確認できたら `python3 scripts/lab.py check --save` で保存する。
- アイテムは自分のワークスペース内で名前と種類から API で特定する。別の参加者のワークスペースで代替しない。
- SQL 接続先・公開 URL などは API または CLI の結果から取得する。候補が複数・見つからない場合は止める。
- 講師提供の外部設定（共有接続名など）は `config/workshop.json` または `config/workshop.local.json` から読む。
  見つからなければ未設定と明示し、架空の値を作らない。

## 認証

- サインイン、MFA、アカウント選択、同意はユーザー本人が行う。Copilot は手順と表示されたコードを案内する。
- Codespaces、SSH、ブラウザが自動で開かない環境では、最初からデバイスコード方式を使う:
  `az login --tenant <tenantId> --allow-no-subscriptions --use-device-code`
- ローカル PC では `az login --tenant <tenantId> --allow-no-subscriptions` を使い、ブラウザが開かなければデバイスコード方式に切り替える。
- ユーザー名・パスワードを引数で渡すサインインは使わない。認証キャッシュを全削除する操作を標準の復旧手順にしない。
- 条件付きアクセスや MFA を回避する方法を提案しない。ポリシーで拒否された場合は講師へ引き継ぐ。
- アクセストークンを表示・ログ出力・ファイル保存しない。

## データ加工は Fabric Notebook で行う

- 業務データの取り込み・加工・検証をローカルの pandas などで実行しない。一時的な Livy セッションだけで済ませない。
- 加工・Warehouse 作成・Ontology 用テーブル・Data Agent 作成の Notebook（`nb_02_prepare_trips`、`nb_03_prepare_dimensions`、
  `nb_04_build_warehouse`、`nb_07_prepare_ontology`、`nb_08_create_agents`）は、**Copilot が仕様書から生成する**。
  - `notebooks/specs/README.md`（共通の約束）と `notebooks/specs/<名前>.md` を読み、`work/notebooks/<名前>.ipynb`（nb_04 は `.sql`）に書く。
  - 生成後にセル構成を受講者に要約し、`python3 scripts/lab.py notebook check <名前>` を通してから
    `python3 scripts/lab.py notebook deploy-run <名前>` で Fabric アイテムとして配置・実行する。
  - 失敗したら `result.error` とセル出力から原因を説明し、**生成した Notebook を直して** 再実行する。
  - 仕様書にない ID・トークン・接続文字列を書かない。ID は `lab.py` の配置時の埋め込み（既定 Lakehouse、`{{WAREHOUSE_ID}}`、`{{AGENT_CONFIG_B64}}`）に任せる。
  - `reference/notebooks/` の模範解答は、受講者が求めたときか、生成と修正を繰り返しても通らないときだけ `--reference` で使う。
    先に模範解答をコピーして生成の代わりにしない。
- 検証 Notebook（`notebooks/*_validate_*`）、`tests/expected/`、`scripts/lab.py` を、生成した Notebook を通すために書き換えない。
- 配置完了と実行完了を区別し、Notebook のリンク、実行状態、`result` の内容を報告する。
- 「加工」の依頼では加工と保存の結果だけを報告する。答え合わせは検証 Notebook の依頼で行う。
- 検証 Notebook はデータを変更しない。不一致は修正せず、期待値・実測値・差異を報告する。
- 期待値は `tests/expected/expected.json` が唯一の基準。Lab 本文の数値と矛盾したら JSON を優先し、矛盾を報告する。
- 確認用レコードは WHERE 条件（trip_id や日付・ID）で特定する。`LIMIT` / `TOP` や順序なしの先頭行を根拠にしない。

## セマンティックモデル・Ontology・Data Agent

- セマンティックモデルは `python3 scripts/lab.py semantic-model` でプレビュー後、`--apply` で配置する。
- Ontology（新しい体験）は `python3 scripts/lab.py ontology` でプレビュー後、`--apply` で REST API から作成・更新する。
  TMDL を手書きで改変しない。旧体験（V1）の JSON 定義を作らない。
- Data Agent は Copilot が仕様書から生成した `nb_08_create_agents` Notebook（fabric-data-agent-sdk）で作成・公開する。ポータル操作は
  Notebook が失敗した場合の代替としてだけ案内する。
- Data Agent への質問は `python3 scripts/lab.py agent-ask` / `agent-compare`（公開済み Agent の MCP）を使う。
  回答を推測で補わない。取得できなかった根拠は「取得できない」と書く。

## Rayfin（Fabric Apps）

- Rayfin プロジェクトは教材ルートの `apps/` 配下に作り、プロジェクト内の `AGENTS.md` と
  `.agents/skills/` を読んでから実装する。Rayfin の API を記憶で書かない。
- Codespaces・リモート環境では `rayfin login` を使わず、`python3 ../../scripts/rayfin_az.py <rayfin のサブコマンド>` で実行する。
  このラッパーは Azure CLI のサインインを確認し、トークンを子プロセスにだけ渡す。
- `RAYFIN_TOKEN` をシェルに export しない。`.env` や `VITE_*` 変数にトークン・シークレットを書かない。
- Data Agent チャットは Rayfin Functions（`AudienceType.Fabric`）から公開済み Data Agent の MCP を呼ぶ。外部プロキシを作らない。
- デプロイ後は公開 URL を開いてサインインし、表示・入力・チャットを確認するよう案内する。HTTP 200 だけで完了扱いにしない。

## 共通

- 実行前に何をするか短く伝え、承認が必要な操作は内容を示す。
- 失敗したら止まった段階と理由を伝え、教材のトラブルシュートにあるプロンプトを提案する。
- 他の参加者のリソース、共有接続、講師のリソースを変更・削除しない。
