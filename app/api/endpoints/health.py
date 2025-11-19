from fastapi import APIRouter

# 为这个路由组创建一个路由器实例
router = APIRouter()

# 定义一个GET请求接口，路径是 /api/v1/health
@router.get("/health")
async def health_check():
    """
    服务健康状态检查端点。
    """
    return {"status": "ok", "message": "Service is healthy"}