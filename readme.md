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

