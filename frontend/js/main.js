
const AppState = {
    currentSegmentId: 1,
    currentTab: '3d',
    wallSegments: [],
    sensorData: {},
    alerts: [],
    erosionPrediction: null,
    reinforcementPlans: [],
    refreshInterval: 30000,
    refreshTimer: null
};

let wallViewer = null;
let erosionPanel = null;
let windField2D = null;
let windField3D = null;
let dataCharts = null;
let mqttClient = null;

document.addEventListener('DOMContentLoaded', function() {
    initApp();
});

async function initApp() {
    try {
        await loadWallSegments();
        initThreeJSViewer();
        initErosionPanel();
        initWindFieldVisualizer();
        initDataCharts();
        initTabSwitching();
        initEventListeners();
        initMQTT();
        
        if (typeof DynastyCompareModule !== 'undefined') DynastyCompareModule.init();
        if (typeof PlantRootModule !== 'undefined') PlantRootModule.init();
        if (typeof VirtualExperienceModule !== 'undefined') VirtualExperienceModule.init();
        
        await loadSegmentData(AppState.currentSegmentId);
        await loadDashboardData();
        await loadAlerts();
        
        startAutoRefresh();
        
        showNotification('系统初始化完成', 'success');
    } catch (error) {
        console.error('初始化失败:', error);
        showNotification('系统初始化失败: ' + error.message, 'error');
    }
}

async function loadWallSegments() {
    try {
        const response = await fetch('/api/wall-segments');
        AppState.wallSegments = await response.json();
        renderWallSegmentList();
    } catch (error) {
        console.error('加载墙体段失败:', error);
    }
}

function renderWallSegmentList() {
    const container = document.getElementById('wallSegmentList');
    if (!container) return;
    
    container.innerHTML = '';
    
    AppState.wallSegments.forEach(segment => {
        const erosionRate = segment.current_erosion_rate || 0;
        const riskClass = getRiskClass(erosionRate);
        
        const div = document.createElement('div');
        div.className = `wall-segment-item ${segment.id === AppState.currentSegmentId ? 'active' : ''}`;
        div.innerHTML = `
            <div class="segment-header">
                <span class="segment-name">${segment.name}</span>
                <span class="risk-badge ${riskClass}">${getRiskText(erosionRate)}</span>
            </div>
            <div class="segment-info">
                <span>风蚀速率: ${erosionRate.toFixed(3)} mm/年</span>
                <span>硬度: ${(segment.average_hardness || 0).toFixed(2)} MPa</span>
            </div>
        `;
        div.onclick = () => selectSegment(segment.id);
        container.appendChild(div);
    });
}

function getRiskClass(erosionRate) {
    if (erosionRate < 0.2) return 'risk-low';
    if (erosionRate < 0.5) return 'risk-medium';
    return 'risk-high';
}

function getRiskText(erosionRate) {
    if (erosionRate < 0.2) return '低风险';
    if (erosionRate < 0.5) return '中风险';
    return '高风险';
}

function initThreeJSViewer() {
    const container = document.getElementById('threejsContainer');
    if (!container) return;
    
    wallViewer = new RammedEarth3DViewer('threejsContainer');
    
    AppState.wallSegments.forEach((segment, index) => {
        if (wallViewer.wallSegments.length < AppState.wallSegments.length) {
        }
    });
    
    wallViewer.animate();
}

function initErosionPanel() {
    const panelContainer = document.getElementById('simulationResults');
    const chartsContainer = document.getElementById('erosionTrendChart')?.parentElement;
    if (!panelContainer) return;
    
    erosionPanel = new ErosionPanelController('simulationResults', 'erosionTrendChart');
    
    const toggleErosion = document.getElementById('showErosion');
    if (toggleErosion) {
        toggleErosion.addEventListener('change', (e) => {
            wallViewer?.setShowErosion(e.target.checked);
        });
    }
    const toggleWind = document.getElementById('showWindField');
    if (toggleWind) {
        toggleWind.addEventListener('change', (e) => {
            wallViewer?.setShowWindField(e.target.checked);
        });
    }
    const toggleWire = document.getElementById('showWireframe');
    if (toggleWire) {
        toggleWire.addEventListener('change', (e) => {
            wallViewer?.setShowWireframe(e.target.checked);
        });
    }
    const intensitySlider = document.getElementById('erosionIntensity');
    if (intensitySlider) {
        intensitySlider.addEventListener('input', (e) => {
            wallViewer?.setErosionIntensity(parseInt(e.target.value));
        });
    }
}

