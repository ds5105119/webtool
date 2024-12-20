from collections.abc import AsyncGenerator, Generator

from sqlalchemy import MetaData, create_engine, exc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from webtool.utils.json import ORJSONDecoder, ORJSONEncoder


class SyncDB:
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

        self.engine = create_engine(db_url, **self.engine_config)
        self.session_factory = sessionmaker(self.engine, **self.session_config)

    def __call__(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            try:
                yield session
                session.commit()
            except exc.SQLAlchemyError as error:
                session.rollback()
                raise error
            finally:
                session.close()

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

    def init_db(self) -> None:
        with self.engine.begin() as conn:
            conn.run_sync(self.meta)

    def close(self) -> None:
        self.engine.dispose()


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

    async def __call__(self) -> AsyncGenerator[AsyncSession, None, None]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except exc.SQLAlchemyError as error:
                await session.rollback()
                raise error
            finally:
                await session.close()

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

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(self.meta)

    async def aclose(self) -> None:
        await self.engine.dispose()
