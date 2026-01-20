#!/usr/bin/env python3
"""
模拟数据填充脚本
运行: python seed_sample_data.py
"""

import sys
import os

# 添加当前路径到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Location, Robot, User
import bcrypt
from datetime import datetime

def seed_sample_data():
    try:
        # 创建数据库连接
        database_url = "sqlite:///./hospital_guide.db"
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        print("🌱 开始填充模拟数据...")
        
        # 1. 添加测试用户（如果不存在）
        existing_user = db.query(User).filter(User.username == "testuser").first()
        if not existing_user:
            hashed_password = bcrypt.hashpw("testpassword".encode('utf-8'), bcrypt.gensalt())
            test_user = User(
                username="testuser",
                hashed_password=hashed_password.decode('utf-8'),
                created_at=datetime.utcnow()
            )
            db.add(test_user)
            print("✅ 添加测试用户: testuser / testpassword")
        
        # 2. 添加位置数据
        locations = [
            Location(name="医院大门", description="主入口", type="entrance", x=0, y=0, floor=1),
            Location(name="门诊部", description="门诊挂号、就诊", type="department", x=100, y=50, floor=1),
            Location(name="药房", description="取药处", type="facility", x=150, y=100, floor=1),
            Location(name="放射科", description="X光、CT检查", type="department", x=200, y=30, floor=2),
            Location(name="检验科", description="抽血、化验", type="department", x=80, y=120, floor=1),
            Location(name="急诊科", description="急诊救治", type="department", x=50, y=80, floor=1),
            Location(name="住院部", description="病房区域", type="department", x=180, y=150, floor=3),
            Location(name="食堂", description="患者及家属用餐", type="facility", x=120, y=180, floor=1),
            Location(name="电梯A", description="1-3楼电梯", type="entrance", x=100, y=75, floor=1),
            Location(name="楼梯间", description="安全通道", type="entrance", x=60, y=40, floor=1),
        ]
        
        # 先清空再添加（可选，第一次运行不需要）
        # db.query(Location).delete()
        
        db.add_all(locations)
        db.flush()  # 获取生成的ID
        print(f"✅ 添加 {len(locations)} 个位置点")
        
        # 3. 添加导引小车数据
        robots = [
            Robot(name="导引小车-01", status="idle", current_location_id=locations[0].id, battery_level=85),
            Robot(name="导引小车-02", status="idle", current_location_id=locations[0].id, battery_level=92),
            Robot(name="导引小车-03", status="charging", current_location_id=locations[7].id, battery_level=35),
        ]
        
        db.add_all(robots)
        print(f"✅ 添加 {len(robots)} 台导引小车")
        
        # 提交所有更改
        db.commit()
        
        print("\n🎉 模拟数据填充完成！")
        print("📊 数据统计:")
        print(f"   👤 用户: 1 个 (testuser)")
        print(f"   📍 位置: {len(locations)} 个")
        print(f"   🤖 小车: {len(robots)} 台")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 数据填充失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    seed_sample_data()