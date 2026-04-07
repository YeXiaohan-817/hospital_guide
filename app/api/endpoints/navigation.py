from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from pydantic import BaseModel
from app.database import get_db
from app.models import NavigationTask, User, Location, Robot
from app.schemas import NavigationTaskResponse, NavigationRequestCreate, PathPoint
import requests
router = APIRouter()

# 任务状态常量
TASK_STATUS = {
    "PENDING": "pending",
    "NAVIGATING": "navigating",
    "PAUSED": "paused",
    "COMPLETED": "completed",
    "CANCELLED": "cancelled",
    "FAILED": "failed"
}


class NavigationCreateRequest(BaseModel):
    user_id: int
    location_ids: List[int]
    priority: Optional[str] = "normal"


# ============ 硬件语音导航接口 ============

class NavigateRequest(BaseModel):
    user_id: str
    query: str
    current_location: str


class NavigateResponse(BaseModel):
    success: bool
    reply: str
    path: List[dict]


@router.post("/navigate", response_model=NavigateResponse)
async def navigate(request: NavigateRequest, db: Session = Depends(get_db)):
    """
    硬件语音导航接口（接入大模型）
    """
    query = request.query
    current_name = request.current_location

    # ========== 调用本地大模型解析目的地 ==========
    try:
        llm_url = "http://localhost:11434/api/generate"
        llm_payload = {
            "model": "qwen2.5:3b",
            "prompt": f"用户说：{query}。只输出地点名称，不要输出其他任何内容。",
            "stream": False
        }
        response = requests.post(llm_url, json=llm_payload, timeout=10)
        if response.status_code == 200:
            target = response.json().get("response", "").strip()
        else:
            target = None
    except Exception as e:
        print(f"大模型调用失败: {e}")
        target = None

    # 如果大模型解析失败，回退到关键词匹配
    if not target:
        # 回退逻辑
        if "电梯" in query:
            target_loc = db.query(Location).filter(Location.type == "elevator").first()
            target = target_loc.name if target_loc else None
        elif "厕所" in query or "卫生间" in query:
            target_loc = db.query(Location).filter(Location.type == "restroom").first()
            target = target_loc.name if target_loc else None
        else:
            destinations = {
                "药房": "门诊药房",
                "挂号": "门诊挂号收费",
                "放射科": "放射科",
                "CT": "CT室"
            }
            for key, loc_name in destinations.items():
                if key in query:
                    target = loc_name
                    break

    if not target:
        return NavigateResponse(
            success=False,
            reply="抱歉，我没听清楚您要去哪里",
            path=[]
        )

    # 查找当前位置
    start_loc = db.query(Location).filter(Location.name == current_name).first()
    if not start_loc:
        return NavigateResponse(
            success=False,
            reply=f"找不到当前位置：{current_name}",
            path=[]
        )

    # 查找目标位置
    end_loc = db.query(Location).filter(Location.name == target).first()
    if not end_loc:
        return NavigateResponse(
            success=False,
            reply=f"找不到目的地：{target}",
            path=[]
        )

    # 路径规划
    from app.algorithms import create_path_finder
    finder = create_path_finder(db)
    result = finder.find_path(start_loc.id, end_loc.id, "normal")

    if not result.path_ids:
        return NavigateResponse(
            success=False,
            reply="无法规划路径",
            path=[]
        )

    total_dist = result.total_distance
    reply = f"请向前走约{total_dist:.0f}米，即可到达{target}"

    instructions = []
    if total_dist > 0:
        instructions.append({"action": "直行", "distance": f"{total_dist:.0f}米"})
    instructions.append({"action": "到达", "landmark": target})

    return NavigateResponse(
        success=True,
        reply=reply,
        path=instructions
    )

# ============ 原有任务管理接口 ============

