from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# 位置响应模型
class LocationResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = ""
    type: str
    x: float
    y: float
    floor: int
    is_accessible: bool
    z: float=0.0
    class Config:
        from_attributes = True

# 路径规划响应模型
class PathResponse(BaseModel):
    path: List[Dict[str, Any]]
    total_distance: float
    estimated_time: int

# 小车状态响应模型
class RobotResponse(BaseModel):
    id: int
    name: str
    status: str
    battery_level: int
    is_online: bool
    current_location: Optional[LocationResponse] = None

# 导航任务请求模型
class NavigationRequest(BaseModel):
    user_id: int
    start_location_id: int
    target_location_id: int
# 2. 多点导航请求（从A到B到C到D...） - 新增的
class NavigationCreateRequest(BaseModel):
    user_id: int
    location_ids: List[int]  # 要访问的位置ID列表
    priority: Optional[str] = "normal"  # 优先级：high, normal, low

# 导航任务响应模型
class NavigationTaskResponse(BaseModel):
    id: int
    status: str
    estimated_duration: int
    path_coordinates: Optional[List[Dict]] = None
    assigned_robot: Optional[RobotResponse] = None
class Config:
        from_attributes = True

# 用户信息响应模型
class UserResponse(BaseModel):
    id: int
    username: str
    #created_at: Optional[str] = None
    
class Config:
    from_attributes = True

class PathPoint(BaseModel):
    """路径点"""
    id: int
    name: str
    type: str
    x: float
    y: float
    z: float
    floor: int
    point_type: str  # start, end, waypoint
    description: str
    
    class Config:
        from_attributes = True

class PathPlanRequest(BaseModel):
    """路径规划请求"""
    start_id: int
    end_id: int
    user_type: str = "normal"  # wheelchair, emergency, elderly, normal, staff
    preferences: List[str] = []  # avoid_crowds, use_elevator, avoid_stairs, fastest_route
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_id": 1,
                "end_id": 10,
                "user_type": "wheelchair",
                "preferences": ["avoid_crowds", "use_elevator"]
            }
        }

class PathPlanResponse(BaseModel):
    """路径规划响应"""
    success: bool
    path: List[PathPoint]
    total_distance: float
    estimated_time: int
    floor_changes: int
    instructions: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "path": [
                    {
                        "id": 1,
                        "name": "门诊大厅",
                        "type": "entrance",
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        "floor": 1,
                        "point_type": "start",
                        "description": "起点：门诊大厅"
                    }
                ],
                "total_distance": 45.6,
                "estimated_time": 320,
                "floor_changes": 1,
                "instructions": ["从门诊大厅出发", "直行到达电梯", "乘坐电梯到2楼", "到达放射科"]
            }
        }

# 保持原有的 PathResponse（用于向后兼容）
class PathResponse(BaseModel):
    """原有的路径响应（保持兼容）"""
    path: List[Dict[str, Any]]
    total_distance: float
    estimated_time: int
    floor_changes: int
# ==================== 导航任务相关模型 ====================

class NavigationRequestCreate(BaseModel):
    """创建导航任务的请求"""
    user_id: int
    location_ids: List[int]  # 要去的地点ID数组
    user_type: str = "normal"  # wheelchair, normal, elderly, emergency
    preferences: Dict[str, bool] = {
        "avoid_crowds": False,
        "use_elevator": True
    }
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "location_ids": [101, 203, 305],
                "user_type": "wheelchair",
                "preferences": {
                    "avoid_crowds": True,
                    "use_elevator": True
                }
            }
        }

class PathPoint(BaseModel):
    """路径点坐标"""
    x: float
    y: float
    z: float
    floor: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "floor": 1
            }
        }

class NavigationTaskResponse(BaseModel):
    """导航任务响应"""
    id: int
    path_coordinates: List[PathPoint]
    estimated_duration: int
    assigned_robot: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1001,
                "path_coordinates": [
                    {"x": 0, "y": 0, "z": 0, "floor": 1},
                    {"x": 10, "y": 0, "z": 5, "floor": 1}
                ],
                "estimated_duration": 300,
                "assigned_robot": {
                    "id": 8,
                    "name": "导引车08"
                }
            }
        }

