var VirtualExperienceModule = (function () {
    var presets = null;
    var dynastyPresets = null;
    var currentResult = null;
    var materialDefaultMap = {};
    var materialColorMap = {
        'soil_pct': '#c49a6c',
        'clay_pct': '#8b5a3c',
        'sand_pct': '#e8d8a8',
        'lime_pct': '#d9d9d9',
        'rice_paste_pct': '#f5e6c8',
        'straw_pct': '#a67c52',
        'water_pct': '#6baed6'
    };
    var materialLabelMap = {
        'soil_pct': '黄土', 'clay_pct': '粘土', 'sand_pct': '细砂',
        'lime_pct': '石灰', 'rice_paste_pct': '糯米汁', 'straw_pct': '麦草', 'water_pct': '水'
    };

    function init() {
        loadPresets();
        bindEvents();
    }

    function loadPresets() {
        axios.get('/api/virtual/presets').then(function (res) {
            presets = res.data.base_materials || {};
            dynastyPresets = res.data.dynasty_presets || {};
            var nameToKey = {
                'soil': 'soil_pct', 'clay': 'clay_pct', 'sand': 'sand_pct',
                'lime': 'lime_pct', 'rice_paste': 'rice_paste_pct',
                'straw': 'straw_pct', 'water': 'water_pct'
            };
            for (var mname in presets) {
                if (presets.hasOwnProperty(mname) && nameToKey[mname]) {
                    materialDefaultMap[nameToKey[mname]] = presets[mname].default || 0;
                }
            }
            renderMaterialSliders();
            renderTampingOptions();
            renderDynastyPresetButtons();
            updateMixSummary();
            renderMixPieChart();
            updateLiveQualityBar();
        }).catch(function (err) {
            console.error('Failed to load presets:', err);
        });
    }

    function renderMaterialSliders() {
        var container = document.getElementById('material-sliders');
        if (!container || !presets) return;
        var html = '';
        var materialMap = {
            'soil': 'soil_pct', 'clay': 'clay_pct', 'sand': 'sand_pct',
            'lime': 'lime_pct', 'rice_paste': 'rice_paste_pct',
            'straw': 'straw_pct', 'water': 'water_pct'
        };
        for (var mname in materialMap) {
            if (!presets[mname]) continue;
            var m = presets[mname];
            var key = materialMap[mname];
            var defVal = m.default;
            var minVal = m.range[0];
            var maxVal = m.range[1];
            var color = materialColorMap[key] || '#888';
            html += '<div class="material-slider-row" data-key="' + key + '">' +
                '<div class="material-slider-label">' +
                '<span class="material-dot" style="background:' + color + '"></span>' +
                '<span class="material-name">' + m.name + '</span>' +
                '<span class="material-unit"><input type="number" class="material-number" data-key="' + key + '" value="' + defVal + '" min="' + minVal + '" max="' + maxVal + '" step="0.5"> ' + m.unit + '</span>' +
                '</div>' +
                '<div class="material-range-wrap">' +
                '<input type="range" class="material-range" data-key="' + key + '" value="' + defVal + '" min="' + minVal + '" max="' + maxVal + '" step="0.5">' +
                '<div class="material-optimal-tick" title="最优区间"></div>' +
                '</div>' +
                '<div class="material-range-info"><span>min ' + minVal + '</span><span>max ' + maxVal + '</span></div>' +
                '</div>';
        }
        container.innerHTML = html;
        document.querySelectorAll('.material-range, .material-number').forEach(function (el) {
            el.addEventListener('input', onMaterialChange);
        });
    }

    function renderTampingOptions() {
        var sel = document.getElementById('tamping-preset-select');
        var container = document.getElementById('tamping-desc');
        if (!sel || !container || !presets) return;
        var tamping = presets.tamping_presets || {};
        var html = '';
        for (var key in tamping) {
            if (tamping.hasOwnProperty(key)) {
                var selected = key === 'heavy' ? ' selected' : '';
                html += '<option value="' + key + '"' + selected + '>' + tamping[key].name + '</option>';
            }
        }
        sel.innerHTML = html;
        sel.addEventListener('change', function () {
            var key = sel.value;
            if (tamping[key]) {
                container.innerHTML = '能量: ' + tamping[key].energy_kj_m3 + ' kJ/m³ · 压实系数: ' + tamping[key].compaction_factor + ' · ' + tamping[key].description;
            }
            updateLiveQualityBar();
        });
        if (tamping['heavy']) {
            container.innerHTML = '能量: ' + tamping['heavy'].energy_kj_m3 + ' kJ/m³ · 压实系数: ' + tamping['heavy'].compaction_factor + ' · ' + tamping['heavy'].description;
        }
    }

    function renderDynastyPresetButtons() {
        var container = document.getElementById('dynasty-preset-buttons');
        var info = document.getElementById('dynasty-preset-info');
        if (!container || !dynastyPresets) return;
        var html = '';
        for (var code in dynastyPresets) {
            if (dynastyPresets.hasOwnProperty(code)) {
                var d = dynastyPresets[code];
                html += '<button class="dynasty-preset-btn" data-code="' + code + '">' +
                    '<span class="dp-name">' + d.name + '</span>' +
                    '<span class="dp-sub">' + (d.key_metrics ? '压实' + Math.round(d.key_metrics.compaction * 100) + '%' : '') + '</span>' +
                    '</button>';
            }
        }
        container.innerHTML = html;
        document.querySelectorAll('.dynasty-preset-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var code = btn.getAttribute('data-code');
                applyDynastyPreset(code);
                if (info && dynastyPresets[code]) {
                    var dp = dynastyPresets[code];
                    info.innerHTML = '<div class="dpi-title">📖 ' + dp.name + '</div>' +
                        '<div class="dpi-desc">' + dp.description + '</div>' +
                        (dp.archaeological_reference ? '<div class="dpi-ref">🏛️ ' + dp.archaeological_reference + '</div>' : '');
                }
            });
        });
    }

    function applyDynastyPreset(code) {
        if (!dynastyPresets || !dynastyPresets[code]) return;
        var mix = dynastyPresets[code].mix;
        var tamping = dynastyPresets[code].tamping;
        setMixValues(mix);
        var tampSel = document.getElementById('tamping-preset-select');
        if (tampSel) tampSel.value = tamping;
        tampSel.dispatchEvent(new Event('change'));
        updateMixSummary();
        renderMixPieChart();
        updateLiveQualityBar();
    }

    function setMixValues(mix) {
        for (var k in mix) {
            if (mix.hasOwnProperty(k)) {
                var slider = document.querySelector('.material-range[data-key="' + k + '"]');
                var number = document.querySelector('.material-number[data-key="' + k + '"]');
                if (slider) slider.value = mix[k];
                if (number) number.value = mix[k];
            }
        }
    }

    function getCurrentMix() {
        var mix = {};
        var keys = ['soil_pct', 'clay_pct', 'sand_pct', 'lime_pct', 'rice_paste_pct', 'straw_pct', 'water_pct'];
        keys.forEach(function (k) {
            var el = document.querySelector('.material-range[data-key="' + k + '"]');
            mix[k] = el ? parseFloat(el.value) : 0;
        });
        return mix;
    }

    function onMaterialChange(e) {
        var key = e.target.getAttribute('data-key');
        var val = parseFloat(e.target.value);
        if (isNaN(val)) return;
        var rangeEl = document.querySelector('.material-range[data-key="' + key + '"]');
        var numEl = document.querySelector('.material-number[data-key="' + key + '"]');
        if (rangeEl) rangeEl.value = val;
        if (numEl) numEl.value = val;
        updateMixSummary();
        renderMixPieChart();
        updateLiveQualityBar();
    }

    function updateMixSummary() {
        var mix = getCurrentMix();
        var solids = mix.soil_pct + mix.clay_pct + mix.sand_pct + mix.lime_pct + mix.rice_paste_pct + mix.straw_pct;
        var el = document.getElementById('mix-summary');
        if (!el) return;
        var ok = Math.abs(solids - 100) < 5;
        var water = mix.water_pct;
        var waterOk = 14 <= water && water <= 18;
        el.innerHTML =
            '<div class="mix-sum-row"><span class="ms-label">固体材料合计:</span>' +
            '<b style="color:' + (ok ? '#1a9850' : '#d73027') + '">' + solids.toFixed(1) + '%</b>' +
            (ok ? ' ✓ 合理' : ' ⚠ 建议接近100%') + '</div>' +
            '<div class="mix-sum-row"><span class="ms-label">含水量:</span>' +
            '<b style="color:' + (waterOk ? '#1a9850' : '#d73027') + '">' + water.toFixed(1) + '%</b>' +
            (waterOk ? ' ✓ 最优区间' : ' ⚠ 建议14-18%') + '</div>' +
            '<div class="mix-sum-row"><span class="ms-label">固体偏差:</span>' +
            '<b>' + (solids > 100 ? '+' : '') + (solids - 100).toFixed(1) + '%</b></div>';
    }

    function renderMixPieChart() {
        var canvas = document.getElementById('mix-pie-chart');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        var cx = w / 2;
        var cy = h / 2;
        var R = Math.min(cx, cy) - 10;
        ctx.clearRect(0, 0, w, h);
        var mix = getCurrentMix();
        var solids = [
            { key: 'soil_pct', val: mix.soil_pct },
            { key: 'clay_pct', val: mix.clay_pct },
            { key: 'sand_pct', val: mix.sand_pct },
            { key: 'lime_pct', val: mix.lime_pct },
            { key: 'rice_paste_pct', val: mix.rice_paste_pct },
            { key: 'straw_pct', val: mix.straw_pct }
        ];
        var total = 0;
        solids.forEach(function (s) { total += s.val; });
        if (total < 0.1) total = 1;
        var startAngle = -Math.PI / 2;
        solids.forEach(function (s) {
            if (s.val <= 0) return;
            var frac = s.val / total;
            var endAngle = startAngle + frac * 2 * Math.PI;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.arc(cx, cy, R, startAngle, endAngle);
            ctx.closePath();
            ctx.fillStyle = materialColorMap[s.key] || '#999';
            ctx.fill();
            if (frac > 0.05) {
                var midAngle = (startAngle + endAngle) / 2;
                var lx = cx + R * 0.65 * Math.cos(midAngle);
                var ly = cy + R * 0.65 * Math.sin(midAngle);
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 11px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText((frac * 100).toFixed(0) + '%', lx, ly);
            }
            startAngle = endAngle;
        });
        ctx.beginPath();
        ctx.arc(cx, cy, R * 0.45, 0, 2 * Math.PI);
        ctx.fillStyle = '#f7f5f0';
        ctx.fill();
        ctx.fillStyle = '#5a3e28';
        ctx.font = 'bold 13px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('固体配比', cx, cy - 6);
        ctx.font = '12px sans-serif';
        ctx.fillStyle = '#8b5a3c';
        ctx.fillText(total.toFixed(0) + '%', cx, cy + 12);
    }

    function updateLiveQualityBar() {
        var fill = document.getElementById('lq-bar-fill');
        var txt = document.getElementById('lq-bar-text');
        if (!fill || !txt) return;
        var mix = getCurrentMix();
        var score = estimateLiveQuality(mix);
        var pct = Math.max(0, Math.min(100, score * 100));
        var color = '#d73027';
        if (score >= 0.85) color = '#1a9850';
        else if (score >= 0.70) color = '#91cf60';
        else if (score >= 0.50) color = '#fdae61';
        else if (score >= 0.30) color = '#f46d43';
        fill.style.width = pct + '%';
        fill.style.background = color;
        var labels = { 0.85: '优', 0.70: '良', 0.50: '中', 0.30: '差' };
        var lbl = '劣';
        var thresholds = [0.85, 0.70, 0.50, 0.30];
        for (var i = 0; i < thresholds.length; i++) {
            if (score >= thresholds[i]) { lbl = labels[thresholds[i]]; break; }
        }
        txt.innerHTML = (score * 100).toFixed(0) + '分 · ' + lbl;
        txt.style.color = color;
    }

    function estimateLiveQuality(mix) {
        var solids = mix.soil_pct + mix.clay_pct + mix.sand_pct + mix.lime_pct + mix.rice_paste_pct + mix.straw_pct;
        var water = mix.water_pct;
        var solidsScore = Math.max(0, 1.0 - Math.abs(solids - 100) / 30.0);
        var waterScore = 0.5;
        if (14 <= water && water <= 18) waterScore = 1.0;
        else if (12 <= water && water <= 20) waterScore = 0.75;
        else if (10 <= water && water <= 22) waterScore = 0.55;
        var binderScore = Math.min(1.0, (mix.lime_pct * 0.8 + mix.rice_paste_pct * 1.2) / 10.0);
        var fiberScore = mix.straw_pct > 0.5 ? Math.min(1.0, mix.straw_pct / 5.0) * 0.4 : 0;
        var tampSel = document.getElementById('tamping-preset-select');
        var tampVal = tampSel ? tampSel.value : 'heavy';
        var tampScores = { light: 0.5, medium: 0.7, heavy: 0.88, extreme: 0.95 };
        var tampScore = tampScores[tampVal] || 0.75;
        var score = solidsScore * 0.25 + waterScore * 0.25 + binderScore * 0.2 + fiberScore * 0.1 + tampScore * 0.2;
        return Math.max(0.05, Math.min(0.98, score));
    }

    function bindEvents() {
        var btn = document.getElementById('run-evaluate');
        if (btn) btn.addEventListener('click', runEvaluate);
        var btnReset = document.getElementById('btn-reset-mix');
        if (btnReset) btnReset.addEventListener('click', actionResetMix);
        var btnNorm = document.getElementById('btn-normalize-mix');
        if (btnNorm) btnNorm.addEventListener('click', actionNormalizeMix);
        var btnQin = document.getElementById('btn-recommend-qin');
        if (btnQin) btnQin.addEventListener('click', function () { applyDynastyPreset('QIN'); });
        var btnBal = document.getElementById('btn-recommend-balanced');
        if (btnBal) btnBal.addEventListener('click', actionRecommendBalanced);
        document.querySelectorAll('#virtual-wall-height, #virtual-wind-speed').forEach(function (el) {
            if (el) el.addEventListener('input', updateLiveQualityBar);
        });
    }

    function actionResetMix() {
        setMixValues(materialDefaultMap);
        updateMixSummary();
        renderMixPieChart();
        updateLiveQualityBar();
    }

    function actionNormalizeMix() {
        var mix = getCurrentMix();
        var solids = ['soil_pct', 'clay_pct', 'sand_pct', 'lime_pct', 'rice_paste_pct', 'straw_pct'];
        var total = 0;
        solids.forEach(function (k) { total += mix[k]; });
        if (total < 0.1) { alert('固体材料总量为0，无法归一化'); return; }
        var factor = 100.0 / total;
        var presetsData = presets || {};
        var nameToKey = { 'soil': 'soil_pct', 'clay': 'clay_pct', 'sand': 'sand_pct', 'lime': 'lime_pct', 'rice_paste': 'rice_paste_pct', 'straw': 'straw_pct', 'water': 'water_pct' };
        solids.forEach(function (k) {
            var newVal = mix[k] * factor;
            var rawName = null;
            for (var nm in nameToKey) {
                if (nameToKey[nm] === k) { rawName = nm; break; }
            }
            if (rawName && presetsData[rawName] && presetsData[rawName].range) {
                var r = presetsData[rawName].range;
                newVal = Math.max(r[0], Math.min(r[1], newVal));
            }
            mix[k] = Math.round(newVal * 10) / 10;
        });
        setMixValues(mix);
        updateMixSummary();
        renderMixPieChart();
        updateLiveQualityBar();
    }

    function actionRecommendBalanced() {
        var mix = {
            soil_pct: 62, clay_pct: 18, sand_pct: 10,
            lime_pct: 5, rice_paste_pct: 2, straw_pct: 3, water_pct: 16
        };
        setMixValues(mix);
        var tampSel = document.getElementById('tamping-preset-select');
        if (tampSel) { tampSel.value = 'heavy'; tampSel.dispatchEvent(new Event('change')); }
        updateMixSummary();
        renderMixPieChart();
        updateLiveQualityBar();
    }

    function runEvaluate() {
        var mix = getCurrentMix();
        var tamping = document.getElementById('tamping-preset-select').value || 'heavy';
        var wallHeight = parseFloat(document.getElementById('virtual-wall-height').value) || 2.5;
        var windSpeed = parseFloat(document.getElementById('virtual-wind-speed').value) || 8;
        var payload = {
            mix: mix,
            tamping_preset: tamping,
            wall_height_m: wallHeight,
            wind_speed: windSpeed
        };
        var btn = document.getElementById('run-evaluate');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 评估中...'; }
        axios.post('/api/virtual/evaluate', payload).then(function (res) {
            currentResult = res.data;
            renderEvaluationResult(res.data);
            renderWallPreview(res.data);
        }).catch(function (err) {
            console.error('Evaluate failed:', err);
            alert('评估失败：' + (err.response ? err.response.data.detail : err.message));
        }).finally(function () {
            if (btn) { btn.disabled = false; btn.textContent = '🏗️ 开始夯筑评估'; }
        });
    }

    function renderEvaluationResult(data) {
        var box = document.getElementById('evaluation-result');
        if (!box) return;
        var scoreColor = data.quality_color || '#888';
        var dynastyNames = { 'QIN': '秦代版筑夯土', 'HAN': '汉代草拌夯土', 'MING': '明代三合土' };
        var matchName = dynastyNames[data.dynasty_match] || data.dynasty_match;
        var suggestionsHtml = '';
        data.suggestions.forEach(function (s) {
            suggestionsHtml += '<li>' + s + '</li>';
        });
        box.innerHTML =
            '<div class="quality-display">' +
            '<div class="quality-circle" style="background: conic-gradient(' + scoreColor + ' 0% ' + (data.quality_score * 100) + '%, #e0e0e0 ' + (data.quality_score * 100) + '% 100%)">' +
            '<div class="quality-inner">' +
            '<div class="quality-score">' + (data.quality_score * 100).toFixed(0) + '</div>' +
            '<div class="quality-rating" style="color:' + scoreColor + '">' + data.quality_rating + '</div>' +
            '</div></div>' +
            '<div class="quality-details">' +
            '<h3>评估结果</h3>' +
            '<div class="detail-row"><span>压实度</span><b>' + (data.compaction_ratio * 100).toFixed(1) + '%</b></div>' +
            '<div class="detail-row"><span>侵蚀率</span><b>' + data.erosion_rate_mm_per_year.toFixed(3) + ' mm/年</b></div>' +
            '<div class="detail-row"><span>硬度</span><b>' + data.hardness_mpa.toFixed(2) + ' MPa</b></div>' +
            '<div class="detail-row"><span>粘结力</span><b>' + data.cohesion_kpa.toFixed(1) + ' kPa</b></div>' +
            '<div class="detail-row"><span>抗裂性</span><b>' + data.crack_resistance.toFixed(2) + '</b></div>' +
            '<div class="detail-row"><span>抗水性</span><b>' + data.moisture_resistance.toFixed(2) + '</b></div>' +
            '<div class="dynasty-match">🎯 匹配工艺: <b>' + matchName + '</b> (相似度 ' + (data.dynasty_match_score * 100).toFixed(0) + '%)</div>' +
            '</div></div>' +
            '<div class="suggestions-box"><h4>💡 改进建议</h4><ul>' + suggestionsHtml + '</ul></div>';
    }

    function renderWallPreview(data) {
        var canvas = document.getElementById('virtual-wall-canvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        var wallX = w * 0.25;
        var wallW = w * 0.5;
        var wallTopY = h * 0.2;
        var wallBottomY = h * 0.9;
        var grad = ctx.createLinearGradient(wallX, wallTopY, wallX + wallW, wallBottomY);
        var baseR = 196 + (data.hardness_mpa / 5.0) * 30;
        var baseG = 154 - (data.erosion_rate_mm_per_year / 200) * 30;
        var baseB = 108 + (data.compaction_ratio) * 20;
        baseG = Math.max(80, Math.min(200, baseG));
        grad.addColorStop(0, 'rgb(' + baseR + ',' + baseG + ',' + baseB + ')');
        grad.addColorStop(1, 'rgb(' + (baseR - 30) + ',' + (baseG - 20) + ',' + (baseB - 10) + ')');
        ctx.fillStyle = grad;
        ctx.fillRect(wallX, wallTopY, wallW, wallBottomY - wallTopY);
        var layerCount = 12;
        var layerH = (wallBottomY - wallTopY) / layerCount;
        ctx.strokeStyle = 'rgba(60,40,20,0.35)';
        ctx.lineWidth = 1;
        for (var i = 0; i < layerCount; i++) {
            var ly = wallTopY + i * layerH;
            ctx.beginPath();
            ctx.moveTo(wallX, ly);
            ctx.lineTo(wallX + wallW, ly);
            ctx.stroke();
        }
        var erosionPct = Math.min(0.8, data.erosion_rate_mm_per_year / 600);
        ctx.fillStyle = 'rgba(139,69,19,' + (0.1 + erosionPct * 0.3) + ')';
        for (var ei = 0; ei < 50; ei++) {
            var ex = wallX + Math.random() * wallW;
            var ey = wallTopY + Math.random() * (wallBottomY - wallTopY) * 0.3;
            var ew = 5 + Math.random() * 20 * erosionPct;
            var eh = 2 + Math.random() * 8 * erosionPct;
            ctx.fillRect(ex, ey, ew, eh);
        }
        ctx.fillStyle = data.quality_color;
        ctx.font = 'bold 20px sans-serif';
        ctx.fillText(data.quality_rating + ' · ' + (data.quality_score * 100).toFixed(0) + '分', wallX + 10, wallTopY - 10);
        var dynastyLabels = { 'QIN': '秦代工艺', 'HAN': '汉代工艺', 'MING': '明代工艺' };
        ctx.fillStyle = '#5a3e28';
        ctx.font = '12px sans-serif';
        ctx.fillText('匹配: ' + (dynastyLabels[data.dynasty_match] || data.dynasty_match), wallX + wallW - 120, wallTopY - 10);
    }

    return {
        init: init,
        runEvaluate: runEvaluate,
        loadPresets: loadPresets,
        applyDynastyPreset: applyDynastyPreset,
        actionResetMix: actionResetMix,
        actionNormalizeMix: actionNormalizeMix,
        actionRecommendBalanced: actionRecommendBalanced
    };
})();
