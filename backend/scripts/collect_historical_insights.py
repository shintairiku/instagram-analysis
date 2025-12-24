#!/usr/bin/env python3
"""
Instagram Historical Insights Collection Script
過去のアカウントレベルインサイト（follower_count, reach）を収集するスクリプト

Usage:
    # 単一アカウントの指定期間のインサイト収集
    python scripts/collect_historical_insights.py --account 17841435735142253 --from 2025-01-01 --to 2025-07-01

    # 全アカウントの指定期間のインサイト収集
    python scripts/collect_historical_insights.py --all-accounts --from 2025-01-01 --to 2025-07-01

    # 単一アカウントの過去93日間のインサイト収集
    python scripts/collect_historical_insights.py --account 17841435735142253 --days-back 93
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

from app.core.database import test_connection, get_db_sync
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_daily_stats_repository import InstagramDailyStatsRepository
from app.services.data_collection.instagram_api_client import InstagramAPIClient, InstagramAPIError

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('historical_insights_collection.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(
        description='Instagram Historical Insights Collection Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 単一アカウントの指定期間のインサイト収集
  python scripts/collect_historical_insights.py --account 17841435735142253 --from 2025-01-01 --to 2025-07-01

  # 全アカウントの指定期間のインサイト収集
  python scripts/collect_historical_insights.py --all-accounts --from 2025-01-01 --to 2025-07-01

  # 単一アカウントの過去93日間のインサイト収集
  python scripts/collect_historical_insights.py --account 17841435735142253 --days-back 93
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
    
    # 期間指定オプション（排他的）
    period_group = parser.add_mutually_exclusive_group()
    period_group.add_argument(
        '--days-back',
        type=int,
        help='過去n日間のデータを収集（最大93日）',
        metavar='DAYS'
    )
    
    # 開始・終了日付（days-backと排他的）
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
    
    return parser.parse_args()

def validate_date(date_string: str) -> date:
    """日付文字列の検証"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"無効な日付形式です: {date_string}. YYYY-MM-DD 形式を使用してください。")

def validate_arguments(args):
    """引数の検証"""
    # 期間指定の検証
    if args.days_back:
        if args.days_back < 1 or args.days_back > 93:
            raise ValueError("--days-back は 1 から 93 の間で指定してください。")
        # days-backの場合は、from/toを自動設定
        args.to_date = date.today()
        args.from_date = args.to_date - timedelta(days=args.days_back - 1)
    else:
        # from/toが指定されていない場合はデフォルトで過去30日
        if not args.from_date or not args.to_date:
            args.to_date = date.today()
            args.from_date = args.to_date - timedelta(days=29)  # 30日間
        else:
            # 日付の検証
            args.from_date = validate_date(args.from_date)
            args.to_date = validate_date(args.to_date)
    
    # 日付の順序確認
    if args.from_date > args.to_date:
        raise ValueError("開始日付は終了日付より前か、同じでなければなりません。")
    
    # 期間が93日を超えていないかチェック
    period_days = (args.to_date - args.from_date).days + 1
    if period_days > 93:
        raise ValueError("Instagram API の制限により、インサイトデータは最大93日間までしか取得できません。")

async def get_target_accounts(args) -> List[str]:
    """対象アカウントのリストを取得"""
    if args.account:
        return [args.account]
    elif args.all_accounts:
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
    print("📊 過去インサイトデータ収集計画")
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
    
    period_days = (args.to_date - args.from_date).days + 1
    print(f"📅 期間: {args.from_date} から {args.to_date} ({period_days} 日間)")
    print(f"📋 データ種別: アカウントレベルインサイト")
    print(f"   - follower_count: 日別フォロワー数変化")
    print(f"   - reach: 日別リーチ数")
    print("="*60)

class InsightsCollectionResult:
    """インサイト収集結果"""
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.instagram_user_id = account_id
        self.collection_type = "account_insights"
        self.start_date = None
        self.end_date = None
        self.total_days = 0
        self.processed_days = 0
        self.success_days = 0
        self.failed_days = 0
        self.duration_seconds = 0
        self.started_at = datetime.now()
        self.completed_at = None
        self.error_message = None
        self.collected_insights = []

