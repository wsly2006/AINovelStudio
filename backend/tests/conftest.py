import os
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# 测试用临时数据库,必须在导入 app 前设置
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # 延迟导入,确保上面的环境变量先生效
    from app.database import Base, engine
    from app.main import app

    # 每个测试用例前重建表
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session(client: TestClient) -> Generator[Session, None, None]:
    """提供原始 SQLAlchemy Session,用于绕过 API 直接 seed 测试数据。
    依赖 client fixture 保证表已建好且 DATABASE_URL 已设置。"""
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
