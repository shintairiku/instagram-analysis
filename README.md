# Instagram Analysis App

フルスタックWebアプリケーション（Next.js + FastAPI + PostgreSQL）

## 技術スタック

### フロントエンド
- **Next.js 15** (React 19)
- **TypeScript**
- **shadcn/ui** (UIコンポーネント)
- **Tailwind CSS**

### バックエンド
- **FastAPI** (Python)
- **PostgreSQL** (Supabase)
- **Supabase SDK** (supabase-py)

### デプロイ
- **Frontend**: Vercel
- **Backend**: Railway
- **Database**: Supabase

## プロジェクト構造

```
project-root/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── cli/
│   │   ├── model/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── utils/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   ├── common/
│   │   │   ├── constants/
│   │   │   ├── display/
│   │   │   ├── modal/
│   │   │   └── ui/
│   │   ├── feature/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
├── supabase/
│   ├── config.toml
│   └── migrations/
├── docs/
└── docker-compose.yml
```

## 開発環境セットアップ

### 1. 必要な環境変数の設定

まずは例ファイルをコピーして、実値を設定してください。

```bash
# Frontend
cp frontend/.env.example frontend/.env.local

# Backend
cp backend/.env.example backend/.env

# verification（必要な場合のみ）
cp verification/.env.example verification/.env
```

#### 環境変数一覧

##### Frontend（`frontend/.env.local`）
| 変数名 | 必須 | 説明 |
|---|---:|---|
| `NEXT_PUBLIC_API_URL` | ✅ | フロントエンドから呼び出すバックエンドAPIのベースURL（例: `http://localhost:8000`） |
| `COLLECTION_TRIGGER_TOKEN` | ✅ | Next.js API ルート（サーバ側）から手動更新APIを呼ぶためのトークン（ブラウザには公開されません） |

##### Backend（`backend/.env`）
| 変数名 | 必須 | 説明 |
|---|---:|---|
| `SUPABASE_URL` | ✅ | SupabaseプロジェクトURL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Supabaseのservice role key（**フロントには絶対に渡さない**） |
| `SUPABASE_ANON_KEY` | 任意 | 将来的にフロントでSupabaseを直接使う場合のanon key |
| `DATABASE_URL` | 任意 | Supabase CLI / 直接SQLツール用のPostgreSQL接続URL |
| `FACEBOOK_APP_ID` | 任意 | Facebook/InstagramアプリID（設定検証・拡張用途。未設定でも動作します） |
| `FACEBOOK_APP_SECRET` | 任意 | Facebook/InstagramアプリSecret（設定検証・拡張用途。未設定でも動作します） |
| `COLLECTION_TRIGGER_TOKEN` | ✅ | 定期実行（Cloud Scheduler）/ 手動更新API の保護トークン |
| `MANUAL_REFRESH_MIN_INTERVAL_SECONDS` | 任意 | 手動更新の最短間隔（秒、デフォルト60） |
| `SLACK_WEBHOOK_URL` | 任意 | GitHub Actions等からSlack通知するWebhook URL（未設定の場合は通知をスキップ） |

##### GitHub Actions（Repository Secrets）
| 変数名 | 必須 | 説明 |
|---|---:|---|
| `SUPABASE_URL` | ✅ | Actions実行時のSupabase URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Actions実行時のSupabase service role key |
| `SLACK_WEBHOOK_URL` | 任意 | 失敗/新規投稿などのSlack通知先 |

##### verification（`verification/.env`：検証スクリプト用）
| 変数名 | 必須 | 説明 |
|---|---:|---|
| `INSTAGRAM_USER_ID` | ✅ | 検証対象のInstagram User ID |
| `ACCESS_TOKEN` | ✅ | Instagram Graph APIにアクセスできる（通常はFacebook Page）アクセストークン |
| `USERNAME` | 任意 | ログ/確認用のユーザー名（スクリプトによって参照） |
| `INSTAGRAM_APP_ID` | 任意 | アカウントセットアップ検証用のApp ID |
| `INSTAGRAM_APP_SECRET` | 任意 | アカウントセットアップ検証用のApp Secret |
| `INSTAGRAM_SHORT_TOKEN` | 任意 | アカウントセットアップ検証用の短期トークン |

### 2. Docker Compose での起動
```bash
docker-compose up --build
```

### 3. 個別での起動

#### フロントエンド
```bash
cd frontend
npm install
npm run dev
```

#### バックエンド
```bash
cd backend
uv sync
uv run --env-file .env uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### バックエンド（pip / 互換）
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## カラーテーマ

- **Primary**: #f3a522 (オレンジ)
- **Secondary**: #322c2c (ダークグレー)
- **Background**: #f7f9fc (ライトブルー)
- **Foreground**: #404749 (グレー)

## API エンドポイント

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 定期実行（Cloud Scheduler 等）

バックエンドに Cloud Scheduler から叩けるトリガーを用意しています。

- `POST /api/v1/collection/daily`（Authorization: Bearer `COLLECTION_TRIGGER_TOKEN`）
- `GET /api/v1/collection/daily/status`（Authorization: Bearer `COLLECTION_TRIGGER_TOKEN`）

## データベース

PostgreSQL (Supabase) を使用。スキーマは `supabase/migrations/` に管理し、後で `npx supabase db push` で反映できます（このリポジトリではマイグレーションの実行は行いません）。
