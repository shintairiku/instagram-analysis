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
- **SQLAlchemy** (ORM)

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
│   ├── insert-table/
│   └── insert-dummy-data/
├── docs/
└── docker-compose.yml
```

## 開発環境セットアップ

### 1. 必要な環境変数の設定

#### frontend/.env.local
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

#### backend/.env
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/instagram_analysis
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

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

## データベース

PostgreSQL (Supabase) を使用。テーブル作成とダミーデータ挿入は `supabase/` ディレクトリ内のSQLファイルを参照。
