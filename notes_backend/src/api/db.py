import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _build_db_url() -> str:
    """
    Build the SQLAlchemy async database URL from environment variables.

    Expected environment variables (provided by the database container):
    - POSTGRES_URL
    - POSTGRES_USER
    - POSTGRES_PASSWORD
    - POSTGRES_DB
    - POSTGRES_PORT

    Notes:
    - We intentionally do not assume what each env var contains beyond the name.
    - If POSTGRES_URL already contains a full URL, we attempt to adapt it to async.
    """
    postgres_url = os.getenv("POSTGRES_URL", "").strip()
    user = os.getenv("POSTGRES_USER", "").strip()
    password = os.getenv("POSTGRES_PASSWORD", "").strip()
    db = os.getenv("POSTGRES_DB", "").strip()
    port = os.getenv("POSTGRES_PORT", "").strip()

    # If POSTGRES_URL is a full connection string, prefer it.
    # Examples:
    #   postgresql://user:pass@host:5432/db
    #   postgres://user:pass@host:5432/db
    if postgres_url:
        url = postgres_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            # Use psycopg async driver for SQLAlchemy 2.x async
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        return url

    # Otherwise assemble from discrete fields; host is expected in POSTGRES_URL in most setups,
    # but some environments provide only host there. We support that too.
    host = postgres_url or "localhost"
    if host.startswith("http://") or host.startswith("https://"):
        host = host.split("://", 1)[1]

    # Default Postgres port is 5432, but we use env if present.
    port_part = port if port else "5432"
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port_part}/{db}"


DATABASE_URL = _build_db_url()

# Engine configuration: keep it simple and robust for container environments.
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# PUBLIC_INTERFACE
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession and ensures it is closed."""
    async with AsyncSessionLocal() as session:
        yield session
