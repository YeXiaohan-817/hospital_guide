from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# 位置响应模型
class LocationResponse(BaseModel):
    id: int
    name: str
    description: str
    type: str
    x: float
    y: float
    floor: int
    is_accessible: bool
    
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