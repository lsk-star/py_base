# PyBase

PyBase 是一个基于 FastAPI 的异步 Python 后端脚手架。它的最小核心只提供 Web 应用、配置、日志、统一响应、异常处理、请求链路标识和健康检查；数据库等外部能力按需安装并显式启用。

## 设计原则

- **最小核心**：未启用的能力不连接、不初始化，也不要求安装其依赖。
- **显式装配**：`src/pybase/application.py` 是唯一的应用装配点，负责配置、日志、中间件、生命周期组件和路由注册。
- **按模块配置**：`Settings` 由 `AppSettings`、`LoggingSettings`、`DatabaseSettings` 等模块配置组成，新增能力只添加自己的配置对象。
- **按业务拆分**：业务代码放入 `modules/<业务名>/`，其中 HTTP 路由、Schema、服务和仓储可随模块演进，不形成全局巨型 `services` 目录。
- **只在边界抽象**：生命周期、外部服务、持久化等可替换边界才定义契约；不存在只有一个实现的 `IFooService/FooServiceImpl` 占位层。

## 目录

```text
src/pybase/
├── application.py                 # 应用工厂，唯一总装配点
├── core/                          # 配置、日志、上下文、异常与错误码
├── contracts/                     # 有替换价值的边界协议
├── presentation/                  # HTTP 响应、中间件、异常处理
├── infrastructure/database/       # 可选 SQLAlchemy 实现
├── modules/                       # 业务或运维模块
├── common/                        # 跨模块值对象，如分页
└── utils/                         # 无状态小工具
```

## 前置条件

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/)

安装 uv 后，在项目目录执行：

```powershell
uv sync
uv run pybase
```

服务默认监听 `http://127.0.0.1:8000`，OpenAPI 文档位于 `http://127.0.0.1:8000/docs`。

若本机已有项目占用 `8000`，可在 `.env` 修改端口后重新启动：

```env
PYBASE_APP__PORT=8001
```

此时文档地址为 `http://127.0.0.1:8001/docs`。可用以下命令确认端口实际由哪个进程监听：

```powershell
netstat -ano | Select-String ':8000'
```

## 配置

复制配置示例并按环境修改：

```powershell
Copy-Item .env.example .env
```

所有环境变量使用 `PYBASE_` 前缀和双下划线分层：

```env
PYBASE_APP__ENVIRONMENT=production
PYBASE_LOGGING__FORMAT=json
PYBASE_DATABASE__ENABLED=false
```

数据库默认关闭。关闭时可只安装核心依赖，应用不会导入 SQLAlchemy 或建立数据库连接。

## 可选数据库

安装数据库能力：

```powershell
uv sync --extra database-postgresql
```

在 `.env` 中启用并配置：

```env
PYBASE_DATABASE__ENABLED=true
PYBASE_DATABASE__URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/pybase
PYBASE_DATABASE__STRICT_STARTUP=true
```

启用数据库后，应用启动时将创建引擎并验证连接；关闭时释放连接池。

- `STRICT_STARTUP=true`：无法连接数据库时拒绝启动，适合绝大多数生产服务。
- `STRICT_STARTUP=false`：应用可启动，但 `/ready` 会报告数据库未就绪，直到依赖恢复。

本地或测试场景可用 SQLite：

```env
PYBASE_DATABASE__URL=sqlite+aiosqlite:///./pybase.db
```

## 数据库迁移

数据库模型继承 `pybase.infrastructure.database.base.Base`。新增模型后，在
`src/pybase/infrastructure/database/models/__init__.py` 导入它，Alembic 才能发现元数据；然后生成迁移：

```powershell
uv run alembic revision --autogenerate -m "create users"
uv run alembic upgrade head
```

迁移命令同样读取 `.env` 中的 `PYBASE_DATABASE__URL`。

## 健康检查

| 路径 | 含义 | 检查外部依赖 |
| --- | --- | --- |
| `GET /live` | 进程与 HTTP 应用仍在运行 | 否 |
| `GET /ready` | 当前是否可接收业务流量 | 是，仅检查已启用组件 |

数据库失效时，`/live` 仍成功，避免编排系统错误重启一个仍可恢复的应用；`/ready` 返回 503 并带上各组件状态。

版本化 API 默认使用 `/api/v1` 前缀，初始信息端点为 `GET /api/v1/system/info`。

## 响应与错误

接口成功和失败均采用统一格式，同时保留准确的 HTTP 状态码：

```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "ok",
  "data": {},
  "request_id": "..."
}
```

默认只生成 `request_id`，用于关联一次 HTTP 请求的全部日志。客户端可以通过 `X-Request-ID` 传入自己的请求标识，应用会将它回写到响应头。

`trace_id` 是可选的分布式追踪能力，默认关闭。接入 OpenTelemetry、网关或多服务调用链后，设置 `PYBASE_TRACING__ENABLED=true`，应用才会透传上游传入的 `X-Trace-ID` 或 W3C `traceparent`。它不会在未接入追踪系统时额外生成随机值。

访问日志由中间件输出，记录请求方法、路径、脱敏后的查询参数、响应状态码和耗时；不记录请求体、`Authorization`、`Cookie` 等敏感信息。

## 架构与启动流程

分包、分层、外部基础设施接入示例、不同数据库适配方式、Alembic 迁移流程，以及从启动到关闭的完整流程，请阅读 [架构指南](docs/分包指南.md)。

## 扩展一个可选能力

只有实际需要替换实现、隔离第三方依赖或方便测试时才定义契约。新增 Redis、消息队列等能力时：

1. 在 `core/config.py` 添加该能力自己的配置模型，并默认 `enabled=false`。
2. 为真正需要替换的边界在 `contracts/` 添加协议。
3. 在 `infrastructure/` 实现连接、`start`、`stop` 和 `readiness`。
4. 在 `application.py` 的 `_build_components` 中根据 `enabled` 显式装配。
5. 将第三方库放入 `pyproject.toml` 的独立 optional extra。

这样能力未安装且未启用时不会影响应用；只有显式启用却缺少依赖或配置时才会在启动时失败。

## 验证

无需安装额外测试框架，可运行内置回归测试：

```powershell
uv run python -m unittest discover -s tests -v
```

## 模块生成

生成通用业务模块骨架：

```powershell
uv run pybase generate module user
```

生成带数据库模型、通用仓储和请求级 Service 依赖的模块：

```powershell
uv run pybase generate module user --with-model
```

默认路由前缀和表名均使用模块名原样。可通过 `--route-prefix`、`--table-name` 覆盖；使用
`--dry-run` 仅查看文件变更。生成器不会猜测业务字段，也不会自动生成 CRUD HTTP 接口。

生成器支持增量升级：先执行基础命令，后续再追加 `--with-model` 即可补齐模型、仓储、依赖注入、
数据库路由标记和 Alembic 模型导入。重复执行同一命令不会重复注册模块或覆盖已有 Router、Schema、
README、测试文件。若 Service 缺少生成器标记且无法确认安全升级，会拒绝覆盖；只有显式传入
`--force` 才会覆盖 Service 文件。

完整的生成文件说明、模块注册和数据库模型发现规则见 [分包指南](docs/分包指南.md)。
