<p align="center">
  <img src="apps/web/src/assets/images/logo.png" alt="AI Image Creation Workbench 로고" width="160" />
</p>

<h1 align="center">AI Image Creation Workbench</h1>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-Hant.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <strong>한국어</strong>
</p>

**AI Image Creation Workbench（Visual Workbench）** 는 사진 관리, 로컬 보정, 스타일 처리, AI 지원을 결합한 오픈 소스 사진 제작 워크벤치입니다. 촬영 사진을 가져오고, 선별하고, 되돌릴 수 있는 조정을 적용하고, 스타일을 저장한 뒤 필요할 때 AI를 사용하는 실제 사진 작업 흐름에 맞춰 설계되었습니다.

워크벤치는 다음 모드를 제공합니다.

- **Photo Library** — 사진 가져오기, 파일명 또는 고객 피드백 ID 검색, RAW/JPG 페어 관리, 형식과 선택 상태별 필터링.
- **Develop** — 노출, 대비, 채도, 색온도, 색조 등을 즉시 미리 보며 조정.
- **Color Match / Styles** — 참조 이미지 기반 색상 매칭, LUT, 재사용 가능한 스타일 프리셋.
- **AI Agent** — 사진을 분석하고 요청을 분해해 로컬 처리 또는 설정된 AI 모델로 전달.
- **Editor** — 국소 영역에 마크와 정밀한 지시를 추가해 마무리 편집.

일상적인 사진 작업을 빠르고 통제 가능하게 만들고, AI 작업을 추적하고 되돌릴 수 있게 하는 것이 목표입니다. 브라우저에서 실행할 수 있으며 Electron 데스크톱 앱으로도 패키징할 수 있습니다.

오픈 소스. 프라이버시 친화적. Web, 데스크톱 앱, Docker 등 다양한 배포 방식 지원.

## 빠른 시작

### 사전 요구사항

