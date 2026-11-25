# 講師ガイド 03 — Fabric App と Data Agent の認証・権限

V3 では Lab 10 の Rayfin がトークンを渡さないと進まず、Lab 08 のチャットは未同梱の中継プロキシに依存していました。
V4 では、認証を次の 4 段階に分け、それぞれに確実な経路を用意しています。

| 段階 | 実行主体 | V4 の方式 | 確認方法 |
|---|---|---|---|
| ① CLI の認証 | 受講者 | ローカル: `rayfin login`／Codespaces: `scripts/rayfin_az.py` | `rayfin_az.py login status` |
| ② デプロイ | 受講者 | 受講者自身の権限で自分のワークスペースへ | `rayfin_az.py up status` |
| ③ アプリの利用 | アプリを開いた人 | Fabric SSO（Entra ID） | 別ブラウザでサインインして表示 |
| ④ データアクセス | 機能ごとに異なる（下表） | delegated／アプリ ID | 表示・入力・チャットの動作 |

## ① Codespaces で Rayfin CLI が止まる理由と対策

`rayfin login` はブラウザで認証した後、コンテナー内の `localhost:<ランダムなポート>` へ戻る方式です。
Codespaces ではこの戻り先がホストのブラウザから届かないことがあり、CLI が待ち続けます。
また、OS のキーチェーンがない環境では、ログイン情報の保存にも失敗します。

V4 の `scripts/rayfin_az.py` は、Rayfin が公式にサポートする `RAYFIN_TOKEN`（事前に認証済みの環境向け）を使います。

1. Azure CLI のサインインを参加者設定（アカウント・テナント・ワークスペース）と照合し、不一致なら停止します。
2. Azure CLI から Fabric 用の短期トークンを取得します（デバイスコード認証済みのセッションを再利用）。
3. トークンを **その 1 回の `npx rayfin` 子プロセスの環境変数だけ**に渡します。表示・保存・export はしません。

講師のトークンを配布する、`.env` にトークンを書く、`VITE_*` に入れる、といった運用は禁止です。
トークンの有効期限は約 1 時間なので、長時間後に失敗した場合は同じコマンドを再実行すれば取り直します。

## ④ データアクセスの実行主体

| 機能 | 仕組み | 実行主体 | 必要な権限 |
|---|---|---|---|
| ダッシュボード | `fabric-semanticmodel` connector（`executeQuery`） | **アプリを使う各ユーザー**（delegated のみ） | `sm_taxi` の Read + Build |
| 入力フォーム | アプリ専用 DB（Rayfin data） | 各ユーザー | アプリのエンティティ権限（`@role` など） |
| チャット | Rayfin Function → Data Agent の MCP | **アプリのアイテム所有者**（application） | 所有者が Agent とデータに読み取りアクセス |

- ハンズオンでは受講者が自分のアプリ・モデル・Agent の所有者なので、追加の権限付与は不要です。
- 受講者がアプリを**他の人と共有する**と、チャットは所有者の権限でデータを読むことになります。
  共有前に、回答してよい範囲かを確認するよう説明してください（Lab 09 にも記載）。
- Function のタイムアウトは Fabric UDF ホストの上限 250 秒です。参照実装は 240 秒で打ち切ります。

## Data Agent（Lab 08）

- 作成・公開は受講者の Copilot が [`notebooks/specs/nb_08_create_agents.md`](../notebooks/specs/nb_08_create_agents.md) から生成した `nb_08_create_agents` Notebook で、`fabric-data-agent-sdk==0.1.36a0` を使います（模範解答は `reference/notebooks/`）。
  - セマンティックモデル: `add_staging_datasource`（公開 API）
  - Ontology: `add_staging_ontology`（コンテキストソース。**Notebook の実行環境が必要**なため Notebook で実行）
  - 公開: `publish_staging`。公開時の説明文が MCP ツールの説明になります。
- 追加直後のデータソースは一覧への反映が遅れることがあります。仕様書で再取得（10 秒 × 最大 6 回）を必須にしています。
- Ontology の追加で `401 CUSTOMER_UNAUTHORIZED`（`Failed to generate MWC token for OntologyWorkload`）が返る場合は、テナントの Ontology / Data Agent 設定と受講者の権限を確認してください。Agent ごとに失敗を分けているため、`taxi_metrics_agent` は作成・公開されます。
- Notebook 内の `%pip install` が実行時に許可されていない環境では失敗します（Gate G6）。
  その場合は、ワークスペースに Environment を作成して SDK を登録し、Notebook に関連付けてください。
- 代替（ポータル）: ワークスペース › **新しい項目 › Data agent** で作成し、データソースに `sm_taxi`／`onto_taxi` を追加して、
  `config/agents.json` の `instructions` を「Agent instructions」に貼り付けて公開します。

## Gate G8 の確認項目

1. テスト受講者 A が Codespaces で Lab 09 を完了し、`rayfin_az.py up status` が正常。
2. A が別ブラウザ（InPrivate）で公開 URL を開き、SSO 後にダッシュボードの数値が `tests/expected/expected.json` と一致。
3. 入力フォームで 1 件保存し、再読み込み後も残る。
4. チャットで「総トリップ数は？」に 37,948 件を含む回答が返る。
5. 受講者 B が A のアプリ URL を開いても、権限がなければデータが表示されない（他人のデータが見えない）。
