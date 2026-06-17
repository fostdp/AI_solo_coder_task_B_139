var EraComparatorModule = (function () {
    var currentCrossEraResult = null;

    function init() {
        bindEvents();
    }

    function bindEvents() {
        var btn = document.getElementById('run-cross-era-compare');
        if (btn) {
            btn.addEventListener('click', runCrossEraComparison);
        }
    }

    function getSelectedDynasties() {
        var checks = document.querySelectorAll('.dynasty-check:checked');
        var codes = [];
        checks.forEach(function (c) {
            codes.push(c.value);
        });
        return codes;
    }

    function runCrossEraComparison() {
        var windSpeedEl = document.getElementById('crossera-wind-speed');
        var moistureEl = document.getElementById('crossera-moisture');
        var windSpeed = windSpeedEl ? parseFloat(windSpeedEl.value) || 8 : parseFloat(document.getElementById('dynasty-wind-speed').value) || 8;
        var moisture = moistureEl ? parseFloat(moistureEl.value) || 5 : parseFloat(document.getElementById('dynasty-moisture').value) || 5;
        var payload = {
            include_dynasties: getSelectedDynasties(),
            include_modern: ["GEOSYNTHETIC", "FIBER", "CEMENT"],
            wind_speed: windSpeed,
            soil_moisture: moisture
        };
        axios.post('/api/cross-era/compare', payload).then(function (res) {
            currentCrossEraResult = res.data;
            renderCrossEraTable(res.data);
            renderCrossEraRadar(res.data);
        }).catch(function (err) {
            console.error('Cross-era comparison failed:', err);
            alert('跨时代对比失败：' + (err.response ? err.response.data.detail : err.message));
        });
    }

    function renderCrossEraTable(data) {
        var tbody = document.getElementById('cross-era-tbody');
        if (!tbody) return;
        var html = '';
        data.items.forEach(function (it, i) {
            var eraBadge = it.era === 'ancient'
                ? '<span class="badge badge-archaic">古代</span>'
                : '<span class="badge badge-modern">现代</span>';
            html += '<tr>' +
                '<td><b>' + (i + 1) + '</b></td>' +
                '<td>' + it.name + ' ' + eraBadge + '</td>' +
                '<td>' + it.erosion_rate_mm_per_year.toFixed(3) + ' mm/年</td>' +
                '<td>' + it.hardness_mpa.toFixed(2) + ' MPa</td>' +
                '<td>' + it.cohesion_kpa.toFixed(1) + ' kPa</td>' +
                '<td>' + (it.environmental_impact * 100).toFixed(0) + '%</td>' +
                '<td>' + (it.reversibility * 100).toFixed(0) + '%</td>' +
                '<td>' + (it.cultural_authenticity * 100).toFixed(0) + '%</td>' +
                '<td><b>' + ((it.topsis_score || 0) * 100).toFixed(1) + '分</b></td>' +
                '</tr>';
        });
        tbody.innerHTML = html;
    }

    function renderCrossEraRadar(data) {
        var canvas = document.getElementById('cross-era-radar');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        if (window._crossEraRadar) {
            window._crossEraRadar.destroy();
        }
        var labels = ['抗侵蚀性(%)', '硬度(%)', '粘结力(%)', '环保性(%)', '可逆性(%)', '文化真实性(%)'];
        var datasets = [];
        var colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#a65628'];
        data.items.forEach(function (it, i) {
            var color = colors[i % colors.length];
            datasets.push({
                label: it.name,
                data: [
                    Math.max(0, Math.min(100, (1 - it.erosion_rate_mm_per_year / 2.0) * 100)),
                    Math.min(100, it.hardness_mpa / 5.0 * 100),
                    Math.min(100, it.cohesion_kpa / 200.0 * 100),
                    (1 - it.environmental_impact) * 100,
                    it.reversibility * 100,
                    it.cultural_authenticity * 100
                ],
                backgroundColor: color + '33',
                borderColor: color,
                borderWidth: 2,
                pointBackgroundColor: color
            });
        });
        window._crossEraRadar = new Chart(ctx, {
            type: 'radar',
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                title: { display: true, text: '跨时代工程对比雷达图' },
                scales: { r: { min: 0, max: 100, beginAtZero: true } }
            }
        });
    }

    return {
        init: init,
        runCrossEraComparison: runCrossEraComparison
    };
})();