function initWindFieldVisualizer() {
    const canvas = document.getElementById('windFieldCanvas');
    if (!canvas) return;
    
    windField2D = new WindFieldVisualizer('windFieldCanvas');
    windField2D.start();
    
    if (wallViewer) {
        windField3D = new WindField3D(wallViewer.scene);
    }
}

function initDataCharts() {
    dataCharts = new DataCharts();
    dataCharts.initAllCharts();
}

function initTabSwitching() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', async () => {
            const tabId = tab.dataset.tab;
            switchTab(tabId);
        });
    });
}

async function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(`${tabId}Tab`).classList.add('active');
    
    AppState.currentTab = tabId;
    
    switch (tabId) {
        case '3d':
            break;
        case 'erosion':
            await updateErosionTab();
            break;
        case 'windfield':
            await updateWindTab();
            break;
        case 'reinforcement':
            await updateReinforcementTab();
            break;
        case 'charts':
            await updateChartsTab();
            break;
        case 'dynasty':
            if (typeof DynastyCompareModule !== 'undefined' && !AppState.dynastyInited) {
                DynastyCompareModule.loadDynastyList();
                AppState.dynastyInited = true;
            }
            break;
        case 'crossera':
            break;
        case 'plants':
            if (typeof PlantRootModule !== 'undefined' && !AppState.plantsInited) {
                PlantRootModule.loadPlantList();
                AppState.plantsInited = true;
            }
            break;
        case 'virtual':
            if (typeof VirtualExperienceModule !== 'undefined' && !AppState.virtualInited) {
                VirtualExperienceModule.loadPresets();
                AppState.virtualInited = true;
            }
            break;
    }
}

function initEventListeners() {
    document.getElementById('btnRefresh').addEventListener('click', () => {
        refreshAllData();
    });
    
    document.getElementById('btnSimulate').addEventListener('click', () => {
        runErosionSimulation();
    });
    
    document.getElementById('btnEvaluate').addEventListener('click', () => {
        evaluateReinforcementPlans();
    });
    
    document.getElementById('btnGenerateHistory').addEventListener('click', () => {
        generateHistoricalData();
    });
    
    document.getElementById('btnTestMQTT').addEventListener('click', () => {
        testMQTTPublish();
    });
    
    document.getElementById('alertCloseBtn').addEventListener('click', () => {
        document.getElementById('alertPanel').classList.remove('show');
    });
    
    window.addEventListener('resize', () => {
        if (wallViewer) wallViewer.onWindowResize();
        if (windField2D) {
            const container = document.getElementById('windFieldContainer');
            if (container) {
                windField2D.resize(container.clientWidth, container.clientHeight);
            }
        }
    });
}

function initMQTT() {
    try {
        const clientId = 'web_client_' + Math.random().toString(16).substr(2, 8);
        mqttClient = new Paho.MQTT.Client(
            window.location.hostname,
            9001,
            clientId
        );
        
        mqttClient.onConnectionLost = onConnectionLost;
        mqttClient.onMessageArrived = onMessageArrived;
        
        mqttClient.connect({
            onSuccess: onConnect,
            onFailure: onConnectFailure,
            useSSL: false
        });
    } catch (error) {
        console.warn('MQTT连接不可用，使用轮询方式接收告警:', error);
    }
}

function onConnect() {
    console.log('MQTT连接成功');
    mqttClient.subscribe('wall/alert/#');
}

function onConnectFailure(responseObject) {
    console.warn('MQTT连接失败:', responseObject.errorMessage);
}

function onConnectionLost(responseObject) {
    if (responseObject.errorCode !== 0) {
        console.warn('MQTT连接丢失:', responseObject.errorMessage);
    }
}

function onMessageArrived(message) {
    console.log('收到MQTT消息:', message.destinationName, message.payloadString);
    
    try {
        const alert = JSON.parse(message.payloadString);
        addAlert(alert);
        showNotification(`告警: ${alert.message}`, 'warning');
        
        if (alert.alert_type === 'erosion_rate' && alert.segment_id === AppState.currentSegmentId) {
            if (wallViewer) {
                wallViewer.updateErosionColors(alert.segment_id, alert.current_value);
            }
        }
    } catch (error) {
        console.error('解析MQTT消息失败:', error);
    }
}

