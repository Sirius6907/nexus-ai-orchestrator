from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from api.core.config import settings

engine = create_async_engine(settings.POSTGRES_URI, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
