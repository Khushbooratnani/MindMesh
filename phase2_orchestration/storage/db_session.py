import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from phase2_orchestration.config import settings

Base = declarative_base()

def get_engine():
    postgres_url = os.getenv("POSTGRES_URL", settings.POSTGRES_URL)
    try:
        engine = create_engine(postgres_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        print(f" [!] PostgreSQL not available ({str(e)}). Using local SQLite fallback for testing/dev.")
        db_path = os.path.join(os.path.dirname(__file__), "..", "mind_mesh_orchestration.db")
        return create_engine(f"sqlite:///{os.path.abspath(db_path)}", echo=False)

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    if engine.dialect.name == "postgresql":
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
        except Exception:
            pass
    Base.metadata.create_all(bind=engine)
