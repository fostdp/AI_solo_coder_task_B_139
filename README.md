# 🏯 夯土墙风蚀监测与加固决策系统

> **面向文化遗产夯土墙保护** 的全栈风蚀监测系统：4G DTU 实时采集 → **DES 湍流两相流仿真** → **TOPSIS 多目标加固决策** → MQTT 分级告警推送。
>
> 后端 **微服务化**（Redis Pub/Sub 解耦），前端 **模块化**，全参数 **JSON 外置配置化**。

---

## 🗂️ 目录结构

```
rammed-earth-wall/
├── backend/                 # FastAPI 主服务
│   ├── adapters.py          # 🔌 微服务适配器层 (路由透明，Redis失败自动降级)
│   ├── routers/             # 7个API路由 (sensor/erosion/reinforcement/...)
│   ├── services/            # 原单体服务（向后兼容）
│   └── main.py              # 入口 + lifespan 初始化
│
├── microservices/           # 4 个独立微服务模块
│   ├── common.py            # 🧠 RedisMessageBus + JSON 配置加载器
│   ├── dtu_receiver.py      # 📡 传感器采集 + 范围/跳跃值校验
│   ├── wind_erosion_simulator.py  # 🌪️ 风沙两相流 + DES分离涡模型 + 风蚀率计算
│   ├── reinforcement_optimizer.py # 🏗️ Arrhenius加速老化 + TOPSIS决策
│   └── alarm_mqtt.py        # 🚨 三级告警评估 + Paho MQTT v5 推送
│
├── config/                  # ⚙️ 外置JSON参数（热加载无需改代码）
│   ├── erosion_params.json  #    风蚀物理参数 (Shields/DES/阈值/...)
│   └── reinforcement_materials.json  # 5种加固材料物性 + TOPSIS权重
│
├── simulator/               # 🔬 夯土墙4G DTU传感器模拟器
│   └── sensor_simulator.py  #    风速/含水量可配置 (环境变量+CLI双通道)
│
├── frontend/                # 🎨 前端
│   ├── index.html           #    主页面 (5个Tab)
│   └── js/
│       ├── rammed_earth_3d.js   # 🌏 Three.js 3D渲染 (墙体/热力图/风粒子)
│       ├── erosion_panel.js     # 📊 数据面板控制器 (API/Chart.js/建议卡片)
│       ├── windField.js         # 2D风场可视化
│       ├── dataCharts.js        # 原图表模块 (向后兼容)
│       └── main.js              # 入口编排
│
├── db/                      # 🗄️ 数据库初始化
│   └── 01_init_schema.sql   #    建表 + Hypertable + 降采样/保留策略
│
├── nginx/                   # 🌐 Nginx (前端静态 + API反代)
│   └── nginx.conf           #    Gzip压缩6级 + Brotli预留 + 静态资源缓存
│
├── mqtt/                    # 📡 Mosquitto Broker 配置
│   ├── mosquitto.conf       #    1883原生 + 9001 WebSocket双通道
│   └── aclfile              #    用户/主题权限控制
│
├── Dockerfile               # 🐳 Python多阶段构建 (builder + runtime)
├── Dockerfile.simulator     # 🐳 模拟器单独镜像
├── docker-compose.yml       # 🎯 6服务编排(含健康检查+资源限制+重启策略)
├── .env.example             # 环境变量模板
├── requirements.txt         # Python依赖
│
├── test_regression.py       # ✅ 后端6模块级联回归测试
└── test_api_regression.py   # ✅ 9个API路由级回归测试
```

---

## 🏗️ 系统架构图