async function selectSegment(segmentId) {
    AppState.currentSegmentId = segmentId;
    renderWallSegmentList();
    
    if (wallViewer) {
        wallViewer.highlightSegment(segmentId);
    }
    
    await loadSegmentData(segmentId);
    
    switch (AppState.currentTab) {
        case 'erosion':
            await updateErosionTab();
            break;
        case 'wind':
            await updateWindTab();
            break;
        case 'reinforcement':
            await updateReinforcementTab();
            break;
        case 'charts':
            await updateChartsTab();
            break;
    }
}

async function loadSegmentData(segmentId) {
    try {
        const response = await fetch(`/api/wall-segments/${segmentId}/status`);
        const status = await response.json();
        
        AppState.sensorData[segmentId] = status;
        updateSegmentStatusDisplay(status);
        
        if (wallViewer && status) {
            wallViewer.updateErosionColors(segmentId, status.erosion_rate || 0);
            wallViewer.setWindParameters(
                status.avg_wind_speed_24h || 5,
                180
            );
        }
        
        if (windField2D && status.latest_data) {
            windField2D.setWindParams(
                status.latest_data.wind_speed || 5,
                status.latest_data.wind_direction || 0
            );
        }
    } catch (error) {
        console.error('加载墙体状态失败:', error);
    }
}

function updateSegmentStatusDisplay(status) {
    const segment = AppState.wallSegments.find(s => s.id === AppState.currentSegmentId);
    if (!segment) return;
    
    document.getElementById('currentSegmentName').textContent = segment.name;
    
    const latestData = status.latest_data || {};
    document.getElementById('currentErosionDepth').textContent = 
        (latestData.erosion_depth || 0).toFixed(3) + ' mm';
    document.getElementById('currentMoisture').textContent = 
        (latestData.moisture_content || 0).toFixed(2) + ' %';
    document.getElementById('currentHardness').textContent = 
        (latestData.surface_hardness || 0).toFixed(2) + ' MPa';
    document.getElementById('currentWindSpeed').textContent = 
        (latestData.wind_speed || 0).toFixed(1) + ' m/s';
    document.getElementById('currentWindDirection').textContent = 
        (latestData.wind_direction || 0).toFixed(0) + '°';
    document.getElementById('currentErosionRate').textContent = 
        (status.erosion_rate || 0).toFixed(4) + ' mm/年';
    
    const erosionRate = status.erosion_rate || 0;
    const rateElement = document.getElementById('currentErosionRate');
    rateElement.className = '';
    if (erosionRate >= 0.5) {
        rateElement.classList.add('text-danger');
    } else if (erosionRate >= 0.2) {
        rateElement.classList.add('text-warning');
    } else {
        rateElement.classList.add('text-success');
    }
}

async function loadDashboardData() {
    try {
        const response = await fetch('/api/statistics/dashboard');
        const data = await response.json();
        
        document.getElementById('totalSegments').textContent = data.total_segments;
        document.getElementById('highRiskSegments').textContent = data.high_risk_count;
        document.getElementById('avgErosionRate').textContent = 
            data.avg_erosion_rate.toFixed(4) + ' mm/年';
        document.getElementById('activeAlerts').textContent = data.active_alerts;
        
        if (dataCharts) {
            dataCharts.updateSegmentComparison();
        }
    } catch (error) {
        console.error('加载看板数据失败:', error);
    }
}

async function loadAlerts() {
    try {
        const response = await fetch('/api/alerts?limit=20');
        const alerts = await response.json();
        
        AppState.alerts = alerts;
        renderAlerts();
    } catch (error) {
        console.error('加载告警失败:', error);
    }
}

function renderAlerts() {
    const container = document.getElementById('alertsList');
    if (!container) return;
    
    if (AppState.alerts.length === 0) {
        container.innerHTML = '<div class="no-data">暂无告警信息</div>';
        return;
    }
    
    container.innerHTML = '';
    
    AppState.alerts.forEach(alert => {
        const div = document.createElement('div');
        div.className = `alert-item ${alert.severity} ${alert.acknowledged ? 'acknowledged' : ''}`;
        
        const typeText = alert.alert_type === 'erosion_rate' ? '风蚀速率' : '裂缝扩展';
        const time = new Date(alert.created_at).toLocaleString('zh-CN');
        
        div.innerHTML = `
            <div class="alert-header">
                <span class="alert-type">${typeText}</span>
                <span class="alert-time">${time}</span>
            </div>
            <div class="alert-message">${alert.message}</div>
            <div class="alert-details">
                <span>当前值: ${alert.current_value.toFixed(4)}</span>
                <span>阈值: ${alert.threshold_value}</span>
            </div>
            ${!alert.acknowledged ? `
                <button class="btn-acknowledge" onclick="acknowledgeAlert(${alert.id})">
                    确认
                </button>
            ` : ''}
        `;
        
        container.appendChild(div);
    });
}