- **Python 3.11+** 및 [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)
- **Node.js 20+** 및 [pnpm](https://pnpm.io/) (JavaScript 패키지 매니저)

### 실행

```bash
# 모든 의존성 설치 (프론트엔드 + 백엔드)
make setup

# 개발 서버 시작 (http://localhost:8000)
make serve
```

프론트엔드는 백엔드에서 제공되므로 별도의 개발 서버가 필요하지 않습니다. 코드 변경 시 자동으로 재빌드 및 브라우저 리로드가 수행됩니다.

## 프로젝트 구조

```text
.
├── apps/
│   ├── api/                  # Python FastAPI 백엔드 (uv + litellm)
│   │   ├── src/
│   │   │   ├── main.py       # 앱 팩토리, 미들웨어, 정적 파일 서빙
│   │   │   ├── config.py     # 설정 (Pydantic Settings)
│   │   │   ├── livereload.py # 개발 모드 라이브 리로드 (watchfiles + SSE)
│   │   │   ├── routers/      # HTTP 라우터
│   │   │   │   ├── health.py     # GET /health
│   │   │   │   ├── agent.py      # POST /api/v1/agent/run (스트리밍)
│   │   │   │   ├── editor.py     # POST /api/v1/editor/run
│   │   │   │   ├── settings.py   # GET/PUT/DELETE /api/v1/settings
│   │   │   │   └── workspaces.py # CRUD /api/v1/workspaces
│   │   │   ├── core/         # 핵심 비즈니스 로직
│   │   │   │   ├── orchestration.py  # Agent & Editor 워크플로
│   │   │   │   ├── analysis.py      # Agent 출력 JSON 파싱
│   │   │   │   ├── prompts.py       # AI 모델 프롬프트
│   │   │   │   └── types.py         # 데이터 타입 정의
│   │   │   ├── services/     # 외부 서비스 클라이언트
│   │   │   │   ├── ai_client.py     # litellm 통합
│   │   │   │   └── image_utils.py   # Pillow 이미지 처리
│   │   │   └── models/       # 데이터 모델 및 스키마
│   │   │       ├── settings.py  # SQLModel (AppConfig, WorkspaceRecord)
│   │   │       └── schemas.py   # Pydantic 요청/응답 모델
│   │   ├── Dockerfile        # 멀티스테이지 Docker 빌드
│   │   └── run.py            # PyInstaller 진입점
│   └── web/                  # Vue 3 + Vite + Tailwind CSS 프론트엔드
│       └── src/
│           ├── views/        # HomeView, WorkspaceView, SettingsView
│           ├── components/   # TopBar, TabBar, Sidebar, ImageViewport 등
│           ├── lib/          # API 클라이언트, 워크스페이스 상태, 설정 저장
│           ├── types/        # TypeScript 타입 정의
│           ├── i18n/         # 국제화 (5개 언어)
│           └── assets/       # 로고, 스타일
├── electron/                 # 데스크톱 앱 (Electron + electron-builder)
│   ├── main.js               # 메인 프로세스 (백엔드 생명주기, 창 관리)
│   ├── preload.js            # contextBridge IPC
│   └── package.json          # electron-builder 설정 (macOS/Win/Linux)
├── scripts/                  # 빌드 및 유틸리티 스크립트
│   ├── serve.py              # 개발 서버 오케스트레이터
│   ├── setup.py              # 의존성 설치
│   ├── build-desktop.py      # PyInstaller + electron-builder 파이프라인
│   ├── generate-icons.py     # 로고에서 .icns/.ico 생성
│   └── banner.py             # ASCII 배너
├── docker-compose.yml        # 원커맨드 Docker 배포
└── Makefile                  # 주요 명령어
```

## 기능

- **두 가지 편집 모드** — Agent (자연어) 및 Editor (영역 마킹)
- **유연한 AI 프로바이더** — OpenRouter, Gemini 및 모든 OpenAI 호환 API 지원
- **실시간 스트리밍** — Agent 진행 상황 NDJSON 스트림으로 푸시
- **이미지 처리** — 자동 리사이즈, 압축, 주석 렌더링 (Pillow)
- **워크스페이스 관리** — 여러 프로젝트 저장/불러오기/삭제
- **이미지 히스토리** — 편집 실행 취소 지원
- **데스크톱 앱** — Electron 래퍼, 커스텀 타이틀 바, 크로스플랫폼 설치 프로그램
- **Docker 지원** — 단일 컨테이너 배포, 영구 스토리지
- **국제화** — 영어, 간체 중국어, 번체 중국어, 일본어, 한국어
- **다크/라이트 테마** — 설정에서 전환 가능
- **프라이버시** — AI API 호출은 자체 백엔드를 통해 프록시, API 키는 로컬에 저장

## 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                  브라우저 / Electron                   │
│  ┌───────────────────────────────────────────────┐  │
│  │         Vue 3 + Vite + Tailwind CSS            │  │
│  │         (순수 UI 레이어, 비즈니스 로직 없음)     │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ HTTP / NDJSON 스트림          │
├──────────────────────┼──────────────────────────────┤
│              FastAPI 백엔드 (포트 8000)                │
│  ┌───────────────────┴───────────────────────────┐  │
│  │  라우터 → 코어 (오케스트레이션 + 프롬프트)       │  │
│  │  ↓                                            │  │
│  │  서비스 (litellm → AI 프로바이더)               │  │
│  │  모델 (SQLite via SQLModel)                    │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 설정

### API 키

AI 프로바이더 API 키는 `apps/api/.env` 에서 설정합니다 (실행 시 프론트엔드에서 전달 가능):

```bash
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

모든 키는 선택 사항입니다——설정하지 않으면 프론트엔드에서 입력을 요청합니다.

### 백엔드 설정

`apps/api/.env` 를 편집하거나 환경 변수 설정:

```bash
HOST=0.0.0.0        # 바인드 주소 (기본값: 0.0.0.0)
PORT=8000           # 포트 (기본값: 8000)
DOUSHABAO_DATA_DIR=/path/to/data  # 데이터 디렉토리 재정의 (Docker 용)
```

## Docker 배포

```bash
# Docker Compose 로 시작 (포그라운드)
docker compose up

# 백그라운드 실행
docker compose up -d

# 중지
docker compose down

# 로그 확인
docker compose logs -f
```

컨테이너는 포트 8000 에서 프론트엔드와 API 를 모두 제공하며, Docker 볼륨을 통해 영구 스토리지를 구현합니다.

## 데스크톱 앱

크로스플랫폼 데스크톱 설치 프로그램 빌드:

```bash
# 현재 플랫폼용 빌드
make build-desktop

# 특정 플랫폼용 빌드
make build-desktop-mac      # macOS DMG
make build-desktop-win      # Windows NSIS
make build-desktop-linux    # Linux AppImage/deb
make build-desktop-all      # 모든 플랫폼

# 백엔드만 패키징 (설치 프로그램 없음)
make build-api
```

데스크톱 앱 구성:
- **Python 백엔드** — PyInstaller 로 독립 실행 파일로 패키징
- **Vue 프론트엔드** — 정적 파일로 포함
- **Electron** — 창 관리 및 네이티브 기능 담당

## 개발

### 주요 명령어

```bash
# 의존성 설치
make setup

# 개발 서버 시작 (자동 리로드)
make serve

# 프론트엔드만 빌드
make build

# 백엔드 테스트 실행
cd apps/api && uv run pytest

# 프론트엔드 테스트 실행
cd apps/web && pnpm test:unit

# 프론트엔드 린트
cd apps/web && pnpm lint
```

### 개발 서버 상세

`make serve` 는 단일 프로세스 (`python scripts/serve.py`)를 실행하여 다음을 수행합니다:

1. 백그라운드에서 `vite build --watch` 시작 (최초 빌드 + 증분 재빌드)
2. 최초 빌드 완료 대기
3. 포트 8000 에서 `uvicorn --reload` 시작
4. 프론트엔드 재컴파일 시 브라우저 자동 리로드 (SSE 라이브 리로드)

### 아키텍처 참고

모든 비즈니스 로직은 `apps/api/src/core/` 에 있으며, 프론트엔드 (`apps/web/`)는 순수 UI 레이어입니다. 타입 정의는 `apps/web/src/types/` 에 있습니다. 백엔드는 **litellm** 을 사용하여 요청을 다양한 AI 프로바이더로 라우팅하며, OpenRouter, Gemini 및 OpenAI 호환 API를 지원합니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE) 로 배포됩니다.
