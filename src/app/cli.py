import argparse
from pathlib import Path
from typing import Sequence

from app.scaffolding.module_generator import GenerationError, ModuleOptions, generate_module


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口；不带子命令时保持原有启动服务行为。"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "serve"):
        # 仅启动服务时导入应用，生成代码不应依赖运行期配置或可选组件。
        from app.main import run

        run()
        return 0

    if args.command == "generate" and args.generator_target == "module":
        options = ModuleOptions(
            name=args.name,
            with_model=args.with_model,
            route_prefix=args.route_prefix,
            table_name=args.table_name,
            dry_run=args.dry_run,
            force=args.force,
        )
        try:
            result = generate_module(Path.cwd(), options)
        except GenerationError as exc:
            parser.error(str(exc))

        action = "将创建" if result.dry_run else "已创建"
        for path in result.created_files:
            print(f"{action}: {path.relative_to(Path.cwd())}")
        for path in result.modified_files:
            print(f"{'将修改' if result.dry_run else '已修改'}: {path.relative_to(Path.cwd())}")
        for path in result.unchanged_files:
            print(f"已跳过: {path.relative_to(Path.cwd())}")
        return 0

    parser.error("不支持的命令")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app", description="后端脚手架命令行工具")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("serve", help="启动 Web 服务")

    generate_parser = subparsers.add_parser("generate", help="生成代码骨架")
    generate_subparsers = generate_parser.add_subparsers(dest="generator_target", required=True)
    module_parser = generate_subparsers.add_parser("module", help="生成业务模块")
    module_parser.add_argument("name", help="模块名，必须是 snake_case")
    module_parser.add_argument("--with-model", action="store_true", help="生成数据库模型和仓储层")
    module_parser.add_argument("--route-prefix", help="路由前缀，默认使用模块名")
    module_parser.add_argument("--table-name", help="数据库表名，默认使用模块名")
    module_parser.add_argument("--dry-run", action="store_true", help="只显示将执行的文件变更")
    module_parser.add_argument(
        "--force",
        action="store_true",
        help="无法安全升级 Service 时覆盖该文件",
    )
    return parser
