class ErosionPanelController {
    constructor(containerId, chartsContainerId) {
        this.container = document.getElementById(containerId);
        this.chartsContainer = chartsContainerId ? document.getElementById(chartsContainerId) : null;

        this.charts = {};
        this.colors = {
            primary: '#3b82f6',
            secondary: '#8b5cf6',
            success: '#10b981',
            warning: '#f59e0b',
            danger: '#ef4444',
            info: '#06b6d4',
            erosion: '#f97316'
        };

        this.currentSegmentId = 1;
        this.refreshTimer = null;
        this.refreshIntervalSeconds = 30;

        this.initErosionTrendChart();
    }

    async loadErosionPrediction(segmentId, years = 10) {
        this.currentSegmentId = segmentId;
        try {
            const response = await fetch('/api/erosion/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    segment_id: segmentId,
                    years: years,
                    climate_change_factor: 1.0
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            this.renderPredictionResults(result);
            return result;
        } catch (error) {
            console.error('加载风蚀预测失败:', error);
            this.renderError('风蚀预测加载失败: ' + error.message);
            return null;
        }
    }

    async loadSegmentSensorData(segmentId, days = 7) {
        this.currentSegmentId = segmentId;
        try {
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - days * 24 * 60 * 60 * 1000);

            const params = new URLSearchParams({
                segment_id: segmentId,
                start_time: startTime.toISOString(),
                end_time: endTime.toISOString(),
                aggregation: 'hourly'
            });

            const response = await fetch(`/api/sensor-data/query?${params}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.updateErosionTrendChart(data);
            return data;
        } catch (error) {
            console.error('加载传感器数据失败:', error);
            this.renderError('传感器数据加载失败: ' + error.message);
            return null;
        }
    }

    initErosionTrendChart() {
        const canvas = document.getElementById('erosionTrendChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        this.charts.erosionTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: '风蚀深度 (mm)',
                        data: [],
                        borderColor: this.colors.erosion,
                        backgroundColor: 'rgba(249, 115, 22, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointHoverRadius: 5
                    },
                    {
                        label: '风蚀速率 (mm/年)',
                        data: [],
                        borderColor: this.colors.danger,
                        backgroundColor: 'transparent',
                        borderDash: [5, 5],
                        tension: 0.4,
                        pointRadius: 2,
                        yAxisID: 'y1'
                    },
                    {
                        label: '预警阈值',
                        data: [],
                        borderColor: this.colors.warning,
                        backgroundColor: 'transparent',
                        borderDash: [2, 2],
                        pointRadius: 0,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleColor: '#f8fafc',
                        bodyColor: '#e2e8f0',
                        borderColor: 'rgba(148, 163, 184, 0.3)',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '风蚀深度 (mm)',
                            color: '#e2e8f0'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '风蚀速率 (mm/年)',
                            color: '#e2e8f0'
                        }
                    }
                }
            }
        });
    }

    updateErosionTrendChart(dataPoints) {
        if (!this.charts.erosionTrend || !dataPoints || dataPoints.length === 0) return;

        const labels = dataPoints.map(d => {
            const date = new Date(d.timestamp);
            return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
        });

        const erosionDepths = dataPoints.map(d => d.erosion_depth || 0);
        const erosionRates = dataPoints.map(d => d.erosion_rate || 0);
        const thresholdLine = dataPoints.map(() => 0.5);

        this.charts.erosionTrend.data.labels = labels;
        this.charts.erosionTrend.data.datasets[0].data = erosionDepths;
        this.charts.erosionTrend.data.datasets[1].data = erosionRates;
        this.charts.erosionTrend.data.datasets[2].data = thresholdLine;
        this.charts.erosionTrend.update('none');
    }

    updateWindRose(windSpeedBins, directionBins) {
        const container = document.getElementById('windRoseContainer');
        if (!container) return;

        const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
        const directionLabels = directionBins || directions;

        container.innerHTML = `
            <div class="wind-rose-header">
                <h5>风速风向统计</h5>
            </div>
            <div class="wind-rose-stats">
                <div class="stat-row">
                    <span class="stat-label">总样本数:</span>
                    <span class="stat-value">${(windSpeedBins ? windSpeedBins.reduce((a, b) => a + (b.count || 0), 0) : 0)}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">平均风速:</span>
                    <span class="stat-value">${(windSpeedBins ? this.calculateAvgWindSpeed(windSpeedBins).toFixed(2) : 0)} m/s</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">主导风向:</span>
                    <span class="stat-value">${this.findDominantDirection(directionBins)}</span>
                </div>
            </div>
            <div class="direction-bins">
                ${directionLabels.map((dir, idx) => {
                    const count = directionBins && directionBins[idx] ? (directionBins[idx].count || 0) : 0;
                    const maxCount = directionBins ? Math.max(...directionBins.map(d => d.count || 1)) : 1;
                    const percentage = maxCount > 0 ? (count / maxCount * 100) : 0;
                    return `
                        <div class="direction-bin">
                            <span class="dir-label">${typeof dir === 'object' ? dir.label : dir}</span>
                            <div class="dir-bar">
                                <div class="dir-bar-fill" style="width: ${percentage}%"></div>
                            </div>
                            <span class="dir-count">${count}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    calculateAvgWindSpeed(windSpeedBins) {
        if (!windSpeedBins || windSpeedBins.length === 0) return 0;
        let total = 0;
        let count = 0;
        windSpeedBins.forEach(bin => {
            total += (bin.speed || 0) * (bin.count || 0);
            count += bin.count || 0;
        });
        return count > 0 ? total / count : 0;
    }

    findDominantDirection(directionBins) {
        if (!directionBins || directionBins.length === 0) return '-';
        let maxIdx = 0;
        let maxCount = 0;
        directionBins.forEach((bin, idx) => {
            const c = typeof bin === 'object' ? (bin.count || 0) : 0;
            if (c > maxCount) {
                maxCount = c;
                maxIdx = idx;
            }
        });
        const directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北'];
        return directions[maxIdx % directions.length];
    }

    updateCriticalZones(criticalZones) {
        const container = document.getElementById('criticalZonesContainer');
        if (!container) return;

        if (!criticalZones || criticalZones.length === 0) {
            container.innerHTML = '<div class="no-data">暂无危险区域数据</div>';
            return;
        }

        container.innerHTML = `
            <h5>危险区域分布</h5>
            <table class="critical-zones-table">
                <thead>
                    <tr>
                        <th>位置</th>
                        <th>侵蚀速率 (mm/年)</th>
                        <th>风险等级</th>
                        <th>加固建议</th>
                    </tr>
                </thead>
                <tbody>
                    ${criticalZones.map(zone => {
                        const rate = zone.erosion_rate || 0;
                        const riskClass = this.getRiskClass(rate);
                        const riskText = this.getRiskText(rate);
                        return `
                            <tr>
                                <td>${zone.location || zone.position || '-'}</td>
                                <td class="${riskClass}-text">${rate.toFixed(4)}</td>
                                <td><span class="risk-badge ${riskClass}">${riskText}</span></td>
                                <td>${zone.suggestion || zone.recommendation || this.getDefaultSuggestion(rate)}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    }

    getRiskClass(erosionRate) {
        if (erosionRate < 0.2) return 'risk-low';
        if (erosionRate < 0.5) return 'risk-medium';
        return 'risk-high';
    }

    getRiskText(erosionRate) {
        if (erosionRate < 0.2) return '低风险';
        if (erosionRate < 0.5) return '中风险';
        return '高风险';
    }

    getDefaultSuggestion(rate) {
        if (rate < 0.2) return '定期监测，暂无加固需求';
        if (rate < 0.5) return '建议进行表面防护处理';
        return '建议立即实施加固工程';
    }

    updateDESHeatmap(erosionMapData, enhancementData) {
        const container = document.getElementById('desHeatmapContainer');
        if (!container) return;

        if (!erosionMapData) {
            container.innerHTML = '<div class="no-data">暂无DES风蚀热力图数据</div>';
            return;
        }

        const grid = erosionMapData.erosion_grid || erosionMapData;
        const gridSize = grid.grid_size || 10;
        const erosionRates = grid.erosion_rates || [];

        if (erosionRates.length === 0) {
            container.innerHTML = '<div class="no-data">热力图数据为空</div>';
            return;
        }

        const canvas = document.createElement('canvas');
        canvas.className = 'des-heatmap-canvas';
        canvas.id = 'desHeatmapCanvas';

        container.innerHTML = `
            <h5>DES风蚀热力图</h5>
            <div class="heatmap-wrapper">
                ${enhancementData ? `
                    <div class="enhancement-info">
                        <div class="enhancement-item">
                            <span>增强算法:</span>
                            <span>${enhancementData.algorithm || 'DES+'}</span>
                        </div>
                        <div class="enhancement-item">
                            <span>分辨率提升:</span>
                            <span>${enhancementData.resolution_boost || '2x'}</span>
                        </div>
                        <div class="enhancement-item">
                            <span>信噪比提升:</span>
                            <span>${enhancementData.snr_gain || '+' + (enhancementData.snr_gain || 3) + 'dB'}</span>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        const wrapper = container.querySelector('.heatmap-wrapper');
        wrapper.appendChild(canvas);

        requestAnimationFrame(() => {
            this.renderHeatmapCanvas(canvas, gridSize, erosionRates);
        });
    }

    renderHeatmapCanvas(canvas, gridSize, erosionRates) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width = canvas.parentElement ? canvas.parentElement.clientWidth - 40 : 400;
        const height = canvas.height = 300;

        const cellWidth = width / gridSize;
        const cellHeight = height / gridSize;

        const maxErosion = Math.max(...erosionRates, 1);

        for (let i = 0; i < gridSize; i++) {
            for (let j = 0; j < gridSize; j++) {
                const idx = i * gridSize + j;
                const erosion = erosionRates[idx] || 0;
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

    updateReinforcementSuggestion(plan) {
        const container = document.getElementById('reinforcementSuggestionContainer');
        if (!container) return;

        if (!plan) {
            container.innerHTML = '<div class="no-data">暂无推荐加固方案</div>';
            return;
        }

        const effectiveness = (plan.effectiveness_score || plan.effectiveness || 0) * 100;
        const cost = plan.estimated_cost || plan.cost || 0;
        const durability = plan.estimated_durability || plan.durability || 0;
        const penetration = plan.penetration_depth || plan.penetration || 0;

        container.innerHTML = `
            <h5>推荐加固方案</h5>
            <div class="reinforcement-card ${effectiveness >= 70 ? 'card-best' : ''}">
                <div class="card-header">
                    <span class="plan-name">${plan.plan_name || plan.name || '标准加固方案'}</span>
                    ${effectiveness >= 70 ? '<span class="badge-best">推荐</span>' : ''}
                </div>
                <div class="card-body">
                    <div class="plan-material">
                        <span class="label">主要材料:</span>
                        <span class="value">${plan.material_name || plan.material || '硅基加固剂'}</span>
                    </div>
                    <div class="plan-stats">
                        <div class="stat-item">
                            <span class="stat-label">加固效果</span>
                            <span class="stat-value ${effectiveness >= 70 ? 'text-success' : effectiveness >= 40 ? 'text-warning' : 'text-danger'}">
                                ${effectiveness.toFixed(1)}%
                            </span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">渗透深度</span>
                            <span class="stat-value">${penetration.toFixed(2)} mm</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">耐用年限</span>
                            <span class="stat-value">${durability} 年</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">预估成本</span>
                            <span class="stat-value">${cost.toFixed(2)} 万元</span>
                        </div>
                    </div>
                    ${plan.description ? `
                        <div class="plan-description">
                            <p>${plan.description}</p>
                        </div>
                    ` : ''}
                    ${plan.steps && plan.steps.length > 0 ? `
                        <div class="plan-steps">
                            <span class="steps-title">施工步骤:</span>
                            <ol>
                                ${plan.steps.map(step => `<li>${step}</li>`).join('')}
                            </ol>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    setRefreshInterval(seconds) {
        this.refreshIntervalSeconds = seconds;
        this.stopAutoRefresh();

        if (seconds > 0) {
            this.startAutoRefresh();
        }
    }

    startAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }

        this.refreshTimer = setInterval(() => {
            this.autoRefreshCallback();
        }, this.refreshIntervalSeconds * 1000);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    autoRefreshCallback() {
        this.loadSegmentSensorData(this.currentSegmentId, 7);
    }

    renderPredictionResults(result) {
        const container = document.getElementById('predictionResultsContainer');
        if (!container) return;

        const avgRate = result.average_erosion_rate || 0;
        const rateClass = this.getRiskClass(avgRate);

        container.innerHTML = `
            <div class="prediction-summary">
                <h5>仿真结果摘要</h5>
                <div class="result-grid">
                    <div class="result-item">
                        <span class="result-label">预测年限</span>
                        <span class="result-value">${result.prediction_years || result.years || 10} 年</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">最终风蚀深度</span>
                        <span class="result-value">${(result.final_erosion_depth || 0).toFixed(3)} mm</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">平均风蚀速率</span>
                        <span class="result-value ${rateClass}-text">
                            ${avgRate.toFixed(4)} mm/年
                        </span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">最大风蚀速率</span>
                        <span class="result-value text-danger">${(result.max_erosion_rate || 0).toFixed(4)} mm/年</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">气候变化因子</span>
                        <span class="result-value">${result.climate_change_factor || 1.0}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">剩余寿命预估</span>
                        <span class="result-value ${(result.estimated_lifetime || 100) < 50 ? 'text-danger' : 'text-success'}">
                            ${(result.estimated_lifetime || 0).toFixed(1)} 年
                        </span>
                    </div>
                </div>
            </div>
        `;

        if (result.erosion_grid) {
            this.updateDESHeatmap({ erosion_grid: result.erosion_grid }, null);
        }
    }

    renderError(message) {
        if (this.container) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-notification';
            errorDiv.textContent = message;
            errorDiv.style.cssText = 'background:#fee2e2;color:#991b1b;padding:12px;border-radius:6px;margin:8px 0;';
            this.container.insertBefore(errorDiv, this.container.firstChild);
            setTimeout(() => errorDiv.remove(), 5000);
        }
    }

    destroy() {
        this.stopAutoRefresh();

        for (const key in this.charts) {
            if (this.charts[key]) {
                try {
                    this.charts[key].destroy();
                } catch (e) {
                    console.warn('销毁图表失败:', key, e);
                }
            }
        }
        this.charts = {};
        this.container = null;
    }
}

window.ErosionPanelController = ErosionPanelController;
