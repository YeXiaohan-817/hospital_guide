from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from pydantic import BaseModel  # 新增
from app.database import get_db
from app.models import NavigationTask, User, Location, Robot
from app.schemas import NavigationTaskResponse
from app.api.endpoints.map import calculate_distance, generate_simple_path
class NavigationCreateRequest(BaseModel):
    user_id: int
    location_ids: List[int]
    priority: Optional[str] = "normal"

router = APIRouter()

# 任务状态常量
TASK_STATUS = {
    "PENDING": "pending",      # 等待分配小车
    "NAVIGATING": "navigating", # 导航中
    "PAUSED": "paused",        # 暂停中
    "COMPLETED": "completed",  # 已完成
    "CANCELLED": "cancelled",  # 已取消
    "FAILED": "failed"         # 失败
}

@router.post("/tasks", response_model=NavigationTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_navigation_task(
    request: NavigationCreateRequest,
    db: Session = Depends(get_db)
):
    """
    创建新的导航任务
    
    请求示例：
    {
        "user_id": 1,
        "location_ids": [1, 3, 5],  # 要去的位置ID列表
        "priority": "normal"        # 优先级：high, normal, low
    }
    """
    try:
        # 1. 验证用户是否存在
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户ID {request.user_id} 不存在"
            )
        
        # 2. 验证所有位置是否存在
        locations = []
        for loc_id in request.location_ids:
            location = db.query(Location).filter(Location.id == loc_id).first()
            if not location:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"位置ID {loc_id} 不存在"
                )
            locations.append(location)
        
        if len(locations) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要指定一个目标位置"
            )
        
        # 3. 获取用户当前位置（假设为起点）
        # 这里简化处理：使用第一个位置作为起点
        # 实际项目中可以从用户定位或登记处获取
        start_location = db.query(Location).filter(Location.id == 1).first()  # 假设从医院大门开始
        if not start_location:
            start_location = locations[0]  # 如果没有大门，用第一个目标作为起点
        
        # 4. 计算最优路径序列（多点优化）
        optimal_sequence = calculate_optimal_sequence(start_location, locations)
        
        # 5. 生成详细路径点
        full_path = []
        total_distance = 0.0
        
        # 生成起点到第一个点
        for i in range(len(optimal_sequence) - 1):
            start = optimal_sequence[i]
            end = optimal_sequence[i + 1]
            
            # 计算这段路径
            segment_distance = calculate_distance(start, end)
            segment_path = generate_simple_path(start, end)
            
            total_distance += segment_distance
            
            # 如果是第一段，包含起点信息
            if i == 0:
                full_path.extend(segment_path)
            else:
                # 后续段去掉重复的起点
                full_path.extend(segment_path[1:])
        
        # 6. 分配导引小车
        assigned_robot = assign_available_robot(start_location.id, db)
        
        # 7. 估算总时间
        estimated_time = estimate_total_time(total_distance, optimal_sequence)
        
        # 8. 创建导航任务记录
        task = NavigationTask(
            user_id=request.user_id,
            start_location_id=start_location.id,
            target_location_id=optimal_sequence[-1].id,  # 最后一个位置
            assigned_robot_id=assigned_robot.id if assigned_robot else None,
            status=TASK_STATUS["PENDING"],
            path_coordinates=json.dumps(full_path),  # 存储为JSON字符串
            estimated_duration=estimated_time,
            created_at=datetime.utcnow(),
            #priority=request.priority or "normal"
        )
        
        # 9. 如果有分配小车，更新小车状态
        if assigned_robot:
            assigned_robot.status = "busy"
            assigned_robot.current_task_id = task.id
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 10. 返回创建的任务信息
        return format_task_response(task, full_path, assigned_robot)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
        )

