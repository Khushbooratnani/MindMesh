"""MindMesh Phase 2 Bulk Indexing & Verification Tool.

Indexes ALL completed Phase 1 MemoryV1 records currently in PostgreSQL (target: 106)
into phase2_embeddings using real BAAI/bge-m3 dual 1024-dimensional embeddings.

Guarantees:
- Indexes ALL 106 completed records from phase1_outputs (evaluation dataset + manual/iPhone records).
- Excludes failed Phase 1 records (e.g. image rows 12, 13, 27 which failed LLM extraction).
- Skips already-indexed records (idempotent, 0 duplicates).
- Requires real BAAI/bge-m3 model (dimension=1024, no mock embeddings).
- Dual vector columns (content_vector 1024, context_vector 1024).
- Resilient per-row commit (failures logged without stopping remaining rows).
- Read-only PostgreSQL verification of all 4 SQL target metrics after execution.
"""

import asyncio
import logging
from pathlib import Path
import sys
from typing import Any
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Ensure backend root is in sys.path
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.config import settings
from app.database.connection.session import create_async_engine_instance
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.phase2_embedding import Phase2EmbeddingModel
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.services.embedding_service import EmbeddingService
from app.services.phase2_service import Phase2Service

logger = logging.getLogger(__name__)


async def index_all_phase1_records(
    database_url: str | None = None,
) -> dict[str, Any]:
    """Indexes all completed phase1_outputs into phase2_embeddings."""
    db_url = database_url or settings.database_url
    engine = create_async_engine_instance(database_url=db_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    print("=" * 80)
    print("      MINDMESH PHASE 2 — DUAL-VECTOR INDEXING (ALL COMPLETED RECORDS)")
    print("=" * 80)

    # 1. Query all completed Phase 1 outputs directly from PostgreSQL
    print("\n[1/4] Querying all completed Phase 1 records from PostgreSQL...")
    async with session_maker() as session:
        stmt = (
            select(Phase1OutputModel)
            .where(Phase1OutputModel.processing_status == "completed")
            .order_by(Phase1OutputModel.created_at.asc())
        )
        result = await session.execute(stmt)
        completed_p1_records = result.scalars().all()

        initial_p2_count = (await session.execute(select(func.count(Phase2EmbeddingModel.id)))).scalar() or 0

    total_completed = len(completed_p1_records)
    print(f"Total completed phase1_outputs in PostgreSQL : {total_completed}")
    print(f"Existing phase2_embeddings before operation   : {initial_p2_count}")

    # 2. Initialize real BAAI/bge-m3 embedding service
    print("\n[2/4] Initializing EmbeddingService (BAAI/bge-m3, dimension=1024, force_mock=False)...")
    embedding_service = EmbeddingService(
        model_name="BAAI/bge-m3",
        dimension=1024,
        force_mock=False,
    )

    newly_indexed = 0
    skipped_existing = 0
    failed_records: list[dict[str, Any]] = []

    # 3. Index each completed record
    print(f"\n[3/4] Processing {total_completed} completed memories into dual 1024-dim vectors...")
    for idx, p1_record in enumerate(completed_p1_records, start=1):
        p1_id = p1_record.id
        mem_id = p1_record.memory_id
        media_type = p1_record.payload.get("system", {}).get("media_type", "unknown").upper() if p1_record.payload else "UNKNOWN"

        print(f"  [{idx:03d}/{total_completed:03d}] ({media_type:5s}) mem={mem_id} p1_id={str(p1_id)[:8]}...", end=" ", flush=True)

        async with session_maker() as session:
            p1_repo = Phase1OutputRepository(session)
            p2_repo = Phase2EmbeddingRepository(session)
            phase2_service = Phase2Service(
                phase1_output_repo=p1_repo,
                phase2_embedding_repo=p2_repo,
                embedding_service=embedding_service,
                session=session,
            )

            # Check if already indexed
            existing = await p2_repo.get_by_phase1_output_id(p1_id)
            if existing is not None:
                content_dim = len(existing.content_vector) if existing.content_vector is not None else 0
                context_dim = len(existing.context_vector) if existing.context_vector is not None else 0
                if content_dim == 1024 and context_dim == 1024 and existing.embedding_model == "BAAI/bge-m3":
                    skipped_existing += 1
                    print("-> SKIPPED (Already indexed & valid)")
                    continue
                else:
                    print(f"-> MALFORMED RECORD (dim={content_dim}/{context_dim}, model={existing.embedding_model})")
                    failed_records.append({
                        "memory_id": mem_id,
                        "phase1_output_id": str(p1_id),
                        "error": f"Malformed existing record: dim=({content_dim}, {context_dim}), model={existing.embedding_model}",
                    })
                    continue

            # Generate and store embedding
            try:
                res = await phase2_service.process_phase1_output_id(p1_id)
                await session.commit()
                newly_indexed += 1
                print(f"-> INDEXED (emb_id={str(res.embedding_id)[:8]})")
            except Exception as e:
                await session.rollback()
                print(f"-> FAILED ({type(e).__name__}: {str(e)})")
                failed_records.append({
                    "memory_id": mem_id,
                    "phase1_output_id": str(p1_id),
                    "error": str(e),
                })

    # 4. Post-Indexing Database Verification
    print("\n[4/4] Executing Read-Only PostgreSQL Verification...")
    async with session_maker() as session:
        final_completed_p1 = (await session.execute(
            select(func.count(Phase1OutputModel.id)).where(Phase1OutputModel.processing_status == "completed")
        )).scalar() or 0
        final_p2_count = (await session.execute(select(func.count(Phase2EmbeddingModel.id)))).scalar() or 0
        distinct_p1_ids = (await session.execute(select(func.count(func.distinct(Phase2EmbeddingModel.phase1_output_id))))).scalar() or 0
        distinct_mem_ids = (await session.execute(select(func.count(func.distinct(Phase2EmbeddingModel.memory_id))))).scalar() or 0

        # Check vector dimensions and model
        stmt = select(Phase2EmbeddingModel)
        result = await session.execute(stmt)
        all_embeddings = result.scalars().all()

        dim_1024_count = sum(1 for e in all_embeddings if len(e.content_vector or []) == 1024 and len(e.context_vector or []) == 1024)
        bge_model_count = sum(1 for e in all_embeddings if e.embedding_model == "BAAI/bge-m3")

    await engine.dispose()

    # Final summary report
    print("\n" + "=" * 80)
    print("                 PHASE 2 INDEXING VERIFICATION REPORT")
    print("=" * 80)
    print(f"Total completed phase1_outputs in DB       : {final_completed_p1}")
    print(f"Total Phase 2 Embeddings Before Operation  : {initial_p2_count}")
    print(f"Newly Indexed in this run                  : {newly_indexed}")
    print(f"Skipped (Already Indexed & Valid)          : {skipped_existing}")
    print(f"Failed Records                             : {len(failed_records)}")
    print(f"Total Phase 2 Embeddings in Table          : {final_p2_count}")
    print(f"Distinct Phase 1 Output IDs in Phase 2     : {distinct_p1_ids}")
    print(f"Distinct Memory IDs in Phase 2             : {distinct_mem_ids}")
    print(f"Embeddings with 1024-dim dual vectors      : {dim_1024_count}/{final_p2_count}")
    print(f"Embeddings with model 'BAAI/bge-m3'        : {bge_model_count}/{final_p2_count}")
    print("=" * 80)

    # Return structured results
    return {
        "total_completed_phase1": final_completed_p1,
        "initial_p2_count": initial_p2_count,
        "newly_indexed": newly_indexed,
        "skipped_existing": skipped_existing,
        "failed_count": len(failed_records),
        "failed_records": failed_records,
        "final_p2_count": final_p2_count,
        "distinct_p1_ids": distinct_p1_ids,
        "distinct_mem_ids": distinct_mem_ids,
        "dim_1024_count": dim_1024_count,
        "bge_model_count": bge_model_count,
    }


# Backwards compatibility wrapper for dataset runner imports
async def index_dataset_phase2(database_url: str | None = None, **kwargs: Any) -> dict[str, Any]:
    return await index_all_phase1_records(database_url=database_url)


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(index_all_phase1_records(database_url=db_url))
