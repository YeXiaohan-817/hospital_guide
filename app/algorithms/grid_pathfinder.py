import json
import heapq
import numpy as np
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models import Location

class GridPathFinder:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.grids = {}
        self.origins = {}
    
    def load_grid(self, floor: int):
        json_file = f"hospital_floor_data/m{floor}F_paths.json"
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        boundary = data["walkable_area"]["boundary"]
        holes = data["walkable_area"]["holes"]
        
        x_min, y_min = boundary[0]
        x_max, y_max = boundary[2]
        
        cell_size = 0.5
        nx = int((x_max - x_min) / cell_size) + 1
        ny = int((y_max - y_min) / cell_size) + 1
        
        grid = np.ones((ny, nx), dtype=int)
        
        # 标记墙体为不可走（暂时禁用）
        # for hole in holes:
        #     xs = [p[0] for p in hole]
        #     ys = [p[1] for p in hole]
        #     hx_min, hx_max = min(xs), max(xs)
        #     hy_min, hy_max = min(ys), max(ys)
        #     
        #     gx_min = max(0, int((hx_min - x_min) / cell_size))
        #     gx_max = min(nx-1, int((hx_max - x_min) / cell_size))
        #     gy_min = max(0, int((hy_min - y_min) / cell_size))
        #     gy_max = min(ny-1, int((hy_max - y_min) / cell_size))
        #     
        #     grid[gy_min:gy_max+1, gx_min:gx_max+1] = 0
        
        self.grids[floor] = grid
        self.origins[floor] = (x_min, y_min, cell_size)
        print(f"✅ 加载 {floor}楼网格：{grid.shape}，可走比例 {grid.sum()/grid.size:.1%}")
    
    def _world_to_grid(self, x: float, y: float, floor: int):
        x_min, y_min, cell_size = self.origins[floor]
        gx = int((x - x_min) / cell_size)
        gy = int((y - y_min) / cell_size)
        return gx, gy
    
    def _grid_to_world(self, gx: int, gy: int, floor: int):
        x_min, y_min, cell_size = self.origins[floor]
        x = x_min + (gx + 0.5) * cell_size
        y = y_min + (gy + 0.5) * cell_size
        return x, y
    
    def _find_path_same_floor(self, start_id: int, end_id: int):
        start_loc = self.db.query(Location).filter(Location.id == start_id).first()
        end_loc = self.db.query(Location).filter(Location.id == end_id).first()
        floor = start_loc.floor
        
        if floor not in self.grids:
            self.load_grid(floor)
        
        grid = self.grids[floor]
        gx1, gy1 = self._world_to_grid(start_loc.x, start_loc.y, floor)
        gx2, gy2 = self._world_to_grid(end_loc.x, end_loc.y, floor)
        
        grid[gy1, gx1] = 1
        grid[gy2, gx2] = 1
        
        start = (gx1, gy1)
        end = (gx2, gy2)
        
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        f_score = {start: abs(gx1-gx2) + abs(gy1-gy2)}
        
        dirs = [(0,1), (1,0), (0,-1), (-1,0)]
        
        while open_set:
            _, current = heapq.heappop(open_set)
            if current == end:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()
                
                world_path = []
                for gx, gy in path:
                    x, y = self._grid_to_world(gx, gy, floor)
                    world_path.append((x, y, floor))
                
                # 简化路径
                if len(world_path) > 2:
                    simplified = [world_path[0]]
                    for i in range(1, len(world_path)-1):
                        x1, y1, _ = world_path[i-1]
                        x2, y2, _ = world_path[i]
                        x3, y3, _ = world_path[i+1]
                        if not ((abs(x1 - x2) < 0.01 and abs(x2 - x3) < 0.01) or (abs(y1 - y2) < 0.01 and abs(y2 - y3) < 0.01)):
                            simplified.append(world_path[i])
                    simplified.append(world_path[-1])
                    world_path = simplified
                return world_path
            
            cx, cy = current
            for dx, dy in dirs:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < grid.shape[1] and 0 <= ny < grid.shape[0]:
                    if grid[ny, nx] == 0:
                        continue
                    neighbor = (nx, ny)
                    tentative_g = g_score[current] + 1
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f = tentative_g + abs(nx-gx2) + abs(ny-gy2)
                        heapq.heappush(open_set, (f, neighbor))
        
        return None
    
    def _find_path_cross_floor(self, start_id: int, end_id: int):
        stairs = self.db.query(Location).filter(
            Location.type.in_(['stairs', 'elevator'])
        ).all()
        
        start_loc = self.db.query(Location).filter(Location.id == start_id).first()
        end_loc = self.db.query(Location).filter(Location.id == end_id).first()
        
        if not start_loc or not end_loc:
            return None
        
        # 找到起点层最近的楼梯
        nearest_stair_start = None
        min_dist = float('inf')
        for stair in stairs:
            if stair.floor == start_loc.floor:
                dist = abs(stair.x - start_loc.x) + abs(stair.y - start_loc.y)
                if dist < min_dist:
                    min_dist = dist
                    nearest_stair_start = stair
        
        if not nearest_stair_start:
            return None
        
        # 找到终点层对应的楼梯（同一部）
        nearest_stair_end = None
        for stair in stairs:
            if stair.floor == end_loc.floor:
                if abs(stair.x - nearest_stair_start.x) < 1.0 and \
                abs(stair.y - nearest_stair_start.y) < 1.0:
                    nearest_stair_end = stair
                    break
        
        if not nearest_stair_end:
            min_dist_end = float('inf')
            for stair in stairs:
                if stair.floor == end_loc.floor:
                    dist = abs(stair.x - end_loc.x) + abs(stair.y - end_loc.y)
                    if dist < min_dist_end:
                        min_dist_end = dist
                        nearest_stair_end = stair
        
        if not nearest_stair_end:
            return None
        
        # 起点到楼梯
        start_path = self._find_path_same_floor(start_id, nearest_stair_start.id)
        # 楼梯到终点
        end_path = self._find_path_same_floor(nearest_stair_end.id, end_id)
        
        if not start_path or not end_path:
            return None
        
        # 合并：起点路径（不含最后一点）+ 起点楼梯 + 终点楼梯 + 终点路径（不含第一点）
        full_path = []
        
        # 起点路径（去掉最后一个点，避免重复）
        if len(start_path) > 1:
            full_path.extend(start_path[:-1])
        else:
            full_path.extend(start_path)
        
        # 起点楼梯点
        full_path.append((nearest_stair_start.x, nearest_stair_start.y, nearest_stair_start.floor))
        # 终点楼梯点（垂直移动）
        full_path.append((nearest_stair_end.x, nearest_stair_end.y, nearest_stair_end.floor))
        
        # 终点路径（去掉第一个点）
        if len(end_path) > 1:
            full_path.extend(end_path[1:])
        else:
            full_path.extend(end_path)
        
        # 去重
        unique_path = []
        for p in full_path:
            if not unique_path or unique_path[-1] != p:
                unique_path.append(p)
        
        return unique_path
        
    def find_path(self, start_id: int, end_id: int):
        start_loc = self.db.query(Location).filter(Location.id == start_id).first()
        end_loc = self.db.query(Location).filter(Location.id == end_id).first()
        
        if not start_loc or not end_loc:
            return None
        
        if start_loc.floor == end_loc.floor:
            return self._find_path_same_floor(start_id, end_id)
        
        return self._find_path_cross_floor(start_id, end_id)