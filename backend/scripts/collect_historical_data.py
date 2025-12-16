#!/usr/bin/env python3
"""
Instagram Historical Data Collection Script (Enhanced)
過去の投稿データ・メトリクス・日次統計データを収集するスクリプト

Usage:
    # 単一アカウントの指定期間のデータ収集（投稿+日次統計）
    python scripts/collect_historical_data.py --account 17841435735142253 --from 2025-01-01 --to 2025-07-01

    # 全アカウントの指定期間のデータ収集
    python scripts/collect_historical_data.py --all-accounts --from 2025-01-01 --to 2025-07-01

    # メトリクス未取得投稿のみ収集
    python scripts/collect_historical_data.py --missing-metrics

    # 投稿のみ収集（日次統計なし）
    python scripts/collect_historical_data.py --account 17841435735142253 --from 2025-01-01 --to 2025-07-01 --posts-only

    # 日次統計のみ収集（新機能）
    python scripts/collect_historical_data.py --account 17841435735142253 --from 2025-01-01 --to 2025-07-01 --daily-stats-only
"""

import asyncio
import sys
import argparse
import logging
import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import json
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# .envファイルを読み込み
load_dotenv()

from app.services.data_collection.historical_collector_service import create_historical_collector
from app.core.database import test_connection, get_db_sync
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_daily_stats_repository import InstagramDailyStatsRepository
from app.services.data_collection.instagram_api_client import InstagramAPIClient

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('historical_collection.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """コマンドライン引数の解析（簡素化版）"""
    parser = argparse.ArgumentParser(
        description='Instagram Historical Data Collection Script (Simplified)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 単一アカウントの指定期間のデータ収集
  python scripts/collect_historical_data.py --account 17841435735142253 --from 2025-01-01 --to 2025-07-01

  # 全アカウントの指定期間のデータ収集
  python scripts/collect_historical_data.py --all-accounts --from 2025-01-01 --to 2025-07-01

  # メトリクス未取得投稿のみ収集
  python scripts/collect_historical_data.py --missing-metrics

  # 全アカウントのメトリクス未取得投稿のみ収集
  python scripts/collect_historical_data.py --all-accounts --missing-metrics
        """
    )
    
    # アカウント指定オプション（排他的）
    account_group = parser.add_mutually_exclusive_group(required=True)
    account_group.add_argument(
        '--account',
        type=str,
        help='Instagram User ID（単一アカウント）',
        metavar='USER_ID'
    )
    
    account_group.add_argument(
        '--all-accounts',
        action='store_true',
        help='全アクティブアカウントを対象に実行'
    )
    
    account_group.add_argument(
        '--missing-metrics',
        action='store_true',
        help='メトリクス未取得投稿のメトリクスのみ収集（全アカウント対象）'
    )
    
    # 期間指定オプション（missing-metricsの場合は不要）
    parser.add_argument(
        '--from',
        dest='from_date',
        type=str,
        help='開始日付 (YYYY-MM-DD形式)',
        metavar='YYYY-MM-DD'
    )
    
    parser.add_argument(
        '--to',
        dest='to_date',
        type=str,
        help='終了日付 (YYYY-MM-DD形式)',
        metavar='YYYY-MM-DD'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログ出力'
    )
    
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='確認プロンプトをスキップ'
    )
    
    # 新しいオプション: 収集データ種別
    parser.add_argument(
        '--posts-only',
        action='store_true',
        help='投稿データのみ収集（日次統計を作成しない）'
    )
    
    parser.add_argument(
        '--daily-stats-only',
        action='store_true',
        help='日次統計のみ作成（投稿データは既存データから集約）'
    )
    
    return parser.parse_args()

def validate_date(date_string: str) -> date:
    """日付文字列の検証"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"無効な日付形式です: {date_string}. YYYY-MM-DD 形式を使用してください。")

def validate_arguments(args):
    """引数の検証"""
    # missing-metrics以外の場合は期間指定が必要
    if not args.missing_metrics:
        if not args.from_date or not args.to_date:
            raise ValueError("--from と --to の日付が必要です。--missing-metrics を使用していない場合は、--from と --to の日付を指定してください。")
    
    # 日付の検証
    if args.from_date:
        args.from_date = validate_date(args.from_date)
    if args.to_date:
        args.to_date = validate_date(args.to_date)
        
    # 日付の順序確認
    if args.from_date and args.to_date and args.from_date > args.to_date:
        raise ValueError("開始日付は終了日付より前か、同じでなければなりません。")

async def get_target_accounts(args) -> List[str]:
    """対象アカウントのリストを取得"""
    if args.account:
        return [args.account]
    elif args.all_accounts or args.missing_metrics:
        # データベースから全アクティブアカウントを取得
        db = get_db_sync()
        repo = InstagramAccountRepository(db)
        accounts = await repo.get_active_accounts()
        return [str(account.instagram_user_id) for account in accounts]
    else:
        raise ValueError("アカウントが指定されていません。")

def setup_logging(verbose: bool):
    """ログレベル設定"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('app').setLevel(logging.DEBUG)
        logger.info("詳細ログ出力を有効にしました")

def print_collection_plan(args, target_accounts: List[str]):
    """収集計画の表示"""
    print("\n" + "="*60)
    print("📊 過去データ収集計画")
    print("="*60)
    
    if len(target_accounts) == 1:
        print(f"🎯 アカウント: {target_accounts[0]}")
    else:
        print(f"🎯 アカウント: {len(target_accounts)} アカウント")
        if len(target_accounts) <= 5:
            for i, account in enumerate(target_accounts, 1):
                print(f"   {i:2d}. {account}")
        else:
            for i, account in enumerate(target_accounts[:3], 1):
                print(f"   {i:2d}. {account}")
            print(f"   ... そして {len(target_accounts) - 3} アカウント")
    
    if args.missing_metrics:
        print(f"📋 モード: メトリクス未取得投稿のみ収集")
        print(f"📅 期間: 過去30日間（メトリクスのみ）")
    elif args.posts_only:
        print(f"📋 モード: 投稿データのみ収集")
        print(f"📅 期間: {args.from_date} から {args.to_date}")
        print(f"🔄 処理: 投稿データ + メトリクス収集")
    elif args.daily_stats_only:
        print(f"📋 モード: 日次統計のみ作成")
        print(f"📅 期間: {args.from_date} から {args.to_date}")
        print(f"🔄 処理: 既存投稿データから日次統計を集約")
    else:
        print(f"📋 モード: 完全データ収集（投稿 + 日次統計）")
        print(f"📅 期間: {args.from_date} から {args.to_date}")
        print(f"🔄 処理: 投稿データ収集 → メトリクス取得 → 日次統計作成")
    
    print("="*60)

def generate_output_filename(operation_type: str, account_info: str = None) -> str:
    """出力ファイル名を生成"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if operation_type == "missing_metrics":
        filename = f"missing_etrics_collection_{timestamp}.json"
    elif operation_type == "single_account":
        filename = f"single_account_collection_{account_info}_{timestamp}.json"
    elif operation_type == "all_accounts":
        filename = f"all_accounts_collection_{timestamp}.json"
    else:
        filename = f"historical_collection_{timestamp}.json"
    
    return filename

def save_collection_result(result_data: Dict[str, Any], filename: str):
    """収集結果をJSONファイルに保存"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"結果を保存しました: {output_path}")
    print(f"📁 結果を保存しました: {output_path}")

def format_single_result(result, operation_type: str, execution_time: float) -> Dict[str, Any]:
    """単一アカウントの結果を整形"""
    # 日次統計結果の場合（dict形式）
    if isinstance(result, dict):
        return {
            "metadata": {
                "operation_type": operation_type,
                "execution_timestamp": datetime.now().isoformat(),
                "execution_time_seconds": round(execution_time, 2),
                "script_version": "2.0-enhanced"
            },
            "account_info": {
                "account_id": result.get('account_id'),
                "instagram_user_id": result.get('account_id')
            },
            "collection_config": {
                "collection_type": "daily_stats_aggregation",
                "date_range": {
                    "start_date": result.get('start_date').isoformat() if result.get('start_date') else None,
                    "end_date": result.get('end_date').isoformat() if result.get('end_date') else None
                }
            },
            "execution_results": {
                "total_days": result.get('total_days', 0),
                "processed_days": result.get('processed_days', 0),
                "success_days": result.get('success_days', 0),
                "failed_days": result.get('failed_days', 0),
                "success_rate_percent": round(result.get('success_days', 0) / result.get('total_days', 1) * 100, 1) if result.get('total_days', 0) > 0 else 0
            },
            "status": {
                "completed_successfully": result.get('error_message') is None,
                "error_message": result.get('error_message')
            },
            "collected_data": {
                "current_account_data": result.get('current_account_data', {}),
                "daily_stats": result.get('daily_stats', [])
            }
        }
    
    # 従来の投稿収集結果の場合（オブジェクト形式）
    else:
        return {
            "metadata": {
                "operation_type": operation_type,
                "execution_timestamp": datetime.now().isoformat(),
                "execution_time_seconds": round(execution_time, 2),
                "script_version": "2.0-enhanced"
            },
            "account_info": {
                "account_id": result.account_id,
                "instagram_user_id": result.instagram_user_id
            },
            "collection_config": {
                "collection_type": result.collection_type,
                "date_range": {
                    "start_date": result.start_date.isoformat() if result.start_date else None,
                    "end_date": result.end_date.isoformat() if result.end_date else None
                }
            },
            "execution_results": {
                "total_items": result.total_items,
                "processed_items": result.processed_items,
                "success_items": result.success_items,
                "failed_items": result.failed_items,
                "success_rate_percent": round(result.success_items / result.total_items * 100, 1) if result.total_items > 0 else 0
            },
            "timing": {
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "duration_seconds": result.duration_seconds
            },
            "status": {
                "completed_successfully": result.error_message is None,
                "error_message": result.error_message
            },
            "additional_data": getattr(result, 'additional_data', None)
        }

def format_bulk_results(all_results: List, target_accounts: List[str], operation_type: str, execution_time: float) -> Dict[str, Any]:
    """複数アカウントの結果を整形"""
    successful_accounts = len([r for r in all_results if r and r.error_message is None])
    failed_accounts = len(target_accounts) - successful_accounts
    
    total_items = sum(r.total_items for r in all_results if r)
    total_success = sum(r.success_items for r in all_results if r)
    total_failed = sum(r.failed_items for r in all_results if r)
    
    return {
        "metadata": {
            "operation_type": operation_type,
            "execution_timestamp": datetime.now().isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "script_version": "2.0-simplified"
        },
        "summary": {
            "total_accounts": len(target_accounts),
            "successful_accounts": successful_accounts,
            "failed_accounts": failed_accounts,
            "account_success_rate_percent": round(successful_accounts / len(target_accounts) * 100, 1) if target_accounts else 0,
            "total_data_items": total_items,
            "successful_data_items": total_success,
            "failed_data_items": total_failed,
            "data_success_rate_percent": round(total_success / total_items * 100, 1) if total_items > 0 else 0
        },
        "account_results": [
            {
                "account_id": result.account_id,
                "instagram_user_id": result.instagram_user_id,
                "success": result.error_message is None,
                "total_items": result.total_items,
                "success_items": result.success_items,
                "failed_items": result.failed_items,
                "duration_seconds": result.duration_seconds,
                "error_message": result.error_message
            }
            for result in all_results if result
        ],
        "failed_accounts": [
            account_id for account_id in target_accounts 
            if not any(r and r.account_id == account_id for r in all_results)
        ]
    }

def print_result_summary(result_data: Dict[str, Any]):
    """結果サマリーを表示"""
    print("\n" + "="*60)
    print("📊 COLLECTION RESULTS SUMMARY")
    print("="*60)
    
    if "summary" in result_data:
        # 複数アカウントの場合
        summary = result_data["summary"]
        print(f"🎯 対象アカウント: {summary['total_accounts']}")
        print(f"✅ 成功アカウント: {summary['successful_accounts']}")
        print(f"❌ 失敗アカウント: {summary['failed_accounts']}")
        print(f"📈 アカウント成功率: {summary['account_success_rate_percent']}%")
        print(f"📊 データ件数: {summary['total_data_items']}")
        print(f"🎉 成功データ件数: {summary['successful_data_items']}")
        print(f"💥 失敗データ件数: {summary['failed_data_items']}")
        print(f"📈 データ成功率: {summary['data_success_rate_percent']}%")
    else:
        # 単一アカウントの場合
        results = result_data["execution_results"]
        print(f"🎯 対象アカウント: {result_data['account_info']['instagram_user_id']}")
        
        # 日次統計の場合とその他の場合で表示を分ける
        if "total_days" in results:
            # 日次統計の場合
            print(f"📅 対象日数: {results['total_days']}")
            print(f"✅ 成功日数: {results['success_days']}")
            print(f"❌ 失敗日数: {results['failed_days']}")
            print(f"📈 成功率: {results['success_rate_percent']}%")
            
            # 現在のアカウントデータ表示
            if "collected_data" in result_data and result_data["collected_data"]["current_account_data"]:
                current_data = result_data["collected_data"]["current_account_data"]
                print(f"👥 現在のフォロワー数: {current_data.get('followers_count', 'N/A')}")
                print(f"📝 総投稿数: {current_data.get('media_count', 'N/A')}")
            
            # 日次統計サマリー
            daily_stats = result_data["collected_data"]["daily_stats"]
            if daily_stats:
                total_posts = sum(stat['posts_count'] for stat in daily_stats)
                total_likes = sum(stat['total_likes'] for stat in daily_stats)
                total_comments = sum(stat['total_comments'] for stat in daily_stats)
                print(f"📊 期間内投稿数: {total_posts}")
                print(f"👍 期間内いいね数: {total_likes}")
                print(f"💬 期間内コメント数: {total_comments}")
        else:
            # 従来の投稿収集の場合
            print(f"📊 データ件数: {results['total_items']}")
            print(f"✅ 成功データ件数: {results['success_items']}")
            print(f"❌ 失敗データ件数: {results['failed_items']}")
            print(f"📈 データ成功率: {results['success_rate_percent']}%")
            
            if "timing" in result_data:
                print(f"⏱️ 実行時間: {result_data['timing']['duration_seconds']}s")
    
    print(f"⏱️ 合計実行時間: {result_data['metadata']['execution_time_seconds']}s")
    print("="*60)

async def collect_daily_stats_from_posts(
    account_id: str, 
    start_date: date, 
    end_date: date
) -> Dict[str, Any]:
    """既存の投稿データから日次統計を作成"""
    logger.info(f"📊 日次統計作成開始: {account_id} ({start_date} から {end_date})")
    
    result = {
        'account_id': account_id,
        'start_date': start_date,
        'end_date': end_date,
        'total_days': 0,
        'processed_days': 0,
        'success_days': 0,
        'failed_days': 0,
        'current_account_data': {},
        'daily_stats': []
    }
    
    try:
        # データベース接続
        db = get_db_sync()
        account_repo = InstagramAccountRepository(db)
        daily_stats_repo = InstagramDailyStatsRepository(db)
        
        # アカウント取得
        account = await account_repo.get_by_instagram_user_id(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        # 現在のアカウントデータ取得（基本情報）
        async with InstagramAPIClient() as api_client:
            try:
                current_basic_data = await api_client.get_basic_account_data(
                    account.instagram_user_id,
                    account.access_token_encrypted
                )
                result['current_account_data'] = current_basic_data
                logger.info(f"現在のアカウントデータ: followers={current_basic_data.get('followers_count')}, posts={current_basic_data.get('media_count')}")
            except Exception as e:
                logger.warning(f"基本アカウントデータ取得失敗: {e}")
                current_basic_data = {}
        
        # 全投稿データ取得
        async with InstagramAPIClient() as api_client:
            logger.info("全投稿データを取得中...")
            url = api_client.config.get_user_media_url(account.instagram_user_id)
            all_posts = []
            next_url = None
            page_count = 0
            
            while True:
                page_count += 1
                params = {
                    'fields': 'id,media_type,permalink,caption,timestamp,like_count,comments_count',
                    'access_token': account.access_token_encrypted,
                    'limit': 100
                }
                
                try:
                    if next_url:
                        response = await api_client._make_request(next_url, {})
                    else:
                        response = await api_client._make_request(url, params)
                    
                    posts = response.get('data', [])
                    all_posts.extend(posts)
                    
                    logger.debug(f"Page {page_count}: {len(posts)} posts retrieved")
                    
                    paging = response.get('paging', {})
                    next_url = paging.get('next')
                    
                    if not next_url:
                        break
                    
                    await asyncio.sleep(1)  # レート制限対応
                    
                except Exception as e:
                    logger.error(f"投稿データ取得エラー (page {page_count}): {e}")
                    break
            
            logger.info(f"取得完了: {len(all_posts)} 件の投稿")
        
        # 日付ごとに投稿データを集約
        current_date = start_date
        while current_date <= end_date:
            result['total_days'] += 1
            result['processed_days'] += 1
            
            try:
                # その日の投稿をフィルタリング
                daily_posts = []
                for post in all_posts:
                    timestamp = post.get('timestamp', '')
                    if timestamp:
                        try:
                            post_date_str = timestamp.split('T')[0]
                            post_date = date.fromisoformat(post_date_str)
                            if post_date == current_date:
                                daily_posts.append(post)
                        except:
                            continue
                
                # 日次統計計算
                posts_count = len(daily_posts)
                total_likes = sum(p.get('like_count', 0) for p in daily_posts)
                total_comments = sum(p.get('comments_count', 0) for p in daily_posts)
                
                # メディアタイプ分布
                media_types = {}
                for post in daily_posts:
                    media_type = post.get('media_type', 'UNKNOWN')
                    media_types[media_type] = media_types.get(media_type, 0) + 1
                
                # データベース保存
                stats_data = {
                    'account_id': account.id,
                    'stats_date': current_date,
                    'followers_count': current_basic_data.get('followers_count', 0),  # 現在値
                    'following_count': current_basic_data.get('follows_count', 0),    # 現在値
                    'media_count': current_basic_data.get('media_count', 0),          # 現在値
                    'posts_count': posts_count,
                    'total_likes': total_likes,
                    'total_comments': total_comments,
                    'media_type_distribution': json.dumps(media_types),
                    'data_sources': json.dumps(['posts_aggregation'])
                }
                
                # 既存データチェックして作成または更新
                existing_stats = await daily_stats_repo.get_by_specific_date(account.id, current_date)
                
                if existing_stats:
                    # 更新
                    updated_stats = await daily_stats_repo.update(existing_stats.id, stats_data)
                    logger.debug(f"✅ 更新: {current_date} - {posts_count}投稿, {total_likes}いいね, {total_comments}コメント")
                else:
                    # 新規作成
                    new_stats = await daily_stats_repo.create(stats_data)
                    logger.debug(f"✅ 新規: {current_date} - {posts_count}投稿, {total_likes}いいね, {total_comments}コメント")
                
                result['success_days'] += 1
                result['daily_stats'].append({
                    'date': current_date.isoformat(),
                    'posts_count': posts_count,
                    'total_likes': total_likes,
                    'total_comments': total_comments,
                    'media_types': media_types
                })
                
            except Exception as e:
                logger.error(f"❌ 日次統計作成失敗: {current_date} - {str(e)}")
                result['failed_days'] += 1
            
            current_date += timedelta(days=1)
        
        logger.info(f"✅ 日次統計作成完了: {result['success_days']}/{result['total_days']} 日")
        return result
        
    except Exception as e:
        logger.error(f"❌ 日次統計作成に失敗しました: {str(e)}")
        result['error_message'] = str(e)
        return result

async def collect_single_account(account_id: str, args) -> Optional[any]:
    """単一アカウントのデータ収集"""
    logger.info(f"🚀 アカウント: {account_id} のデータ収集を開始します")
    
    try:
        if args.daily_stats_only:
            # 日次統計のみ作成
            result = await collect_daily_stats_from_posts(
                account_id=account_id,
                start_date=args.from_date,
                end_date=args.to_date
            )
            return result
        
        else:
            # 従来の投稿データ収集
            collector = create_historical_collector()
            
            if args.missing_metrics:
                result = await collector.collect_missing_metrics(
                    account_id=account_id,
                    days_back=30
                )
            else:
                include_metrics = not args.posts_only
                result = await collector.collect_historical_posts(
                    account_id=account_id,
                    start_date=args.from_date,
                    end_date=args.to_date,
                    include_metrics=include_metrics,
                    chunk_size=50
                )
            
            # 投稿データ収集後、日次統計も作成（posts-onlyでない場合）
            if not args.posts_only and not args.missing_metrics:
                logger.info("投稿データ収集完了。日次統計を作成中...")
                daily_stats_result = await collect_daily_stats_from_posts(
                    account_id=account_id,
                    start_date=args.from_date,
                    end_date=args.to_date
                )
                
                # 結果をマージ
                result.additional_data = daily_stats_result
            
            logger.info(f"✅ アカウント: {account_id} のデータ収集が完了しました: {result.success_items}/{result.total_items} 件")
            return result
        
    except Exception as e:
        logger.error(f"❌ アカウント: {account_id} のデータ収集に失敗しました: {str(e)}")
        return None

async def collect_multiple_accounts(target_accounts: List[str], args) -> List:
    """複数アカウントの順次データ収集"""
    logger.info(f"🏁 {len(target_accounts)} アカウントのデータ収集を開始します")
    
    all_results = []
    
    for i, account_id in enumerate(target_accounts, 1):
        logger.info(f"アカウント: {i}/{len(target_accounts)}: {account_id} のデータ収集を開始します")
        
        try:
            result = await collect_single_account(account_id, args)
            if result:
                all_results.append(result)
            
            # アカウント間の待機（最後以外）
            if i < len(target_accounts):
                logger.info("⏱️ 次のアカウントへの移行を10秒待ちます...")
                await asyncio.sleep(10)
                
        except Exception as e:
            logger.error(f"アカウント: {account_id} のデータ収集に失敗しました: {e}")
    
    return all_results

async def main():
    """メイン処理"""
    start_time = datetime.now()
    
    try:
        args = parse_arguments()
        
        # ログレベル設定
        setup_logging(args.verbose)
        
        # 引数検証
        validate_arguments(args)
        
        logger.info("Instagram 過去データ収集スクリプトを開始します")
        
        # データベース接続テスト
        logger.info("データベース接続をテストします...")
        if not test_connection():
            logger.error("データベース接続に失敗しました")
            return 1
        logger.info("データベース接続に成功しました")
        
        # 対象アカウント取得
        target_accounts = await get_target_accounts(args)
        logger.info(f"対象アカウント: {len(target_accounts)} アカウント")
        
        # 収集計画表示
        print_collection_plan(args, target_accounts)
        
        # 確認プロンプト
        if not args.yes:
            response = input("\n過去データ収集を続行しますか？ (y/N): ")
            if response.lower() != 'y':
                print("収集をキャンセルしました。")
                return 0
        
        # データ収集実行
        if len(target_accounts) == 1:
            # 単一アカウント処理
            result = await collect_single_account(target_accounts[0], args)
            
            if result:
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # 結果整形
                if args.missing_metrics:
                    operation_type = "missing_metrics_single"
                else:
                    operation_type = "single_account"
                
                result_data = format_single_result(result, operation_type, execution_time)
                
                # ファイル名生成・保存
                filename = generate_output_filename(operation_type, target_accounts[0])
                save_collection_result(result_data, filename)
                
                # 結果表示
                print_result_summary(result_data)
                
                # エラーチェック: dict形式とオブジェクト形式の両方に対応
                if isinstance(result, dict):
                    return 0 if result.get('error_message') is None else 1
                else:
                    return 0 if result.error_message is None else 1
            else:
                logger.error("収集に失敗しました")
                return 1
        
        else:
            # 複数アカウント処理
            all_results = await collect_multiple_accounts(target_accounts, args)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 結果整形
            if args.missing_metrics:
                operation_type = "missing_metrics_all"
            else:
                operation_type = "all_accounts"
            
            result_data = format_bulk_results(all_results, target_accounts, operation_type, execution_time)
            
            # ファイル名生成・保存
            filename = generate_output_filename(operation_type)
            save_collection_result(result_data, filename)
            
            # 結果表示
            print_result_summary(result_data)
            
            # 失敗したアカウントがある場合は exit code 1
            failed_accounts = len(target_accounts) - len(all_results)
            return 1 if failed_accounts > 0 else 0
        
    except KeyboardInterrupt:
        logger.info("収集をユーザーによって中断しました")
        return 130
    except Exception as e:
        logger.error(f"過去データ収集に致命的なエラーが発生しました: {str(e)}", exc_info=True)
        return 1

def cli_entry_point():
    """CLI エントリーポイント"""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ 収集をユーザーによって中断しました")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 致命的なエラー: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    cli_entry_point()
