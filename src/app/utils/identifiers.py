from uuid import uuid4


def new_id() -> str:
    """生成供应用实体使用的 URL 安全、不透明标识符。"""
    return uuid4().hex
