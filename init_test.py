"""
初始化测试数据脚本
生成医院地图的测试数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import Base, Location, Path, Robot, User

# 先创建所有表
print("正在创建数据库表...")
Base.metadata.create_all(bind=engine)
print("✅ 数据库表创建完成")

def init_database(db):
    """初始化数据库"""
    
    # 测试地点数据 - 确保z坐标 = floor * 3.0
    test_locations = [
        # 1楼地点 (z = 0.0)
        {"name": "门诊大厅", "description": "医院主入口", "type": "entrance", 
         "x": 0.0, "y": 0.0, "z": 0.0, "floor": 1, "is_accessible": True},
        {"name": "药房", "description": "取药处", "type": "pharmacy", 
         "x": 15.0, "y": 5.0, "z": 0.0, "floor": 1, "is_accessible": True},
        {"name": "1号电梯", "description": "主电梯", "type": "elevator", 
         "x": 8.0, "y": 3.0, "z": 0.0, "floor": 1, "is_accessible": True},
        {"name": "挂号处", "description": "挂号缴费", "type": "counter", 
         "x": 5.0, "y": -2.0, "z": 0.0, "floor": 1, "is_accessible": True},
        {"name": "楼梯1", "description": "1-2楼楼梯", "type": "stairs", 
         "x": 12.0, "y": -4.0, "z": 0.0, "floor": 1, "is_accessible": False},
        
        # 2楼地点 (z = 3.0)
        {"name": "放射科", "description": "X光、CT检查", "type": "department", 
         "x": 25.0, "y": 10.0, "z": 3.0, "floor": 2, "is_accessible": True},
        {"name": "CT室", "description": "CT检查室", "type": "room", 
         "x": 30.0, "y": 12.0, "z": 3.0, "floor": 2, "is_accessible": True},
        {"name": "2楼电梯", "description": "1号电梯的2楼出口", "type": "elevator", 
         "x": 8.0, "y": 3.0, "z": 3.0, "floor": 2, "is_accessible": True},
        {"name": "楼梯2", "description": "1-2楼楼梯的2楼出口", "type": "stairs", 
         "x": 12.0, "y": -4.0, "z": 3.0, "floor": 2, "is_accessible": False},
        {"name": "医生办公室", "description": "放射科医生办公室", "type": "office", 
         "x": 22.0, "y": 8.0, "z": 3.0, "floor": 2, "is_accessible": True},
    ]

    # 测试路径连接 (双向连接)
    test_paths = [
        # 1楼路径 - 使用start_id和end_id
        {"start_id": 1, "end_id": 2, "distance": 18.0, "type": "corridor"},
        {"start_id": 1, "end_id": 4, "distance": 7.0, "type": "corridor"},
        {"start_id": 2, "end_id": 3, "distance": 10.0, "type": "corridor"},
        {"start_id": 4, "end_id": 5, "distance": 8.0, "type": "stairs"},
        
        # 楼层间连接 (电梯)
        {"start_id": 3, "end_id": 8, "distance": 3.0, "type": "elevator"},
        
        # 楼层间连接 (楼梯)
        {"start_id": 5, "end_id": 9, "distance": 3.0, "type": "stairs"},
        
        # 2楼路径
        {"start_id": 6, "end_id": 7, "distance": 7.0, "type": "corridor"},
        {"start_id": 6, "end_id": 10, "distance": 5.0, "type": "corridor"},
        {"start_id": 8, "end_id": 6, "distance": 20.0, "type": "corridor"},
    ]

    # 测试用户
    test_users = [
        {"username": "test_user", "hashed_password": "test123", "user_type": "normal"},
        {"username": "wheelchair_user", "hashed_password": "test123", "user_type": "wheelchair"},
        {"username": "emergency_user", "hashed_password": "test123", "user_type": "emergency"},
    ]

    # 测试机器人
    test_robots = [
        {"name": "导引车01", "status": "idle", "current_location_id": 1, "battery_level": 95},
        {"name": "导引车02", "status": "busy", "current_location_id": 6, "battery_level": 80},
    ]
    
    print("正在清空数据库...")
    # 清空所有表（简单的顺序）
    db.query(Path).delete()
    db.query(Location).delete()
    db.query(Robot).delete()
    db.query(User).delete()
    db.commit()
    
    print("创建测试地点...")
    location_objects = []
    for loc_data in test_locations:
        location = Location(**loc_data)
        db.add(location)
        location_objects.append(location)
    db.commit()
    
    # 获取ID映射
    location_ids = {loc.name: loc.id for loc in location_objects}
    print(f"地点ID映射: {location_ids}")
    
    print("创建测试路径...")
    for path_data in test_paths:
        db.add(Path(**path_data))
    
    print("创建测试用户...")
    for user_data in test_users:
        db.add(User(**user_data))
    
    print("创建测试机器人...")
    for robot_data in test_robots:
        db.add(Robot(**robot_data))
    
    db.commit()
    print("✅ 数据库初始化完成！")
    print(f"创建了 {len(test_locations)} 个地点")
    print(f"创建了 {len(test_paths)} 条路径")
    print(f"创建了 {len(test_users)} 个用户")
    print(f"创建了 {len(test_robots)} 个机器人")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        init_database(db)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()