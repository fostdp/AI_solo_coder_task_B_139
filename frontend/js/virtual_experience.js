var VirtualExperienceModule = (function () {
    var presets = null;
    var dynastyPresets = null;
    var currentResult = null;

    function init() {
        loadPresets();
        bindEvents();
    }

    function loadPresets() {
        axios.get('/api/virtual/presets').then(function (res) {
            presets = res.data.base_materials || {};
            dynastyPresets = res.data.dynasty_presets || {};
            renderMaterialSliders();
            renderTampingOptions();
            renderDynastyPresetButtons();
            updateMixSummary();
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
            html += '<div class="material-slider-row" data-key="' + key + '">' +
                '<div class="material-slider-label">' +
                '<span class="material-name">' + m.name + '</span>' +
                '<span class="material-unit"><input type="number" class="material-number" data-key="' + key + '" value="' + defVal + '" min="' + minVal + '" max="' + maxVal + '" step="0.5"> ' + m.unit + '</span>' +
                '</div>' +
                '<input type="range" class="material-range" data-key="' + key + '" value="' + defVal + '" min="' + minVal + '" max="' + maxVal + '" step="0.5">' +
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
        });
        if (tamping['heavy']) {
            container.innerHTML = '能量: ' + tamping['heavy'].energy_kj_m3 + ' kJ/m³ · 压实系数: ' + tamping['heavy'].compaction_factor + ' · ' + tamping['heavy'].description;
        }
    }

    function renderDynastyPresetButtons() {
        var container = document.getElementById('dynasty-preset-buttons');
        if (!container || !dynastyPresets) return;
        var html = '';
        for (var code in dynastyPresets) {
            if (dynastyPresets.hasOwnProperty(code)) {
                var d = dynastyPresets[code];
                html += '<button class="dynasty-preset-btn" data-code="' + code + '">' + d.name + '</button>';
            }
        }
        container.innerHTML = html;
        document.querySelectorAll('.dynasty-preset-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                applyDynastyPreset(btn.getAttribute('data-code'));
            });
        });
    }

    function applyDynastyPreset(code) {
        if (!dynastyPresets || !dynastyPresets[code]) return;
        var mix = dynastyPresets[code].mix;
        var tamping = dynastyPresets[code].tamping;
        for (var k in mix) {
            if (mix.hasOwnProperty(k)) {
                var slider = document.querySelector('.material-range[data-key="' + k + '"]');
                var number = document.querySelector('.material-number[data-key="' + k + '"]');
                if (slider) slider.value = mix[k];
                if (number) number.value = mix[k];
            }
        }
        var tampSel = document.getElementById('tamping-preset-select');
        if (tampSel) tampSel.value = tamping;
        tampSel.dispatchEvent(new Event('change'));
        updateMixSummary();
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
        var slider = document.querySelector('.material-range[data-key="' + key + '"]');
        var number = document.querySelector('.material-number[data-key="' + key + '"]');
        if (slider) slider.value = val;
        if (number) number.value = val;
        updateMixSummary();
    }

    function updateMixSummary() {
        var mix = getCurrentMix();
        var solids = mix.soil_pct + mix.clay_pct + mix.sand_pct + mix.lime_pct + mix.rice_paste_pct + mix.straw_pct;
        var el = document.getElementById('mix-summary');
        if (!el) return;
        var ok = Math.abs(solids - 100) < 5;
        el.innerHTML =
            '<div>固体材料合计: <b style="color:' + (ok ? '#1a9850' : '#d73027') + '">' + solids.toFixed(1) + '%</b>' +
            (ok ? ' ✓' : ' (建议接近100%)') + '</div>' +
            '<div>含水量: ' + mix.water_pct.toFixed(1) + '%</div>';
    }

    function bindEvents() {
        var btn = document.getElementById('run-evaluate');
        if (btn) btn.addEventListener('click', runEvaluate);
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
        axios.post('/api/virtual/evaluate', payload).then(function (res) {
            currentResult = res.data;
            renderEvaluationResult(res.data);
            renderWallPreview(res.data);
        }).catch(function (err) {
            console.error('Evaluate failed:', err);
            alert('评估失败：' + (err.response ? err.response.data.detail : err.message));
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
        var baseG = 154 - (data.erosion_rate_mm_per_year) * 20;
        var baseB = 108 + (data.compaction_ratio) * 20;
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
        var erosionPct = Math.min(0.8, data.erosion_rate_mm_per_year / 2.0);
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
        applyDynastyPreset: applyDynastyPreset
    };
})();
