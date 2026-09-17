# App

一个基于 FastAPI 的异步 Python 后端脚手架。它的目标不是替你做业务决策，而是把每个后端服务都要
重复写一遍的东西——应用装配、配置、日志、统一响应、异常映射、请求链路标识、健康检查、数据库会话
和业务模块骨架——先固定下来，让新项目 clone 之后可以直接写业务。

包名、发行名和 CLI 命令统一叫 `app`。想换成自己的项目名，见 [如何重命名](#如何重命名)。

## 它提供什么

- **Web 应用骨架**：FastAPI + uvicorn，应用工厂 + 生命周期组件，`/live` 与 `/ready` 分离。
- **分模块配置**：`pydantic-settings`，环境变量 + `.env`，前缀 `APP_`，嵌套用 `__`。
- **日志**：文本 / JSON 两种格式，自动附带 `request_id`，访问日志对查询参数脱敏。
- **统一响应与错误码**：成功和失败都是同一套信封，同时保留准确的 HTTP 状态码。
- **请求链路标识**：默认生成 `request_id` 并回写响应头；`trace_id` 可选透传（默认关闭）。
- **数据库**：SQLAlchemy 2.x 异步引擎，默认 MySQL；**默认关闭**，不启用就完全不连接。
- **代码生成器**：`app generate module <name>` 生成分层骨架，可增量升级出模型、仓储和依赖注入。
- **回归测试**：基于标准库 `unittest`，不需要额外测试框架。

## 设计原则

- **最小核心**：未启用的能力不连接、不初始化；数据库等内置能力随核心安装，但默认关闭。
- **显式装配**：`src/app/application.py` 是唯一的应用装配点，负责配置、日志、中间件、生命周期组件和路由注册。
- **按模块配置**：`Settings` 由 `AppSettings`、`LoggingSettings`、`DatabaseSettings` 等模块配置组成，新增能力只添加自己的配置对象。
- **按业务拆分**：业务代码放入 `modules/<业务名>/`，其中 HTTP 路由、Schema、服务和仓储可随模块演进，不形成全局巨型 `services` 目录。
- **只在边界抽象**：生命周期、外部服务、持久化等可替换边界才定义契约；不存在只有一个实现的 `IFooService/FooServiceImpl` 占位层。

## 目录

```text
src/app/
├── application.py                 # 应用工厂，唯一总装配点
├── main.py                        # uvicorn 入口（app.main:app）
├── cli.py                         # 命令行入口：serve / generate
├── core/                          # 配置、日志、上下文、异常与错误码
├── contracts/                     # 有替换价值的边界协议
├── presentation/                  # HTTP 响应、中间件、异常处理
├── infrastructure/database/       # 可选 SQLAlchemy 实现
├── modules/                       # 业务或运维模块
├── scaffolding/                   # 模块代码生成器
├── common/                        # 跨模块值对象，如分页
└── utils/                         # 无状态小工具

tests/                             # 回归测试
docs/分包指南.md                    # 分包、分层与启动流程详解
```

## 快速开始

前置条件：Python 3.12 或更高版本，以及 [uv](https://docs.astral.sh/uv/)。

```powershell
# 1. 安装依赖（会自动创建 .venv）
uv sync

# 2. 生成本地配置，按需修改
Copy-Item .env.example .env

# 3. 启动服务
uv run app
```

服务默认监听 `http://127.0.0.1:8000`：

| 地址 | 说明 |
| --- | --- |
| `http://127.0.0.1:8000/docs` | OpenAPI 交互文档 |
| `http://127.0.0.1:8000/live` | 存活探针 |
| `http://127.0.0.1:8000/ready` | 就绪探针 |
| `http://127.0.0.1:8000/api/v1/system/info` | 应用信息 |

`uv run app` 等价于 `uv run app serve`。需要显式指定 ASGI 应用时用
`uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`。

若 `8000` 被占用，在 `.env` 里改端口后重启：

```env
APP_APP__PORT=8001
```

可用 `Get-NetTCPConnection -LocalPort 8000 -State Listen` 确认端口被谁占用。

跑测试：

```powershell
uv run python -m unittest discover -s tests -v
```

## 配置

所有环境变量使用 `APP_` 前缀、双下划线分层，对应 `core/config.py` 里的配置模型。
例如 `APP_APP__PORT` 对应 `Settings.app.port`，`APP_DATABASE__ENABLED` 对应
`Settings.database.enabled`。

```env
APP_APP__ENVIRONMENT=production
APP_LOGGING__FORMAT=json
APP_DATABASE__ENABLED=false
```

`APP_APP__*` 里的第一个 `APP_` 是环境变量前缀，第二个 `app` 是配置模块名（`AppSettings`）。
如果觉得重复，改 `core/config.py` 中的 `env_prefix`（例如改成 `MYPROJECT_`）并同步 `.env` 即可，
这也是唯一一处需要改的地方。若连模块名也不想叫 `app`，见 [如何重命名](#如何重命名)。

## 数据库

数据库默认关闭，未启用时不会建立任何连接。启用后默认使用 MySQL（`asyncmy` 异步驱动）：

```env
APP_DATABASE__ENABLED=true
APP_DATABASE__URL=mysql+asyncmy://root:root@127.0.0.1:3306/app
APP_DATABASE__STRICT_STARTUP=true
```

- `STRICT_STARTUP=true`：启动时连不上数据库就拒绝启动，适合绝大多数生产服务。
- `STRICT_STARTUP=false`：应用可以启动，但 `/ready` 会返回 503 并报告数据库未就绪。

换成其他数据库只需替换 URL 的方言并安装对应异步驱动，代码不用改，例如
`postgresql+asyncpg://...` 或 `sqlite+aiosqlite:///./app.db`。

事务边界是**整个请求**：`get_db_session` 为每个请求创建一个 `AsyncSession`，正常返回时提交，
抛出异常时回滚。所以 Service 里不要调用 `commit()`，需要立刻写库或取得自增主键时用
`flush()`。细节见 [分包指南](docs/分包指南.md#2-业务模块如何使用-session)。

> 脚手架不含数据库迁移工具。生成模型后需要你自己建表，例如在部署脚本里调用
> `Base.metadata.create_all()`，或者用 Alembic 等外部工具管理表结构变更。

## 响应与错误

成功和失败使用同一套信封，同时保留准确的 HTTP 状态码：

```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "ok",
  "data": {},
  "request_id": "..."
}
```

默认只生成 `request_id`，用于把一次 HTTP 请求的全部日志串起来。客户端可以通过
`X-Request-ID` 传入自己的标识（会做格式校验，不安全的值会被丢弃并重新生成），应用会把它回写到
响应头。

`trace_id` 默认关闭。接入网关、OpenTelemetry 或多服务调用链后，设置
`APP_TRACING__ENABLED=true`，应用才会透传上游的 `X-Trace-ID` 或 W3C `traceparent`；未接入时
不会额外生成随机值，避免产生两个含义不同的 ID。

访问日志由中间件输出，记录方法、路径、脱敏后的查询参数、状态码和耗时；不记录请求体、
`Authorization`、`Cookie`。`password`、`token`、`secret`、`authorization`、`cookie`、`api_key`
等查询参数会替换成 `***`。

**未捕获异常造成的 500 响应没有 `X-Request-ID` 响应头，响应体里的 `request_id` 也是 `null`。**
500 由 Starlette 的 `ServerErrorMiddleware` 在所有用户中间件之外生成，中间件无法再往里写响应头。
排查 500 请以访问日志为准——`AccessLogMiddleware` 已经用同一个 `request_id` 记录了该请求。

## 健康检查

| 路径 | 含义 | 检查外部依赖 |
| --- | --- | --- |
| `GET /live` | 进程与 HTTP 应用仍在运行 | 否 |
| `GET /ready` | 当前是否可接收业务流量 | 是，仅检查已启用组件 |

数据库失效时 `/live` 仍返回成功，避免编排系统反复重启一个其实还能恢复的应用；`/ready` 返回 503
并带上各组件状态。

## 模块生成器

只生成统一的分层骨架，不猜测 `email`、`password` 等业务字段，也不生成没有业务语义的 CRUD 接口。

```powershell
# 基础模块：router / schemas / service / README / 测试
uv run app generate module user

# 追加数据库模型、通用仓储和请求级 Service 依赖
uv run app generate module user --with-model

# 只预览文件变更
uv run app generate module user --with-model --dry-run

# 覆盖无法安全升级的 Service（只影响 service.py）
uv run app generate module user --with-model --force

# 覆盖默认的路由前缀和表名
uv run app generate module user_profile --route-prefix users --table-name user_profiles --with-model
```

生成器是幂等的，支持增量升级：先跑基础命令，补完业务代码之后再追加 `--with-model`，只会创建缺失的
文件并更新受保护标记区域，不会覆盖你写过的 Router、Schema、README 和业务方法。它还会自动注册模块
路由、导入模型，并创建 `tests/modules/__init__.py`，保证生成的测试真的会被 `unittest discover` 执行。

完整的文件清单、标记约定和数据库模型发现规则见 [分包指南](docs/分包指南.md)。

## 如何重命名

按顺序执行，改完跑一次 `uv run python -m unittest discover -s tests` 确认没有遗漏。

**1. 重命名包目录**

```powershell
git mv src/app src/myproject
```

**2. 替换导入路径**

把 `src/` 和 `tests/` 下所有 `from app.` 与 `import app.` 改成 `from myproject.` 与
`import myproject.`，例如用 IDE 的"在目录中替换"限定这两个目录。

注意**只改导入路径**，不要全局替换 `app` 这个词：`main.py` 里的 `app = create_application()`、
`request.app.state`、`@app.exception_handler` 指的是 FastAPI 应用对象，不是包名。同时
`app.main:app` 这种字符串里，冒号前是包名、冒号后是 FastAPI 对象，只需要改冒号前的部分。

**3. 告诉生成器新的包名**

`src/myproject/scaffolding/module_generator.py` 顶部：

```python
PACKAGE_NAME = "myproject"
```

生成器写文件的目标路径、生成代码里的导入和模块注册都从这一处派生，不需要改模板。
生成器使用的 `# scaffold: generated ...` 标记与项目名无关，不需要跟着改。

**4. 更新 `pyproject.toml`**

```toml
[project]
name = "myproject"

[project.scripts]
myproject = "myproject.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/myproject"]
```

**5. 重新同步依赖**

`uv.lock` 记录了发行名，改名后必须重新生成，同时刷新 editable 安装指向：

```powershell
uv lock
uv sync
```

**6.（可选）改环境变量前缀**

`core/config.py` 里的 `env_prefix="APP_"` 改成 `"MYPROJECT_"`，并同步 `.env` 和 `.env.example`。

**7.（可选）改应用显示名**

`.env` 中的 `APP_APP__NAME` 决定 `/docs` 标题和 `GET /api/v1/system/info` 的返回值，默认是 `App`。

**8. 改文档**

`README.md`、`docs/分包指南.md` 里的示例路径和命令（`uv run app` → `uv run myproject`）按需
替换。`src/app/__init__.py` 和 `application.py`、`modules/system/router.py` 里的版本号目前是
硬编码的 `0.1.0`，改版本号时这几处需要一起改。

## 扩展一个可选能力

只有确实需要替换实现、隔离第三方依赖或方便测试时才定义契约。新增 Redis、消息队列等能力时：

1. 在 `core/config.py` 添加该能力自己的配置模型，并默认 `enabled=false`。
2. 为真正需要替换的边界在 `contracts/` 添加协议。
3. 在 `infrastructure/` 实现连接、`start`、`stop` 和 `readiness`。
4. 在 `application.py` 的 `_build_components` 中根据 `enabled` 显式装配。
5. 将第三方库放入 `pyproject.toml` 的独立 optional extra。

这样能力未安装且未启用时不会影响应用；只有显式启用却缺少依赖或配置时才会在启动时失败。
`docs/分包指南.md` 里有以 Redis 为例的完整步骤。

## 已知限制

- **没有数据库迁移工具**：表结构需要自己创建或由外部工具管理，见上文[数据库](#数据库)。
- **500 响应不带 `request_id`**：受 Starlette 中间件层级限制，见上文[响应与错误](#响应与错误)。
- **没有鉴权实现**：`AuthSettings` 只是留出的配置位；接入认证时按"扩展一个可选能力"的流程实现。
- **`common/pagination.py` 使用了 PEP 695 泛型语法**，需要 Python 3.12+ 和较新的 pydantic；
  `pyproject.toml` 只显式约束了 `pydantic-settings`，pydantic 由它间接引入。
- **单进程启动**：`main.py` 固定 `reload=False`，多 worker 部署请自行使用
  `uvicorn app.main:app --workers N` 或交给编排层。

## 架构与启动流程

分包、分层、外部基础设施接入示例、不同数据库适配方式，以及从启动到关闭的完整流程，见
[分包指南](docs/分包指南.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