@router.post("/tasks", response_model=NavigationTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_navigation_task(
    request: NavigationRequestCreate,
    db: Session = Depends(get_db)
):
    """
    创建新的导航任务 - 支持用户类型和偏好
    """
    try:
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户ID {request.user_id} 不存在"
            )

        locations = []
        for loc_id in request.location_ids:
            location = db.query(Location).filter(Location.id == loc_id).first()
            if not location:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"位置ID {loc_id} 不存在"
                )
            locations.append(location)

        if len(locations) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要指定两个目标位置"
            )

        from app.algorithms import create_path_finder
        finder = create_path_finder(db)

        all_path_points = []
        total_distance = 0

        for i in range(len(locations) - 1):
            path_result = finder.find_path(
                start_id=locations[i].id,
                end_id=locations[i+1].id,
                user_type=request.user_type,
                preferences=list(request.preferences.keys()) if request.preferences else []
            )

            if not path_result.path_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无法从位置{locations[i].id}到{locations[i+1].id}规划路径"
                )

            segment_points = finder.get_path_details(path_result.path_ids)
            total_distance += path_result.total_distance

            if i == 0:
                all_path_points.extend(segment_points)
            else:
                all_path_points.extend(segment_points[1:])

        assigned_robot = assign_available_robot(locations[0].id, db)
        estimated_time = estimate_total_time(total_distance, locations, request.user_type)

        task = NavigationTask(
            user_id=request.user_id,
            start_location_id=locations[0].id,
            target_location_id=locations[-1].id,
            assigned_robot_id=assigned_robot.id if assigned_robot else None,
            status=TASK_STATUS["PENDING"],
            path_coordinates=json.dumps(all_path_points),
            estimated_duration=estimated_time,
            created_at=datetime.utcnow()
        )

        if assigned_robot:
            assigned_robot.status = "busy"
            assigned_robot.current_task_id = task.id

        db.add(task)
        db.commit()
        db.refresh(task)

        return format_task_response(task, all_path_points, assigned_robot)

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
    task = db.query(NavigationTask).filter(NavigationTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )

    path_coordinates = []
    if task.path_coordinates:
        try:
            path_coordinates = json.loads(task.path_coordinates)
        except:
            path_coordinates = []

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
        path_coordinates = []
        if task.path_coordinates:
            try:
                path_coordinates = json.loads(task.path_coordinates)
            except:
                pass

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
    task = db.query(NavigationTask).filter(NavigationTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )

    if task.status in [TASK_STATUS["COMPLETED"], TASK_STATUS["CANCELLED"]]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法取消"
        )

    task.status = TASK_STATUS["CANCELLED"]

    if task.assigned_robot_id:
        robot = db.query(Robot).filter(Robot.id == task.assigned_robot_id).first()
        if robot:
            robot.status = "idle"
            robot.current_task_id = None

    db.commit()
    db.refresh(task)

    return await get_navigation_task(task_id, db)


# ============ 辅助函数 ============

def assign_available_robot(near_location_id: int, db: Session) -> Optional[Robot]:
    robot = db.query(Robot).filter(
        Robot.status == "idle",
        Robot.is_online == True,
        Robot.battery_level > 20
    ).first()
    return robot


def estimate_total_time(total_distance: float, sequence: List[Location], user_type: str = "normal") -> int:
    speeds = {
        "wheelchair": 0.6,
        "elderly": 0.8,
        "normal": 1.0,
        "emergency": 1.5,
        "staff": 1.2
    }
    speed = speeds.get(user_type, 1.0)

    walking_time = total_distance / speed

    floor_change_time = 0
    for i in range(len(sequence) - 1):
        floor_diff = abs(sequence[i+1].floor - sequence[i].floor)
        floor_change_time += floor_diff * 15

    stay_time = (len(sequence) - 1) * 30

    total_time = walking_time + floor_change_time + stay_time
    return int(total_time)


def format_task_response(task: NavigationTask, path_coordinates: list, robot: Optional[Robot]) -> dict:
    response = {
        "id": task.id,
        "user_id": task.user_id,
        "status": task.status,
        "estimated_duration": task.estimated_duration,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "path_coordinates": path_coordinates,
    }

    if robot:
        response["assigned_robot"] = {
            "id": robot.id,
            "name": robot.name,
            "status": robot.status,
            "battery_level": robot.battery_level,
            "is_online": robot.is_online if hasattr(robot, 'is_online') else True
        }
    else:
        response["assigned_robot"] = None

    return response