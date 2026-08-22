from dataclasses import dataclass
from importlib import import_module

from fastapi import APIRouter


@dataclass(frozen=True)
class ModuleRegistration:
    """模块路由的延迟导入描述。"""

    name: str
    router_path: str
    requires_database: bool = False


MODULE_REGISTRATIONS: tuple[ModuleRegistration, ...] = (
    # pybase: generated module registrations - start
    ModuleRegistration(name="user", router_path="pybase.modules.user.router:router", requires_database=True),
    # pybase: generated module registrations - end
)


def register_modules(router: APIRouter, *, database_enabled: bool) -> None:
    """仅导入当前配置允许启用的模块路由。"""
    for registration in MODULE_REGISTRATIONS:
        if registration.requires_database and not database_enabled:
            continue

        module_path, router_name = registration.router_path.split(":", maxsplit=1)
        module = import_module(module_path)
        router.include_router(getattr(module, router_name))
