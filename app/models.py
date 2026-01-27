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