function addAlert(alert) {
    AppState.alerts.unshift(alert);
    if (AppState.alerts.length > 50) {
        AppState.alerts.pop();
    }
    renderAlerts();
}

async function acknowledgeAlert(alertId) {
    try {
        await fetch(`/api/alerts/${alertId}/acknowledge`, {
            method: 'POST'
        });
        
        const alert = AppState.alerts.find(a => a.id === alertId);
        if (alert) {
            alert.acknowledged = true;
        }
        renderAlerts();
        showNotification('告警已确认', 'success');
    } catch (error) {
        console.error('确认告警失败:', error);
        showNotification('确认失败', 'error');
    }
}

async function updateErosionTab() {
    if (!dataCharts) return;
    
    await Promise.all([
        dataCharts.updateErosionTrend(AppState.currentSegmentId, 7),
        dataCharts.updateMoisture(AppState.currentSegmentId, 7),
        dataCharts.updateHardness(AppState.currentSegmentId, 30)
    ]);
}

async function updateWindTab() {
    if (!dataCharts) return;
    
    await dataCharts.updateWindSpeed(AppState.currentSegmentId, 24);
    
    if (windField3D) {
        const endTime = new Date();
        const startTime = new Date(endTime.getTime() - 24 * 60 * 60 * 1000);
        await windField3D.updateWindField(
            AppState.currentSegmentId,
            startTime.toISOString(),
            endTime.toISOString()
        );
    }
}

async function updateReinforcementTab() {
    try {
        const response = await fetch(`/api/reinforcement/plans?segment_id=${AppState.currentSegmentId}`);
        AppState.reinforcementPlans = await response.json();
        renderReinforcementPlans();
    } catch (error) {
        console.error('加载加固方案失败:', error);
    }
}

async function updateChartsTab() {
    if (!dataCharts) return;
    
    await Promise.all([
        dataCharts.updateErosionTrend(AppState.currentSegmentId, 30),
        dataCharts.updateWindSpeed(AppState.currentSegmentId, 48),
        dataCharts.updateSegmentComparison(),
        dataCharts.updateMoisture(AppState.currentSegmentId, 14),
        dataCharts.updateHardness(AppState.currentSegmentId, 60)
    ]);
}

async function runErosionSimulation() {
    const years = parseInt(document.getElementById('simulationYears').value) || 10;
    const climateFactor = parseFloat(document.getElementById('climateFactor').value) || 1.0;
    
    try {
        showNotification('风蚀仿真计算中...', 'info');
        
        const response = await fetch('/api/erosion/predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                segment_id: AppState.currentSegmentId,
                years: years,
                climate_change_factor: climateFactor
            })
        });
        
        const result = await response.json();
        AppState.erosionPrediction = result;
        
        renderErosionPrediction(result);
        showNotification('风蚀仿真完成', 'success');
    } catch (error) {
        console.error('风蚀仿真失败:', error);
        showNotification('风蚀仿真失败: ' + error.message, 'error');
    }
}

