from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.core.exceptions import DependencyUnavailableError
from pybase.infrastructure.database.component import DatabaseComponent


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """为当前 HTTP 请求创建独立的数据库会话。"""
    try:
        database = request.app.state.components.get(DatabaseComponent)
    except LookupError as exc:
        raise DependencyUnavailableError("数据库能力未启用") from exc

    if database.session_factory is None:
        raise DependencyUnavailableError("数据库尚未就绪")

    async with database.session_factory() as session:
        # 只要 yield 之后没有抛出异常，async with 退出时会自动 commit
        # 如果抛出异常，async with 退出时会自动 rollback
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise



