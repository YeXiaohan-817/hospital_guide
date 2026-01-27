# 简化版图结构
from typing import Dict, List
import heapq

class HospitalGraph:
    def __init__(self):
        self.graph: Dict[int, List] = {}
    
    def add_edge(self, u: int, v: int, weight: float):
        if u not in self.graph:
            self.graph[u] = []
        self.graph[u].append((v, weight))
    
    def dijkstra(self, start: int, end: int):
        if start not in self.graph or end not in self.graph:
            return [], float('inf')
        
        distances = {node: float('inf') for node in self.graph}
        previous = {node: None for node in self.graph}
        distances[start] = 0
        pq = [(0, start)]
        
        while pq:
            dist, node = heapq.heappop(pq)
            if dist > distances[node]:
                continue
            
            if node == end:
                break
            
            for neighbor, weight in self.graph.get(node, []):
                new_dist = dist + weight
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = node
                    heapq.heappush(pq, (new_dist, neighbor))
        
        if distances[end] == float('inf'):
            return [], float('inf')
        
        # 重构路径
        path = []
        current = end
        while current is not None:
            path.append(current)
            current = previous[current]
        
        return path[::-1], distances[end]
    
# 在 HospitalGraph 类定义之后添加：

def build_graph_from_db(db_session):
    """从数据库构建图结构"""
    from app.models import Location, Path
    
    graph = HospitalGraph()
    
    try:
        # 添加所有位置节点
        locations = db_session.query(Location).all()
        for loc in locations:
            graph.add_location(loc.id, {
                "name": loc.name,
                "type": loc.type,
                "floor": loc.floor,
                "x": loc.x,
                "y": loc.y,
                "z": loc.floor * 3.0  # 假设每层3米高
            })
        
        # 添加所有路径边
        paths = db_session.query(Path).all()
        for path in paths:
            # 确保路径的两个端点都存在
            start_exists = any(loc.id == path.start_id for loc in locations)
            end_exists = any(loc.id == path.end_id for loc in locations)
            
            if start_exists and end_exists:
                graph.add_path(
                    start_id=path.start_id,
                    end_id=path.end_id,
                    distance=path.distance,
                    path_type=path.type,
                    attributes=path.attributes
                )
        
        print(f"✅ 图构建完成：{len(locations)}个位置，{len(paths)}条路径")
        return graph
        
    except Exception as e:
        print(f"❌ 图构建失败：{e}")
        # 返回空图
        return graph