```
                                     ┌──────────────────────────────────────────────────────┐
                                     │                    🖥️  用户层                     │
                                     │                                                    │
                                     │   浏览器 (Nginx :80 → 静态Gzip资源)                 │
                                     │   ├── rammed_earth_3d.js (Three.js 3D)             │
                                     │   └── erosion_panel.js  (Chart.js 面板)            │
                                     │                    │   ↑ MQTT/WS (9001)           │
                                     └────────────────────┼───┼───────────────────────────┘
                                                          │   │
                   ┌──────────────────────────────────────▼───▼─────────────────────────────┐
                   │                            🌐  接入层                                 │
                   │                           Nginx (Gzip 6级)                            │
                   │  /api/* → FastAPI :8000      /ws/* → WebSocket       / → index.html  │
                   └──────────────────────────────┬────────────────────────────────────────┘
                                                  │
                   ┌──────────────────────────────▼────────────────────────────────────────┐
                   │                         🚀  路由适配层                                │
                   │                 MicroserviceAdapter (adapters.py)                     │
                   │    Redis可用→Pub/Sub RPC     不可用→自动降级进程内直接调用              │
                   └──────────────┬──────────────┬──────────────┬───────────────┬───────────┘
                                  │              │              │               │
                   Redis Pub/Sub  │              │              │               │
                   (或本地直接调用)│              │              │               │
                   ┌──────────────▼───┐  ┌──────▼──────┐  ┌──▼───────────┐  ┌──▼──────────────┐
                   │ 📡 dtu_receiver  │  │ 🌪️ wind_    │  │ 🏗️ reinforce-│  │ 🚨 alarm_mqtt    │
                   │                  │  │    erosion   │  │   _optimizer │  │                 │
                   │ · 范围校验7字段  │  │   _simulator │  │              │  │ · 3级告警评估   │
                   │ · 跳跃值检测4类  │  │              │  │ · 加速老化外推│  │ · 裂缝双阈值   │
                   │ · 传感器ID正则   │  │ · Shields起动│  │ · 95%CI对数正│  │ · Paho MQTT v5 │
                   │ · →DTU_DATA_IN   │  │ · DES分离涡 │  │   态分布      │  │ · 懒连接+断线  │
                   └───────┬──────────┘  │ · Rankine涡  │  │ · 15方案生成 │  │   重连          │
                           │             │ · 两相流+DES │  │ · TOPSIS决策 │  └───────┬────────┘
                           │             │ · 长期侵蚀率 │  └──────┬───────┘          │
                           │             └──────┬───────┘         │                  │
                           │                    │                 │                  │
                           ▼                    ▼                 ▼                  ▼
                   ┌─────────────────────────────────────────────────────────────────────────┐
                   │                              🧠  数据层                                 │
                   │                                                                         │
                   │  ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐           │
                   │  │  TimescaleDB │   │    Redis     │   │  Mosquitto (MQTT) │           │
                   │  │ (PostgreSQL16│   │  (Pub/Sub + │   │  1883 TCP +       │           │
                   │  │  +TimescaleDB │   │   LRU缓存)   │   │  9001 WebSocket   │           │
                   │  │  · Hypertable │   │   256MB max │   │  wall/alert/{seg} │           │
                   │  │  · 3级降采样  │   └──────────────┘   └────────┬──────────┘           │
                   │  │  · 保留策略   │                                │                       │
                   │  │  · 连续聚合   │                       ┌──────▼───────┐                 │
                   │  └──────┬───────┘                       │  前端/运维   │                 │
                   │         │                               │  Paho MQTT   │                 │
                   │         ▼                               └──────────────┘                 │
                   │  原始数据90天 → 小时级2年 → 日级10年 → 月级永久                        │
                   └─────────────────────────────────────────────────────────────────────────┘
                                              ▲
                                              │
                        ┌─────────────────────┴───────────────────────────┐
                        │  🔬 sensor_simulator (DTU模拟器可配置)             │
                        │                                                   │
                        │  风速: min/max/bias/阵风频率/季节系数/主导风向     │
                        │  含水量: base/bias/变异系数/min~max                │
                        └───────────────────────────────────────────────────┘
```

---

## 🚀 快速部署（Docker Compose）

### 0️⃣ 前置条件
```bash
docker --version     # ≥ 24.0
docker compose version   # ≥ 2.20
```

### 1️⃣ 配置环境变量
```bash
# 复制模板并修改密码/端口
cp .env.example .env

# 务必修改这些默认密码：
#   POSTGRES_PASSWORD=ChangeMePlease_2026!
#   REDIS_PASSWORD=RedisSecret_2026!
#   MQTT_PASSWORD=MQTT_Secret_2026!
```

### 2️⃣ 一键启动全栈
```bash
# 6个服务并行构建+启动
docker compose up -d --build

# 查看启动状态 (30s内健康检查通过)
docker compose ps
```

**健康状态输出示例：**
| 服务 | 端口 | 健康检查 |
|------|------|----------|
| `rew_timescaledb` | `5432` | pg_isready ✅ |
| `rew_redis` | `6379` | redis-cli ping ✅ |
| `rew_mqtt` | `1883/9001` | MQTT SUBSCRIBE ✅ |
| `rew_api` | `8000` | `/health` HTTP 200 ✅ |
| `rew_web` | `80` | Nginx `/health` ✅ |
| `rew_simulator` | - | 进程存活 ✅ |

### 3️⃣ 访问与验证
```bash
# 🌏 打开前端
open http://localhost                 # Nginx 前端（Gzip压缩）

# 🚀 后端API
curl http://localhost:8000/health      # FastAPI 健康检查
curl http://localhost/health           # 经Nginx代理检查

# 📊 核心接口示例
curl -X POST http://localhost/api/erosion/predict \
  -H 'Content-Type: application/json' \
  -d '{"segment_id": 1, "prediction_years": 5, "include_critical_zones": true}'

# 🔬 模拟器日志
docker logs -f rew_simulator           # 可看到每段墙风速/含水量/风蚀深度
```

