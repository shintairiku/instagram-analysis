"""
Supabase configuration and client management.

This project intentionally avoids direct PostgreSQL connections at runtime and uses
Supabase's official SDK instead (PostgREST / RPC).
"""

from __future__ import annotations

import logging
import os
from typing import Generator, Optional

from supabase import Client, create_client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for backend runtime.")

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Create (once) and return a Supabase client (service role)."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info("Supabase client initialized")
    return _supabase_client


def get_db() -> Generator[Client, None, None]:
    """
    Supabase client dependency for FastAPI's Depends.
    Kept as get_db() for compatibility with existing app structure.
    """
    yield get_supabase_client()


def get_db_sync() -> Client:
    """Supabase client for scripts / background tasks."""
    return get_supabase_client()


def test_connection() -> bool:
    """Test Supabase connectivity with a lightweight query."""
    try:
        client = get_supabase_client()
        # NOTE: This assumes the base schema has been applied. It's ok to fail on a fresh DB.
        client.table("instagram_accounts").select("id").limit(1).execute()
        logger.info("Supabase connection test successful")
        return True
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return False
