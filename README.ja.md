<p align="center">
  <img src="apps/web/src/assets/images/logo.png" alt="Doushabao ロゴ" width="160" />
</p>

<h1 align="center">Doushabao（豆沙包）</h1>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-Hant.md">繁體中文</a> ·
  <strong>日本語</strong> ·
  <a href="README.ko.md">한국어</a>
</p>

**Doushabao（豆沙包）** は、オープンソースのブラウザベース AI 画像エディターです。マスコットのように——一口かじったあん入りまんじゅうから、たっぷりのあんがのぞく——アプリは温かみがあり、親しみやすく、大切なことに集中します。画像を、編集のたびに少しずつ良くしていくことです。

強力な AI 編集を求めながら、重いデスクトップワークフローは避けたいクリエイター向けに設計され、Doushabao はブラウザだけで動作し、2 つの補完的なモードを提供します。

- **Agent モード** — 自然言語で望む編集を説明すると、AI が画像を分析し、インテリジェントな編集を自動で適用します。
- **Editor モード** — キャンバス上で領域を指定し、精密で局所的な指示により細かい制御が可能です。

写真のレタッチ、不要物の除去、ディテールの調整など、Doushabao は手順をシンプルに保ちます。画像を開き、AI で編集し、結果を書き出す——すべて、すっきりしたワークスペース UI で完結します。

オープンソース。プライバシーに配慮。Web、デスクトップアプリ、Docker と複数のデプロイ方法をサポート。

## クイックスタート

### 前提条件

