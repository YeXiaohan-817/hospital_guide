"""
导入所有楼层坐标和路径数据
从JSON文件中提取并建立完整的医院导航网络
"""

import sys
import os
import json
import math
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import Base, Location, Path

# 楼层Z值映射（从Excel表格）
FLOOR_Z = {
    1: 0,  # 一楼
    2: 1,  # 二楼  
    3: 2,  # 三楼
    4: 3   # 四楼
}

# 楼层名称映射
FLOOR_NAME = {
    1: "一楼",
    2: "二楼",
    3: "三楼", 
    4: "四楼"
}

def parse_json_paths(json_file, floor):
    """从JSON文件提取功能区域"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        locations = []
        
        # 提取功能区域（楼梯、电梯、厕所）
        for area in data.get("functional_areas", []):
            name = area.get("name", "")
            material = area.get("material", "")
            category = area.get("category", "unknown")
            center = area.get("center", [0, 0])
            
            # 根据材质确定类型
            if material == "电梯" or category == "elevator":
                loc_type = "elevator"
            elif material == "楼梯" or category == "stair":
                loc_type = "stairs"
            elif material == "厕所" or category == "toilet":
                loc_type = "restroom"
            else:
                loc_type = "department"
            
            # 生成一个可读的名称
            if loc_type == "elevator":
                display_name = f"电梯_{floor}F"
            elif loc_type == "stairs":
                # 根据位置给楼梯命名
                if center[0] > 5:
                    display_name = f"东楼梯_{floor}F"
                elif center[0] < -5:
                    display_name = f"西楼梯_{floor}F"
                elif center[1] > 2:
                    display_name = f"北楼梯_{floor}F"
                else:
                    display_name = f"楼梯_{floor}F"
            elif loc_type == "restroom":
                display_name = f"厕所_{floor}F"
            else:
                display_name = f"{material}_{floor}F"
            
            locations.append({
                "name": display_name,
                "type": loc_type,
                "x": center[0],
                "y": center[1],
                "z": FLOOR_Z[floor],
                "floor": floor,
                "is_accessible": True if loc_type != "stairs" else False
            })
        
        return locations
    except Exception as e:
        print(f"  解析文件 {json_file} 失败: {e}")
        return []

def calculate_distance(x1, y1, x2, y2):
    """计算两点距离"""
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def import_all_data(db):
    """导入所有楼层数据"""
    
    # 清空现有数据
    print("清空数据库...")
    db.query(Path).delete()
    db.query(Location).delete()
    db.commit()
    
    all_locations = []
    
    # 从JSON文件导入各楼层功能区域
    json_files = [
        ("m1F_paths.json", 1),
        ("m2F_paths.json", 2),
        ("m3F_paths.json", 3),
        ("m4F_paths.json", 4)
    ]
    
    for json_file, floor in json_files:
        file_path = os.path.join("hospital_floor_data", json_file)
        if os.path.exists(file_path):
            print(f"导入 {FLOOR_NAME[floor]} 数据...")
            locations = parse_json_paths(file_path, floor)
            all_locations.extend(locations)
            print(f"  找到 {len(locations)} 个功能区域")
        else:
            print(f"文件不存在: {file_path}")
    
    print(f"\n总共找到 {len(all_locations)} 个地点")
    
    # 导入到数据库
    print("\n导入地点到数据库...")
    location_objects = []
    for loc_data in all_locations:
        location = Location(**loc_data)
        db.add(location)
        location_objects.append(location)
    db.commit()
    print(f"✅ 成功导入 {len(location_objects)} 个地点")
    
    # 创建地点名称到ID的映射
    loc_map = {}
    for loc in location_objects:
        # 用楼层+类型+大致位置作为键
        key = f"{loc.floor}_{loc.type}_{round(loc.x)}_{round(loc.y)}"
        loc_map[key] = loc.id
        # 同时也保存原始名称映射
       
            
    
    # 生成路径
    print("\n生成路径连接...")
    paths_added = 0
    
    # 1. 同层连接：按Y坐标分组连接
    for floor in range(1, 5):
        floor_locs = [loc for loc in location_objects if loc.floor == floor]
        
        # 按Y坐标分组（每2米一组）
        groups = {}
        for loc in floor_locs:
            y_group = round(loc.y)
            if y_group not in groups:
                groups[y_group] = []
            groups[y_group].append(loc)
        
        # 在同一组内按X顺序连接
        for y_group, locs in groups.items():
            locs.sort(key=lambda l: l.x)
            
            for i in range(len(locs) - 1):
                loc1 = locs[i]
                loc2 = locs[i+1]
                
                distance = calculate_distance(loc1.x, loc1.y, loc2.x, loc2.y)
                # 只连接距离小于10米的点
                if distance < 10:
                    # 双向连接
                    path1 = Path(
                        start_id=loc1.id,
                        end_id=loc2.id,
                        distance=round(distance, 2),
                        type="corridor"
                    )
                    db.add(path1)
                    paths_added += 1
                    
                    path2 = Path(
                        start_id=loc2.id,
                        end_id=loc1.id,
                        distance=round(distance, 2),
                        type="corridor"
                    )
                    db.add(path2)
                    paths_added += 1
    
    # 2. 垂直连接：相同类型的楼梯/电梯跨楼层连接
    for floor in range(1, 4):  # 1-2, 2-3, 3-4
        # 获取相邻楼层
        floor_locs_curr = [loc for loc in location_objects if loc.floor == floor]
        floor_locs_next = [loc for loc in location_objects if loc.floor == floor + 1]
        
        # 连接电梯
        elevators_curr = [loc for loc in floor_locs_curr if loc.type == "elevator"]
        elevators_next = [loc for loc in floor_locs_next if loc.type == "elevator"]
        
        for e1 in elevators_curr:
            for e2 in elevators_next:
                # 如果位置相近（同一部电梯）
                if abs(e1.x - e2.x) < 3 and abs(e1.y - e2.y) < 3:
                    # 垂直距离（层高）
                    distance = 3.0  # 假设层高3米
                    
                    path1 = Path(
                        start_id=e1.id,
                        end_id=e2.id,
                        distance=distance,
                        type="elevator"
                    )
                    db.add(path1)
                    paths_added += 1
                    
                    path2 = Path(
                        start_id=e2.id,
                        end_id=e1.id,
                        distance=distance,
                        type="elevator"
                    )
                    db.add(path2)
                    paths_added += 1
        
        # 连接楼梯
        stairs_curr = [loc for loc in floor_locs_curr if loc.type == "stairs"]
        stairs_next = [loc for loc in floor_locs_next if loc.type == "stairs"]
        
        for s1 in stairs_curr:
            for s2 in stairs_next:
                # 如果位置相近（同一楼梯）
                if abs(s1.x - s2.x) < 3 and abs(s1.y - s2.y) < 3:
                    # 楼梯距离（斜边）
                    distance = 4.0  # 估算楼梯长度
                    
                    path1 = Path(
                        start_id=s1.id,
                        end_id=s2.id,
                        distance=distance,
                        type="stairs"
                    )
                    db.add(path1)
                    paths_added += 1
                    
                    path2 = Path(
                        start_id=s2.id,
                        end_id=s1.id,
                        distance=distance,
                        type="stairs"
                    )
                    db.add(path2)
                    paths_added += 1
    
    db.commit()
    print(f"✅ 成功添加 {paths_added} 条路径")
    
    # 统计信息
    print("\n📊 导入完成统计：")
    for floor in range(1, 5):
        count = len([loc for loc in location_objects if loc.floor == floor])
        print(f"  {FLOOR_NAME[floor]}: {count} 个地点")
    print(f"  总计: {len(location_objects)} 个地点, {paths_added} 条路径")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        import_all_data(db)
        print("\n🎉 所有楼层数据导入完成！")
    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()