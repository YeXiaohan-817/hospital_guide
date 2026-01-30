"""
初始化测试数据脚本
在项目根目录运行：python init_test.py
"""

import sys
sys.path.append('.')

from app.database import SessionLocal, engine
from app.models import Base, User, Location, Path, Robot, NavigationTask
from datetime import datetime
import json

def init_database():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")

def create_test_data():
    """创建测试数据"""
    db = SessionLocal()
    
    try:
        # 1. 创建测试用户
        if db.query(User).count() == 0:
            test_user = User(
                username="test_user",
                hashed_password="test_pass"
            )
            db.add(test_user)
            print("✅ 创建测试用户")
        
        # 2. 创建测试地点（5个）
        if db.query(Location).count() == 0:
            locations = [
                Location(
                    name="门诊大厅", 
                    type="entrance", 
                    x=0.0, y=0.0, floor=1,
                    description="医院主入口"
                ),
                Location(
                    name="药房", 
                    type="pharmacy", 
                    x=15.0, y=5.0, floor=1,
                    description="取药处"
                ),
                Location(
                    name="放射科", 
                    type="department", 
                    x=25.0, y=10.0, floor=2,
                    description="X光、CT检查"
                ),
                Location(
                    name="1号电梯", 
                    type="elevator", 
                    x=8.0, y=3.0, floor=1,
                    description="主电梯"
                ),
                Location(
                    name="CT室", 
                    type="room", 
                    x=30.0, y=12.0, floor=2,
                    description="CT检查室"
                ),
                Location(
                    name="急诊室", 
                    type="emergency", 
                    x=40.0, y=20.0, floor=1,
                    description="急诊科"
                ),
                Location(
                    name="二楼走廊", 
                    type="corridor_node", 
                    x=20.0, y=15.0, floor=2,
                    description="二楼主干道"
                ),
                Location(
                    name="楼梯间", 
                    type="stairs", 
                    x=10.0, y=8.0, floor=1,
                    description="安全楼梯"
                )
            ]
            db.add_all(locations)
            print(f"✅ 创建 {len(locations)} 个测试地点")
        
        # 3. 创建测试机器人
        if db.query(Robot).count() == 0:
            robots = [
                Robot(name="导引车01", status="idle", battery_level=80),
                Robot(name="导引车02", status="idle", battery_level=90),
                Robot(name="导引车03", status="busy", battery_level=60)
            ]
            db.add_all(robots)
            print(f"✅ 创建 {len(robots)} 个测试机器人")
        
        db.commit()
        
        # 4. 创建路径网络（所有地点间双向连接）
        location_ids = [loc.id for loc in db.query(Location).all()]
        print(f"可用地点ID: {location_ids}")
        
        if db.query(Path).count() == 0:
            # 基础路径连接
            path_definitions = [
                # 楼层1内连接
                (1, 2, 15.0, "corridor"),
                (1, 4, 8.0, "corridor"),
                (1, 8, 10.0, "corridor"),
                (2, 4, 12.0, "corridor"),
                (2, 6, 25.0, "corridor"),
                (4, 8, 5.0, "corridor"),
                
                # 跨楼层连接（电梯/楼梯）
                (4, 3, 15.0, "elevator"),   # 电梯到2楼
                (4, 5, 18.0, "elevator"),   # 电梯到CT室
                (4, 7, 12.0, "elevator"),   # 电梯到二楼走廊
                (8, 3, 20.0, "stairs"),     # 楼梯到2楼
                (8, 5, 22.0, "stairs"),     # 楼梯到CT室
                
                # 二楼内连接
                (3, 5, 10.0, "corridor"),
                (3, 7, 8.0, "corridor"),
                (5, 7, 15.0, "corridor"),
                (7, 8, 18.0, "corridor")    # 走廊到楼梯（同楼层）
            ]
            
            paths = []
            for start_id, end_id, distance, path_type in path_definitions:
                # 正向路径
                paths.append(Path(
                    start_id=start_id,
                    end_id=end_id,
                    distance=distance,
                    type=path_type,
                    attributes={
                        "width": 2.0,
                        "wheelchair_accessible": path_type != "stairs",
                        "crowdedness": 0.3,
                        "is_bidirectional": True
                    }
                ))
                # 反向路径（如果是双向）
                paths.append(Path(
                    start_id=end_id,
                    end_id=start_id,
                    distance=distance,
                    type=path_type,
                    attributes={
                        "width": 2.0,
                        "wheelchair_accessible": path_type != "stairs",
                        "crowdedness": 0.3,
                        "is_bidirectional": True
                    }
                ))
            
            db.add_all(paths)
            print(f"✅ 创建 {len(paths)} 条路径（双向网络）")
        
        db.commit()
        
        # 5. 打印总结
        print("\n" + "="*40)
        print("📊 数据库状态总结:")
        print(f"  用户数: {db.query(User).count()}")
        print(f"  地点数: {db.query(Location).count()}")
        print(f"  机器人: {db.query(Robot).count()}")
        print(f"  路径数: {db.query(Path).count()}")
        print(f"  任务数: {db.query(NavigationTask).count()}")
        print("="*40)
        print("\n🎉 测试数据初始化完成！")
        print("\n📍 可用测试地点ID:")
        locations = db.query(Location).all()
        for loc in locations:
            print(f"  ID {loc.id}: {loc.name} ({loc.type}, 楼层{loc.floor})")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        raise
    finally:
        db.close()

def cleanup_old_data():
    """清理旧数据（可选）"""
    db = SessionLocal()
    try:
        db.query(NavigationTask).delete()
        db.query(Path).delete()
        print("✅ 清理旧数据完成")
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 开始初始化医院导航系统测试数据...")
    
    # 可选：清理旧数据
    # cleanup_old_data()
    
    # 初始化数据库表
    init_database()
    
    # 创建测试数据
    create_test_data()
    
    print("\n✅ 所有测试数据准备就绪！")
    print("\n🧪 测试命令:")
    print("  1. 获取地点列表: curl http://127.0.0.1:8000/api/v1/locations")
    print("  2. 智能路径规划: curl -X POST http://127.0.0.1:8000/api/v1/plan -H \"Content-Type: application/json\" -d '{\"start_id\":1,\"end_id\":3,\"user_type\":\"wheelchair\"}'")
    print("  3. 创建导航任务: curl -X POST http://127.0.0.1:8000/api/v1/navigation/tasks -H \"Content-Type: application/json\" -d '{\"user_id\":1,\"location_ids\":[1,2,3,4,5],\"user_type\":\"normal\"}'")
    print("\n📢 注意：请确保后端服务正在运行 (uvicorn app.main:app --reload)")