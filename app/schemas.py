from pydantic import BaseModel
from typing import List, Optional, Dict, Any

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
    z: float
    class Config:
        from_attributes = True

# 路径规划响应模型（兼容版，含楼层变化）
class PathResponse(BaseModel):
    """原有的路径响应（保持兼容）"""
    path: List[Dict[str, Any]]
    total_distance: float
    estimated_time: int
    floor_changes: int

# 小车状态响应模型
class RobotResponse(BaseModel):
    id: int
    name: str
    status: str
    battery_level: int
    is_online: bool
    current_location: Optional[LocationResponse] = None

# 路径点 - 适配前端需求（合并坐标与类型/描述字段）
class PathPoint(BaseModel):
    """路径点 - 适配前端需求"""
    x: float
    y: float
    z: float = 0.0
    floor: int
    type: Optional[str] = "waypoint"  # corridor/elevator/stairs/start/end 等
    description: Optional[str] = ""

    class Config:
        json_schema_extra = {
            "example": {
                "x": 120,
                "y": 100,
                "z": 0.0,
                "floor": 1,
                "type": "start",
                "description": "从门诊挂号收费出发"
            }
        }

# 路径规划请求
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

# 路径规划响应
class PathPlanResponse(BaseModel):
    """路径规划响应 - 适配前端需求"""
    success: bool
    path: List[PathPoint]
    total_distance: float
    estimated_time: int
    floor_changes: int
    instructions: List[str]
    dynamic_assignment: Optional[Dict[str, Any]] = None  # 动态路径分配信息

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "path": [
                    {
                        "x": 120,
                        "y": 100,
                        "z": 0.0,
                        "floor": 1,
                        "type": "start",
                        "description": "从门诊挂号收费出发"
                    }
                ],
                "total_distance": 45.6,
                "estimated_time": 320,
                "floor_changes": 1,
                "instructions": ["从门诊大厅出发", "直行到达电梯", "乘坐电梯到2楼", "到达放射科"]
            }
        }

# 导航任务请求（统一入口）
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

# 导航任务响应（合并两版字段，兼容既有调用）
class NavigationTaskResponse(BaseModel):
    """导航任务响应"""
    id: int
    user_id: Optional[int] = None
    status: Optional[str] = None
    estimated_duration: Optional[int] = 0
    path_coordinates: Optional[List[Dict[str, Any]]] = None
    assigned_robot: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1001,
                "user_id": 1,
                "status": "pending",
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

# 用户信息响应模型
class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True
