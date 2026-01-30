from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite数据库连接
SQLALCHEMY_DATABASE_URL = "sqlite:///./hospital_guide.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依赖注入函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# app/database.py 中添加初始化函数
def init_database():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")