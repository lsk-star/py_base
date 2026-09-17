from typing import Any
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.contracts.lifecycle import ReadinessStatus, LifecycleComponent
from app.core.config import DatabaseSettings
from app.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class DatabaseComponent(LifecycleComponent):
    name = "database"

    def __init__(self, settings: DatabaseSettings) -> None:
        if not settings.url:
            raise ConfigurationError(
                "数据库已启用，但未配置 APP_DATABASE__URL。"
            )
        self._settings = settings
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[Any] | None = None
        self._startup_error: str | None = None

    async def start(self) -> None:
        options: dict[str, Any] = {"echo": self._settings.echo}
        if not self._settings.url.startswith("sqlite"):
            options.update(
                pool_size=self._settings.pool_size,
                max_overflow=self._settings.max_overflow,
            )
        self.engine = create_async_engine(self._settings.url, **options)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        try:
            await self._check_connection()
        except Exception as exc:
            self._startup_error = str(exc)
            if self._settings.strict_startup:
                await self.stop()
                logger.exception("数据库启动连接失败")
                raise ConfigurationError("数据库连接失败") from exc

    async def stop(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None

    async def readiness(self) -> ReadinessStatus:
        if self.engine is None:
            return ReadinessStatus(self.name, False, self._startup_error or "数据库尚未初始化")
        try:
            await self._check_connection()
            return ReadinessStatus(self.name, True)
        except Exception as exc:
            logger.warning("数据库就绪检查失败: %s", exc)
            return ReadinessStatus(self.name, False, "数据库暂不可用")

    async def _check_connection(self) -> None:
        if self.engine is None:
            raise RuntimeError("数据库引擎尚未创建")
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
