#!/usr/bin/env python3
"""
数据库初始化脚本
运行: python init_database.py
"""

import sys
import os

# 添加当前路径到Python路径，确保可以导入app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from app.models import Base

def init_database():
    try:
        # 创建数据库连接 - 使用SQLite
        database_url = "sqlite:///./hospital_guide.db"
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        
        print("🔄 正在创建数据库表...")
        
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        
        print("✅ 数据库表创建成功！")
        print("📊 创建的表：")
        tables = Base.metadata.tables.keys()
        for table in tables:
            print(f"   - {table}")
            
        print(f"\n🎯 数据库文件位置: {os.path.abspath('./hospital_guide.db')}")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()