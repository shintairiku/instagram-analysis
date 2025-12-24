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

## develop ブランチの主な変更点（main との差分メモ）

- **DBアクセス方式の移行**: SQLAlchemy中心から Supabase SDK（PostgREST）へ切替。`backend/app/core/database.py`・`backend/app/core/supabase_utils.py` を追加し、各リポジトリ/サービスをSupabaseクライアントベースに更新。
- **収集API追加**: `POST /api/v1/collection/daily` と `GET /api/v1/collection/daily/status` を追加。`COLLECTION_TRIGGER_TOKEN` による簡易認証と同時実行ロックを実装。
- **手動更新機能**: `POST /api/v1/collection/accounts/{account_id}/refresh` を追加し、直近投稿の同期（window_days/max_posts）と手動更新の最短間隔制限（`MANUAL_REFRESH_MIN_INTERVAL_SECONDS`）を導入。
- **データ収集の拡張**: 直近投稿同期サービス、メトリクス正規化ユーティリティ、Instagram API の「指定日時以降の投稿取得」処理を追加。
- **集計ロジック更新**: 日次集計に media_type 分布・data_sources のJSON保存、recorded_at のUTC統一などを反映。
- **フロントエンド連携**: 投稿インサイト画面に「最新情報を取得」ボタンと最終更新表示を追加。Next.js API ルートでバックエンドへ安全に中継。
- **設定/スキーマ管理**: `supabase/migrations/` に初期スキーマを追加し、`docker-compose.yml` は `env_file` 参照に変更。環境変数例に `COLLECTION_TRIGGER_TOKEN` などを追加。

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

### Google Cloud Scheduler（HTTP）設定例

前提：
- バックエンド環境変数 `COLLECTION_TRIGGER_TOKEN` を設定済み（`backend/.env` / Railway Variables 等）

Console（推奨）:
- Cloud Scheduler →「ジョブを作成」
- ターゲット：HTTP
- URL：`https://<BACKEND_HOST>/api/v1/collection/daily`
- メソッド：POST
- ヘッダー：`X-Collection-Token: <COLLECTION_TRIGGER_TOKEN>`（または `Authorization: Bearer <COLLECTION_TRIGGER_TOKEN>`）
- Body：`{}`（空でも動く想定ですが、明示しておくのが安全です）
- タイムゾーン：`Asia/Tokyo`
- スケジュール：例）毎日 06:00 JST → `0 6 * * *`
- 作成後「今すぐ実行」で疎通確認

`gcloud`（例）:
```bash
gcloud scheduler jobs create http instagram-analysis-daily \
  --location=asia-northeast1 \
  --schedule="0 6 * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://<BACKEND_HOST>/api/v1/collection/daily" \
  --http-method=POST \
  --headers="X-Collection-Token=<COLLECTION_TRIGGER_TOKEN>,Content-Type=application/json" \
  --message-body="{}"
```

## データベース

PostgreSQL (Supabase) を使用。スキーマは `supabase/migrations/` に管理し、後で `npx supabase db push` で反映できます（このリポジトリではマイグレーションの実行は行いません）。
