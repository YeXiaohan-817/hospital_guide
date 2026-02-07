"""
智能路径规划算法
支持不同用户类型和偏好的最优路径计算
"""

from typing import List, Dict, Tuple, Optional, Set
import heapq
import math
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.core.config import USER_WEIGHTS, PATH_TYPE_COSTS
from app.core.graph import HospitalGraph, build_graph_from_db
from app.models import Location, Path

@dataclass
class PathResult:
    """路径规划结果"""
    path_ids: List[int]          # 路径节点ID列表
    total_distance: float        # 总距离（米）
    estimated_time: int          # 预计时间（秒）
    total_cost: float           # 总代价
    floor_changes: int          # 楼层变化次数


class PathFinder:
    """智能路径查找器"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.graph = None
        
    def initialize_graph(self):
        """初始化图结构（懒加载）"""
        if self.graph is None:
            self.graph = build_graph_from_db(self.db)
    
    def calculate_edge_cost(self, edge, path_obj: Path, 
                           user_type: str, preferences: List[str]) -> float:
        """计算单条边的实际代价"""
        if path_obj is None:
            return float('inf')
        
        # 基础距离
        cost = path_obj.distance
        
        # 获取用户配置
        user_config = USER_WEIGHTS.get(user_type, USER_WEIGHTS["normal"])
        weights = user_config["weights"]
        
        # 根据路径类型调整代价
        path_type = path_obj.type.lower()
        
        # 轮椅用户特殊处理
        if user_type == "wheelchair":
            if path_type == "stairs":
                return float('inf')  # 完全不可用
            if not path_obj.attributes.get("wheelchair_accessible", True):
                return float('inf')
            if path_obj.attributes.get("slope", 0) > 8.0:  # 坡度大于8%
                cost *= weights.get("slope", 2.0)
        
        # 急诊患者
        elif user_type == "emergency":
            if path_type == "elevator":
                wait_time = path_obj.attributes.get("average_wait_time", 0)
                cost += wait_time * weights.get("waiting", 2.0)
        
        # 老年人
        elif user_type == "elderly":
            if path_type == "stairs":
                cost *= weights.get("stairs", 3.0)
        
        # 所有用户通用的拥挤度处理
        crowdedness = path_obj.attributes.get("crowdedness", 0)
        if crowdedness > 0.5 and "avoid_crowds" in preferences:
            cost *= (1 + crowdedness * 2)
        
        # 楼梯偏好处理
        if path_type == "stairs":
            if "avoid_stairs" in preferences:
                cost *= 5.0
            elif "use_stairs" in preferences:
                cost *= 0.8  # 偏好楼梯的用户
        
        # 电梯偏好处理
        if path_type == "elevator":
            if "use_elevator" in preferences:
                cost *= 0.7
            elif "avoid_elevator" in preferences:
                cost *= 1.5
        
        # 路径类型基础代价
        type_cost = PATH_TYPE_COSTS.get(path_type, 1.0)
        cost *= type_cost
        
        return cost
    
    def find_path(self, start_id: int, end_id: int, 
                  user_type: str = "normal",
                  preferences: Optional[List[str]] = None) -> PathResult:
        """
        使用A*算法查找最优路径
        
        Args:
            start_id: 起点位置ID
            end_id: 终点位置ID
            user_type: 用户类型 (wheelchair, emergency, elderly, normal, staff)
            preferences: 用户偏好列表
            
        Returns:
            PathResult: 路径规划结果
        """
        if preferences is None:
            preferences = []
        
        self.initialize_graph()
        
        # 验证起点终点存在
        start_loc = self.db.query(Location).filter(Location.id == start_id).first()
        end_loc = self.db.query(Location).filter(Location.id == end_id).first()
        
        if not start_loc or not end_loc:
            raise ValueError("起点或终点不存在")
        
        # 初始化数据结构
        open_set = []
        heapq.heappush(open_set, (0, start_id, 0, [start_id]))  # (f, node, g, path)
        
        g_score = {start_id: 0}  # 从起点到当前节点的实际代价
        f_score = {start_id: self._heuristic(start_loc, end_loc)}  # 总估计代价
        
        visited = set()
        
        while open_set:
            current_f, current_id, current_g, current_path = heapq.heappop(open_set)
            
            # 找到终点
            if current_id == end_id:
                return self._build_path_result(current_path, current_g, user_type)
            
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # 获取当前节点位置信息
            current_loc = self.db.query(Location).filter(Location.id == current_id).first()
            if not current_loc:
                continue
            
            # 遍历邻居
            for edge in self.graph.get_neighbors(current_id):
                if edge.get("to_id") in visited:
                    continue
                
                # 获取路径详情
                path_obj = self._get_path_between(current_id, edge.get("to_id"))
                if not path_obj:
                    continue
                
                # 计算到邻居的实际代价
                edge_cost = self.calculate_edge_cost(edge, path_obj, user_type, preferences)
                if edge_cost == float('inf'):
                    continue  # 不可达
                
                tentative_g = current_g + edge_cost
                
                # 如果找到更优路径
                if edge.get("to_id") not in g_score or tentative_g < g_score[edge.get("to_id")]:
                    g_score[edge.get("to_id")] = tentative_g
                    
                    # 计算启发式代价
                    neighbor_loc = self.db.query(Location).filter(Location.id == edge.get("to_id")).first()
                    if neighbor_loc:
                        h_cost = self._heuristic(neighbor_loc, end_loc)
                        f_cost = tentative_g + h_cost
                    else:
                        f_cost = tentative_g
                    
                    f_score[edge.get("to_id")] = f_cost
                    
                    # 新路径
                    new_path = current_path + [edge.get("to_id")]
                    heapq.heappush(open_set, (f_cost, edge.get("to_id"), tentative_g, new_path))
        
        # 未找到路径
        return PathResult([], 0.0, 0, float('inf'), 0)
    
    def _get_path_between(self, start_id: int, end_id: int) -> Optional[Path]:
        """获取两个位置之间的路径对象"""
        return self.db.query(Path).filter(
            ((Path.start_id == start_id) & (Path.end_id == end_id)) |
            ((Path.start_id == end_id) & (Path.end_id == start_id))
        ).first()
    
    def _heuristic(self, loc1: Location, loc2: Location) -> float:
        """A*算法的启发式函数（三维直线距离）"""
        # 平面距离
        dx = loc1.x - loc2.x
        dy = loc1.y - loc2.y
        plane_distance = math.sqrt(dx*dx + dy*dy)
        
        # 楼层转换代价（每层按10米计算）
        floor_diff = abs(loc1.floor - loc2.floor)
        vertical_cost = floor_diff * 10.0
        
        return plane_distance + vertical_cost
    
    def _build_path_result(self, path_ids: List[int], total_cost: float,
                          user_type: str) -> PathResult:
        """构建路径结果"""
        if not path_ids:
            return PathResult([], 0.0, 0, float('inf'), 0)
        
        # 计算总距离
        total_distance = 0.0
        floor_changes = 0
        
        for i in range(len(path_ids) - 1):
            path = self._get_path_between(path_ids[i], path_ids[i+1])
            if path:
                total_distance += path.distance
                # 检查楼层变化
                start_loc = self.db.query(Location).filter(Location.id == path_ids[i]).first()
                end_loc = self.db.query(Location).filter(Location.id == path_ids[i+1]).first()
                if start_loc and end_loc and start_loc.floor != end_loc.floor:
                    floor_changes += 1
        
        # 计算预计时间
        user_config = USER_WEIGHTS.get(user_type, USER_WEIGHTS["normal"])
        base_speed = user_config["base_speed"]  # 米/秒
        
        # 考虑楼层转换时间（每层30秒）
        floor_time = floor_changes * 30
        
        # 基本行走时间 + 楼层转换时间
        estimated_time = int((total_distance / base_speed) + floor_time)
        
        return PathResult(
            path_ids=path_ids,
            total_distance=round(total_distance, 2),
            estimated_time=estimated_time,
            total_cost=round(total_cost, 2),
            floor_changes=floor_changes
        )
    
    def get_path_details(self, path_ids: List[int]) -> List[Dict]:
        """获取路径的详细坐标点"""
        details = []
        
        for i, loc_id in enumerate(path_ids):
            location = self.db.query(Location).filter(Location.id == loc_id).first()
            if location:
                point_type = "start" if i == 0 else "end" if i == len(path_ids)-1 else "waypoint"
                
                details.append({
                    "id": location.id,
                    "name": location.name,
                    "type": location.type,
                    "x": location.x,
                    "y": location.y,
                    "z": location.z,  
                    "floor": location.floor,
                    "point_type": point_type,
                    "description": self._get_point_description(i, len(path_ids), location)
                })
        
        return details
    
    def _get_point_description(self, index: int, total: int, location: Location) -> str:
        """生成路径点描述"""
        if index == 0:
            return f"起点：{location.name}"
        elif index == total - 1:
            return f"终点：{location.name}"
        else:
            return f"途经：{location.name}"
    
    def get_navigation_instructions(self, path_points: List[Dict]) -> List[str]:
        """生成导航指令"""
        if len(path_points) < 2:
            return ["已在目的地"]
        
        instructions = []
        current_floor = path_points[0]["floor"]
        
        for i in range(1, len(path_points)):
            current = path_points[i-1]
            next_point = path_points[i]
            
            # 楼层变化
            if current["floor"] != next_point["floor"]:
                floor_diff = next_point["floor"] - current["floor"]
                if floor_diff > 0:
                    instructions.append(f"上楼{abs(floor_diff)}层")
                else:
                    instructions.append(f"下楼{abs(floor_diff)}层")
            
            # 地点类型变化
            elif current["type"] != next_point["type"]:
                if current["type"] == "corridor" and next_point["type"] == "elevator":
                    instructions.append("到达电梯间")
                elif current["type"] == "elevator" and next_point["type"] == "corridor":
                    instructions.append("出电梯")
            
            # 一般移动指令
            else:
                if i == 1:
                    instructions.append(f"从{current['name']}出发")
                elif i == len(path_points) - 1:
                    instructions.append(f"到达{next_point['name']}")
                else:
                    instructions.append(f"继续前往{next_point['name']}")
        
        # 添加总结指令
        if instructions:
            instructions.append("请按照指示前往目的地")
        
        return instructions


# 工具函数
def create_path_finder(db_session: Session) -> PathFinder:
    """创建路径查找器实例"""
    return PathFinder(db_session)