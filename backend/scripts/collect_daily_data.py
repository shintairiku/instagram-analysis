#!/usr/bin/env python3
"""
Daily Data Collection Script
GitHub Actions で実行される日次データ収集のエントリーポイント

Usage:
    python scripts/collect_daily_data.py --date 2024-01-20
    python scripts/collect_daily_data.py --accounts user1,user2 --dry-run
    python scripts/collect_daily_data.py --help
"""

import asyncio
import sys
import argparse
import logging
import os
from datetime import datetime, date, timedelta
from typing import List, Optional
import json

# プロジェクトルートディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.data_collection.daily_collector_service import create_daily_collector
from app.core.database import test_connection

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('daily_collection.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(
        description='Instagram Daily Data Collection Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 昨日のデータ収集
  python scripts/collect_daily_data.py

  # 指定日のデータ収集
  python scripts/collect_daily_data.py --date 2024-01-20

  # 特定アカウントのみ収集
  python scripts/collect_daily_data.py --accounts user123,user456

  # ドライランで実行（データベース保存なし）
  python scripts/collect_daily_data.py --dry-run

  # 詳細ログ出力
  python scripts/collect_daily_data.py --verbose
        """
    )
    
    parser.add_argument(
        '--date',
        type=str,
        help='対象日付 (YYYY-MM-DD形式、未指定時は昨日)',
        metavar='YYYY-MM-DD'
    )
    
    parser.add_argument(
        '--accounts',
        type=str,
        help='収集対象アカウント (instagram_user_idをカンマ区切り)',
        metavar='user1,user2,user3'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='ドライラン実行（データベースに保存しない）'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログ出力'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='結果をJSONファイルに出力',
        metavar='output.json'
    )
    
    return parser.parse_args()

def validate_date(date_string: str) -> date:
    """日付文字列の検証"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD format.")

def parse_accounts(accounts_string: str) -> List[str]:
    """アカウント文字列の解析"""
    if not accounts_string:
        return []
    
    accounts = [acc.strip() for acc in accounts_string.split(',') if acc.strip()]
    logger.info(f"Parsed {len(accounts)} account filters: {accounts}")
    return accounts

def setup_logging(verbose: bool):
    """ログレベル設定"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('app').setLevel(logging.DEBUG)
        logger.info("Verbose logging enabled")

def format_summary_for_output(summary) -> dict:
    """サマリーを出力用に整形"""
    return {
        'target_date': summary.target_date.isoformat(),
        'execution_summary': {
            'started_at': summary.started_at.isoformat(),
            'completed_at': summary.completed_at.isoformat() if summary.completed_at else None,
            'total_duration_seconds': summary.total_duration_seconds,
        },
        'collection_summary': {
            'total_accounts': summary.total_accounts,
            'successful_accounts': summary.successful_accounts,
            'failed_accounts': summary.failed_accounts,
            'success_rate': round(summary.successful_accounts / summary.total_accounts * 100, 2) if summary.total_accounts > 0 else 0
        },
        'account_results': [
            {
                'account_id': result.account_id,
                'instagram_user_id': result.instagram_user_id,
                'success': result.success,
                'collected_at': result.collected_at.isoformat(),
                'error_message': result.error_message,
                'data_summary': result.data_summary
            }
            for result in summary.collection_results
        ]
    }

def print_summary(summary):
    """実行結果サマリーを表示"""
    print("\n" + "="*60)
    print("📊 DAILY DATA COLLECTION SUMMARY")
    print("="*60)
    
    print(f"📅 Target Date: {summary.target_date}")
    print(f"⏱️  Duration: {summary.total_duration_seconds:.2f} seconds")
    print(f"🎯 Total Accounts: {summary.total_accounts}")
    print(f"✅ Successful: {summary.successful_accounts}")
    print(f"❌ Failed: {summary.failed_accounts}")
    
    if summary.total_accounts > 0:
        success_rate = (summary.successful_accounts / summary.total_accounts) * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
    
    print("\n📋 Account Details:")
    print("-" * 60)
    
    for result in summary.collection_results:
        status_icon = "✅" if result.success else "❌"
        print(f"{status_icon} {result.instagram_user_id}")
        
        if result.success and result.data_summary:
            print(f"   📊 Data: {result.data_summary.get('posts_count', 0)} posts, "
                  f"{result.data_summary.get('follower_count', 0)} followers")
        elif result.error_message:
            print(f"   💥 Error: {result.error_message}")
    
    print("="*60)

async def main():
    """メイン処理"""
    args = parse_arguments()
    
    # ログレベル設定
    setup_logging(args.verbose)
    
    # 環境変数チェック
    required_env_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return 1
    
    logger.info("Starting Instagram daily data collection script")
    
    try:
        # データベース接続テスト
        logger.info("Testing database connection...")
        if not test_connection():
            logger.error("Database connection failed")
            return 1
        logger.info("Database connection successful")
        
        # 引数解析
        target_date = None
        if args.date:
            target_date = validate_date(args.date)
        else:
            # デフォルトは昨日
            target_date = (datetime.now() - timedelta(days=1)).date()
        
        account_filter = parse_accounts(args.accounts) if args.accounts else None
        
        logger.info(f"Collection parameters:")
        logger.info(f"  Target Date: {target_date}")
        logger.info(f"  Account Filter: {account_filter or 'All active accounts'}")
        logger.info(f"  Dry Run: {args.dry_run}")
        
        # データ収集実行
        collector = create_daily_collector()
        
        logger.info("🚀 Starting data collection...")
        summary = await collector.collect_daily_data(
            target_date=target_date,
            account_filter=account_filter,
            dry_run=args.dry_run
        )
        
        # 結果表示
        print_summary(summary)
        
        # JSONファイル出力
        if args.output:
            output_data = format_summary_for_output(summary)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {args.output}")
        
        # GitHub Actions用の出力設定
        if os.getenv('GITHUB_ACTIONS'):
            # GitHub Actions の output として結果を設定
            print(f"::set-output name=success_rate::{summary.successful_accounts}/{summary.total_accounts}")
            print(f"::set-output name=duration::{summary.total_duration_seconds:.2f}")
            
            # 失敗した場合は exit code 1
            if summary.failed_accounts > 0:
                logger.warning(f"Collection completed with {summary.failed_accounts} failed accounts")
                return 1
        
        logger.info("Daily data collection completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Critical error in daily data collection: {str(e)}", exc_info=True)
        return 1

def cli_entry_point():
    """CLI エントリーポイント"""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Collection interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    cli_entry_point()
