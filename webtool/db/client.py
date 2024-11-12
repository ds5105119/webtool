from typing import AsyncGenerator

from sqlalchemy import MetaData, exc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class AsyncDB:
    def __init__(self, db_url: str, meta: MetaData = None) -> None:
        self.meta = meta
        self.engine = create_async_engine(
            db_url,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            autocommit=False, autoflush=False, expire_on_commit=False, bind=self.engine
        )

    async def __call__(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except exc.SQLAlchemyError as error:
                await session.rollback()
                raise error

    async def init_db(self):
        async with self.engine.begin() as conn:
            return await conn.run_sync(self.meta)
