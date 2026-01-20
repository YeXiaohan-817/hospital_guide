from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Robot, Location
from app.schemas import RobotResponse

router = APIRouter()

@router.get("/robots", response_model=List[RobotResponse])
async def get_robots(
    status: str = None,
    db: Session = Depends(get_db)
):
    """获取小车列表，支持按状态筛选"""
    query = db.query(Robot)
    
    if status:
        query = query.filter(Robot.status == status)
    
    robots = query.all()
    return robots

@router.get("/robots/{robot_id}", response_model=RobotResponse)
async def get_robot_detail(robot_id: int, db: Session = Depends(get_db)):
    """获取特定小车的详细信息"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(status_code=404, detail="小车不存在")
    return robot

@router.get("/robots/available", response_model=List[RobotResponse])
async def get_available_robots(db: Session = Depends(get_db)):
    """获取可用的小车（空闲且在线）"""
    robots = db.query(Robot).filter(
        Robot.status == "idle",
        Robot.is_online == True,
        Robot.battery_level > 20  # 电量大于20%
    ).all()
    return robots