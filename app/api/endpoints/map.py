from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import math

from app.database import get_db
from app.models import Location, Robot
from app.schemas import LocationResponse, PathResponse

from app.algorithms import create_path_finder
from app.schemas import PathPlanRequest, PathPlanResponse

router = APIRouter()

@router.get("/locations", response_model=List[LocationResponse])
async def get_locations(
    floor: Optional[int] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取位置列表，支持按楼层和类型筛选"""
    query = db.query(Location)
    
    if floor:
        query = query.filter(Location.floor == floor)
    if type:
        query = query.filter(Location.type == type)
    
    locations = query.all()
    return locations

@router.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location_detail(location_id: int, db: Session = Depends(get_db)):
    """获取特定位置的详细信息"""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="位置不存在")
    return location

@router.post("/path/calculate", response_model=PathResponse)
async def calculate_path(
    start_id: int,
    target_id: int,
    db: Session = Depends(get_db)
):
    """计算从起点到终点的路径"""
    start_loc = db.query(Location).filter(Location.id == start_id).first()
    target_loc = db.query(Location).filter(Location.id == target_id).first()
    
    if not start_loc or not target_loc:
        raise HTTPException(status_code=404, detail="起点或终点不存在")
    
    # 计算直线距离
    distance = calculate_distance(start_loc, target_loc)
    
    # 生成简单路径
    path = generate_simple_path(start_loc, target_loc)
    
    # 估算时间（假设移动速度 1单位/秒）
    estimated_time = int(distance * 1.5)  # 加上缓冲时间
    # 如果是跨楼层，增加额外时间
    floor_difference = abs(start_loc.floor - target_loc.floor)
    if floor_difference > 0:
        estimated_time += floor_difference * 15 
    
    return {
        "path": path,
        "total_distance": distance,
        "estimated_time": estimated_time,
        "floor_changes": floor_difference
    }

def calculate_distance(start: Location, target: Location) -> float:
    """计算两点间距离（考虑楼层差异）"""
    import math
    
    # 平面直线距离
    plane_distance = math.sqrt((target.x - start.x) ** 2 + (target.y - start.y) ** 2)
    
    # 如果不同楼层，增加楼层转换成本
    floor_difference = abs(target.floor - start.floor)
    if floor_difference > 0:
        # 每层楼增加10单位的转换成本
        floor_cost = floor_difference * 10
        return plane_distance + floor_cost
    
    return plane_distance

def generate_simple_path(start: Location, target: Location) -> List[dict]:
    """生成路径点（考虑楼层转换）"""
    
    if start.floor == target.floor:
        # 同楼层：直接连接
        return [
            {
                "x": start.x, 
                "y": start.y, 
                "floor": start.floor, 
                "type": "start",
                "description": "起点"
            },
            {
                "x": target.x, 
                "y": target.y, 
                "floor": target.floor, 
                "type": "end",
                "description": "终点"
            }
        ]
    else:
        # 跨楼层：需要经过中转点
        # 找到中间点（假设电梯位置在两个点的中间）
        elevator_x = (start.x + target.x) / 2
        elevator_y = (start.y + target.y) / 2
        floor_difference = abs(target.floor - start.floor)
        
        return [
            {
                "x": start.x, 
                "y": start.y, 
                "floor": start.floor, 
                "type": "start",
                "description": f"起点（{start.name}）"
            },
            {
                "x": elevator_x, 
                "y": elevator_y, 
                "floor": start.floor, 
                "type": "transfer",
                "description": f"电梯/楼梯（前往{target.floor}楼）"
            },
            {
                "x": elevator_x, 
                "y": elevator_y, 
                "floor": target.floor, 
                "type": "transfer",
                "description": f"到达{target.floor}楼"
            },
            {
                "x": target.x, 
                "y": target.y, 
                "floor": target.floor, 
                "type": "end",
                "description": f"终点（{target.name}）"
            }
        ]
    
@router.post("/plan", response_model=PathPlanResponse)
async def plan_path(
    request: PathPlanRequest,
    db: Session = Depends(get_db)
):
    """
    智能路径规划
    
    - **start_id**: 起点位置ID
    - **end_id**: 终点位置ID  
    - **user_type**: 用户类型 (wheelchair, emergency, elderly, normal, staff)
    - **preferences**: 用户偏好列表
    """
    try:
        # 创建路径查找器
        finder = create_path_finder(db)
        
        # 查找路径
        path_result = finder.find_path(
            start_id=request.start_id,
            end_id=request.end_id,
            user_type=request.user_type,
            preferences=request.preferences
        )
        
        if not path_result.path_ids:
            raise HTTPException(
                status_code=404,
                detail=f"未找到从位置{request.start_id}到{request.end_id}的可行路径"
            )
        
        # 获取路径详情
        path_points = finder.get_path_details(path_result.path_ids)
        
        # 生成导航指令
        instructions = finder.get_navigation_instructions(path_points)
        
        return {
            "success": True,
            "path": path_points,
            "total_distance": path_result.total_distance,
            "estimated_time": path_result.estimated_time,
            "floor_changes": path_result.floor_changes,
            "instructions": instructions
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"路径规划失败：{str(e)}"
        )

# 保持原有的 calculate_path 接口（向后兼容）
@router.post("/path/calculate", response_model=PathResponse)
async def calculate_path(
    start_id: int,
    target_id: int,
    db: Session = Depends(get_db)
):
    """原有的路径计算接口（保持兼容）"""
    # 调用智能算法，使用默认用户类型
    finder = create_path_finder(db)
    path_result = finder.find_path(start_id, target_id, "normal")
    
    if not path_result.path_ids:
        raise HTTPException(status_code=404, detail="未找到路径")
    
    # 转换为旧格式
    path_points = finder.get_path_details(path_result.path_ids)
    
    return {
        "path": [{
            "x": p["x"],
            "y": p["y"], 
            "floor": p["floor"],
            "type": p["point_type"],
            "description": p["description"]
        } for p in path_points],
        "total_distance": path_result.total_distance,
        "estimated_time": path_result.estimated_time,
        "floor_changes": path_result.floor_changes
    }