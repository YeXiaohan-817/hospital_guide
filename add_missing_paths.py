"""
手动添加缺失的路径连接
确保所有地点都可到达
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Location, Path

def add_missing_paths(db):
    """添加缺失的路径连接"""
    
    # 获取所有地点
    locations = db.query(Location).all()
    loc_map = {loc.id: loc for loc in locations}
    
    print("正在添加缺失路径...")
    paths_added = 0
    
    # 1. 每个楼层的厕所连接到该楼层的电梯和楼梯
    for floor in range(1, 5):
        # 找到该楼层的厕所
        toilets = [loc for loc in locations if loc.floor == floor and loc.type == "restroom"]
        # 找到该楼层的电梯
        elevators = [loc for loc in locations if loc.floor == floor and loc.type == "elevator"]
        # 找到该楼层的楼梯
        stairs = [loc for loc in locations if loc.floor == floor and loc.type == "stairs"]
        
        for toilet in toilets:
            # 连接到电梯
            for elevator in elevators:
                # 计算距离（估算）
                distance = 5.0  # 假设距离5米
                
                # 检查是否已存在路径
                existing = db.query(Path).filter(
                    ((Path.start_id == toilet.id) & (Path.end_id == elevator.id)) |
                    ((Path.start_id == elevator.id) & (Path.end_id == toilet.id))
                ).first()
                
                if not existing:
                    # 添加双向路径
                    db.add(Path(start_id=toilet.id, end_id=elevator.id, distance=distance, type="corridor"))
                    db.add(Path(start_id=elevator.id, end_id=toilet.id, distance=distance, type="corridor"))
                    paths_added += 2
                    print(f"  添加: 厕所_{floor}F ↔ 电梯_{floor}F")
            
            # 连接到楼梯（每个厕所连到最近的楼梯）
            if stairs:
                # 找最近的楼梯（简单起见连第一个）
                stair = stairs[0]
                distance = 6.0
                
                existing = db.query(Path).filter(
                    ((Path.start_id == toilet.id) & (Path.end_id == stair.id)) |
                    ((Path.start_id == stair.id) & (Path.end_id == toilet.id))
                ).first()
                
                if not existing:
                    db.add(Path(start_id=toilet.id, end_id=stair.id, distance=distance, type="corridor"))
                    db.add(Path(start_id=stair.id, end_id=toilet.id, distance=distance, type="corridor"))
                    paths_added += 2
                    print(f"  添加: 厕所_{floor}F ↔ 楼梯_{floor}F")
    
    # 2. 确保同层所有楼梯和电梯互相连接（形成网络）
    for floor in range(1, 5):
        floor_locs = [loc for loc in locations if loc.floor == floor]
        elev_stairs = [loc for loc in floor_locs if loc.type in ["elevator", "stairs"]]
        
        # 两两连接
        for i in range(len(elev_stairs)):
            for j in range(i+1, len(elev_stairs)):
                loc1 = elev_stairs[i]
                loc2 = elev_stairs[j]
                
                # 估算距离
                distance = 8.0
                
                existing = db.query(Path).filter(
                    ((Path.start_id == loc1.id) & (Path.end_id == loc2.id)) |
                    ((Path.start_id == loc2.id) & (Path.end_id == loc1.id))
                ).first()
                
                if not existing:
                    db.add(Path(start_id=loc1.id, end_id=loc2.id, distance=distance, type="corridor"))
                    db.add(Path(start_id=loc2.id, end_id=loc1.id, distance=distance, type="corridor"))
                    paths_added += 2
                    print(f"  添加: {loc1.name} ↔ {loc2.name}")
    
    # 3. 确保垂直连接完整（电梯连电梯，楼梯连楼梯）
    # 电梯连接
    elevators_1f = [loc for loc in locations if loc.floor == 1 and loc.type == "elevator"]
    elevators_2f = [loc for loc in locations if loc.floor == 2 and loc.type == "elevator"]
    elevators_3f = [loc for loc in locations if loc.floor == 3 and loc.type == "elevator"]
    elevators_4f = [loc for loc in locations if loc.floor == 4 and loc.type == "elevator"]
    
    # 连接1-2楼电梯
    for e1 in elevators_1f:
        for e2 in elevators_2f:
            existing = db.query(Path).filter(
                ((Path.start_id == e1.id) & (Path.end_id == e2.id)) |
                ((Path.start_id == e2.id) & (Path.end_id == e1.id))
            ).first()
            if not existing:
                db.add(Path(start_id=e1.id, end_id=e2.id, distance=3.0, type="elevator"))
                db.add(Path(start_id=e2.id, end_id=e1.id, distance=3.0, type="elevator"))
                paths_added += 2
                print(f"  添加: 电梯_1F ↔ 电梯_2F")
    
    # 连接2-3楼电梯
    for e2 in elevators_2f:
        for e3 in elevators_3f:
            existing = db.query(Path).filter(
                ((Path.start_id == e2.id) & (Path.end_id == e3.id)) |
                ((Path.start_id == e3.id) & (Path.end_id == e2.id))
            ).first()
            if not existing:
                db.add(Path(start_id=e2.id, end_id=e3.id, distance=3.0, type="elevator"))
                db.add(Path(start_id=e3.id, end_id=e2.id, distance=3.0, type="elevator"))
                paths_added += 2
                print(f"  添加: 电梯_2F ↔ 电梯_3F")
    
    # 连接3-4楼电梯
    for e3 in elevators_3f:
        for e4 in elevators_4f:
            existing = db.query(Path).filter(
                ((Path.start_id == e3.id) & (Path.end_id == e4.id)) |
                ((Path.start_id == e4.id) & (Path.end_id == e3.id))
            ).first()
            if not existing:
                db.add(Path(start_id=e3.id, end_id=e4.id, distance=3.0, type="elevator"))
                db.add(Path(start_id=e4.id, end_id=e3.id, distance=3.0, type="elevator"))
                paths_added += 2
                print(f"  添加: 电梯_3F ↔ 电梯_4F")
    
    db.commit()
    print(f"\n✅ 成功添加 {paths_added} 条路径")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        add_missing_paths(db)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()