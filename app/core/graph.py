"""
图数据结构，用于路径规划
"""

from typing import Dict, List, Tuple, Optional
import heapq

class HospitalGraph:
    """医院地图图结构"""
    
    def __init__(self):
        self.adjacency: Dict[int, List[Tuple[int, float]]] = {}
        self.locations: Dict[int, Dict] = {}
    
    def add_location(self, location_id: int, location_info: Dict):
        if location_id not in self.adjacency:
            self.adjacency[location_id] = []
        self.locations[location_id] = location_info
    
    def add_edge(self, start_id: int, end_id: int, weight: float):
        if start_id not in self.adjacency:
            self.adjacency[start_id] = []
        self.adjacency[start_id].append((end_id, weight))
    
    def add_path(self, start_id: int, end_id: int, 
                 distance: float, path_type: str, attributes: Dict):
        self.add_edge(start_id, end_id, distance)
        if attributes.get("is_bidirectional", True):
            self.add_edge(end_id, start_id, distance)
    
    def get_neighbors(self, location_id: int) -> List[Dict]:
        if location_id not in self.adjacency:
            return []
        return [{"to_id": nid, "distance": w, "weight": w} 
                for nid, w in self.adjacency[location_id]]
    
    def dijkstra(self, start_id: int, end_id: int) -> Tuple[List[int], float]:
        if start_id not in self.adjacency or end_id not in self.adjacency:
            return [], float('inf')
        
        distances = {node: float('inf') for node in self.adjacency}
        previous = {node: None for node in self.adjacency}
        distances[start_id] = 0
        pq = [(0, start_id)]
        
        while pq:
            dist, node = heapq.heappop(pq)
            if dist > distances[node]:
                continue
            if node == end_id:
                break
            
            for neighbor, weight in self.adjacency.get(node, []):
                new_dist = dist + weight
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = node
                    heapq.heappush(pq, (new_dist, neighbor))
        
        if distances[end_id] == float('inf'):
            return [], float('inf')
        
        path = []
        current = end_id
        while current is not None:
            path.append(current)
            current = previous[current]
        
        return path[::-1], distances[end_id]

def build_graph_from_db(db_session):
    """从数据库构建图结构"""
    from app.models import Location, Path
    
    graph = HospitalGraph()
    
    try:
        locations = db_session.query(Location).all()
        for loc in locations:
            graph.add_location(loc.id, {
                "name": loc.name,
                "type": loc.type,
                "floor": loc.floor,
                "x": loc.x,
                "y": loc.y,
                "z": loc.floor * 3.0
            })
        
        paths = db_session.query(Path).all()
        for path in paths:
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
        return graph