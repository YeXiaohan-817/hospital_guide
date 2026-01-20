from fastapi import FastAPI
from app.api.endpoints import health  # 导入我们即将编写的健康检查路由
from app.api.endpoints import auth,health, map, robots 
from app.api.endpoints import navigation

# 创建FastAPI应用实例
app = FastAPI(
    title="医院导引系统后端API",
    description="为APP和硬件小车提供服务的后端系统",
    version="0.1.0"
)

# 将健康检查路由包含到应用中，并为其指定前缀和标签
app.include_router(health.router, prefix="/api/v1", tags=["健康检查"])
app.include_router(auth.router, prefix="/api/v1", tags=["用户认证"])
app.include_router(map.router, prefix="/api/v1", tags=["地图导航"])  # 新增
app.include_router(robots.router, prefix="/api/v1", tags=["导引小车"])  # 新增
app.include_router(navigation.router, prefix="/api/v1/navigation", tags=["导航任务"])  # 新增

# 一个最简单的根路径路由，用于快速验证服务是否存活
@app.get("/")
async def root():
    return {"message": "Server is alive and ready for Hospital Guide!"}