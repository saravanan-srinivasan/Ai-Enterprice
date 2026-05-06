#!/usr/bin/env python3
"""
scripts/seed_data.py
---------------------
Seeds the vector store and PostgreSQL with the sample enterprise datasets.
Run once after setup, or re-run to refresh sample data.
"""

import asyncio
import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("VECTOR_STORE_TYPE", "chroma")
os.environ.setdefault("CHROMA_PERSIST_DIR", "./data/chroma")
os.environ.setdefault("UPLOAD_DIR", "./data/uploads")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://enterprise_user:enterprise_pass@localhost:5432/enterprise_ai")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample"

SAMPLE_FILES = [
    ("logistics_delays.json",           "logistics"),
    ("finance_report_q1_2024.json",     "finance"),
    ("vendor_master_data.csv",          "vendor_management"),
    ("supply_chain_policy.txt",         "policy"),
    ("operational_logs_2024-01-15.log", "operations"),
]


async def seed():
    from utils.database import create_all_tables, db_session_context
    from ingestion_service.ingestor import DocumentIngestor

    print("\n📦 Enterprise AI — Data Seeder")
    print("=" * 45)

    await create_all_tables()
    ingestor = DocumentIngestor()

    seeded = 0
    failed = 0

    for filename, source_tag in SAMPLE_FILES:
        filepath = SAMPLE_DIR / filename
        if not filepath.exists():
            print(f"  ⚠️  Sample file not found: {filename}")
            failed += 1
            continue

        file_bytes = filepath.read_bytes()
        print(f"\n  → Ingesting: {filename} ({len(file_bytes):,} bytes) [{source_tag}]")

        try:
            async with db_session_context() as db:
                result = await ingestor.ingest(
                    file_bytes=file_bytes,
                    filename=filename,
                    db=db,
                    source_metadata={"source_tag": source_tag, "seeded": True},
                )
            print(f"     ✅ {result.message}")
            seeded += 1
        except Exception as exc:
            print(f"     ❌ Failed: {exc}")
            failed += 1

    print(f"\n{'=' * 45}")
    print(f"  Seeded: {seeded} documents")
    if failed:
        print(f"  Failed: {failed} documents")
    print(f"  Vector store ready for querying\n")


if __name__ == "__main__":
    asyncio.run(seed())
