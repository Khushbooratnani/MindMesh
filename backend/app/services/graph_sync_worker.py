from app.config import settings
from app.db.neo4j import Neo4jRepository
from app.db.postgres import PostgresRepository
from app.services.graph_builder import GraphBuilder


class GraphSyncWorker:
    def __init__(
        self,
        repository: PostgresRepository | None = None,
        neo4j_repository: Neo4jRepository | None = None,
        graph_builder: GraphBuilder | None = None,
    ):
        self.repository = repository or PostgresRepository()
        self.neo4j_repository = neo4j_repository or Neo4jRepository()
        self.graph_builder = graph_builder or GraphBuilder()

    def run(
        self,
        limit: int = 25,
        memory_ids: list[str] | None = None,
    ) -> dict:
        rows = self.repository.fetch_graph_inputs(
            graph_model=settings.graph_extraction_model,
            limit=limit,
            memory_ids=memory_ids or [],
        )
        processed = 0
        failed = 0
        errors: list[str] = []

        for row in rows:
            memory_id = row["memory_id"]
            try:
                document = self.graph_builder.build_from_memory_row(row)
                self.neo4j_repository.write_graph_document(document)
                self.repository.mark_graph_job_completed(
                    memory_id,
                    settings.graph_extraction_model,
                )
                processed += 1
            except Exception as exc:
                failed += 1
                message = f"{memory_id}: {exc}"
                errors.append(message)
                self.repository.mark_graph_job_failed(
                    memory_id,
                    settings.graph_extraction_model,
                    str(exc),
                )

        return {
            "processed": processed,
            "failed": failed,
            "neo4j_database": settings.neo4j_database,
            "errors": errors,
        }
