from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 SQLAlchemy 模型的声明基类。"""


class IntIdMixin:
    """绝大多数业务实体使用的默认自增整数主键。"""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)