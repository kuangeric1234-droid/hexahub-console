"""
Seed runner — explicit, never auto-runs in production.

Usage::

    # From backend/ directory
    python db/seeds/run_seeds.py

    # Or with a specific DATABASE_URL
    DATABASE_URL=postgresql://... python db/seeds/run_seeds.py

Idempotent: skips words that already exist (match on word + language).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
from backend.config import settings
from backend.db.seeds.sensitive_words import SENSITIVE_WORDS


def run() -> None:
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    print(f"Connecting to: {sync_url.split('@')[-1]}")  # hide credentials

    conn = psycopg2.connect(sync_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            inserted = 0
            skipped  = 0

            for w in SENSITIVE_WORDS:
                cur.execute(
                    "SELECT 1 FROM sensitive_words WHERE word = %s AND language = %s",
                    (w["word"], w["language"]),
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO sensitive_words (id, word, language, severity, category, created_at)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, NOW())
                    """,
                    (w["word"], w["language"], w["severity"], w["category"]),
                )
                inserted += 1

        conn.commit()
        print(f"Done. Inserted: {inserted}  Skipped (already exist): {skipped}")

    except Exception as exc:
        conn.rollback()
        print(f"Seed failed: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
