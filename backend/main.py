import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime

from .config import settings
from .database import Base, async_engine
from .routers import (
    wall_segments,
    sensor_data,
    erosion,
    reinforcement,
    alerts,
    wind_field,
    statistics,
    dynasty,
    plants,
    virtual
)
from .modules.craft_comparator import router as craft_router
from .modules.era_comparator import router as era_router
from .modules.vegetation_protector import router as vegetation_router
from .modules.vr_rammed_earth import router as vr_router
from .services.mqtt_alert import mqtt_alert_service
from .adapters import get_adapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application...")
    
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    if mqtt_alert_service.connect():
        logger.info("MQTT alert service connected")
    else:
        logger.warning("Failed to connect to MQTT broker - alerts will not be published")

    try:
        adapter = get_adapter()
        await adapter.ensure_services()
        if adapter.local_only:
            logger.info("Microservice adapter running in local-only mode (in-process)")
        else:
            logger.info("Microservice adapter running with Redis Pub/Sub message bus")
    except Exception as e:
        logger.error(f"Failed to initialize microservice adapter: {e}")

    yield
    
    logger.info("Shutting down application...")
    mqtt_alert_service.disconnect()
    logger.info("MQTT connection closed")


app = FastAPI(
    title="古代咸阳宫夯土墙抗风蚀仿真与加固方案优化系统",
    description="秦咸阳宫遗址夯土墙保护研究系统 - 风蚀仿真、加固方案优化、实时监测预警",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wall_segments.router)
app.include_router(sensor_data.router)
app.include_router(erosion.router)
app.include_router(reinforcement.router)
app.include_router(alerts.router)
app.include_router(wind_field.router)
app.include_router(statistics.router)
app.include_router(dynasty.router)
app.include_router(plants.router)
app.include_router(virtual.router)
app.include_router(craft_router)
app.include_router(era_router)
app.include_router(vegetation_router)
app.include_router(vr_router)

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir)), name="frontend")
    logger.info(f"Frontend static files mounted from {frontend_dir}")
else:
    logger.warning(f"Frontend directory not found: {frontend_dir}")


@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>古代咸阳宫夯土墙抗风蚀仿真系统</title>
        <style>
            body {
                font-family: 'Microsoft YaHei', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                padding: 40px;
                max-width: 800px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 10px;
                font-size: 28px;
            }
            .subtitle {
                text-align: center;
                color: #666;
                margin-bottom: 30px;
                font-size: 16px;
            }
            .info-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 30px;
            }
            .info-card {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 12px;
                border-left: 4px solid #667eea;
            }
            .info-card h3 {
                margin: 0 0 10px 0;
                color: #667eea;
                font-size: 18px;
            }
            .info-card p {
                margin: 5px 0;
                color: #555;
                font-size: 14px;
            }
            .status {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
            }
            .status.running {
                background: #d4edda;
                color: #155724;
            }
            .btn {
                display: inline-block;
                padding: 12px 30px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                margin: 5px;
                transition: all 0.3s;
                font-weight: bold;
            }
            .btn:hover {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
            .btn-secondary {
                background: #6c757d;
            }
            .btn-secondary:hover {
                background: #5a6268;
            }
            .features {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 20px;
                justify-content: center;
            }
            .feature-tag {
                background: #e9ecef;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 13px;
                color: #495057;
            }
            .buttons {
                text-align: center;
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏛️ 古代咸阳宫夯土墙抗风蚀仿真系统</h1>
            <p class="subtitle">秦咸阳宫遗址夯土墙保护研究平台</p>
            
            <div class="info-grid">
                <div class="info-card">
                    <h3>🚀 系统状态</h3>
                    <p>API服务: <span class="status running">运行中</span></p>
                    <p>启动时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
                    <p>版本: v1.0.0</p>
                </div>
                <div class="info-card">
                    <h3>📡 数据接入</h3>
                    <p>墙体段数: 8段</p>
                    <p>上报频率: 每小时1次</p>
                    <p>通信方式: 4G DTU</p>
                </div>
                <div class="info-card">
                    <h3>🔬 核心模型</h3>
                    <p>风蚀模型: 风沙两相流+颗粒撞击</p>
                    <p>优化方法: TOPSIS多目标决策</p>
                    <p>告警推送: MQTT协议</p>
                </div>
                <div class="info-card">
                    <h3>🧱 加固材料</h3>
                    <p>硅酸乙酯 (TEOS)</p>
                    <p>糯米灰浆 (传统材料)</p>
                    <p>复合加固剂</p>
                </div>
            </div>
            
            <div class="features">
                <span class="feature-tag">🌪️ 风蚀仿真</span>
                <span class="feature-tag">📊 实时监测</span>
                <span class="feature-tag">🔔 MQTT告警</span>
                <span class="feature-tag">🧮 TOPSIS优化</span>
                <span class="feature-tag">🎨 3D可视化</span>
                <span class="feature-tag">💨 风场粒子</span>
                <span class="feature-tag">🏗️ 加固方案</span>
                <span class="feature-tag">📈 趋势预测</span>
            </div>
            
            <div class="buttons">
                <a href="/docs" class="btn">📚 API文档</a>
                <a href="/frontend/index.html" class="btn btn-secondary">🎨 3D可视化</a>
                <a href="/api/statistics/dashboard" class="btn btn-secondary">📊 数据看板</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mqtt_connected": mqtt_alert_service.connected,
        "version": "1.0.0"
    }


@app.get("/api/config")
async def get_config():
    return {
        "erosion_threshold": settings.EROSION_THRESHOLD,
        "crack_threshold": settings.CRACK_THRESHOLD,
        "mqtt_broker": settings.MQTT_BROKER,
        "mqtt_port": settings.MQTT_PORT,
        "mqtt_topic": settings.MQTT_TOPIC,
        "wall_segments": settings.WALL_SEGMENTS,
        "simulation_interval": settings.SIMULATION_INTERVAL
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )
