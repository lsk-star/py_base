import uvicorn

from app.application import create_application

app = create_application()


def run() -> None:
    # 直接传入本项目已创建的应用对象，避免依赖模块字符串的导入路径。
    settings = app.state.settings
    # 访问日志由中间件在请求上下文仍有效时输出，避免丢失链路标识。
    uvicorn.run(
        app,
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
        access_log=False,
    )
