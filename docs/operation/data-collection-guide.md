# Instagram データ収集システム運用ガイド

## 概要
このドキュメントは、Instagram データ収集システムの日常運用について説明します。日次データ収集と過去データ収集の両方を効率的に運用するためのガイドです。

## システム構成

### 主要コンポーネント
- **日次データ収集**: 毎日自動実行される通常の収集
- **過去データ収集**: 初回設定や補完のための一括収集
- **GitHub Actions**: 自動化されたワークフロー
- **Supabase**: データ保存先

## 🔄 日次データ収集

### 自動実行（推奨）
毎日06:00 JST に GitHub Actions で自動実行されます。

**ワークフロー**: `.github/workflows/daily-data-collection.yml`

```yaml
# 自動実行スケジュール
schedule:
  - cron: '0 21 * * *'  # 毎日 06:00 JST (21:00 UTC)
```

## 🕗 直近投稿同期（Post Insight / 日次更新）

投稿インサイト（`instagram_post_metrics`）は、直近投稿同期（upsert: `create_or_update_daily`）で更新されます。  
「最新情報を取得」ボタンを押さなくても、**毎日 08:00 JST に自動実行**されるようにスケジューラを設定してください。

### 自動実行（GitHub Actions）
**ワークフロー**: `.github/workflows/recent-post-sync.yml`

```yaml
schedule:
  # GitHub Actions cron は UTC。08:00 JST = 23:00 UTC (前日)
  - cron: '0 23 * * *'
```

### トリガー先（Backend API）
GitHub Actions からは Backend のトリガーAPIを叩きます。

- `POST /api/v1/collection/recent-posts`
- 認証: `Authorization: Bearer $COLLECTION_TRIGGER_TOKEN`

必要な GitHub Secrets:
- `BACKEND_BASE_URL`（例: `https://xxxx.railway.app`）
- `COLLECTION_TRIGGER_TOKEN`

### 手動実行
緊急時や特定アカウントのみ実行したい場合：

```bash
# 全アカウントの昨日分データ収集
python3 scripts/collect_daily_data.py

# 特定アカウントのみ
python3 scripts/collect_daily_data.py --accounts 17841402015304577

# ドライラン（確認用）
python3 scripts/collect_daily_data.py --dry-run --verbose

# 指定日付のデータ収集
python3 scripts/collect_daily_data.py --date 2025-06-20
```

## 📚 過去データ収集

### 新規アカウント追加時
新しいアカウントを追加した際の初期データ取得：

```bash
# 過去30日間のデータ取得
python3 scripts/collect_historical_data.py --account NEW_ACCOUNT_ID --days 30 -y

# 過去1年間のデータ取得
python3 scripts/collect_historical_data.py --account NEW_ACCOUNT_ID --days 365 -y

# 全投稿データ取得（時間がかかります）
python3 scripts/collect_historical_data.py --account NEW_ACCOUNT_ID --all-posts -y
```

### データ補完
システム障害などでデータが欠損した場合：

```bash
# 指定期間のデータ再収集
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --from 2025-06-01 --to 2025-06-15 -y

# メトリクスが未取得の投稿のメトリクスのみ収集
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --missing-metrics -y
```

### 大量データ収集時の注意点
```bash
# レート制限を考慮して小さなチャンクで実行
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --all-posts --chunk-size 25 -y

# 最大投稿数を制限
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --all-posts --max-posts 500 -y

# 投稿のみ（メトリクスなし）で高速実行
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --days 90 --no-metrics -y
```

## ⚙️ 環境設定

### 必要な環境変数
```bash
# データベース接続
export DATABASE_URL="postgresql://user:pass@host:port/db"

# Supabase設定
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

# Instagram API設定（オプション）
export FACEBOOK_APP_ID="your-app-id"
export FACEBOOK_APP_SECRET="your-app-secret"
```

### Python環境
```bash
# 仮想環境の有効化
source venv/bin/activate

# 必要なパッケージのインストール
pip install -r requirements.txt

# パスの設定
export PYTHONPATH=.
```

## 📊 監視とメンテナンス

### 日次チェック項目
1. **GitHub Actions の実行状況確認**
   - Actions タブで成功/失敗を確認
   - 失敗時はログを確認してエラー原因を特定

2. **データ収集状況確認**
   ```sql
   -- 最新の日次統計確認
   SELECT account_id, stats_date, follower_count, posts_count 
   FROM instagram_daily_stats 
   ORDER BY created_at DESC LIMIT 10;

   -- 投稿数確認
   SELECT COUNT(*) as total_posts FROM instagram_posts;

   -- メトリクス数確認
   SELECT COUNT(*) as total_metrics FROM instagram_post_metrics;
   ```

