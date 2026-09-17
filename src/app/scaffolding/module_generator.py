from dataclasses import dataclass
from pathlib import Path
import keyword
import re
from string import Template

# 改包名时只需要改这一处：路径、生成代码里的导入和模块注册都从这里派生。
PACKAGE_NAME = "app"

MODULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
# 标记属于生成器自身的协议，与项目名无关，因此不随 PACKAGE_NAME 变化。
REGISTRY_MARKERS = (
    "# scaffold: generated module registrations - start",
    "# scaffold: generated module registrations - end",
)
MODEL_IMPORT_MARKERS = (
    "# scaffold: generated model imports - start",
    "# scaffold: generated model imports - end",
)
SERVICE_IMPORT_MARKERS = (
    "# scaffold: generated service imports - start",
    "# scaffold: generated service imports - end",
)
SERVICE_SETUP_MARKERS = (
    "# scaffold: generated database setup - start",
    "# scaffold: generated database setup - end",
)


class GenerationError(ValueError):
    """生成前置条件不满足时抛出。"""


@dataclass(frozen=True)
class ModuleOptions:
    name: str
    with_model: bool = False
    route_prefix: str | None = None
    table_name: str | None = None
    dry_run: bool = False
    force: bool = False


@dataclass(frozen=True)
class GenerationResult:
    created_files: tuple[Path, ...]
    modified_files: tuple[Path, ...]
    unchanged_files: tuple[Path, ...]
    dry_run: bool


def generate_module(project_root: Path, options: ModuleOptions) -> GenerationResult:
    """生成或增量升级模块骨架，默认不覆盖已有人工代码。"""
    _validate_options(project_root, options)

    module_name = options.name
    module_class_name = _to_pascal_case(module_name)
    route_prefix = (options.route_prefix or module_name).strip("/")
    table_name = options.table_name or module_name
    module_directory = project_root / "src" / PACKAGE_NAME / "modules" / module_name
    test_directory = project_root / "tests" / "modules" / module_name
    registry_path = project_root / "src" / PACKAGE_NAME / "modules" / "registry.py"
    model_import_path = (
        project_root
        / "src"
        / PACKAGE_NAME
        / "infrastructure"
        / "database"
        / "models"
        / "__init__.py"
    )

    if module_directory.exists() and not module_directory.is_dir():
        raise GenerationError(f"模块路径不是目录: {module_directory}")

    templates = _build_module_files(
        module_name=module_name,
        module_class_name=module_class_name,
        route_prefix=route_prefix,
        table_name=table_name,
        with_model=options.with_model,
        module_directory=module_directory,
        test_directory=test_directory,
    )
    created_files: dict[Path, str] = {}
    modified_files: dict[Path, str] = {}
    unchanged_files: list[Path] = []

    for path, content in templates.items():
        if not path.exists():
            created_files[path] = content
            continue

        if path.name == "service.py" and options.with_model:
            upgraded_content = _upgrade_service(
                current_content=path.read_text(encoding="utf-8"),
                module_name=module_name,
                module_class_name=module_class_name,
                force=options.force,
                path=path,
            )
            _plan_modified_file(path, upgraded_content, modified_files, unchanged_files)
            continue

        # 已有文件视为开发者拥有，生成器不覆盖。
        unchanged_files.append(path)

    registry_content = _upsert_registry_entry(
        content=registry_path.read_text(encoding="utf-8"),
        module_name=module_name,
        with_model=options.with_model,
        path=registry_path,
    )
    _plan_modified_file(registry_path, registry_content, modified_files, unchanged_files)

    if options.with_model:
        model_import_content = _upsert_model_import(
            content=model_import_path.read_text(encoding="utf-8"),
            module_name=module_name,
            module_class_name=module_class_name,
            path=model_import_path,
        )
        _plan_modified_file(model_import_path, model_import_content, modified_files, unchanged_files)

    if not options.dry_run:
        for path, content in created_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        for path, content in modified_files.items():
            path.write_text(content, encoding="utf-8", newline="\n")

    return GenerationResult(
        created_files=tuple(created_files),
        modified_files=tuple(modified_files),
        unchanged_files=tuple(dict.fromkeys(unchanged_files)),
        dry_run=options.dry_run,
    )