@router.get("/tasks/{task_id}", response_model=NavigationTaskResponse)
async def get_navigation_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    获取导航任务详情
    """
    task = db.query(NavigationTask).filter(NavigationTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )
    
    # 解析路径坐标
    path_coordinates = []
    if task.path_coordinates:
        try:
            path_coordinates = json.loads(task.path_coordinates)
        except:
            path_coordinates = []
    
    # 获取关联的小车信息
    assigned_robot = None
    if task.assigned_robot_id:
        assigned_robot = db.query(Robot).filter(Robot.id == task.assigned_robot_id).first()
    
    return format_task_response(task, path_coordinates, assigned_robot)

@router.get("/tasks/user/{user_id}", response_model=List[NavigationTaskResponse])
async def get_user_navigation_tasks(
    user_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    获取用户的导航任务历史
    """
    # 验证用户存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户ID {user_id} 不存在"
        )
    
    tasks = db.query(NavigationTask)\
        .filter(NavigationTask.user_id == user_id)\
        .order_by(NavigationTask.created_at.desc())\
        .limit(limit)\
        .all()
    
    results = []
    for task in tasks:
        # 解析路径坐标
        path_coordinates = []
        if task.path_coordinates:
            try:
                path_coordinates = json.loads(task.path_coordinates)
            except:
                pass
        
        # 获取小车信息
        assigned_robot = None
        if task.assigned_robot_id:
            assigned_robot = db.query(Robot).filter(Robot.id == task.assigned_robot_id).first()
        
        results.append(format_task_response(task, path_coordinates, assigned_robot))
    
    return results

@router.post("/tasks/{task_id}/cancel", response_model=NavigationTaskResponse)
async def cancel_navigation_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    取消导航任务
    """
    task = db.query(NavigationTask).filter(NavigationTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )
    
    # 检查任务是否可取消
    if task.status in [TASK_STATUS["COMPLETED"], TASK_STATUS["CANCELLED"]]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法取消"
        )
    
    # 更新任务状态
    task.status = TASK_STATUS["CANCELLED"]
    
    # 如果有关联的小车，释放小车
    if task.assigned_robot_id:
        robot = db.query(Robot).filter(Robot.id == task.assigned_robot_id).first()
        if robot:
            robot.status = "idle"
            robot.current_task_id = None
    
    db.commit()
    db.refresh(task)
    
    # 返回更新后的任务
    return await get_navigation_task(task_id, db)

# ============ 辅助函数 ============

def calculate_optimal_sequence(start: Location, targets: List[Location]) -> List[Location]:
    """
    计算最优访问顺序（贪心算法）
    """
    if not targets:
        return [start]
    
    sequence = [start]
    remaining = targets.copy()
    current = start
    
    while remaining:
        # 找到距离当前点最近的下一个点
        nearest = min(remaining, key=lambda loc: calculate_distance(current, loc))
        sequence.append(nearest)
        remaining.remove(nearest)
        current = nearest
    
    return sequence

def assign_available_robot(near_location_id: int, db: Session) -> Optional[Robot]:
    """
    分配可用的导引小车
    简化版：返回第一个可用小车
    """
    # 查询空闲且在线的小车
    robot = db.query(Robot).filter(
        Robot.status == "idle",
        Robot.is_online == True,
        Robot.battery_level > 20  # 电量大于20%
    ).first()
    
    return robot

def estimate_total_time(total_distance: float, sequence: List[Location]) -> int:
    """
    估算总导航时间（秒）
    """
    # 基础行走时间（老年人速度：0.8单位/秒）
    walking_time = total_distance / 0.8
    
    # 楼层转换时间（每层+15秒）
    floor_change_time = 0
    for i in range(len(sequence) - 1):
        floor_diff = abs(sequence[i+1].floor - sequence[i].floor)
        floor_change_time += floor_diff * 15
    
    # 地点停留时间（假设每个目标点停留30秒）
    stay_time = (len(sequence) - 1) * 30
    
    total_time = walking_time + floor_change_time + stay_time
    
    return int(total_time)

def format_task_response(task: NavigationTask, path_coordinates: list, robot: Optional[Robot]) -> dict:
    """
    格式化任务响应
    """
    response = {
        "id": task.id,
        "user_id": task.user_id,
        "status": task.status,
        "estimated_duration": task.estimated_duration,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "path_coordinates": path_coordinates,
        #"priority": task.priority or "normal"
    }
    
    # 添加小车信息
    if robot:
        response["assigned_robot"] = {
            "id": robot.id,
            "name": robot.name,
            "status": robot.status,
            "battery_level": robot.battery_level,
            "is_online": robot.is_online if hasattr(robot, 'is_online') else True  # 添加这行
        }
    else:
        response["assigned_robot"] = None
    
    return response