async def collect_account_insights(
    account_id: str,
    start_date: date,
    end_date: date
) -> InsightsCollectionResult:
    """単一アカウントのインサイト収集"""
    result = InsightsCollectionResult(account_id)
    result.start_date = start_date
    result.end_date = end_date
    
    logger.info(f"🚀 アカウント: {account_id} のインサイト収集を開始します")
    logger.info(f"   期間: {start_date} から {end_date}")
    
    try:
        # データベース接続
        db = get_db_sync()
        account_repo = InstagramAccountRepository(db)
        daily_stats_repo = InstagramDailyStatsRepository(db)
        
        # アカウント取得
        account = await account_repo.get_by_instagram_user_id(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        # 対象日付リスト生成
        current_date = start_date
        target_dates = []
        while current_date <= end_date:
            target_dates.append(current_date)
            current_date += timedelta(days=1)
        
        result.total_days = len(target_dates)
        logger.info(f"   対象日数: {result.total_days} 日")
        
        async with InstagramAPIClient() as api_client:
            for target_date in target_dates:
                result.processed_days += 1
                
                try:
                    logger.debug(f"   処理中: {target_date} ({result.processed_days}/{result.total_days})")
                    
                    # 既存データチェック
                    existing_stats = await daily_stats_repo.get_by_specific_date(
                        account.id, target_date
                    )
                    
                    # インサイトデータ取得
                    insights_data = await api_client.get_insights_metrics(
                        account.instagram_user_id,
                        account.access_token_encrypted,
                        target_date
                    )
                    
                    # データベース保存
                    if existing_stats:
                        # 既存データの更新（現在のテーブル定義ではreach等は保持しない）
                        update_data = {
                            "followers_count": insights_data.get("follower_count", 0),
                            "data_sources": json.dumps(["api_insights"], ensure_ascii=False),
                        }
                        await daily_stats_repo.update(existing_stats.id, update_data)
                        logger.debug(f"     ✅ 更新: {target_date} - followers: {insights_data.get('follower_count', 0)}")
                    else:
                        # 新規データ作成
                        create_data = {
                            "account_id": account.id,
                            "stats_date": target_date,
                            "followers_count": insights_data.get("follower_count", 0),
                            "following_count": 0,
                            "media_count": 0,
                            "posts_count": 0,
                            "total_likes": 0,
                            "total_comments": 0,
                            "media_type_distribution": "{}",
                            "data_sources": json.dumps(["api_insights"], ensure_ascii=False),
                        }
                        await daily_stats_repo.create(create_data)
                        logger.debug(f"     ✅ 新規: {target_date} - followers: {insights_data.get('follower_count', 0)}")
                    
                    result.success_days += 1
                    result.collected_insights.append({
                        'date': target_date.isoformat(),
                        'reach': insights_data.get('reach', 0),
                        'follower_count': insights_data.get('follower_count', 0)
                    })
                    
                    # API制限対応：呼び出し間隔
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"     ❌ 失敗: {target_date} - {str(e)}")
                    result.failed_days += 1
        
        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        logger.info(f"✅ アカウント: {account_id} のインサイト収集が完了しました")
        logger.info(f"   成功: {result.success_days}/{result.total_days} 日")
        logger.info(f"   失敗: {result.failed_days} 日")
        logger.info(f"   実行時間: {result.duration_seconds:.2f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ アカウント: {account_id} のインサイト収集に失敗しました: {str(e)}")
        result.error_message = str(e)
        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        return result

