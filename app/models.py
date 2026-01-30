from sqlalchemy import Column, Integer, String,Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

# 创建基类
Base = declarative_base()

class User(Base):
    __tablename__ = "users"  # 数据库中的表名

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)  # 用户名，必须唯一
    hashed_password = Column(String(255))  # 存放加密后的密码
    #created_at = Column(DateTime, default=datetime.utcnow)  # 可以添加这个字段


class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)  # 我也加上长度限制，保持统一
    description = Column(String(255))
    type = Column(String(50))  # department, facility, entrance, special
    x = Column(Float)
    y = Column(Float)
    floor = Column(Integer)
    is_accessible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Robot(Base):
    __tablename__ = "robots"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True)
    status = Column(String(20), default="idle")
    current_location_id = Column(Integer, ForeignKey("locations.id"))
    battery_level = Column(Integer, default=100)
    current_task_id = Column(Integer, nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    is_online = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    current_location = relationship("Location")

class NavigationTask(Base):
    __tablename__ = "navigation_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_location_id = Column(Integer, ForeignKey("locations.id"))
    target_location_id = Column(Integer, ForeignKey("locations.id"))
    assigned_robot_id = Column(Integer, ForeignKey("robots.id"))
    status = Column(String(20), default="pending")
    path_coordinates = Column(JSON, nullable=True)
    estimated_duration = Column(Integer)
    actual_duration = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User")
    start_location = relationship("Location", foreign_keys=[start_location_id])
    target_location = relationship("Location", foreign_keys=[target_location_id])
    assigned_robot = relationship("Robot")

Location.outgoing_paths = relationship(
    "Path", 
    foreign_keys="[Path.start_id]",
    back_populates="start_location"
)
Location.incoming_paths = relationship(
    "Path", 
    foreign_keys="[Path.end_id]",
    back_populates="end_location"
)

# 2. 添加新的 Path 模型（智能路径所需）
class Path(Base):
    __tablename__ = "paths"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 使用整数ID与现有Location模型兼容
    start_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    end_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    
    distance = Column(Float, nullable=False)  # 距离（米）
    
    # 路径类型：corridor, elevator, stairs, ramp, escalator, door
    type = Column(String(50), nullable=False, default="corridor")
    
    # 路径属性（JSON存储，灵活扩展）
    attributes = Column(JSON, default={
        "width": 2.0,                    # 宽度（米）
        "wheelchair_accessible": True,   # 轮椅是否可通行
        "slope": 0.0,                    # 坡度（百分比）
        "crowdedness": 0.0,              # 拥挤度 0-1
        "is_emergency_route": False,     # 是否为应急通道
        "average_wait_time": 0,          # 平均等待时间（秒）
        "lighting": 1.0,                 # 照明情况 0-1
        "is_bidirectional": True         # 是否双向通行
    })
    
    # 与Location的关联
    start_location = relationship(
        "Location", 
        foreign_keys=[start_id],
        back_populates="outgoing_paths"
    )
    end_location = relationship(
        "Location", 
        foreign_keys=[end_id],
        back_populates="incoming_paths"
    )
    
    created_at = Column(DateTime, default=datetime.utcnow)
# ==================== 导航任务相关模型 ====================

class NavigationRequest(Base):
    """导航请求（对应POST /api/tasks）"""
    __tablename__ = "navigation_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_type = Column(String(20), default="normal")  # wheelchair, normal, elderly, emergency
    
    # 偏好设置（JSON存储）
    preferences = Column(JSON, default={
        "avoid_crowds": False,
        "use_elevator": True,
        "avoid_stairs": False,
        "fastest_route": True
    })
    
    # 状态
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    assigned_robot_id = Column(Integer, ForeignKey("robots.id"), nullable=True)
    
    # 路径结果
    path_coordinates = Column(JSON, nullable=True)  # 存储路径坐标点
    total_distance = Column(Float, nullable=True)   # 总距离（米）
    estimated_duration = Column(Integer, nullable=True)  # 预计时间（秒）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    user = relationship("User")
    assigned_robot = relationship("Robot")
    
    def to_dict(self):
        """转换为字典，用于API响应"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_type": self.user_type,
            "preferences": self.preferences,
            "status": self.status,
            "assigned_robot": {
                "id": self.assigned_robot_id,
                "name": self.assigned_robot.name if self.assigned_robot else None
            } if self.assigned_robot_id else None,
            "path_coordinates": self.path_coordinates,
            "total_distance": self.total_distance,
            "estimated_duration": self.estimated_duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }