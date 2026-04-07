"""
使用建模师预埋的道路点构建横平竖直的路径
"""

import json
import math
from app.database import SessionLocal
from app.models import Location, Path

def load_floor_data(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_distance(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def calculate_manhattan_distance(x1, y1, x2, y2):
    """曼哈顿距离（横平竖直）"""
    return abs(x1 - x2) + abs(y1 - y2)

def build_paths_for_floor(floor, json_file):
    """为指定楼层构建横平竖直的路径"""
    print(f"\n处理 {floor}楼...")
    
    data = load_floor_data(json_file)
    
    # 1. 提取道路点
    path_nodes = data.get("path_nodes", [])
    print(f"  找到 {len(path_nodes)} 个道路点")
    
    db = SessionLocal()
    
    # 2. 获取该楼层所有地点
    locations = db.query(Location).filter(Location.floor == floor).all()
    print(f"  数据库中有 {len(locations)} 个地点")
    
    # 3. 创建道路点映射（用于快速查找ID）
    node_map = {}
    for node in path_nodes:
        pos = node["position"]
        node_type = node["type"]
        node_name = node.get("name", f"{node_type}_{floor}")
        
        # 查找对应的Location
        existing = None
        for loc in locations:
            if abs(loc.x - pos[0]) < 0.1 and abs(loc.y - pos[1]) < 0.1:
                existing = loc
                break
        
        if existing:
            node_map[node["id"]] = existing.id
        else:
            # 如果道路点不在数据库中，创建它
            new_loc = Location(
                name=f"道路点_{floor}_{node['id']}",
                type="path_node",
                x=pos[0],
                y=pos[1],
                z=floor - 1,
                floor=floor,
                is_accessible=True
            )
            db.add(new_loc)
            db.flush()
            node_map[node["id"]] = new_loc.id
            print(f"    新增道路点: {node['id']}")
    
    db.commit()
    
    paths_added = 0
    
    # 4. 连接所有道路点（形成主干网络）
    node_ids = list(node_map.values())
    for i in range(len(node_ids)):
        for j in range(i+1, len(node_ids)):
            # 获取两个道路点的坐标
            loc1 = db.query(Location).get(node_ids[i])
            loc2 = db.query(Location).get(node_ids[j])
            
            if loc1 and loc2:
                # 用曼哈顿距离（横平竖直）
                distance = calculate_manhattan_distance(loc1.x, loc1.y, loc2.x, loc2.y)
                
                # 只连接距离合理的点（根据楼层大小调整）
                if distance < 30:
                    # 检查是否已存在
                    existing = db.query(Path).filter(
                        ((Path.start_id == node_ids[i]) & (Path.end_id == node_ids[j])) |
                        ((Path.start_id == node_ids[j]) & (Path.end_id == node_ids[i]))
                    ).first()
                    
                    if not existing:
                        db.add(Path(start_id=node_ids[i], end_id=node_ids[j], distance=round(distance,2), type="corridor"))
                        db.add(Path(start_id=node_ids[j], end_id=node_ids[i], distance=round(distance,2), type="corridor"))
                        paths_added += 2
    
    print(f"  道路点之间添加了 {paths_added} 条路径")
    
    # 5. 连接所有科室到最近的道路点
    dept_paths = 0
    for loc in locations:
        if loc.type == "department":  # 只处理科室
            # 找到最近的道路点
            min_dist = float('inf')
            nearest_node = None
            
            for node_id in node_ids:
                node = db.query(Location).get(node_id)
                if node:
                    dist = calculate_manhattan_distance(loc.x, loc.y, node.x, node.y)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_node = node_id
            
            if nearest_node and min_dist < 20:  # 20米内都能连接
                # 检查是否已存在
                existing = db.query(Path).filter(
                    ((Path.start_id == loc.id) & (Path.end_id == nearest_node)) |
                    ((Path.start_id == nearest_node) & (Path.end_id == loc.id))
                ).first()
                
                if not existing:
                    db.add(Path(start_id=loc.id, end_id=nearest_node, distance=round(min_dist,2), type="corridor"))
                    db.add(Path(start_id=nearest_node, end_id=loc.id, distance=round(min_dist,2), type="corridor"))
                    dept_paths += 2
    
    db.commit()
    print(f"  科室到道路点添加了 {dept_paths} 条路径")
    
    # 6. 连接功能区域（厕所、电梯、楼梯）到最近的道路点
    func_paths = 0
    for loc in locations:
        if loc.type in ["restroom", "elevator", "stairs"]:
            # 找到最近的道路点
            min_dist = float('inf')
            nearest_node = None
            
            for node_id in node_ids:
                node = db.query(Location).get(node_id)
                if node:
                    dist = calculate_manhattan_distance(loc.x, loc.y, node.x, node.y)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_node = node_id
            
            if nearest_node and min_dist < 15:
                existing = db.query(Path).filter(
                    ((Path.start_id == loc.id) & (Path.end_id == nearest_node)) |
                    ((Path.start_id == nearest_node) & (Path.end_id == loc.id))
                ).first()
                
                if not existing:
                    db.add(Path(start_id=loc.id, end_id=nearest_node, distance=round(min_dist,2), type="corridor"))
                    db.add(Path(start_id=nearest_node, end_id=loc.id, distance=round(min_dist,2), type="corridor"))
                    func_paths += 2
    
    db.commit()
    print(f"  功能区域到道路点添加了 {func_paths} 条路径")
    
    total = paths_added + dept_paths + func_paths
    db.close()
    print(f"  ✅ 为 {floor}楼总共添加了 {total} 条路径")
    return total

def add_vertical_connections():
    """添加垂直连接（楼梯和电梯）"""
    print("\n处理垂直连接...")
    db = SessionLocal()
    
    # 获取所有楼梯和电梯
    vertical_locs = db.query(Location).filter(Location.type.in_(["stairs", "elevator"])).all()
    
    # 按类型和大致位置分组
    paths_added = 0
    for loc_type in ["stairs", "elevator"]:
        type_locs = [loc for loc in vertical_locs if loc.type == loc_type]
        
        # 按坐标分组（同一部楼梯/电梯）
        groups = {}
        for loc in type_locs:
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
    db.close()
    print(f"  ✅ 添加了 {paths_added} 条垂直连接")
    return paths_added

if __name__ == "__main__":
    json_files = [
        (1, "hospital_floor_data/m1F_paths.json"),
        (2, "hospital_floor_data/m2F_paths.json"),
        (3, "hospital_floor_data/m3F_paths.json"),
        (4, "hospital_floor_data/m4F_paths.json"),
    ]
    
    # 清空现有路径
    db = SessionLocal()
    print("清空现有路径...")
    db.query(Path).delete()
    db.commit()
    db.close()
    
    total_paths = 0
    for floor, json_file in json_files:
        paths = build_paths_for_floor(floor, json_file)
        total_paths += paths
    
    vertical_paths = add_vertical_connections()
    total_paths += vertical_paths
    
    print(f"\n🎉 总共添加了 {total_paths} 条横平竖直的路径")
    
    # 最终统计
    db = SessionLocal()
    final_count = db.query(Path).count()
    print(f"数据库最终路径数: {final_count}")
    db.close()