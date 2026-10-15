# 医路通 · 医院智能导诊与导航系统

> 面向大型医院场景的智能导诊与院内导航一体化系统：患者可通过 **3D 医院地图** 选择起点与目标科室，系统基于 **A\* 算法** 自动规划最优路径，并根据 **患者类型** 与 **实时路况** 动态分配路径；同时内置 **AI 智能问诊** 与 **导引小车任务调度**，为患者提供"从挂号到就诊"的全流程智能引导。

---

## 功能特性

- **3D 医院地图导航**：基于 Three.js 渲染多楼层 3D 场景，支持跨楼层路径绘制、楼层切换与关键设施高亮。
- **多用户类型路径规划**：支持 **普通用户 / 轮椅用户 / 老年用户 / 急症重症 / 医护人员** 五种类型，按类型差异化计算路径（轮椅自动规避楼梯与坡道、老年用户优先电梯、急症重症走绿色通道）。
- **急症/重症绿色通道**：为急症、重症患者自动规划"最短最快"路径，强制避让人群密集路段，争取黄金救援时间。
- **动态路径分配**：后端实时跟踪所有进行中的导航路线（按请求到达先后、患者类型行驶速度计算路段占用时长）；当默认路径拥挤（多人未走完）时，自动将新请求分流至更空闲的备选路径，均衡全院人流。
- **AI 智能导诊问答**：接入 DeepSeek 大模型，患者可自然语言提问，AI 结合医院科室信息给出挂号与就诊建议。
- **导引小车任务管理**：导航任务自动分配空闲导引机器人（含电量检测、在线状态判定），支持任务取消与状态追踪。
- **个性化服务**：自动关联历史导航记录（时间 + 起点 → 终点）、支持收藏常用科室，一键直达。
- **中英双语**：界面支持中文 / English 一键切换。

## 技术架构

| 层 | 技术栈 |
| --- | --- |
| 后端 | Python 3.9+ · FastAPI · SQLAlchemy · SQLite · A* 路径算法 · DeepSeek API |
| 前端 | React 18 · Vite · Tailwind CSS 4 · Three.js（3D 渲染）· Recharts |
| 移动端 | Capacitor 8（Android 原生打包，`frontend/android/`） |
| 数据 | SQLite（`hospital_guide.db`，含 182 个导航节点 / 1980 条路径） |

## 项目结构

```
hospital_guide/
├── app/                        # 后端服务
│   ├── main.py                 # FastAPI 入口（挂载全部 /api/v1 路由）
│   ├── database.py             # SQLite 数据库连接与会话
│   ├── models.py               # 数据模型（Location/Path/User/Robot/NavigationTask）
│   ├── schemas.py              # 请求/响应 Pydantic 模型
│   ├── core/                   # 配置（config.py 用户权重、图结构 graph.py）
│   ├── algorithms/             # 路径规划核心
│   │   ├── path_finder.py      #   A* 智能寻路（含用户类型加权）
│   │   └── route_tracker.py    #   动态路径分配（活跃路线跟踪/拥挤检测/分流）
│   ├── api/endpoints/          # 业务接口
│   │   ├── auth.py             #   登录注册（JWT + bcrypt）
│   │   ├── map.py              #   地点查询、路径规划 /plan（含动态分配）
│   │   ├── robots.py           #   导引小车管理
│   │   ├── navigation.py       #   导航任务创建/查询/取消
│   │   ├── speech.py           #   语音服务
│   │   └── health.py           #   健康检查
│   ├── hardware/               # 硬件小车相关代码
│   ├── hospital_floor_data/    # 楼层 JSON 原始数据
│   └── import_all_floors.py    # 数据库初始化/重建脚本
├── frontend/                   # 前端工程
│   ├── src/                    # React 源码
│   │   └── app/
│   │       ├── components/     #   3D 地图、导航页、个人中心、AI 问诊等
│   │       ├── services/       #   API 封装（navigationApi / navigationStorage）
│   │       └── utils/          #   多语言 i18n、展示工具
│   ├── android/                # Capacitor Android 工程
│   ├── capacitor.config.json   # Capacitor 配置
│   ├── vite.config.ts          # Vite 配置（/api/v1 代理到后端）
│   └── package.json
├── hospital_guide.db           # SQLite 数据库（已内置地点与路径数据）
├── requirements.txt            # 后端依赖
├── LICENSE                     # MIT 开源许可证
└── README.md
```

## 部署与运行

### 环境要求

- Python 3.9 或更高版本
- Node.js 18 或更高版本（含 npm）
- Android Studio（仅 Android 打包需要）

### 1. 启动后端

```bash
# 安装依赖
pip install -r requirements.txt

# （可选）配置环境变量：AI 智能问诊需要 DeepSeek API Key
# 在项目根目录创建 .env 文件：
#   DEEPSEEK_API_KEY=sk-xxxxxxxx

# 启动后端服务（监听 8000 端口）
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> **数据库说明**：仓库已内置 `hospital_guide.db`（含全部楼层地点与路径数据），可直接使用。
> 如需重新从原始楼层数据重建数据库：
> ```bash
> python -m app.import_all_floors
> ```

### 2. 启动前端

```bash
cd frontend
npm install

# 配置后端地址（默认已指向 http://localhost:8000）
# 修改 frontend/.env.development：
#   VITE_BACKEND_TARGET=http://localhost:8000
#   VITE_USE_MOCK_BACKEND=false

npm run dev
```

启动后浏览器访问 **http://localhost:5173/** 即可使用。

### 3. 局域网 / 真机访问

- 后端以 `--host 0.0.0.0` 启动后，手机与电脑处于同一局域网即可访问；
- 前端需将 `frontend/.env.development` 中的 `VITE_BACKEND_TARGET` 改为后端所在电脑的局域网 IP（例如 `http://192.168.1.100:8000`）。

### 4. Android 打包（Capacitor）

```bash
cd frontend
npx cap sync android    # 同步前端构建产物到 Android 工程
npx cap open android    # 用 Android Studio 打开并构建 APK
```

## 核心接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/v1/health` | 健康检查 |
| `POST /api/v1/auth/register` / `login` | 注册 / 登录（JWT） |
| `GET /api/v1/locations` | 获取地点列表（可按楼层/类型筛选） |
| `POST /api/v1/plan` | **智能路径规划**（含动态路径分配与绿色通道，响应含 `dynamic_assignment` 分流信息） |
| `GET/POST /api/v1/navigation/tasks` | 导航任务创建 / 查询 |
| `POST /api/v1/navigation/tasks/{id}/cancel` | 取消导航任务 |
| `GET /api/v1/robots` | 导引小车状态查询 |

## 开源许可证

本项目采用 **MIT License** 开源，详见 [LICENSE](./LICENSE)。

---

*医路通 · 大学生创新创业训练计划（大创）项目*
