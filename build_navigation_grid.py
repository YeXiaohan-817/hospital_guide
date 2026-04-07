"""
从JSON文件构建导航网格
考虑墙体障碍物，区分科室和真正的墙体
生成真正的可通行路径
"""

import json
import math
import numpy as np
from queue import PriorityQueue
from app.database import SessionLocal
from app.models import Location, Path

# 网格大小（米）
GRID_SIZE = 0.5

def load_floor_data(json_file):
    """加载楼层数据"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_navigation_grid(boundary, holes, obstacles, grid_size=0.5):
    """
    创建导航网格
    boundary: 楼层边界 [ [x_min,y_min], [x_max,y_min], [x_max,y_max], [x_min,y_max] ]
    holes: 墙体区域列表，每个区域是4个点的多边形
    obstacles: 原始障碍物数据，用于区分墙体和科室
    """
    x_min, y_min = boundary[0]
    x_max, y_max = boundary[2]
    
    # 计算网格维度
    x_cells = int((x_max - x_min) / grid_size) + 1
    y_cells = int((y_max - y_min) / grid_size) + 1
    
    # 初始全部标记为可走
    grid = np.ones((y_cells, x_cells), dtype=int)
    
    print(f"    网格范围: x[{x_min:.2f}, {x_max:.2f}], y[{y_min:.2f}, {y_max:.2f}]")
    print(f"    网格大小: {x_cells} x {y_cells}")
    
    # 1. 先标记所有holes为不可走（真正的墙体）
    hole_count = 0
    for hole in holes:
        # 获取墙体多边形的最小包围盒
        x_vals = [p[0] for p in hole]
        y_vals = [p[1] for p in hole]
        hole_x_min, hole_x_max = min(x_vals), max(x_vals)
        hole_y_min, hole_y_max = min(y_vals), max(y_vals)
        
        # 计算对应的网格范围
        start_x = max(0, int((hole_x_min - x_min) / grid_size))
        end_x = min(x_cells-1, int((hole_x_max - x_min) / grid_size))
        start_y = max(0, int((hole_y_min - y_min) / grid_size))
        end_y = min(y_cells-1, int((hole_y_max - y_min) / grid_size))
        
        # 标记为不可走
        grid[start_y:end_y+1, start_x:end_x+1] = 0
        hole_count += 1
    
    print(f"    标记了 {hole_count} 个墙体区域为不可走")
    
    # 2. 把科室位置重新标记为可走（因为科室内部是可以进入的）
    dept_count = 0
    for obs in obstacles:
        material = obs.get("material", "")
        # 检查是否是科室（注意处理乱码）
        if "科室" in material or "诊室" in material or "绉戝" in material:
            bounds = obs.get("bounds", {})
            if bounds:
                obs_x_min = bounds.get("x_min", 0)
                obs_x_max = bounds.get("x_max", 0)
                obs_z_min = bounds.get("z_min", 0)
                obs_z_max = bounds.get("z_max", 0)
                
                # 转换为网格坐标
                start_x = max(0, int((obs_x_min - x_min) / grid_size))
                end_x = min(x_cells-1, int((obs_x_max - x_min) / grid_size))
                start_y = max(0, int((obs_z_min - y_min) / grid_size))
                end_y = min(y_cells-1, int((obs_z_max - y_min) / grid_size))
                
                # 重新标记为可走
                grid[start_y:end_y+1, start_x:end_x+1] = 1
                dept_count += 1
    
    print(f"    恢复了 {dept_count} 个科室区域为可走")
    print(f"    最终可走网格比例: {np.sum(grid)}/{grid.size} ({np.sum(grid)/grid.size*100:.1f}%)")
    
    return grid, x_min, y_min

def point_to_grid(x, y, x_min, y_min, grid_size):
    """将坐标转换为网格索引"""
    gx = int((x - x_min) / grid_size)
    gy = int((y - y_min) / grid_size)
    return gx, gy

def grid_to_point(gx, gy, x_min, y_min, grid_size):
    """将网格索引转换为中心坐标"""
    x = x_min + (gx + 0.5) * grid_size
    y = y_min + (gy + 0.5) * grid_size
    return x, y

def find_path_in_grid(start_gx, start_gy, end_gx, end_gy, grid):
    """在网格中使用A*算法找路径"""
    rows, cols = grid.shape
    start = (start_gy, start_gx)
    end = (end_gy, end_gx)
    
    # 如果起点或终点不可走，返回空
    if grid[start] == 0 or grid[end] == 0:
        return None
    
    # A*算法
    open_set = PriorityQueue()
    open_set.put((0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: abs(end[0]-start[0]) + abs(end[1]-start[1])}
    
    # 8方向移动
    directions = [(0,1), (1,0), (0,-1), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]
    
    while not open_set.empty():
        current = open_set.get()[1]
        
        if current == end:
            # 重建路径
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path
        
        for dy, dx in directions:
            neighbor = (current[0] + dy, current[1] + dx)
            
            # 检查边界
            if neighbor[0] < 0 or neighbor[0] >= rows or neighbor[1] < 0 or neighbor[1] >= cols:
                continue
            
            # 检查是否可走
            if grid[neighbor] == 0:
                continue
            
            # 对角线移动需要检查相邻格子是否可走（防止穿墙）
            if dx != 0 and dy != 0:
                if grid[current[0] + dy, current[1]] == 0 or grid[current[0], current[1] + dx] == 0:
                    continue
            
            # 计算移动代价
            move_cost = math.sqrt(dx*dx + dy*dy) * GRID_SIZE
            tentative_g = g_score[current] + move_cost
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = abs(end[0]-neighbor[0]) + abs(end[1]-neighbor[1])
                f = tentative_g + h
                open_set.put((f, neighbor))
    
    return None

def build_paths_for_floor(floor, json_file):
    """为指定楼层构建真实路径"""
    print(f"\n处理 {floor}楼...")
    
    data = load_floor_data(json_file)
    boundary = data["walkable_area"]["boundary"]
    holes = data["walkable_area"]["holes"]
    obstacles = data.get("obstacles", [])
    
    # 创建导航网格
    grid, x_min, y_min = create_navigation_grid(boundary, holes, obstacles, GRID_SIZE)
    
    # 获取该楼层所有地点
    db = SessionLocal()
    locations = db.query(Location).filter(Location.floor == floor).all()
    print(f"  该楼层有 {len(locations)} 个地点")
    
    # 为每个地点找到对应的网格
    loc_grid_pos = {}
    for loc in locations:
        gx, gy = point_to_grid(loc.x, loc.y, x_min, y_min, GRID_SIZE)
        # 确保网格在范围内
        if 0 <= gy < grid.shape[0] and 0 <= gx < grid.shape[1]:
            if grid[gy, gx] == 1:
                loc_grid_pos[loc.id] = (gx, gy)
            else:
                # 如果点在不可走区域，找最近的可走网格
                found = False
                for r in range(1, 5):
                    for dy in range(-r, r+1):
                        for dx in range(-r, r+1):
                            ny, nx = gy + dy, gx + dx
                            if 0 <= ny < grid.shape[0] and 0 <= nx < grid.shape[1]:
                                if grid[ny, nx] == 1:
                                    loc_grid_pos[loc.id] = (nx, ny)
                                    found = True
                                    break
                        if found:
                            break
                    if found:
                        break
                if not found:
                    print(f"  警告: {loc.name} 无法找到附近的可走网格")
        else:
            print(f"  警告: {loc.name} 超出网格范围")
    
    print(f"  成功映射 {len(loc_grid_pos)} 个地点到网格")
    
    # 为每对地点寻找路径
    paths_added = 0
    loc_ids = list(loc_grid_pos.keys())
    
    for i in range(len(loc_ids)):
        for j in range(i+1, len(loc_ids)):
            id1 = loc_ids[i]
            id2 = loc_ids[j]
            gx1, gy1 = loc_grid_pos[id1]
            gx2, gy2 = loc_grid_pos[id2]
            
            # 如果距离太远，跳过（可以调整这个阈值）
            if abs(gx1 - gx2) > 50 or abs(gy1 - gy2) > 50:
                continue
            
            # 找路径
            path = find_path_in_grid(gx1, gy1, gx2, gy2, grid)
            
            if path:
                # 计算路径实际距离
                distance = 0
                prev_x, prev_y = grid_to_point(gx1, gy1, x_min, y_min, GRID_SIZE)
                
                for step in path[1:]:
                    curr_x, curr_y = grid_to_point(step[1], step[0], x_min, y_min, GRID_SIZE)
                    distance += math.sqrt((curr_x - prev_x)**2 + (curr_y - prev_y)**2)
                    prev_x, prev_y = curr_x, curr_y
                
                # 检查是否已存在路径
                existing = db.query(Path).filter(
                    ((Path.start_id == id1) & (Path.end_id == id2)) |
                    ((Path.start_id == id2) & (Path.end_id == id1))
                ).first()
                
                if not existing:
                    db.add(Path(start_id=id1, end_id=id2, distance=round(distance, 2), type="corridor"))
                    db.add(Path(start_id=id2, end_id=id1, distance=round(distance, 2), type="corridor"))
                    paths_added += 2
                    
                    if paths_added % 100 == 0:
                        print(f"    已添加 {paths_added} 条路径...")
    
    db.commit()
    db.close()
    print(f"  ✅ 为 {floor}楼添加了 {paths_added} 条路径")
    return paths_added

def add_vertical_connections(db):
    """添加垂直连接（楼梯和电梯）"""
    print("\n处理垂直连接...")
    
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
    print(f"  ✅ 添加了 {paths_added} 条垂直连接")
    return paths_added

if __name__ == "__main__":
    json_files = [
        (1, "hospital_floor_data/m1F_paths.json"),
        (2, "hospital_floor_data/m2F_paths.json"),
        (3, "hospital_floor_data/m3F_paths.json"),
        (4, "hospital_floor_data/m4F_paths.json"),
    ]
    
    # 先清空现有路径
    db = SessionLocal()
    print("清空现有路径...")
    db.query(Path).delete()
    db.commit()
    db.close()
    
    total_paths = 0
    for floor, json_file in json_files:
        paths = build_paths_for_floor(floor, json_file)
        total_paths += paths
    
    # 添加垂直连接
    db = SessionLocal()
    vertical_paths = add_vertical_connections(db)
    db.close()
    
    total_paths += vertical_paths
    
    print(f"\n🎉 总共添加了 {total_paths} 条真实路径")
    
    # 最终统计
    db = SessionLocal()
    final_count = db.query(Path).count()
    print(f"数据库最终路径数: {final_count}")
    db.close()