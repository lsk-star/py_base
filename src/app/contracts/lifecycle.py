from dataclasses import dataclass
import logging
from collections.abc import Iterable
from typing import Protocol, TypeVar, cast

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class ReadinessStatus:
    name: str
    ready: bool
    detail: str | None = None


class LifecycleComponent(Protocol):
    name: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def readiness(self) -> ReadinessStatus: ...


class ComponentRegistry:
    """统一管理应用资源，并按确定顺序执行其生命周期。"""

    def __init__(self) -> None:
        self._components: list[LifecycleComponent] = []

    def add(self, component: LifecycleComponent) -> None:
        self._components.append(component)

    def get(self, component_type: type[T]) -> T:
        """按具体组件类型查询已注册的组件。"""
        for component in self._components:
            if isinstance(component, component_type):
                return cast(T, component)
        raise LookupError(f"组件未注册: {component_type.__name__}")

    async def start(self) -> None:
        started: list[LifecycleComponent] = []
        try:
            for component in self._components:
                await component.start()
                started.append(component)
        except Exception:
            await self._stop_components(reversed(started))
            raise

    async def stop(self) -> None:
        errors = await self._stop_components(reversed(self._components))
        if errors:
            raise ExceptionGroup("一个或多个组件关闭失败", errors)

    async def readiness(self) -> list[ReadinessStatus]:
        statuses: list[ReadinessStatus] = []
        for component in self._components:
            try:
                statuses.append(await component.readiness())
            except Exception:
                logger.exception("组件就绪检查失败: %s", component.name)
                statuses.append(ReadinessStatus(component.name, False, "就绪检查失败"))
        return statuses

    async def _stop_components(
        self,
        components: Iterable[LifecycleComponent],
    ) -> list[Exception]:
        errors: list[Exception] = []
        for component in components:
            try:
                await component.stop()
            except Exception as exc:
                logger.exception("组件关闭失败: %s", component.name)
                errors.append(exc)
        return errors
