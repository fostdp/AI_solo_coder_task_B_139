var PlantRootModule = (function () {
    var plantList = [];
    var currentResult = null;

    function init() {
        loadPlantList();
        bindEvents();
    }

    function loadPlantList() {
        axios.get('/api/plants/species').then(function (res) {
            plantList = res.data.plants || [];
            renderPlantCheckboxes();
        }).catch(function (err) {
            console.error('Failed to load plant species:', err);
        });
    }

    function renderPlantCheckboxes() {
        var container = document.getElementById('plant-select-container');
        if (!container) return;
        var html = '';
        var categoryLabel = { 'herb': '草本', 'shrub': '灌木', 'tree': '乔木' };
        plantList.forEach(function (p) {
            html += '<label class="plant-checkbox">' +
                '<input type="checkbox" class="plant-check" value="' + p.code + '"' +
                (p.code === 'GRASS_DEEP' || p.code === 'SHRUB' ? ' checked' : '') + '>' +
                '<span class="plant-icon">' + (p.category === 'tree' ? '🌳' : p.category === 'shrub' ? '🌿' : '🌱') + '</span>' +
                '<span class="plant-info">' +
                '<span class="plant-name">' + p.name + ' (' + p.name_zh + ')</span>' +
                '<span class="plant-detail">根深' + (p.root_depth_mm / 1000).toFixed(1) + 'm · ' + categoryLabel[p.category] + '</span>' +
                '</span></label>';
        });
        container.innerHTML = html;
    }

    function bindEvents() {
        var btn = document.getElementById('run-plant-sim');
        if (btn) btn.addEventListener('click', runSimulation);
    }

    function getSelectedPlants() {
        var checks = document.querySelectorAll('.plant-check:checked');
        var codes = [];
        checks.forEach(function (c) { codes.push(c.value); });
        return codes;
    }

    function runSimulation() {
        var codes = getSelectedPlants();
        if (codes.length < 1) {
            alert('请至少选择一种植物');
            return;
        }
        var coverage = parseFloat(document.getElementById('plant-coverage').value) || 70;
        var wallHeight = parseFloat(document.getElementById('plant-wall-height').value) || 2.5;
        var windSpeed = parseFloat(document.getElementById('plant-wind-speed').value) || 8;
        var moisture = parseFloat(document.getElementById('plant-moisture').value) || 5;
        var season = document.getElementById('plant-season').value || 'summer';
        var payload = {
            plant_codes: codes,
            coverage_pct: coverage,
            wall_height_m: wallHeight,
            wind_speed: windSpeed,
            soil_moisture: moisture,
            season: season
        };
        axios.post('/api/plants/simulate', payload).then(function (res) {
            currentResult = res.data;
            renderSummary(res.data);
            renderEffectsTable(res.data);
            renderProtectionChart(res.data);
            renderRootVisualization(res.data);
        }).catch(function (err) {
            console.error('Plant simulation failed:', err);
            alert('仿真失败：' + (err.response ? err.response.data.detail : err.message));
        });
    }

    function renderSummary(data) {
        var el = document.getElementById('plant-summary');
        if (!el) return;
        var pct = data.total_reduction_pct;
        var color = pct >= 40 ? '#1a9850' : pct >= 20 ? '#fdae61' : '#d73027';
        el.innerHTML =
            '<div class="summary-cards">' +
            '<div class="summary-card"><div class="card-value">' + data.baseline_erosion_rate.toFixed(3) + '</div>' +
            '<div class="card-label">无植被侵蚀率(mm/年)</div></div>' +
            '<div class="summary-card"><div class="card-value" style="color:#1a9850">' + data.protected_erosion_rate.toFixed(3) + '</div>' +
            '<div class="card-label">有植被侵蚀率(mm/年)</div></div>' +
            '<div class="summary-card"><div class="card-value" style="color:' + color + '">' + pct.toFixed(1) + '%</div>' +
            '<div class="card-label">总侵蚀降低率</div></div>' +
            (data.combined_bonus_pct > 0 ?
                '<div class="summary-card badge-card"><div class="card-value" style="color:#984ea3">+' + data.combined_bonus_pct + '%</div>' +
                '<div class="card-label">组合防护加成</div></div>' : '') +
            '</div>';
    }

    function renderEffectsTable(data) {
        var tbody = document.getElementById('plant-effects-tbody');
        if (!tbody) return;
        var html = '';
        data.individual_effects.forEach(function (e) {
            html += '<tr>' +
                '<td>' + e.name + '</td>' +
                '<td>' + e.soil_cohesion_increase_kpa.toFixed(2) + ' kPa</td>' +
                '<td>' + e.wind_speed_reduction_pct.toFixed(1) + '%</td>' +
                '<td style="color:#1a9850"><b>' + e.erosion_rate_reduction_pct.toFixed(1) + '%</b></td>' +
                '<td>' + e.moisture_retention_pct.toFixed(1) + '%</td>' +
                '<td>' + e.surface_binding.toFixed(2) + '</td>' +
                '</tr>';
        });
        tbody.innerHTML = html;
    }

    function renderProtectionChart(data) {
        var canvas = document.getElementById('plant-protection-chart');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        if (window._plantChart) window._plantChart.destroy();
        var labels = data.individual_effects.map(function (e) { return e.name; });
        var erode = data.individual_effects.map(function (e) { return e.erosion_rate_reduction_pct; });
        var wind = data.individual_effects.map(function (e) { return e.wind_speed_reduction_pct; });
        var coh = data.individual_effects.map(function (e) { return e.soil_cohesion_increase_kpa * 10; });
        window._plantChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: '侵蚀降低(%)', data: erode, backgroundColor: 'rgba(26,152,80,0.7)' },
                    { label: '风速降低(%)', data: wind, backgroundColor: 'rgba(69,117,180,0.7)' },
                    { label: '粘聚力提升(×10, kPa)', data: coh, backgroundColor: 'rgba(152,78,163,0.7)' }
                ]
            },
            options: {
                responsive: true,
                title: { display: true, text: '各植物防护效果对比' },
                scales: { y: { beginAtZero: true, title: { display: true, text: '百分比 / kPa×10' } } }
            }
        });
    }

    function renderRootVisualization(data) {
        var canvas = document.getElementById('plant-root-canvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        var wallX = w * 0.55;
        var wallW = w * 0.35;
        var groundY = h * 0.7;
        var wallTopY = groundY - (h * 0.45);
        var grad = ctx.createLinearGradient(wallX, wallTopY, wallX + wallW, groundY);
        grad.addColorStop(0, '#c49a6c');
        grad.addColorStop(0.5, '#a67c52');
        grad.addColorStop(1, '#8b5e3c');
        ctx.fillStyle = grad;
        ctx.fillRect(wallX, wallTopY, wallW, h - wallTopY);
        ctx.strokeStyle = 'rgba(92,64,51,0.4)';
        ctx.lineWidth = 1;
        for (var y = wallTopY + 12; y < groundY; y += 15) {
            ctx.beginPath();
            ctx.moveTo(wallX, y);
            ctx.lineTo(wallX + wallW, y);
            ctx.stroke();
        }
        ctx.fillStyle = '#8b7355';
        ctx.fillRect(0, groundY, w, h - groundY);
        ctx.strokeStyle = 'rgba(60,40,20,0.2)';
        for (var gx = 0; gx < w; gx += 20) {
            ctx.beginPath();
            ctx.moveTo(gx, groundY);
            ctx.lineTo(gx + 3, groundY + 20);
            ctx.stroke();
        }
        var plantColors = { GRASS_SHORT: '#7cbd3e', GRASS_DEEP: '#4a8b2b', SHRUB: '#2d6a2f', TREE: '#1b4d1c' };
        var startX = w * 0.15;
        data.individual_effects.forEach(function (eff, idx) {
            var code = eff.plant_code;
            var plant = plantList.find(function (p) { return p.code === code; });
            if (!plant) return;
            var cx = startX + idx * (w * 0.12);
            var maxDepth = plant.root_depth_mm || 150;
            var rootPixelDepth = Math.min(h - groundY - 20, maxDepth / 5);
            ctx.fillStyle = plantColors[code] || '#2d6a2f';
            if (plant.category === 'tree') {
                ctx.fillStyle = '#6b4423';
                ctx.fillRect(cx - 3, groundY - 30, 6, 30);
                ctx.fillStyle = plantColors[code];
                ctx.beginPath();
                ctx.arc(cx, groundY - 45, 25, 0, Math.PI * 2);
                ctx.fill();
            } else if (plant.category === 'shrub') {
                ctx.beginPath();
                ctx.arc(cx, groundY - 15, 18, 0, Math.PI * 2);
                ctx.fill();
            } else {
                for (var b = -2; b <= 2; b++) {
                    ctx.fillRect(cx + b * 3 - 1, groundY - 20 - Math.abs(b) * 3, 2, 20 + Math.abs(b) * 3);
                }
            }
            ctx.strokeStyle = plantColors[code];
            ctx.lineWidth = 1.5;
            var rootCount = Math.min(plant.root_density_roots_per_dm2 / 10, 15);
            for (var r = 0; r < rootCount; r++) {
                var ang = (-Math.PI / 2) + (Math.random() - 0.5) * Math.PI * 0.8;
                var len = rootPixelDepth * (0.5 + Math.random() * 0.5);
                var ex = cx + Math.cos(ang) * len * 0.4;
                var ey = groundY + Math.abs(Math.sin(ang)) * len;
                ctx.beginPath();
                ctx.moveTo(cx, groundY);
                ctx.quadraticCurveTo(cx + (ex - cx) * 0.5 + (Math.random() - 0.5) * 15,
                    groundY + (ey - groundY) * 0.5,
                    ex, ey);
                ctx.stroke();
            }
        });
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.font = '12px sans-serif';
        ctx.fillText('风 →', 10, 20);
        ctx.fillStyle = '#1a9850';
        ctx.fillText('侵蚀率降低: ' + data.total_reduction_pct.toFixed(1) + '%', 10, 40);
    }

    return {
        init: init,
        runSimulation: runSimulation,
        loadPlantList: loadPlantList
    };
})();