def generate_output_filename(operation_type: str, account_info: str = None) -> str:
    """出力ファイル名を生成"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if operation_type == "single_account":
        filename = f"insights_collection_{account_info}_{timestamp}.json"
    elif operation_type == "all_accounts":
        filename = f"insights_collection_all_{timestamp}.json"
    else:
        filename = f"insights_collection_{timestamp}.json"
    
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

def format_single_result(result: InsightsCollectionResult, execution_time: float) -> Dict[str, Any]:
    """単一アカウントの結果を整形"""
    return {
        "metadata": {
            "operation_type": "account_insights_single",
            "execution_timestamp": datetime.now().isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "script_version": "1.0"
        },
        "account_info": {
            "account_id": result.account_id,
            "instagram_user_id": result.instagram_user_id
        },
        "collection_config": {
            "collection_type": result.collection_type,
            "date_range": {
                "start_date": result.start_date.isoformat() if result.start_date else None,
                "end_date": result.end_date.isoformat() if result.end_date else None,
                "total_days": result.total_days
            }
        },
        "execution_results": {
            "total_days": result.total_days,
            "processed_days": result.processed_days,
            "success_days": result.success_days,
            "failed_days": result.failed_days,
            "success_rate_percent": round(result.success_days / result.total_days * 100, 1) if result.total_days > 0 else 0
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
        "collected_data": {
            "insights_count": len(result.collected_insights),
            "insights": result.collected_insights
        }
    }

def format_bulk_results(all_results: List[InsightsCollectionResult], target_accounts: List[str], execution_time: float) -> Dict[str, Any]:
    """複数アカウントの結果を整形"""
    successful_accounts = len([r for r in all_results if r and r.error_message is None])
    failed_accounts = len(target_accounts) - successful_accounts
    
    total_days = sum(r.total_days for r in all_results if r)
    total_success = sum(r.success_days for r in all_results if r)
    total_failed = sum(r.failed_days for r in all_results if r)
    
    return {
        "metadata": {
            "operation_type": "account_insights_bulk",
            "execution_timestamp": datetime.now().isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "script_version": "1.0"
        },
        "summary": {
            "total_accounts": len(target_accounts),
            "successful_accounts": successful_accounts,
            "failed_accounts": failed_accounts,
            "account_success_rate_percent": round(successful_accounts / len(target_accounts) * 100, 1) if target_accounts else 0,
            "total_days": total_days,
            "successful_days": total_success,
            "failed_days": total_failed,
            "day_success_rate_percent": round(total_success / total_days * 100, 1) if total_days > 0 else 0
        },
        "account_results": [
            {
                "account_id": result.account_id,
                "instagram_user_id": result.instagram_user_id,
                "success": result.error_message is None,
                "total_days": result.total_days,
                "success_days": result.success_days,
                "failed_days": result.failed_days,
                "duration_seconds": result.duration_seconds,
                "error_message": result.error_message,
                "insights_collected": len(result.collected_insights)
            }
            for result in all_results if result
        ]
    }

def print_result_summary(result_data: Dict[str, Any]):
    """結果サマリーを表示"""
    print("\n" + "="*60)
    print("📊 INSIGHTS COLLECTION RESULTS SUMMARY")
    print("="*60)
    
    if "summary" in result_data:
        # 複数アカウントの場合
        summary = result_data["summary"]
        print(f"🎯 対象アカウント: {summary['total_accounts']}")
        print(f"✅ 成功アカウント: {summary['successful_accounts']}")
        print(f"❌ 失敗アカウント: {summary['failed_accounts']}")
        print(f"📈 アカウント成功率: {summary['account_success_rate_percent']}%")
        print(f"📊 対象日数: {summary['total_days']}")
        print(f"🎉 成功日数: {summary['successful_days']}")
        print(f"💥 失敗日数: {summary['failed_days']}")
        print(f"📈 日次成功率: {summary['day_success_rate_percent']}%")
    else:
        # 単一アカウントの場合
        results = result_data["execution_results"]
        print(f"🎯 対象アカウント: {result_data['account_info']['instagram_user_id']}")
        print(f"📊 対象日数: {results['total_days']}")
        print(f"✅ 成功日数: {results['success_days']}")
        print(f"❌ 失敗日数: {results['failed_days']}")
        print(f"📈 成功率: {results['success_rate_percent']}%")
        print(f"📋 収集データ数: {result_data['collected_data']['insights_count']}")
        print(f"⏱️ 実行時間: {result_data['timing']['duration_seconds']}s")
    
    print(f"⏱️ 合計実行時間: {result_data['metadata']['execution_time_seconds']}s")
    print("="*60)

async def main():
    """メイン処理"""
    start_time = datetime.now()
    
    try:
        args = parse_arguments()
        
        # ログレベル設定
        setup_logging(args.verbose)
        
        # 引数検証
        validate_arguments(args)
        
        logger.info("Instagram 過去インサイト収集スクリプトを開始します")
        
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
            response = input("\n過去インサイト収集を続行しますか？ (y/N): ")
            if response.lower() != 'y':
                print("収集をキャンセルしました。")
                return 0
        
        # データ収集実行
        if len(target_accounts) == 1:
            # 単一アカウント処理
            result = await collect_account_insights(
                target_accounts[0], 
                args.from_date, 
                args.to_date
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 結果整形
            result_data = format_single_result(result, execution_time)
            
            # ファイル名生成・保存
            filename = generate_output_filename("single_account", target_accounts[0])
            save_collection_result(result_data, filename)
            
            # 結果表示
            print_result_summary(result_data)
            
            return 0 if result.error_message is None else 1
        
        else:
            # 複数アカウント処理
            all_results = []
            
            for i, account_id in enumerate(target_accounts, 1):
                logger.info(f"アカウント: {i}/{len(target_accounts)}: {account_id} のインサイト収集を開始します")
                
                try:
                    result = await collect_account_insights(
                        account_id, 
                        args.from_date, 
                        args.to_date
                    )
                    all_results.append(result)
                    
                    # アカウント間の待機（最後以外）
                    if i < len(target_accounts):
                        logger.info("⏱️ 次のアカウントへの移行を10秒待ちます...")
                        await asyncio.sleep(10)
                        
                except Exception as e:
                    logger.error(f"アカウント: {account_id} のインサイト収集に失敗しました: {e}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 結果整形
            result_data = format_bulk_results(all_results, target_accounts, execution_time)
            
            # ファイル名生成・保存
            filename = generate_output_filename("all_accounts")
            save_collection_result(result_data, filename)
            
            # 結果表示
            print_result_summary(result_data)
            
            # 失敗したアカウントがある場合は exit code 1
            failed_accounts = len(target_accounts) - len([r for r in all_results if r.error_message is None])
            return 1 if failed_accounts > 0 else 0
        
    except KeyboardInterrupt:
        logger.info("収集をユーザーによって中断しました")
        return 130
    except Exception as e:
        logger.error(f"過去インサイト収集に致命的なエラーが発生しました: {str(e)}", exc_info=True)
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