def _validate_options(project_root: Path, options: ModuleOptions) -> None:
    if not MODULE_NAME_PATTERN.fullmatch(options.name) or keyword.iskeyword(options.name):
        raise GenerationError("模块名必须是非关键字的 snake_case 标识符，例如 user_profile")
    if options.route_prefix is not None and not options.route_prefix.strip("/"):
        raise GenerationError("路由前缀不能为空")
    if options.table_name is not None and not MODULE_NAME_PATTERN.fullmatch(options.table_name):
        raise GenerationError("表名必须是 snake_case 标识符")

    required_paths = [
        project_root / "pyproject.toml",
        project_root / "src" / PACKAGE_NAME / "modules" / "registry.py",
    ]
    if options.with_model:
        required_paths.append(
            project_root
            / "src"
            / PACKAGE_NAME
            / "infrastructure"
            / "database"
            / "models"
            / "__init__.py"
        )
    missing_paths = [str(path) for path in required_paths if not path.is_file()]
    if missing_paths:
        raise GenerationError("当前目录不是完整的项目: " + ", ".join(missing_paths))


def _build_module_files(
    *,
    module_name: str,
    module_class_name: str,
    route_prefix: str,
    table_name: str,
    with_model: bool,
    module_directory: Path,
    test_directory: Path,
) -> dict[Path, str]:
    values = {
        "package_name": PACKAGE_NAME,
        "module_name": module_name,
        "module_class_name": module_class_name,
        "route_prefix": route_prefix,
        "table_name": table_name,
    }
    files = {
        module_directory / "__init__.py": f'"""{module_class_name} 业务模块。"""\n',
        module_directory / "router.py": _render(
            """from fastapi import APIRouter

router = APIRouter(prefix="/$route_prefix", tags=["$module_name"])

# 路由只负责协议转换和依赖注入，业务规则应委托给 Service。
# 例如（启用数据库后）：
# from fastapi import Depends
# from .dependencies import get_${module_name}_service
#
# @router.get("/{entity_id}")
# async def get_$module_name(entity_id: int, service = Depends(get_${module_name}_service)):
#     return await service.get_by_id(entity_id)
""",
            values,
        ),
        module_directory / "schemas.py": _render(
            """from pydantic import BaseModel, ConfigDict


class ${module_class_name}Schema(BaseModel):
    \"\"\"$module_class_name 模块的通用数据模型基类。请按业务增加字段。\"\"\"

    model_config = ConfigDict(from_attributes=True)

    # 示例：name: str
    # 生成器不猜测业务字段，避免生成错误的数据契约。
""",
            values,
        ),
        module_directory / "service.py": _basic_service_content(values),
        module_directory / "README.md": _render(
            """# $module_class_name 模块

## 职责

- `router.py`：HTTP 路由与依赖注入。
- `schemas.py`：请求和响应数据模型。
- `service.py`：业务规则；事务由请求级会话统一提交。

## 开始开发

1. 在 `schemas.py` 增加真实的请求/响应字段。
2. 在 `models.py` 增加与业务对应的持久化字段（使用 `Mapped` 类型标注）。
3. 在 `repository.py` 增加确有业务语义的查询，保留通用方法。
4. 在 `service.py` 编排 Repository；一次请求对应一个事务，Service 不需要也不应该调用
   `commit()`，需要提前写入数据库时使用 `flush()`。
5. 最后在 `router.py` 完成 HTTP 参数校验和响应映射。

不要在 Router 中编写 SQL，也不要让 Repository 访问 FastAPI 的 `Request` 或 `app.state`。
生成器不会猜测业务字段，也不会自动创建 CRUD HTTP 接口。
""",
            values,
        ),
        # 中间层目录同样需要 __init__.py，否则 unittest discover 会静默跳过生成的测试。
        test_directory.parent / "__init__.py": '"""模块测试。"""\n',
        test_directory / "__init__.py": f'"""{module_class_name} 模块测试。"""\n',
        test_directory / "test_module.py": _render(
            """import unittest

from $package_name.modules.$module_name.router import router


class ${module_class_name}ModuleTests(unittest.TestCase):
    def test_router_metadata(self) -> None:
        self.assertEqual(router.prefix, "/$route_prefix")
        self.assertIn("$module_name", router.tags)
""",
            values,
        ),
    }
    if with_model:
        files.update(_build_database_files(module_directory, values))
    return files


def _basic_service_content(values: dict[str, str]) -> str:
    return _render(
        """import logging

# scaffold: generated service imports - start
# scaffold: generated service imports - end

logger = logging.getLogger(__name__)

class ${module_class_name}Service:
    \"\"\"$module_class_name 模块的业务用例在此实现。\"\"\"

    # scaffold: generated database setup - start
    # scaffold: generated database setup - end

    # 在此添加业务方法。一次请求对应一个事务，由请求级会话统一提交；
    # 需要提前写入数据库时使用 flush()，不要调用 commit()。日志使用本模块 logger。
""",
        values,
    )


