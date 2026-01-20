hospital-guide-backend/     # 项目根目录

├── app/                    # 主要应用代码都在这里

│   ├── \_\_init\_\_.py         # 让Python把这个目录当作一个包

│   ├── main.py             # FastAPI应用的创建和核心路由在这里

│   └── api/                # 存放所有不同的API端点（路由）

│       ├── \_\_init\_\_.py

│       └── endpoints/      # 未来你的各个功能接口会分门别类放在这里

│           ├── \_\_init\_\_.py

│           └── health.py   # 我们先从这里开始，放一个健康检查接口

├── requirements.txt        # 项目依赖的Python包列表

└── README.md              # 项目说明文档


# 🏥 医院导引系统 v1.0

FastAPI 后端项目 - xcjj请直接看这里👇

## 🚀 快速启动（前端专用）

### 1. 确保环境
- Python 3.8+ 已安装
- 终端/命令行已打开

### 2. 三步启动后端
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务器（在项目根目录！）
cd hospital_guide
uvicorn app.main:app --reload

#3.前端文件放置位置（可能没有，自己建一下）
app/static/     ← 放 CSS、JS、图片等
app/templates/  ← 放 HTML 文件

#4.访问地址
API文档: http://127.0.0.1:8000/docs
API接口: http://127.0.0.1:8000/api/v1/...
前端页面: http://127.0.0.1:8000/home

#5.API 接口说明
基础信息
服务运行在：http://127.0.0.1:8000
所有API前缀：/api/v1
支持跨域（CORS已配置）

#6.常见问题
Q: 启动报错 "ModuleNotFoundError"
A: 确保执行了 pip install -r requirements.txt

Q: 访问 http://127.0.0.1:8000 显示404
A: 正常！应该访问 http://127.0.0.1:8000/docs 或 http://127.0.0.1:8000/home

Q: 访问 /home 显示404
A: 需要在 app/templates/ 目录下创建 index.html 文件

Q: 想改API或加新接口
A: 修改 app/main.py 或 app/api/endpoints/ 下的文件

Q: 静态文件访问不了
A: 确保文件放在 app/static/ 目录下，访问时用 /static/文件名

联系后端
后端主文件：app/main.py
数据库文件：hospital.db（自动生成）