function renderErosionPrediction(result) {
    const container = document.getElementById('simulationResults');
    if (!container) return;
    
    container.innerHTML = `
        <div class="simulation-summary">
            <h4>仿真结果摘要</h4>
            <div class="result-grid">
                <div class="result-item">
                    <span class="result-label">预测年限</span>
                    <span class="result-value">${result.prediction_years} 年</span>
                </div>
                <div class="result-item">
                    <span class="result-label">最终风蚀深度</span>
                    <span class="result-value">${result.final_erosion_depth.toFixed(3)} mm</span>
                </div>
                <div class="result-item">
                    <span class="result-label">平均风蚀速率</span>
                    <span class="result-value ${result.average_erosion_rate >= 0.5 ? 'text-danger' : result.average_erosion_rate >= 0.2 ? 'text-warning' : 'text-success'}">
                        ${result.average_erosion_rate.toFixed(4)} mm/年
                    </span>
                </div>
                <div class="result-item">
                    <span class="result-label">最大风蚀速率</span>
                    <span class="result-value text-danger">${result.max_erosion_rate.toFixed(4)} mm/年</span>
                </div>
                <div class="result-item">
                    <span class="result-label">气候变化因子</span>
                    <span class="result-value">${result.climate_change_factor}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">剩余寿命预估</span>
                    <span class="result-value ${result.estimated_lifetime < 50 ? 'text-danger' : 'text-success'}">
                        ${result.estimated_lifetime.toFixed(1)} 年
                    </span>
                </div>
            </div>
        </div>
        
        <div class="erosion-map-container">
            <h4>风蚀区域分布图</h4>
            <canvas id="erosionMapCanvas"></canvas>
        </div>
    `;
    
    const canvas = document.getElementById('erosionMapCanvas');
    if (canvas) {
        renderErosionMap(canvas, result.erosion_grid);
    }
}

function renderErosionMap(canvas, grid) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = 300;
    
    const gridSize = grid.grid_size;
    const cellWidth = width / gridSize;
    const cellHeight = height / gridSize;
    
    const maxErosion = Math.max(...grid.erosion_rates);
    
    for (let i = 0; i < gridSize; i++) {
        for (let j = 0; j < gridSize; j++) {
            const idx = i * gridSize + j;
            const erosion = grid.erosion_rates[idx];
            const normalized = Math.min(erosion / maxErosion, 1);
            
            let r, g, b;
            if (normalized < 0.33) {
                const t = normalized / 0.33;
                r = Math.floor(16 + t * (245 - 16));
                g = Math.floor(185 + t * (158 - 185));
                b = Math.floor(129 + t * (11 - 129));
            } else if (normalized < 0.66) {
                const t = (normalized - 0.33) / 0.33;
                r = Math.floor(245 + t * (239 - 245));
                g = Math.floor(158 + t * (68 - 158));
                b = Math.floor(11 + t * (68 - 11));
            } else {
                const t = (normalized - 0.66) / 0.34;
                r = 239;
                g = Math.floor(68 + t * (23 - 68));
                b = Math.floor(68 + t * (76 - 68));
            }
            
            ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
            ctx.fillRect(j * cellWidth, i * cellHeight, cellWidth - 1, cellHeight - 1);
        }
    }
    
    ctx.fillStyle = '#fff';
    ctx.font = '12px Arial';
    ctx.fillText('低', 10, height - 10);
    ctx.fillText('高', width - 20, height - 10);
    
    const gradient = ctx.createLinearGradient(width - 80, height - 25, width - 20, height - 25);
    gradient.addColorStop(0, '#10b981');
    gradient.addColorStop(0.5, '#f59e0b');
    gradient.addColorStop(1, '#ef4444');
    ctx.fillStyle = gradient;
    ctx.fillRect(width - 80, height - 20, 60, 10);
}

async function evaluateReinforcementPlans() {
    const moisture = parseFloat(document.getElementById('evalMoisture').value) || 10;
    const hardness = parseFloat(document.getElementById('evalHardness').value) || 2;
    const constructionPressure = parseFloat(document.getElementById('evalPressure').value) || 0.5;
    
    try {
        showNotification('TOPSIS评估计算中...', 'info');
        
        const response = await fetch('/api/reinforcement/evaluate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                segment_id: AppState.currentSegmentId,
                moisture_content: moisture,
                surface_hardness: hardness,
                construction_pressure: constructionPressure
            })
        });
        
        const result = await response.json();
        renderTOPSISResults(result);
        showNotification('加固方案评估完成', 'success');
    } catch (error) {
        console.error('评估失败:', error);
        showNotification('评估失败: ' + error.message, 'error');
    }
}