def _database_service_content(values: dict[str, str]) -> str:
    return _render(
        """import logging

# scaffold: generated service imports - start
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ${module_class_name}
from .repository import ${module_class_name}Repository
# scaffold: generated service imports - end

logger = logging.getLogger(__name__)

class ${module_class_name}Service:
    \"\"\"$module_class_name 模块的业务用例。

    事务边界是整个 HTTP 请求：Session 由 get_db_session 提供，响应成功返回后统一提交，
    抛出异常时统一回滚。因此这里不要使用 session.begin()，它会在会话已经因查询而自动
    开启事务时抛出 InvalidRequestError；需要立即写库或取得自增主键时使用 flush()。
    \"\"\"

    # scaffold: generated database setup - start
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = ${module_class_name}Repository(session)
    # scaffold: generated database setup - end

    async def get_by_id(self, entity_id: int) -> ${module_class_name} | None:
        \"\"\"按主键查询实体。\"\"\"
        return await self._repository.get_by_id(entity_id)

    async def create(self, entity: ${module_class_name}) -> ${module_class_name}:
        \"\"\"创建实体；flush 后自增主键可用，提交由会话在请求结束时完成。\"\"\"
        self._repository.create(entity)
        await self._session.flush()
        return entity

    async def update(self, entity: ${module_class_name}) -> ${module_class_name}:
        \"\"\"更新实体并返回合并后的实例。\"\"\"
        updated = await self._repository.update(entity)
        await self._session.flush()
        return updated

    async def delete_by_id(self, entity_id: int) -> bool:
        \"\"\"按主键删除实体，实体不存在时返回 False。\"\"\"
        deleted = await self._repository.delete_by_id(entity_id)
        await self._session.flush()
        return deleted

    # 复杂业务用例继续放在 Service；不要把业务规则下沉到 Repository。
    # 确实需要独立于请求事务的提交或保存点时，再用 session.commit() 或 begin_nested()。

""",
        values,
    )


def _build_database_files(module_directory: Path, values: dict[str, str]) -> dict[Path, str]:
    return {
        module_directory / "models.py": _render(
            """from $package_name.infrastructure.database.base import Base, IntIdMixin


class $module_class_name(IntIdMixin, Base):
    __tablename__ = "$table_name"

    # 在此添加业务字段。id 由 IntIdMixin 统一提供。
""",
            values,
        ),
        module_directory / "repository.py": _render(
            """from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from $package_name.common.pagination import PageParams, PageResult

from .models import $module_class_name


class ${module_class_name}Repository:
    \"\"\"$module_class_name 的通用数据访问，不负责提交事务。\"\"\"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def create(self, entity: $module_class_name) -> None:
        self._session.add(entity)

    async def get_by_id(self, entity_id: int) -> $module_class_name | None:
        return await self._session.get($module_class_name, entity_id)

    async def exists_by_id(self, entity_id: int) -> bool:
        \"\"\"判断指定主键是否存在。\"\"\"
        count = await self._session.scalar(
            select(func.count()).where($module_class_name.id == entity_id)
        )
        return bool(count)

    async def count(self) -> int:
        \"\"\"返回实体总数。\"\"\"
        return int(await self._session.scalar(select(func.count()).select_from($module_class_name)) or 0)

    async def get_page(self, params: PageParams) -> PageResult[$module_class_name]:
        total = await self._session.scalar(
            select(func.count()).select_from($module_class_name)
        )
        result = await self._session.scalars(
            select($module_class_name)
            .order_by($module_class_name.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return PageResult(
            items=list(result),
            page=params.page,
            page_size=params.page_size,
            total=total or 0,
        )

    async def update(self, entity: $module_class_name) -> $module_class_name:
        return await self._session.merge(entity)

    async def delete(self, entity: $module_class_name) -> None:
        \"\"\"删除已加载的实体；不会提交事务。\"\"\"
        await self._session.delete(entity)

    async def delete_by_id(self, entity_id: int) -> bool:
        \"\"\"按主键删除实体；返回是否实际删除。\"\"\"
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        return True
""",
            values,
        ),
        module_directory / "dependencies.py": _render(
            """from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from $package_name.infrastructure.database.dependencies import get_db_session

from .service import ${module_class_name}Service

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_${module_name}_service(session: SessionDep) -> ${module_class_name}Service:
    \"\"\"为路由创建请求级 ${module_class_name}Service。\"\"\"
    return ${module_class_name}Service(session)
""",
            values,
        ),
        module_directory / "service.py": _database_service_content(values),
    }


