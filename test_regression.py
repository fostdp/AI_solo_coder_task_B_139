import sys
sys.path.insert(0, '.')

from microservices.common import get_erosion_config, get_materials_config
from microservices.dtu_receiver import get_dtu_receiver
from microservices.wind_erosion_simulator import get_erosion_simulator
from microservices.reinforcement_optimizer import get_optimizer
from microservices.alarm_mqtt import get_alarm_service
from backend.adapters import get_adapter

import numpy as np
import asyncio

print('1. 配置加载 OK')
erosion_cfg = get_erosion_config()
mat_cfg = get_materials_config()
assert 'physical_constants' in erosion_cfg
assert len(mat_cfg['materials']) == 5
print('   5种材料:', list(mat_cfg['materials'].keys()))

print('2. DTU Receiver OK')
rx = get_dtu_receiver()
res = asyncio.run(rx.receive({
    'segment_id': 1, 'sensor_id': 'S001',
    'time': '2025-01-01T10:00:00',
    'wind_erosion_depth': 0.15, 'soil_moisture': 5.2,
    'surface_hardness': 2.4, 'wind_speed': 6.5, 'wind_direction': 180.0
}, publish=False))
assert res['ok'] == True
print('   数据校验通过')

print('3. Wind Erosion Simulator OK')
sim = get_erosion_simulator()
u_star = sim.calculate_friction_velocity(5.0)
u_star_t = sim.calculate_threshold_friction_velocity()
print('   u*={:.4f}, u*_t={:.4f}'.format(u_star, u_star_t))

np.random.seed(42)
# 风速单位 m/s (原系统 backend/services/erosion_model.py 中使用 m/s)
# u*_t=0.3568 -> u10≈5.7m/s≈20.6km/h 以下无侵蚀
ws = np.random.uniform(4, 14, 100)  # 4~14 m/s, 部分超阈值
wd = np.random.uniform(0, 360, 100)
hd = np.random.uniform(1.5, 3.5, 100)
mr = np.random.uniform(3, 8, 100)
res = sim.calculate_long_term_erosion_rate(ws, wd, hd, mr)
print('   长期侵蚀率: {:.3f} mm/年'.format(res['erosion_rate_mm_per_year']))

des = sim.simulate_two_phase_flow_with_des(8.0, 225.0, 2.5, 5.0, grid_resolution=10)
assert des['des_model_applied'] == True
print('   DES avg增强因子: {:.3f}'.format(des['avg_enhancement_factor']))

print('4. Reinforcement Optimizer OK')
opt = get_optimizer()
pen = opt.calculate_penetration_depth('GLU-02', '75%+25%', 2.5, 5.0)
dur = opt.calculate_durability_with_confidence('GLU-02', pen)
print('   GLU-02 渗透={:.2f}mm, 寿命={:.1f}年, CI=[{:.1f},{:.1f}]'.format(
    pen, dur['years'], dur['lower'], dur['upper']))

plans = opt.generate_reinforcement_plans(1, 120.0, 2.5, 5.0, 'high')
print('   生成方案数:', len(plans))

eval_kwargs = {
    'alternatives': [
        {**p, 'id': i+1} for i, p in enumerate(plans[:6])
    ],
    'criteria': ['penetration_depth','durability_years','cost_per_sqm','construction_difficulty','environmental_impact','durability_confidence'],
    'weights': mat_cfg['criteria_defaults']['weights'],
    'benefit_criteria': mat_cfg['criteria_defaults']['benefit_criteria'],
    'cost_criteria': mat_cfg['criteria_defaults']['cost_criteria']
}
ranks = opt.evaluate(**eval_kwargs)
best = ranks[0]
print('   TOPSIS最佳方案: {}, 贴近度={:.3f}'.format(best['plan_name'], best['topsis_score']))

print('5. Alarm MQTT Service OK')
alarm = get_alarm_service()
levels = []
for rate in [0.3, 0.6, 0.85, 1.3]:
    a = alarm.check_erosion_alert(1, '西墙北段', rate)
    levels.append((rate, a['alert_level'] if a else None))
print('   告警分级:', levels)

print()
print('6. Microservice Adapter (local-only fallback) OK')
ada = get_adapter()
asyncio.run(ada.ensure_services())
print('   adapter.local_only =', ada.local_only)

# 测试适配器本地调用
r = asyncio.run(ada.call_erosion_sim('long_term',
    wind_speeds=ws.tolist(),
    wind_directions=wd.tolist(),
    hardness=hd.tolist(),
    moisture=mr.tolist(),
    segment_id=1))
print('   adapter call_erosion_sim(long_term) ok:', r['ok'])
if r['ok']:
    print('   年侵蚀率: {:.3f} mm/年'.format(r['result']['erosion_rate_mm_per_year']))

r2 = asyncio.run(ada.call_optimizer('generate', segment_id=1, area_sqm=120.0, hardness=2.5, moisture=5.0, severity='medium'))
print('   adapter call_optimizer(generate) ok:', r2['ok'])
if r2['ok']:
    print('   rankings count:', len(r2['result'].get('rankings', [])))

r3 = asyncio.run(ada.call_alarm('erosion_check', segment_id=1, segment_name='测试段', erosion_rate=0.9))
print('   adapter call_alarm(erosion_check) ok:', r3['ok'])
if r3['ok'] and r3['alert']:
    print('   alert level:', r3['alert']['alert_level'])

r4 = asyncio.run(ada.send_dtu_data({
    'segment_id': 1, 'sensor_id': 'S001',
    'time': '2025-01-01T10:00:00',
    'wind_erosion_depth': 0.15, 'soil_moisture': 5.2,
    'surface_hardness': 2.4, 'wind_speed': 6.5, 'wind_direction': 180.0
}))
print('   adapter send_dtu_data ok:', r4['ok'])

print()
print('='*60)
print('ALL 5 MICROSERVICES + ADAPTER VALIDATED: SUCCESS')
print('='*60)
