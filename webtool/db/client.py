from collections.abc import AsyncGenerator

from sqlalchemy import MetaData, exc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webtool.utils.json import ORJSONDecoder, ORJSONEncoder


class AsyncDB:
    def __init__(
        self,
        db_url: str,
        meta: MetaData = None,
        engine_args: dict | None = None,
        session_args: dict | None = None,
    ) -> None:
        self.meta = meta

        self.engine_config = self.get_default_engine_config(session_args or {})
        self.session_config = self.get_default_session_config(engine_args or {})

        self.engine = create_async_engine(db_url, **self.engine_config)
        self.session_factory = async_sessionmaker(self.engine, **self.session_config)

    async def __call__(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except exc.SQLAlchemyError as error:
                await session.rollback()
                raise error

    @staticmethod
    def get_default_engine_config(kwargs) -> dict:
        kwargs.setdefault("json_serializer", ORJSONEncoder.encode)
        kwargs.setdefault("json_deserializer", ORJSONDecoder.decode)
        kwargs.setdefault("pool_pre_ping", True)
        return kwargs

    @staticmethod
    def get_default_session_config(kwargs) -> dict:
        kwargs.setdefault("autocommit", False)
        kwargs.setdefault("autoflush", False)
        kwargs.setdefault("expire_on_commit", False)
        return kwargs

    async def init_db(self):
        async with self.engine.begin() as conn:
            return await conn.run_sync(self.meta)

    async def aclose(self):
        await self.engine.dispose()
