from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Alembic 自动生成迁移前，必须导入所有 SQLAlchemy 模型。"""
