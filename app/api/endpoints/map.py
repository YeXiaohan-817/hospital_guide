from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import math

from app.database import get_db
from app.models import Location
from app.schemas import LocationResponse, PathPlanRequest
from app.algorithms.grid_pathfinder import GridPathFinder

router = APIRouter()

@router.get("/locations", response_model=List[LocationResponse])
async def get_locations(
    floor: Optional[int] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Location)
    if floor:
        query = query.filter(Location.floor == floor)
    if type:
        query = query.filter(Location.type == type)
    return query.all()

@router.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location_detail(location_id: int, db: Session = Depends(get_db)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="位置不存在")
    return location

@router.post("/plan")
async def plan_path(request: PathPlanRequest, db: Session = Depends(get_db)):
    try:
        print(f"🔍 收到请求: start_id={request.start_id}, end_id={request.end_id}")
        finder = GridPathFinder(db)
        path = finder.find_path(request.start_id, request.end_id)
        print(f"🔍 find_path 返回: {path}")
        
        if not path:
            raise HTTPException(status_code=404, detail="未找到可行路径")
        
        start_loc = db.query(Location).filter(Location.id == request.start_id).first()
        end_loc = db.query(Location).filter(Location.id == request.end_id).first()
        
        path_points = []
        for i, (x, y, floor) in enumerate(path):
            if i == 0:
                point_type = "start"
                description = f"从{start_loc.name}出发"
            elif i == len(path) - 1:
                point_type = "end"
                description = f"到达{end_loc.name}"
            else:
                point_type = "waypoint"
                description = "继续前进"
            
            path_points.append({
                "x": x,
                "y": y,
                "floor": floor,
                "type": point_type,
                "description": description
            })
        
        total_distance = 0
        for i in range(len(path) - 1):
            x1, y1, _ = path[i]
            x2, y2, _ = path[i+1]
            total_distance += math.sqrt((x2-x1)**2 + (y2-y1)**2)
        
        return {
            "success": True,
            "path": path_points,
            "total_distance": round(total_distance, 2),
            "estimated_time": int(total_distance),
            "floor_changes": 0,
            "instructions": []
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))