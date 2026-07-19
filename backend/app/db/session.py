from sqlmodel import create_engine, Session
from app.core.config import settings

# Get database URL from config
DATABASE_URL = settings.database.get_database_url()

# Create the database engine (SQLite needs this parameter to allow multi-threaded access)
engine = create_engine(
    DATABASE_URL,
    echo=settings.database.echo,
    connect_args={"check_same_thread": False}
)


def get_session():
    """
    FastAPI dependency that provides a transactional database session.
    It ensures that the session is committed on success and rolled back on error.
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close() 