from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pybase.scaffolding.module_generator import GenerationError, ModuleOptions, generate_module


REGISTRY_TEMPLATE = """from pybase.modules.registry import ModuleRegistration

MODULE_REGISTRATIONS = (
    # pybase: generated module registrations - start
    # pybase: generated module registrations - end
)
"""

MODEL_IMPORT_TEMPLATE = """\"\"\"模型导入。\"\"\"

# pybase: generated model imports - start
# pybase: generated model imports - end
"""


class ModuleGeneratorTests(unittest.TestCase):
    def test_generates_basic_module_and_registers_router(self) -> None:
        with self._project_root() as project_root:
            result = generate_module(project_root, ModuleOptions(name="user"))

            module_path = project_root / "src" / "pybase" / "modules" / "user"
            self.assertTrue((module_path / "router.py").is_file())
            self.assertTrue((module_path / "schemas.py").is_file())
            self.assertTrue((module_path / "service.py").is_file())
            self.assertFalse((module_path / "models.py").exists())
            schema_content = (module_path / "schemas.py").read_text(encoding="utf-8")
            service_content = (module_path / "service.py").read_text(encoding="utf-8")
            router_content = (module_path / "router.py").read_text(encoding="utf-8")
            self.assertIn("class UserSchema(BaseModel)", schema_content)
            self.assertIn("logger = logging.getLogger(__name__)", service_content)
            self.assertIn("get_user_service", router_content)
            self.assertIn(
                "requires_database=False",
                (project_root / "src/pybase/modules/registry.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(len(result.modified_files), 1)

    def test_generates_database_module_and_registers_model(self) -> None:
        with self._project_root() as project_root:
            generate_module(project_root, ModuleOptions(name="user_profile", with_model=True))

            module_path = project_root / "src" / "pybase" / "modules" / "user_profile"
            model_content = (module_path / "models.py").read_text(encoding="utf-8")
            repository_content = (module_path / "repository.py").read_text(encoding="utf-8")
            registry_content = (project_root / "src/pybase/modules/registry.py").read_text(encoding="utf-8")
            model_import_content = (
                project_root / "src/pybase/infrastructure/database/models/__init__.py"
            ).read_text(encoding="utf-8")

            self.assertIn("class UserProfile(IntIdMixin, Base)", model_content)
            self.assertIn("async def get_page", repository_content)
            self.assertIn("async def delete_by_id", repository_content)
            self.assertIn("async def exists_by_id", repository_content)
            self.assertIn("async def count", repository_content)
            self.assertIn("requires_database=True", registry_content)
            self.assertIn("from pybase.modules.user_profile.models import UserProfile", model_import_content)
            for file_name in ("models.py", "repository.py", "dependencies.py", "service.py"):
                generated_path = module_path / file_name
                compile(generated_path.read_text(encoding="utf-8"), str(generated_path), "exec")

    def test_dry_run_does_not_write_files(self) -> None:
        with self._project_root() as project_root:
            result = generate_module(project_root, ModuleOptions(name="user", dry_run=True))

            self.assertTrue(result.dry_run)
            self.assertFalse((project_root / "src/pybase/modules/user").exists())
            registry_content = (project_root / "src/pybase/modules/registry.py").read_text(encoding="utf-8")
            self.assertNotIn('name="user"', registry_content)

    def test_rejects_invalid_or_existing_module_name(self) -> None:
        with self._project_root() as project_root:
            with self.assertRaises(GenerationError):
                generate_module(project_root, ModuleOptions(name="../user"))

            generate_module(project_root, ModuleOptions(name="user"))
            result = generate_module(project_root, ModuleOptions(name="user"))

            self.assertFalse(result.created_files)
            self.assertFalse(result.modified_files)

    def test_upgrades_basic_module_to_database_module_without_duplicate_registration(self) -> None:
        with self._project_root() as project_root:
            generate_module(project_root, ModuleOptions(name="user"))
            service_path = project_root / "src/pybase/modules/user/service.py"
            service_path.write_text(
                service_path.read_text(encoding="utf-8")
                + "\n    def custom_business_method(self) -> None:\n        pass\n",
                encoding="utf-8",
            )

            result = generate_module(project_root, ModuleOptions(name="user", with_model=True))

            registry_content = (project_root / "src/pybase/modules/registry.py").read_text(encoding="utf-8")
            model_import_content = (
                project_root / "src/pybase/infrastructure/database/models/__init__.py"
            ).read_text(encoding="utf-8")
            upgraded_service = service_path.read_text(encoding="utf-8")

            self.assertTrue((project_root / "src/pybase/modules/user/models.py").is_file())
            self.assertIn(service_path, result.modified_files)
            self.assertIn("def custom_business_method", upgraded_service)
            self.assertIn("def __init__(self, session: AsyncSession)", upgraded_service)
            compile(upgraded_service, str(service_path), "exec")
            self.assertEqual(registry_content.count('name="user"'), 1)
            self.assertIn("requires_database=True", registry_content)
            self.assertEqual(model_import_content.count("from pybase.modules.user.models import User"), 1)

            second_result = generate_module(project_root, ModuleOptions(name="user", with_model=True))
            self.assertFalse(second_result.created_files)
            self.assertFalse(second_result.modified_files)

    def test_rejects_unsafe_service_upgrade_unless_force_is_set(self) -> None:
        with self._project_root() as project_root:
            generate_module(project_root, ModuleOptions(name="user"))
            service_path = project_root / "src/pybase/modules/user/service.py"
            service_path.write_text("class UserService:\n    pass\n", encoding="utf-8")

            with self.assertRaisesRegex(GenerationError, "无法安全升级"):
                generate_module(project_root, ModuleOptions(name="user", with_model=True))

            result = generate_module(project_root, ModuleOptions(name="user", with_model=True, force=True))
            self.assertIn(service_path, result.modified_files)
            self.assertIn("AsyncSession", service_path.read_text(encoding="utf-8"))

    def _project_root(self):
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        project_root = Path(temporary_directory.name)
        (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
        registry_path = project_root / "src/pybase/modules/registry.py"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(REGISTRY_TEMPLATE, encoding="utf-8")
        model_import_path = project_root / "src/pybase/infrastructure/database/models/__init__.py"
        model_import_path.parent.mkdir(parents=True)
        model_import_path.write_text(MODEL_IMPORT_TEMPLATE, encoding="utf-8")
        return _ProjectRootContext(project_root)


class _ProjectRootContext:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def __enter__(self) -> Path:
        return self._project_root

    def __exit__(self, *_: object) -> None:
        return None