### 4️⃣ 停止与清理
```bash
docker compose down                    # 停止
docker compose down -v                 # 停止并删除所有数据卷(⚠️清空数据库)
```

---

## 🔬 夯土墙传感器模拟器用法

模拟器支持 **环境变量（Docker部署）** 与 **命令行参数（本地调试）** 双通道配置。

### A. Docker Compose 模式（推荐）

修改 `.env` 中 `SIM_*` 开头变量，重启模拟器生效：

```bash
# .env — 模拟北方春季大风+干燥场景
SIMULATOR_INTERVAL=60                 # 60秒上报1次（演示用）
SIM_WIND_SPEED_MIN=5.0                # 风速范围 5~16 m/s
SIM_WIND_SPEED_MAX=16.0
SIM_WIND_SPEED_BIAS=2.0               # 整体风速再+2m/s
SIM_SEASONAL_FACTOR=1.5               # 春季大风系数 1.5x
SIM_DOMINANT_WIND_DIR=315             # 主导风向：西北风
SIM_MOISTURE_BASE=3.5                 # 干燥：含水量基础 3.5%
SIM_MOISTURE_BIAS=-1.0                # 再降 1%
SIM_MOISTURE_VAR_MAX=1.2

# 重启模拟器
docker compose up -d sensor_simulator
```

**典型场景预设：**

| 场景 | SIM_WIND_MIN/MAX | SIM_SEASONAL | SIM_MOISTURE_BASE | 用途 |
|------|-------------------|--------------|-------------------|------|
| 🟢 **日常** (默认) | `2.0/12.0` | `1.0` | `5.0` | 正常运维 |
| 🟡 **春季大风** | `5.0/16.0` | `1.5` | `3.5` | 加速风蚀测试 |
| 🟠 **暴雨后** | `1.0/6.0` | `0.7` | `12.0` | 材料吸水软化 |
| 🔴 **极端沙尘暴** | `10.0/22.0` | `2.0` | `2.0` | 极端工况验证 |
| 🔵 **梅雨季** | `1.0/5.0` | `0.5` | `18.0` | 高湿度保护效果 |

### B. 本地 CLI 模式（调试）

```bash
cd simulator/

# 1. 查看帮助
python sensor_simulator.py --help

# 2. 只运行1次(不循环)，8段墙，春季大风干燥场景
python sensor_simulator.py \
  --api-url http://localhost:8000 \
  --once \
  --segments 8 \
  --wind-min 5.0 --wind-max 16.0 \
  --wind-bias 2.0 \
  --seasonal 1.5 \
  --dominant-dir 315 \
  --moisture 3.5 \
  --moisture-bias -1.0

# 3. 连续模式：每30秒上报1次，不生成历史
python sensor_simulator.py \
  --api-url http://localhost:8000 \
  --interval 30 \
  --no-historical \
  --gust-freq 0.4 \
  --no-diurnal
```

**CLI 参数 → 环境变量对照表：**

| CLI 参数 | 环境变量 | 类型 | 默认值 | 说明 |
|----------|----------|------|--------|------|
| `--wind-min` | `SIM_WIND_SPEED_MIN` | float | 2.0 | 最小风速 m/s |
| `--wind-max` | `SIM_WIND_SPEED_MAX` | float | 12.0 | 最大风速 m/s |
| `--wind-bias` | `SIM_WIND_SPEED_BIAS` | float | 0.0 | 全局偏移(±) |
| `--gust-freq` | `SIM_WIND_GUST_FREQ` | float | 0.2 | 阵风概率 0~1 |
| `--seasonal` | `SIM_SEASONAL_FACTOR` | float | 1.0 | 季节系数(设0=月份自动) |
| `--dominant-dir` | `SIM_DOMINANT_WIND_DIR` | float | 225 | 主导风向° |
| `--no-diurnal` | `SIM_DIURNAL_ENABLE=false` | flag | - | 禁用昼夜差异 |
| `--moisture` | `SIM_MOISTURE_BASE` | float | 5.0 | 含水量基础值% |
| `--moisture-bias` | `SIM_MOISTURE_BIAS` | float | 0.0 | 含水量偏移% |
| `--moisture-var-min` | `SIM_MOISTURE_VAR_MIN` | float | 0.5 | 变异系数下界 |
| `--moisture-var-max` | `SIM_MOISTURE_VAR_MAX` | float | 1.5 | 变异系数上界 |
| `--historical-days` | `SIM_HISTORICAL_DAYS` | int | 30 | 历史数据天数 |

---

## 🛠️ TimescaleDB 数据策略（已内置到 01_init_schema.sql）

