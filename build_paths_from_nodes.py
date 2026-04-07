"""
使用建模师预埋的道路点构建路径网络
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

def build_paths_for_floor(floor, json_file):
    """为指定楼层构建路径"""
    print(f"\n处理 {floor}楼...")
    
    data = load_floor_data(json_file)
    
    # 1. 提取道路点
    path_nodes = data.get("path_nodes", [])
    print(f"  找到 {len(path_nodes)} 个道路点")
    
    # 2. 提取功能区域（厕所、楼梯、电梯）
    functional_areas = data.get("functional_areas", [])
    print(f"  找到 {len(functional_areas)} 个功能区域")
    
    db = SessionLocal()
    
    # 3. 获取该楼层所有地点
    locations = db.query(Location).filter(Location.floor == floor).all()
    print(f"  数据库中有 {len(locations)} 个地点")
    
    # 4. 创建道路点映射（用于快速查找ID）
    node_map = {}
    for node in path_nodes:
        pos = node["position"]
        node_type = node["type"]
        node_name = node.get("name", f"{node_type}_{floor}")
        
        # 查找或创建对应的Location
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
                name=node_name,
                type="path_node",
                x=pos[0],
                y=pos[1],
                z=floor - 1,  # 假设1楼z=0
                floor=floor,
                is_accessible=True
            )
            db.add(new_loc)
            db.flush()
            node_map[node["id"]] = new_loc.id
            print(f"    新增道路点: {node_name}")
    
    db.commit()
    
    # 5. 连接道路点（按照建模师的意图）
    paths_added = 0
    
    # 连接所有hub和corner（形成主干道）
    hubs = [n for n in path_nodes if n["type"] in ["hub", "corner"]]
    for i in range(len(hubs)):
        for j in range(i+1, len(hubs)):
            id1 = node_map.get(hubs[i]["id"])
            id2 = node_map.get(hubs[j]["id"])
            if id1 and id2:
                p1 = hubs[i]["position"]
                p2 = hubs[j]["position"]
                distance = calculate_distance(p1[0], p1[1], p2[0], p2[1])
                
                # 只连接距离合理的点
                if distance < 15:
                    # 检查是否已存在
                    existing = db.query(Path).filter(
                        ((Path.start_id == id1) & (Path.end_id == id2)) |
                        ((Path.start_id == id2) & (Path.end_id == id1))
                    ).first()
                    
                    if not existing:
                        db.add(Path(start_id=id1, end_id=id2, distance=round(distance,2), type="corridor"))
                        db.add(Path(start_id=id2, end_id=id1, distance=round(distance,2), type="corridor"))
                        paths_added += 2
    
    # 6. 连接功能区域到最近的道路点
    for area in functional_areas:
        center = area.get("center", [0,0])
        area_name = area.get("name", "")
        
        # 找到对应的Location
        area_loc = None
        for loc in locations:
            if abs(loc.x - center[0]) < 0.1 and abs(loc.y - center[1]) < 0.1:
                area_loc = loc
                break
        
        if not area_loc:
            continue
        
        # 找到最近的道路点
        nearest_node = None
        min_dist = float('inf')
        
        for node in path_nodes:
            node_id = node_map.get(node["id"])
            if not node_id:
                continue
            p = node["position"]
            dist = calculate_distance(center[0], center[1], p[0], p[1])
            if dist < min_dist:
                min_dist = dist
                nearest_node = node
        
        if nearest_node and min_dist < 20:  # 只连接5米内的道路点
            node_id = node_map[nearest_node["id"]]
            
            # 检查是否已存在
            existing = db.query(Path).filter(
                ((Path.start_id == area_loc.id) & (Path.end_id == node_id)) |
                ((Path.start_id == node_id) & (Path.end_id == area_loc.id))
            ).first()
            
            if not existing:
                db.add(Path(start_id=area_loc.id, end_id=node_id, distance=round(min_dist,2), type="corridor"))
                db.add(Path(start_id=node_id, end_id=area_loc.id, distance=round(min_dist,2), type="corridor"))
                paths_added += 2
    
    db.commit()
    db.close()
    print(f"  ✅ 为 {floor}楼添加了 {paths_added} 条路径")
    return paths_added

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
        
        # 按坐标的整数部分分组（同一部楼梯/电梯）
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
    
    print(f"\n🎉 总共添加了 {total_paths} 条路径")
    
    # 最终统计
    db = SessionLocal()
    final_count = db.query(Path).count()
    print(f"数据库最终路径数: {final_count}")
    db.close()