- **Python 3.11+** と [uv](https://docs.astral.sh/uv/)（Python パッケージマネージャー）
- **Node.js 20+** と [pnpm](https://pnpm.io/)（JavaScript パッケージマネージャー）

### 実行

```bash
# すべての依存関係をインストール（フロントエンド + バックエンド）
make setup

# 開発サーバーを起動（http://localhost:8000）
make serve
```

フロントエンドはバックエンドから提供されるため、別途開発サーバーは不要です。コード変更時に自動再ビルドとブラウザリロードが行われます。

## プロジェクト構成

```text
.
├── apps/
│   ├── api/                  # Python FastAPI バックエンド（uv + litellm）
│   │   ├── src/
│   │   │   ├── main.py       # アプリケーションファクトリ、ミドルウェア、静的ファイル配信
│   │   │   ├── config.py     # 設定（Pydantic Settings）
│   │   │   ├── livereload.py # 開発モードのライブリロード（watchfiles + SSE）
│   │   │   ├── routers/      # HTTP ルーター
│   │   │   │   ├── health.py     # GET /health
│   │   │   │   ├── agent.py      # POST /api/v1/agent/run（ストリーミング）
│   │   │   │   ├── editor.py     # POST /api/v1/editor/run
│   │   │   │   ├── settings.py   # GET/PUT/DELETE /api/v1/settings
│   │   │   │   └── workspaces.py # CRUD /api/v1/workspaces
│   │   │   ├── core/         # コアビジネスロジック
│   │   │   │   ├── orchestration.py  # Agent & Editor ワークフロー
│   │   │   │   ├── analysis.py      # Agent 出力の JSON 解析
│   │   │   │   ├── prompts.py       # AI モデル用プロンプト
│   │   │   │   └── types.py         # データ型定義
│   │   │   ├── services/     # 外部サービス連携
│   │   │   │   ├── ai_client.py     # litellm 統合
│   │   │   │   └── image_utils.py   # Pillow 画像処理
│   │   │   └── models/       # データモデルとスキーマ
│   │   │       ├── settings.py  # SQLModel（AppConfig, WorkspaceRecord）
│   │   │       └── schemas.py   # Pydantic リクエスト/レスポンスモデル
│   │   ├── Dockerfile        # マルチステージ Docker ビルド
│   │   └── run.py            # PyInstaller エントリーポイント
│   └── web/                  # Vue 3 + Vite + Tailwind CSS フロントエンド
│       └── src/
│           ├── views/        # HomeView, WorkspaceView, SettingsView
│           ├── components/   # TopBar, TabBar, Sidebar, ImageViewport 等
│           ├── lib/          # API クライアント、ワークスペース状態、設定保存
│           ├── types/        # TypeScript 型定義
│           ├── i18n/         # 国際化（5言語）
│           └── assets/       # ロゴ、スタイル
├── electron/                 # デスクトップアプリ（Electron + electron-builder）
│   ├── main.js               # メインプロセス（バックエンド管理、ウィンドウ制御）
│   ├── preload.js            # contextBridge IPC
│   └── package.json          # electron-builder 設定（macOS/Win/Linux）
├── scripts/                  # ビルド・ユーティリティスクリプト
│   ├── serve.py              # 開発サーバーオーケストレーター
│   ├── setup.py              # 依存関係インストーラー
│   ├── build-desktop.py      # PyInstaller + electron-builder パイプライン
│   ├── generate-icons.py     # ロゴから .icns/.ico 生成
│   └── banner.py             # ASCII バナー
├── docker-compose.yml        # ワンコマンド Docker デプロイ
└── Makefile                  # よく使うコマンド
```

## 機能

- **2つの編集モード** — Agent（自然言語）と Editor（領域マーキング）
- **柔軟な AI プロバイダ** — OpenRouter、Gemini、OpenAI 互換 API に対応
- **リアルタイムストリーミング** — Agent の進捗を NDJSON でストリーム配信
- **画像処理** — 自動リサイズ、圧縮、アノテーション描画（Pillow）
- **ワークスペース管理** — 複数プロジェクトの保存/読込/削除
- **画像履歴** — 編集のアンドゥ対応
- **デスクトップアプリ** — Electron ラッパー、カスタムタイトルバー、クロスプラットフォームインストーラー
- **Docker サポート** — 単一コンテナデプロイ、永続ストレージ
- **国際化** — 英語、簡体字中国語、繁体字中国語、日本語、韓国語
- **ダーク/ライトテーマ** — 設定画面で切替可能
- **プライバシー** — AI API は自身のバックエンドを経由、API キーはローカルに保存

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│                  ブラウザ / Electron                  │
│  ┌───────────────────────────────────────────────┐  │
│  │         Vue 3 + Vite + Tailwind CSS            │  │
│  │         （純粋な UI 層、ビジネスロジックなし）    │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ HTTP / NDJSON ストリーム      │
├──────────────────────┼──────────────────────────────┤
│              FastAPI バックエンド（ポート 8000）        │
│  ┌───────────────────┴───────────────────────────┐  │
│  │  ルーター → コア（オーケストレーション + プロンプト）│  │
│  │  ↓                                            │  │
│  │  サービス（litellm → AI プロバイダ）             │  │
│  │  モデル（SQLite via SQLModel）                 │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 設定

### API キー

AI プロバイダの API キーは `apps/api/.env` で設定します（実行時にフロントエンドから渡すことも可能）：

```bash
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

すべてのキーはオプションです——設定しない場合、フロントエンドで入力を促します。

### バックエンド設定

`apps/api/.env` を編集するか、環境変数を設定：

```bash
HOST=0.0.0.0        # バインドアドレス（デフォルト: 0.0.0.0）
PORT=8000           # ポート（デフォルト: 8000）
DOUSHABAO_DATA_DIR=/path/to/data  # データディレクトリの上書き（Docker用）
```

## Docker デプロイ

```bash
# Docker Compose で起動（フォアグラウンド）
docker compose up

# バックグラウンドで実行
docker compose up -d

# 停止
docker compose down

# ログを表示
docker compose logs -f
```

コンテナはポート 8000 でフロントエンドと API の両方を提供し、Docker ボリュームで永続ストレージを実現します。

## デスクトップアプリ

クロスプラットフォームのデスクトップインストーラーをビルド：

```bash
# 現在のプラットフォーム用にビルド
make build-desktop

# 特定のプラットフォーム用にビルド
make build-desktop-mac      # macOS DMG
make build-desktop-win      # Windows NSIS
make build-desktop-linux    # Linux AppImage/deb
make build-desktop-all      # 全プラットフォーム

# バックエンドのみパッケージ（インストーラーなし）
make build-api
```

デスクトップアプリの構成：
- **Python バックエンド** — PyInstaller でスタンドアロン実行ファイルに
- **Vue フロントエンド** — 静的ファイルとして
- **Electron** — ウィンドウ管理とネイティブ機能

## 開発

### よく使うコマンド

```bash
# 依存関係のインストール
make setup

# 開発サーバーの起動（自動リロード）
make serve

# フロントエンドのみビルド
make build

# バックエンドテストの実行
cd apps/api && uv run pytest

# フロントエンドテストの実行
cd apps/web && pnpm test:unit

# フロントエンドのリント
cd apps/web && pnpm lint
```

### 開発サーバーの詳細

`make serve` は単一プロセス（`python scripts/serve.py`）を実行し、以下を行います：

1. バックグラウンドで `vite build --watch` を起動（初回ビルド + 差分リビルド）
2. 初回ビルドの完了を待機
3. ポート 8000 で `uvicorn --reload` を起動
4. フロントエンド再コンパイル時にブラウザを自動リロード（SSE ライブリロード）

### アーキテクチャ補足

すべてのビジネスロジックは `apps/api/src/core/` にあり、フロントエンド（`apps/web/`）は純粋な UI 層です。型定義は `apps/web/src/types/` にあります。バックエンドは **litellm** を使用してリクエストを様々な AI プロバイダにルーティングし、OpenRouter、Gemini、OpenAI 互換 API をサポートしています。

## ライセンス

本プロジェクトは [MIT License](LICENSE) の下で提供されています。
