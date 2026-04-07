"""
手动添加缺失的路径连接
确保所有地点都可到达
"""

import sys
import os
import math
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Location, Path

def calculate_distance(x1, y1, x2, y2):
    """计算两点距离"""
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def add_missing_paths(db):
    """添加缺失的路径连接"""
    
    # 获取所有地点
    locations = db.query(Location).all()
    print(f"共有 {len(locations)} 个地点")
    
    # 按楼层分组
    floors = {}
    for loc in locations:
        if loc.floor not in floors:
            floors[loc.floor] = []
        floors[loc.floor].append(loc)
    
    paths_added = 0
    
    # 1. 同层连接：每个楼层内的所有点互相连接（如果距离合适）
    for floor, locs in floors.items():
        print(f"\n处理 {floor}楼，共 {len(locs)} 个地点")
        
        for i in range(len(locs)):
            for j in range(i+1, len(locs)):
                loc1 = locs[i]
                loc2 = locs[j]
                
                # 计算距离
                distance = calculate_distance(loc1.x, loc1.y, loc2.x, loc2.y)
                
                # 只连接距离小于15米的点（避免连得太远）
                if distance < 15:
                    # 检查是否已存在路径
                    existing = db.query(Path).filter(
                        ((Path.start_id == loc1.id) & (Path.end_id == loc2.id)) |
                        ((Path.start_id == loc2.id) & (Path.end_id == loc1.id))
                    ).first()
                    
                    if not existing:
                        # 添加双向路径
                        db.add(Path(start_id=loc1.id, end_id=loc2.id, distance=round(distance, 2), type="corridor"))
                        db.add(Path(start_id=loc2.id, end_id=loc1.id, distance=round(distance, 2), type="corridor"))
                        paths_added += 2
                        print(f"  添加: {loc1.name} ↔ {loc2.name} ({distance:.2f}m)")
        
        db.commit()
    
    # 2. 垂直连接：确保所有楼梯/电梯跨楼层连接
    print("\n处理垂直连接...")
    
    # 获取所有楼梯和电梯
    vertical_locs = [loc for loc in locations if loc.type in ["stairs", "elevator"]]
    
    # 按类型和位置分组
    for loc_type in ["stairs", "elevator"]:
        type_locs = [loc for loc in vertical_locs if loc.type == loc_type]
        
        # 按大致位置分组（同一部楼梯/电梯）
        groups = {}
        for loc in type_locs:
            # 用坐标的整数部分分组
            key = f"{round(loc.x)}_{round(loc.y)}"
            if key not in groups:
                groups[key] = []
            groups[key].append(loc)
        
        # 每组内连接所有楼层
        for key, group in groups.items():
            group.sort(key=lambda x: x.floor)
            for i in range(len(group)-1):
                loc1 = group[i]
                loc2 = group[i+1]
                
                existing = db.query(Path).filter(
                    ((Path.start_id == loc1.id) & (Path.end_id == loc2.id)) |
                    ((Path.start_id == loc2.id) & (Path.end_id == loc1.id))
                ).first()
                
                if not existing:
                    distance = 3.0  # 层高
                    db.add(Path(start_id=loc1.id, end_id=loc2.id, distance=distance, type=loc_type))
                    db.add(Path(start_id=loc2.id, end_id=loc1.id, distance=distance, type=loc_type))
                    paths_added += 2
                    print(f"  添加: {loc1.name} ↔ {loc2.name}")
    
    db.commit()
    print(f"\n✅ 成功添加 {paths_added} 条路径")
    
    # 统计
    total_paths = db.query(Path).count()
    print(f"当前总路径数: {total_paths}")

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