3. **アクセストークンの期限確認**
   ```sql
   -- トークン期限が近いアカウント
   SELECT username, token_expires_at 
   FROM instagram_accounts 
   WHERE token_expires_at < NOW() + INTERVAL '7 days';
   ```

### 週次チェック項目
1. **データ品質チェック**
   ```sql
   -- データ欠損チェック
   SELECT stats_date, COUNT(*) as accounts_count
   FROM instagram_daily_stats 
   WHERE stats_date >= CURRENT_DATE - INTERVAL '7 days'
   GROUP BY stats_date 
   ORDER BY stats_date DESC;
   ```

2. **メトリクス未取得投稿のチェック**
   ```bash
   # メトリクス未取得投稿の補完
   python3 scripts/collect_historical_data.py --account ACCOUNT_ID --missing-metrics -y
   ```

## 🚨 トラブルシューティング

### よくある問題と対処法

#### 1. アクセストークンエラー
**症状**: `Invalid access token` エラー
**対処法**:
```bash
# トークンの再生成が必要
# Instagram Basic Display API でトークンを更新
# データベースのaccess_token_encryptedを更新
```

#### 2. レート制限エラー
**症状**: `Rate limit exceeded` エラー
**対処法**:
```bash
# 1時間待機後に再実行
# または小さなチャンクサイズで実行
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --chunk-size 10 -y
```

#### 3. データベース接続エラー
**症状**: `Database connection failed` エラー
**対処法**:
```bash
# 環境変数の確認
echo $DATABASE_URL

# データベース接続テスト
python3 -c "from app.core.database import test_connection; print(test_connection())"
```

#### 4. メモリ不足エラー
**症状**: 大量データ処理時のメモリ不足
**対処法**:
```bash
# 最大投稿数を制限
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --max-posts 100 -y

# 期間を分割して実行
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --from 2024-01-01 --to 2024-06-30 -y
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --from 2024-07-01 --to 2024-12-31 -y
```

## 📈 パフォーマンス最適化

### 処理時間の目安
- **日次収集**: 1アカウントあたり約10秒
- **過去30日**: 1アカウントあたり約2-3分
- **過去1年**: 1アカウントあたり約15-30分
- **全投稿**: アカウントサイズにより数時間

### 最適化のコツ
1. **並列処理の活用**
   ```bash
   # 複数アカウントを並列処理（注意：レート制限に注意）
   python3 scripts/collect_historical_data.py --account ACCOUNT1 --days 30 -y &
   python3 scripts/collect_historical_data.py --account ACCOUNT2 --days 30 -y &
   wait
   ```

2. **段階的データ収集**
   ```bash
   # 段階1: 投稿データのみ高速収集
   python3 scripts/collect_historical_data.py --account ACCOUNT_ID --all-posts --no-metrics -y

   # 段階2: メトリクスのみ収集
   python3 scripts/collect_historical_data.py --account ACCOUNT_ID --missing-metrics -y
   ```

## 📝 ログとデバッグ

### ログファイル
```bash
# 日次収集ログ
tail -f daily_collection.log

# 過去データ収集ログ
tail -f historical_collection.log

# 詳細デバッグ
python3 scripts/collect_daily_data.py --verbose
python3 scripts/collect_historical_data.py --verbose
```

### デバッグ用コマンド
```bash
# ドライランでAPI動作確認
python3 scripts/collect_daily_data.py --dry-run --verbose

# 単一アカウントでテスト
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --days 1 --verbose -y

# 結果をJSONで出力
python3 scripts/collect_historical_data.py --account ACCOUNT_ID --days 7 --output result.json -y
```

## 🔒 セキュリティ

### アクセストークン管理
- トークンは平文で保存されています（TODO: 暗号化実装予定）
- 定期的なトークン更新が必要
- トークンの漏洩を防ぐため、ログ出力に注意

### データベース保護
- 本番環境では適切な権限設定を実施
- バックアップの定期取得
- 不要なデータの定期削除

## 📞 サポート

### 問題発生時の連絡先
1. システム管理者への報告
2. GitHub Issues での問題報告
3. ログファイルの提供

### 緊急時対応
1. GitHub Actions の一時停止
2. 手動での緊急データ収集
3. データベースのバックアップからの復旧

---

*最終更新: 2025-06-25*  
*バージョン: 1.0*