function renderTOPSISResults(result) {
    const container = document.getElementById('evaluationResults');
    if (!container) return;
    
    const bestPlan = result.evaluations[result.best_plan_index];
    
    container.innerHTML = `
        <div class="topsis-summary">
            <h4>TOPSIS评估结果</h4>
            <div class="best-plan">
                <span class="best-label">推荐方案</span>
                <span class="best-name">${bestPlan.plan_name}</span>
                <span class="best-score">综合评分: ${(bestPlan.closeness * 100).toFixed(2)}</span>
            </div>
        </div>
        
        <div class="charts-row">
            <div class="chart-container">
                <h5>综合评分对比</h5>
                <canvas id="topsisChart"></canvas>
            </div>
            <div class="chart-container">
                <h5>多维度雷达图</h5>
                <canvas id="radarChart"></canvas>
            </div>
        </div>
        
        <div class="plans-table-container">
            <h5>方案详情</h5>
            <table class="plans-table">
                <thead>
                    <tr>
                        <th>方案名称</th>
                        <th>材料</th>
                        <th>渗透深度(mm)</th>
                        <th>耐用年限(年)</th>
                        <th>成本(万元)</th>
                        <th>加固效果</th>
                        <th>TOPSIS评分</th>
                        <th>排名</th>
                    </tr>
                </thead>
                <tbody>
                    ${result.evaluations.map((plan, idx) => `
                        <tr class="${idx === result.best_plan_index ? 'best-plan-row' : ''}">
                            <td>${plan.plan_name}</td>
                            <td>${plan.material_name}</td>
                            <td>${plan.penetration_depth.toFixed(2)}</td>
                            <td>${plan.estimated_durability}</td>
                            <td>${plan.estimated_cost.toFixed(2)}</td>
                            <td>${(plan.effectiveness_score * 100).toFixed(1)}%</td>
                            <td>${(plan.closeness * 100).toFixed(2)}</td>
                            <td>${idx + 1}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    
    if (dataCharts) {
        dataCharts.updateTOPSISChart('topsisChart', result.evaluations);
        dataCharts.updateRadarChart('radarChart', result.evaluations, result.best_plan_index);
        dataCharts.updateReinforcementChart('reinforcementChart', result.evaluations);
    }
}

function renderReinforcementPlans() {
    const container = document.getElementById('reinforcementPlansList');
    if (!container) return;
    
    if (AppState.reinforcementPlans.length === 0) {
        container.innerHTML = '<div class="no-data">暂无加固方案，点击"评估加固方案"生成</div>';
        return;
    }
}

async function generateHistoricalData() {
    const hours = parseInt(prompt('请输入要生成的历史数据小时数:', '720')) || 720;
    
    try {
        showNotification(`正在生成${hours}小时历史数据...`, 'info');
        
        const response = await fetch('/api/sensor-data/generate-history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                hours: hours
            })
        });
        
        const result = await response.json();
        showNotification(`成功生成${result.generated_count}条历史数据`, 'success');
        
        await refreshAllData();
    } catch (error) {
        console.error('生成历史数据失败:', error);
        showNotification('生成失败: ' + error.message, 'error');
    }
}

async function testMQTTPublish() {
    try {
        const response = await fetch('/api/alerts/test-mqtt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                segment_id: AppState.currentSegmentId,
                alert_type: 'erosion_rate',
                message: '测试告警消息'
            })
        });
        
        const result = await response.json();
        showNotification('MQTT测试消息已发送', 'success');
    } catch (error) {
        console.error('MQTT测试失败:', error);
        showNotification('MQTT测试失败: ' + error.message, 'error');
    }
}

async function refreshAllData() {
    await Promise.all([
        loadWallSegments(),
        loadSegmentData(AppState.currentSegmentId),
        loadDashboardData(),
        loadAlerts()
    ]);
    
    switch (AppState.currentTab) {
        case 'erosion':
            await updateErosionTab();
            break;
        case 'wind':
            await updateWindTab();
            break;
        case 'charts':
            await updateChartsTab();
            break;
    }
}

function startAutoRefresh() {
    if (AppState.refreshTimer) {
        clearInterval(AppState.refreshTimer);
    }
    
    AppState.refreshTimer = setInterval(() => {
        refreshAllData();
    }, AppState.refreshInterval);
}

function stopAutoRefresh() {
    if (AppState.refreshTimer) {
        clearInterval(AppState.refreshTimer);
        AppState.refreshTimer = null;
    }
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('notificationContainer');
    if (!container) return;
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <span class="notification-message">${message}</span>
        <span class="notification-close">&times;</span>
    `;
    
    container.appendChild(notification);
    
    notification.querySelector('.notification-close').onclick = () => {
        notification.remove();
    };
    
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

window.acknowledgeAlert = acknowledgeAlert;
