var CraftComparatorModule = (function () {
    var dynastyList = [];
    var climateScenarios = {};
    var currentComparisonResult = null;

    function init() {
        loadDynastyList();
        bindEvents();
    }

    function loadDynastyList() {
        axios.get('/api/dynasty/list').then(function (res) {
            dynastyList = res.data.dynasties || [];
            climateScenarios = res.data.climate_scenarios || {};
            renderDynastyOptions();
            renderClimateOptions();
        }).catch(function (err) {
            console.error('Failed to load dynasty list:', err);
        });
    }

    function renderDynastyOptions() {
        var container = document.getElementById('dynasty-select-container');
        if (!container) return;
        var html = '';
        dynastyList.forEach(function (d) {
            html += '<label class="dynasty-checkbox">' +
                '<input type="checkbox" class="dynasty-check" value="' + d.code + '" checked>' +
                '<span class="dynasty-name">' + d.name + '</span>' +
                '<span class="dynasty-period">(' + d.period + ')</span>' +
                '</label>';
        });
        container.innerHTML = html;
    }

    function renderClimateOptions() {
        var sel = document.getElementById('climate-scenario-select');
        if (!sel) return;
        var html = '<option value="">默认气候</option>';
        for (var key in climateScenarios) {
            if (climateScenarios.hasOwnProperty(key)) {
                html += '<option value="' + key + '">' + climateScenarios[key].description + '</option>';
            }
        }
        sel.innerHTML = html;
    }

    function bindEvents() {
        var btn = document.getElementById('run-dynasty-compare');
        if (btn) {
            btn.addEventListener('click', runComparison);
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

    function runComparison() {
        var codes = getSelectedDynasties();
        if (codes.length < 1) {
            alert('请至少选择一个朝代');
            return;
        }
        var windSpeed = parseFloat(document.getElementById('dynasty-wind-speed').value) || 8;
        var moisture = parseFloat(document.getElementById('dynasty-moisture').value) || 5;
        var duration = parseFloat(document.getElementById('dynasty-duration').value) || 24;
        var climate = document.getElementById('climate-scenario-select').value || null;
        var payload = {
            dynasty_codes: codes,
            wind_speed: windSpeed,
            soil_moisture: moisture,
            duration_hours: duration,
            climate_scenario: climate
        };
        axios.post('/api/dynasty/compare', payload).then(function (res) {
            currentComparisonResult = res.data;
            renderComparisonTable(res.data);
            renderComparisonChart(res.data);
        }).catch(function (err) {
            console.error('Comparison failed:', err);
            alert('对比失败：' + (err.response ? err.response.data.detail : err.message));
        });
    }

    function renderComparisonTable(data) {
        var tbody = document.getElementById('dynasty-compare-tbody');
        if (!tbody) return;
        var html = '';
        data.results.forEach(function (r) {
            html += '<tr>' +
                '<td><b>' + r.rank + '</b></td>' +
                '<td>' + r.name + '</td>' +
                '<td>' + r.erosion_rate_mm_per_year.toFixed(3) + ' mm/年</td>' +
                '<td>' + r.max_erosion_depth_mm.toFixed(3) + ' mm</td>' +
                '<td>' + r.hardness_mpa.toFixed(2) + ' MPa</td>' +
                '<td>' + r.cohesion_kpa.toFixed(1) + ' kPa</td>' +
                '<td>' + r.moisture_resistance.toFixed(2) + '</td>' +
                '<td><b>' + (r.overall_score * 100).toFixed(1) + '分</b></td>' +
                '</tr>';
        });
        tbody.innerHTML = html;
    }

    function renderComparisonChart(data) {
        var canvas = document.getElementById('dynasty-compare-chart');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        if (window._dynastyChart) {
            window._dynastyChart.destroy();
        }
        var labels = data.results.map(function (r) { return r.name; });
        var erosion = data.results.map(function (r) { return r.erosion_rate_mm_per_year; });
        var hardness = data.results.map(function (r) { return r.hardness_mpa; });
        var score = data.results.map(function (r) { return (r.overall_score * 100).toFixed(1); });
        window._dynastyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: '侵蚀率(mm/年)', data: erosion, backgroundColor: 'rgba(214,69,65,0.7)', yAxisID: 'y' },
                    { label: '硬度(MPa)', data: hardness, backgroundColor: 'rgba(69,117,180,0.7)', yAxisID: 'y1' },
                    { label: '综合评分(×10)', data: score.map(function (s) { return parseFloat(s) / 10; }), backgroundColor: 'rgba(116,173,209,0.7)', yAxisID: 'y' }
                ]
            },
            options: {
                responsive: true,
                title: { display: true, text: '朝代夯土抗风蚀性能对比' },
                scales: {
                    y: { type: 'linear', position: 'left', title: { display: true, text: '侵蚀率/评分' } },
                    y1: { type: 'linear', position: 'right', title: { display: true, text: '硬度(MPa)' }, grid: { drawOnChartArea: false } }
                }
            }
        });
    }

    return {
        init: init,
        loadDynastyList: loadDynastyList,
        runComparison: runComparison
    };
})();

var DynastyCompareModule = CraftComparatorModule;