def _upgrade_service(
    *,
    current_content: str,
    module_name: str,
    module_class_name: str,
    force: bool,
    path: Path,
) -> str:
    values = {
        "package_name": PACKAGE_NAME,
        "module_name": module_name,
        "module_class_name": module_class_name,
    }
    database_service_content = _database_service_content(values)
    if current_content == _legacy_basic_service_content(values):
        return database_service_content

    try:
        content = _replace_between_markers(
            current_content,
            SERVICE_IMPORT_MARKERS,
            "from sqlalchemy.ext.asyncio import AsyncSession\n\n"
            f"from .repository import {module_class_name}Repository",
            path,
        )
        return _replace_between_markers(
            content,
            SERVICE_SETUP_MARKERS,
            "def __init__(self, session: AsyncSession) -> None:\n"
            "    self._session = session\n"
            f"    self._repository = {module_class_name}Repository(session)",
            path,
        )
    except GenerationError:
        if force:
            return database_service_content
        raise GenerationError(
            f"无法安全升级已修改的 Service: {path}。请手动加入数据库依赖标记，"
            "或确认后使用 --force 覆盖该文件。"
        )


def _legacy_basic_service_content(values: dict[str, str]) -> str:
    """兼容生成器首版创建的无标记 Service 文件。"""
    return _render(
        """class ${module_class_name}Service:
    \"\"\"$module_class_name 模块的业务用例在此实现。\"\"\"

    # 在此添加业务方法。事务边界应由 Service 管理。
""",
        values,
    )


def _upsert_registry_entry(
    *,
    content: str,
    module_name: str,
    with_model: bool,
    path: Path,
) -> str:
    return _upsert_between_markers(
        content=content,
        markers=REGISTRY_MARKERS,
        entry=_registry_entry(module_name, with_model),
        entry_pattern=(
            rf"^[ \t]*ModuleRegistration\(name=\"{re.escape(module_name)}\",[^\r\n]*\),[ \t]*$"
        ),
        path=path,
    )


def _upsert_model_import(
    *,
    content: str,
    module_name: str,
    module_class_name: str,
    path: Path,
) -> str:
    return _upsert_between_markers(
        content=content,
        markers=MODEL_IMPORT_MARKERS,
        entry=f"from {PACKAGE_NAME}.modules.{module_name}.models import {module_class_name}",
        entry_pattern=(
            rf"^[ \t]*from {re.escape(PACKAGE_NAME)}\.modules\.{re.escape(module_name)}\.models"
            r" import [^\r\n]+$"
        ),
        path=path,
    )


def _upsert_between_markers(
    *,
    content: str,
    markers: tuple[str, str],
    entry: str,
    entry_pattern: str,
    path: Path,
) -> str:
    start_index, end_index = _marker_indexes(content, markers, path)
    existing_block = content[start_index:end_index]
    matches = list(re.finditer(entry_pattern, existing_block, flags=re.MULTILINE))
    if len(matches) > 1:
        raise GenerationError(f"发现重复的生成器注册项: {path}")
    if matches:
        new_block = existing_block[: matches[0].start()] + entry + existing_block[matches[0].end() :]
    else:
        new_block = "\n" + entry + existing_block
    return content[:start_index] + new_block + content[end_index:]


def _replace_between_markers(
    content: str,
    markers: tuple[str, str],
    generated_content: str,
    path: Path,
) -> str:
    start_index, end_index = _marker_indexes(content, markers, path)
    indentation = _marker_indentation(content, markers[0])
    indented_content = "\n".join(
        f"{indentation}{line}" if line else line for line in generated_content.splitlines()
    )
    return content[:start_index] + "\n" + indented_content + "\n" + content[end_index:]


def _marker_indexes(content: str, markers: tuple[str, str], path: Path) -> tuple[int, int]:
    start_marker, end_marker = markers
    try:
        start_index = content.index(start_marker) + len(start_marker)
        end_index = content.index(end_marker, start_index)
    except ValueError as exc:
        raise GenerationError(f"找不到生成器注册标记: {path}") from exc
    return start_index, end_index


def _marker_indentation(content: str, marker: str) -> str:
    marker_position = content.index(marker)
    marker_line_start = content.rfind("\n", 0, marker_position) + 1
    return content[marker_line_start:marker_position]


def _plan_modified_file(
    path: Path,
    content: str,
    modified_files: dict[Path, str],
    unchanged_files: list[Path],
) -> None:
    if content == path.read_text(encoding="utf-8"):
        unchanged_files.append(path)
    else:
        modified_files[path] = content


def _registry_entry(module_name: str, with_model: bool) -> str:
    return (
        f'    ModuleRegistration(name="{module_name}", '
        f'router_path="{PACKAGE_NAME}.modules.{module_name}.router:router", '
        f"requires_database={with_model}),"
    )


def _render(template: str, values: dict[str, str]) -> str:
    return Template(template).substitute(values).strip() + "\n"


def _to_pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))
