
class DataCharts {
    constructor() {
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
    }

    initAllCharts() {
        this.initErosionTrendChart('erosionTrendChart');
        this.initWindSpeedChart('windSpeedChart');
        this.initSegmentComparisonChart('segmentComparisonChart');
        this.initRiskDistributionChart('riskDistributionChart');
        this.initMoistureChart('moistureChart');
        this.initHardnessChart('hardnessChart');
    }

    initErosionTrendChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
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

    initWindSpeedChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        this.charts.windSpeed = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: '风速 (m/s)',
                        data: [],
                        borderColor: this.colors.info,
                        backgroundColor: 'rgba(6, 182, 212, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: '风向 (°)',
                        data: [],
                        borderColor: this.colors.secondary,
                        backgroundColor: 'transparent',
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true
                        }
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
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '风速 (m/s)',
                            color: '#e2e8f0'
                        }
                    },
                    y1: {
                        position: 'right',
                        grid: {
                            drawOnChartArea: false
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '风向 (°)',
                            color: '#e2e8f0'
                        }
                    }
                }
            }
        });
    }

    initSegmentComparisonChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        this.charts.segmentComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: '风蚀速率 (mm/年)',
                        data: [],
                        backgroundColor: [],
                        borderRadius: 6
                    },
                    {
                        label: '表面硬度 (MPa)',
                        data: [],
                        backgroundColor: this.colors.info,
                        borderRadius: 6,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true
                        }
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
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '风蚀速率 (mm/年)',
                            color: '#e2e8f0'
                        }
                    },
                    y1: {
                        position: 'right',
                        grid: {
                            drawOnChartArea: false
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '表面硬度 (MPa)',
                            color: '#e2e8f0'
                        }
                    }
                }
            }
        });
    }

    initRiskDistributionChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        this.charts.riskDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['低风险 (<0.2 mm/年)', '中风险 (0.2-0.5 mm/年)', '高风险 (>0.5 mm/年)'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        this.colors.success,
                        this.colors.warning,
                        this.colors.danger
                    ],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true,
                            padding: 20
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleColor: '#f8fafc',
                        bodyColor: '#e2e8f0'
                    }
                }
            }
        });
    }

    initMoistureChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        this.charts.moisture = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '土体含水量 (%)',
                    data: [],
                    borderColor: this.colors.primary,
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true
                        }
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
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '含水量 (%)',
                            color: '#e2e8f0'
                        }
                    }
                }
            }
        });
    }

    initHardnessChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        this.charts.hardness = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '表面硬度 (MPa)',
                    data: [],
                    borderColor: this.colors.secondary,
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true
                        }
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
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '硬度 (MPa)',
                            color: '#e2e8f0'
                        }
                    }
                }
            }
        });
    }

    getErosionColor(erosionRate) {
        if (erosionRate < 0.2) return this.colors.success;
        if (erosionRate < 0.5) return this.colors.warning;
        return this.colors.danger;
    }

    async updateErosionTrend(segmentId, days = 7) {
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
            const data = await response.json();
            
            const labels = data.map(d => {
                const date = new Date(d.timestamp);
                return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
            });
            
            const erosionDepths = data.map(d => d.erosion_depth);
            const erosionRates = data.map(d => d.erosion_rate || 0);
            const thresholdLine = data.map(() => 0.5);
            
            this.charts.erosionTrend.data.labels = labels;
            this.charts.erosionTrend.data.datasets[0].data = erosionDepths;
            this.charts.erosionTrend.data.datasets[1].data = erosionRates;
            this.charts.erosionTrend.data.datasets[2].data = thresholdLine;
            this.charts.erosionTrend.update('none');
            
            return data;
        } catch (error) {
            console.error('更新风蚀趋势图失败:', error);
        }
    }

    async updateWindSpeed(segmentId, hours = 24) {
        try {
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - hours * 60 * 60 * 1000);
            
            const params = new URLSearchParams({
                segment_id: segmentId,
                start_time: startTime.toISOString(),
                end_time: endTime.toISOString()
            });
            
            const response = await fetch(`/api/sensor-data/query?${params}`);
            const data = await response.json();
            
            const labels = data.map(d => {
                const date = new Date(d.timestamp);
                return `${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
            });
            
            const windSpeeds = data.map(d => d.wind_speed);
            const windDirections = data.map(d => d.wind_direction);
            
            this.charts.windSpeed.data.labels = labels;
            this.charts.windSpeed.data.datasets[0].data = windSpeeds;
            this.charts.windSpeed.data.datasets[1].data = windDirections;
            this.charts.windSpeed.update('none');
            
            return data;
        } catch (error) {
            console.error('更新风速图失败:', error);
        }
    }

    async updateSegmentComparison() {
        try {
            const response = await fetch('/api/wall-segments');
            const segments = await response.json();
            
            const labels = segments.map(s => s.name);
            const erosionRates = segments.map(s => s.current_erosion_rate || 0);
            const hardnessValues = segments.map(s => s.average_hardness || 0);
            const colors = erosionRates.map(r => this.getErosionColor(r));
            
            this.charts.segmentComparison.data.labels = labels;
            this.charts.segmentComparison.data.datasets[0].data = erosionRates;
            this.charts.segmentComparison.data.datasets[0].backgroundColor = colors;
            this.charts.segmentComparison.data.datasets[1].data = hardnessValues;
            this.charts.segmentComparison.update('none');
            
            const lowRisk = erosionRates.filter(r => r < 0.2).length;
            const mediumRisk = erosionRates.filter(r => r >= 0.2 && r < 0.5).length;
            const highRisk = erosionRates.filter(r => r >= 0.5).length;
            
            this.charts.riskDistribution.data.datasets[0].data = [lowRisk, mediumRisk, highRisk];
            this.charts.riskDistribution.update('none');
            
            return segments;
        } catch (error) {
            console.error('更新墙体对比图失败:', error);
        }
    }

    async updateMoisture(segmentId, days = 7) {
        try {
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - days * 24 * 60 * 60 * 1000);
            
            const params = new URLSearchParams({
                segment_id: segmentId,
                start_time: startTime.toISOString(),
                end_time: endTime.toISOString(),
                aggregation: 'daily'
            });
            
            const response = await fetch(`/api/sensor-data/query?${params}`);
            const data = await response.json();
            
            const labels = data.map(d => {
                const date = new Date(d.timestamp);
                return `${date.getMonth() + 1}/${date.getDate()}`;
            });
            
            const moistures = data.map(d => d.moisture_content);
            
            this.charts.moisture.data.labels = labels;
            this.charts.moisture.data.datasets[0].data = moistures;
            this.charts.moisture.update('none');
            
            return data;
        } catch (error) {
            console.error('更新含水量图失败:', error);
        }
    }

    async updateHardness(segmentId, days = 30) {
        try {
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - days * 24 * 60 * 60 * 1000);
            
            const params = new URLSearchParams({
                segment_id: segmentId,
                start_time: startTime.toISOString(),
                end_time: endTime.toISOString(),
                aggregation: 'daily'
            });
            
            const response = await fetch(`/api/sensor-data/query?${params}`);
            const data = await response.json();
            
            const labels = data.map(d => {
                const date = new Date(d.timestamp);
                return `${date.getMonth() + 1}/${date.getDate()}`;
            });
            
            const hardness = data.map(d => d.surface_hardness);
            
            this.charts.hardness.data.labels = labels;
            this.charts.hardness.data.datasets[0].data = hardness;
            this.charts.hardness.update('none');
            
            return data;
        } catch (error) {
            console.error('更新硬度图失败:', error);
        }
    }

    async updateReinforcementChart(canvasId, plans) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        
        const labels = plans.map(p => p.plan_name);
        const costData = plans.map(p => p.estimated_cost);
        const effectivenessData = plans.map(p => p.effectiveness_score * 100);
        const durabilityData = plans.map(p => p.estimated_durability);
        
        if (this.charts.reinforcement) {
            this.charts.reinforcement.destroy();
        }
        
        this.charts.reinforcement = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '预估成本 (万元)',
                        data: costData,
                        backgroundColor: 'rgba(239, 68, 68, 0.7)',
                        borderRadius: 6
                    },
                    {
                        label: '加固效果 (%)',
                        data: effectivenessData,
                        backgroundColor: 'rgba(16, 185, 129, 0.7)',
                        borderRadius: 6,
                        yAxisID: 'y1'
                    },
                    {
                        label: '耐用年限 (年)',
                        data: durabilityData,
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderRadius: 6,
                        yAxisID: 'y2'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
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
                        bodyColor: '#e2e8f0'
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8',
                            maxRotation: 45,
                            minRotation: 45
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
                            text: '成本 (万元)',
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
                            text: '效果 (%)',
                            color: '#e2e8f0'
                        },
                        min: 0,
                        max: 100
                    },
                    y2: {
                        type: 'linear',
                        display: false,
                        position: 'right',
                        offset: true,
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    updateTOPSISChart(canvasId, evaluations) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        
        const labels = evaluations.map(e => e.plan_name);
        const closenessData = evaluations.map(e => e.closeness * 100);
        
        if (this.charts.topsis) {
            this.charts.topsis.destroy();
        }
        
        const colors = closenessData.map(v => {
            if (v > 70) return this.colors.success;
            if (v > 40) return this.colors.warning;
            return this.colors.danger;
        });
        
        this.charts.topsis = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'TOPSIS 综合评分',
                    data: closenessData,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
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
                        callbacks: {
                            label: function(context) {
                                return `评分: ${context.raw.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        title: {
                            display: true,
                            text: '综合评分',
                            color: '#e2e8f0'
                        },
                        min: 0,
                        max: 100
                    },
                    y: {
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#e2e8f0'
                        }
                    }
                }
            }
        });
    }

    updateRadarChart(canvasId, evaluations, bestPlanIndex) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        
        const bestPlan = evaluations[bestPlanIndex];
        
        if (this.charts.radar) {
            this.charts.radar.destroy();
        }
        
        this.charts.radar = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['加固效果', '渗透深度', '耐用年限', '成本效益', '施工难度', '环保性'],
                datasets: evaluations.map((plan, idx) => ({
                    label: plan.plan_name,
                    data: [
                        plan.effectiveness_score * 100,
                        (plan.penetration_depth / 30) * 100,
                        (plan.estimated_durability / 30) * 100,
                        (1 - plan.cost_score) * 100,
                        (1 - plan.construction_score) * 100,
                        (1 - plan.env_impact_score) * 100
                    ],
                    backgroundColor: idx === bestPlanIndex ? 'rgba(16, 185, 129, 0.2)' : `rgba(148, 163, 184, 0.1)`,
                    borderColor: idx === bestPlanIndex ? this.colors.success : this.colors.info,
                    borderWidth: idx === bestPlanIndex ? 3 : 1,
                    pointBackgroundColor: idx === bestPlanIndex ? this.colors.success : this.colors.info
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true
                        }
                    }
                },
                scales: {
                    r: {
                        angleLines: {
                            color: 'rgba(148, 163, 184, 0.2)'
                        },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.2)'
                        },
                        pointLabels: {
                            color: '#e2e8f0',
                            font: {
                                size: 12
                            }
                        },
                        ticks: {
                            color: '#94a3b8',
                            backdropColor: 'transparent'
                        },
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                }
            }
        });
    }

    destroyAll() {
        for (const key in this.charts) {
            if (this.charts[key]) {
                this.charts[key].destroy();
            }
        }
        this.charts = {};
    }
}