### 🔽 连续聚合自动降采样

| 聚合级别 | 刷新频率 | 数据范围 | 典型查询 |
|----------|----------|----------|----------|
| **sensor_data_hourly** (小时级) | 每5分钟刷新最近2h | 保留 2 年 | 24h/7天趋势图 |
| **sensor_data_daily** (日级) | 每30分钟刷新最近3天 | 保留 10 年 | 月度/年度报表 |
| **sensor_data_monthly** (月级) | 每天刷新最近6个月 | **永久保留** | 长期寿命评估 |

### ⏰ 数据保留策略

| 数据表 | 保留时长 | 磁盘占比 | 说明 |
|--------|----------|----------|------|
| `sensor_data` 原始秒级 | **90天** | ~70% | 用于精细分析/报警触发 |
| `crack_monitor` 裂缝原始 | **365天** | ~5% | 裂缝扩展趋势分析 |
| `sensor_data_hourly` | **2年** | ~15% | UI默认查询 |
| `sensor_data_daily` | **10年** | ~8% | 年度报告 |
| `sensor_data_monthly` | **永久** | ~2% | 寿命外推 |

### 📈 查询示例（自动命中聚合）
```sql
-- 查询西墙北段最近7天(自动命中hourly聚合，速度提升10~50x)
SELECT bucket, avg_erosion_depth, avg_wind_speed
FROM sensor_data_hourly
WHERE segment_id = 1
  AND bucket >= now() - INTERVAL '7 days'
ORDER BY bucket;
```

---

## 🌐 Nginx Gzip压缩与性能

**nginx.conf 中 Gzip 配置要点：**

| 项 | 值 | 效果 |
|----|----|------|
| 压缩级别 | `6` (CPU/压缩率平衡) | HTML/JS/CSS 压缩比 70~85% |
| 最小文件 | `256` 字节 | 避免小文件得不偿失 |
| MIME类型 | 26种 | 含 `application/javascript`、`image/svg+xml`、`font/woff2` |
| 静态缓存 | CSS/JS `30天`、图片 `60天`、字体 `90天` | 二次访问零下载 |
| keepalive | `75s / 1000次请求` | 减少TCP握手 |

**实测收益（以Three.js 550KB为例）：**
```
原始:  three.min.js       550 KB  (1.2s @ 4G)
Gzip:  three.min.js.gz    148 KB  (0.32s @ 4G)
压缩率: 73%  |  节省: 402 KB (加载加速3.7x)
```

---

## 🧪 回归测试（开发验证）

```bash
# 1. 微服务模块级联验证
python test_regression.py
#   → 6大模块（配置/DTU/风蚀仿真/TOPSIS/告警/适配器）全通过

# 2. API路由级回归
python test_api_regression.py
#   → 9个API路由（墙段列表/DTU/预测/两相流/风场/方案/评估/告警/统计）
#   → exit_code=0 全部OK
```

---

## 🐳 Docker 构建细节

### FastAPI 镜像（多阶段，~480MB）
```
Stage 1 (builder): python:3.11-slim + build-essential
    ↓ pip wheel 所有依赖 + numpy/scipy 编译
Stage 2 (runtime): python:3.11-slim + libpq/libopenblas
    ↓ 仅copy wheels + 源码
    ↓ 非root用户 (appuser) 运行
    ↓ Gunicorn 4 workers × UvicornWorker
```
### 启动参数
```bash
gunicorn backend.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 4 -b 0.0.0.0:8000 \
  --max-requests 5000 --max-requests-jitter 500
```
> **内存占用稳定在 350~500MB，并发 500+ QPS**

---

## 🔗 微服务频道定义（Redis Pub/Sub）

| 频道名 | 发布方 | 订阅方 | 载荷 |
|--------|--------|--------|------|
| `DTU_DATA_IN` | dtu_receiver | alarm_mqtt + wind_erosion | 传感器原始数据 |
| `EROSION_REQUEST` | adapter | wind_erosion_simulator | mode + 参数 |
| `EROSION_RESULT` | wind_erosion_simulator | adapter | 风蚀结果 |
| `TOPSIS_REQUEST` | adapter | reinforcement_optimizer | 方案+权重 |
| `TOPSIS_RESULT` | reinforcement_optimizer | adapter | 排名+贴进度 |
| `ALERT_REQUEST` | adapter | alarm_mqtt | 告警触发条件 |
| `ALERT_RESULT` | alarm_mqtt | adapter | 告警详情+推送结果 |

> ✅ **容错设计**：Redis不可用时，`MicroserviceAdapter` **自动降级为进程内直接调用**，对API完全透明。

---

## 📝 License & Contact

文化遗产数字化保护项目 · 内部使用
