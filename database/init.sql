-- ============================================================
-- 古代咸阳宫夯土墙保护系统 - TimescaleDB 初始化脚本
-- ============================================================

-- 创建数据库
CREATE DATABASE rammed_earth_wall;

-- 连接到数据库
\c rammed_earth_wall;

-- 安装扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- 墙体段信息表
-- ============================================================
CREATE TABLE IF NOT EXISTS wall_segments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    length_m FLOAT NOT NULL,
    height_m FLOAT NOT NULL,
    thickness_m FLOAT NOT NULL,
    position_start_x FLOAT,
    position_start_y FLOAT,
    position_end_x FLOAT,
    position_end_y FLOAT,
    original_compaction FLOAT,
    construction_year INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 传感器数据表 (时序超表)
-- ============================================================
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    segment_id INT NOT NULL REFERENCES wall_segments(id),
    sensor_id VARCHAR(50) NOT NULL,
    wind_erosion_depth FLOAT NOT NULL,
    soil_moisture FLOAT NOT NULL,
    surface_hardness FLOAT NOT NULL,
    wind_speed FLOAT NOT NULL,
    wind_direction FLOAT NOT NULL,
    temperature FLOAT,
    humidity FLOAT,
    dtu_signal_strength FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建超表
SELECT create_hypertable('sensor_data', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sensor_data_segment_time 
    ON sensor_data(segment_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_time 
    ON sensor_data(sensor_id, time DESC);

-- ============================================================
-- 风蚀仿真结果表
-- ============================================================
CREATE TABLE IF NOT EXISTS erosion_simulation (
    id SERIAL PRIMARY KEY,
    segment_id INT NOT NULL REFERENCES wall_segments(id),
    simulation_time TIMESTAMPTZ NOT NULL,
    prediction_period_days INT NOT NULL,
    erosion_rate FLOAT NOT NULL,
    max_erosion_depth FLOAT NOT NULL,
    critical_zones JSONB,
    wind_energy FLOAT,
    particle_impact_count FLOAT,
    model_parameters JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('erosion_simulation', 'simulation_time',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- ============================================================
-- 加固方案表
-- ============================================================
CREATE TABLE IF NOT EXISTS reinforcement_plans (
    id SERIAL PRIMARY KEY,
    segment_id INT NOT NULL REFERENCES wall_segments(id),
    plan_name VARCHAR(100) NOT NULL,
    material_type VARCHAR(50) NOT NULL,
    material_ratio VARCHAR(100),
    penetration_depth FLOAT,
    cost_per_sqm FLOAT NOT NULL,
    construction_difficulty INT,
    durability_years FLOAT,
    durability_confidence FLOAT,
    durability_lower_bound FLOAT,
    durability_upper_bound FLOAT,
    environmental_impact FLOAT,
    acceleration_factor FLOAT,
    aging_test_days INT,
    strength_retention FLOAT,
    topsis_score FLOAT,
    topsis_rank INT,
    is_selected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 加固材料参数表
-- ============================================================
CREATE TABLE IF NOT EXISTS reinforcement_materials (
    id SERIAL PRIMARY KEY,
    material_name VARCHAR(100) NOT NULL,
    material_code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    penetration_coefficient FLOAT,
    bonding_strength FLOAT,
    cost_per_kg FLOAT,
    application_method VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 告警信息表
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    segment_id INT NOT NULL REFERENCES wall_segments(id),
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL,
    threshold_value FLOAT,
    measured_value FLOAT,
    description TEXT,
    mqtt_message_id VARCHAR(100),
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('alerts', 'created_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- ============================================================
-- 裂缝监测数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS crack_monitoring (
    time TIMESTAMPTZ NOT NULL,
    segment_id INT NOT NULL REFERENCES wall_segments(id),
    crack_id VARCHAR(50) NOT NULL,
    crack_width FLOAT NOT NULL,
    crack_length FLOAT,
    crack_depth FLOAT,
    extension_rate FLOAT,
    location_x FLOAT,
    location_y FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('crack_monitoring', 'time',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- ============================================================
-- 风场数据快照表
-- ============================================================
CREATE TABLE IF NOT EXISTS wind_field_snapshots (
    time TIMESTAMPTZ NOT NULL,
    grid_x INT NOT NULL,
    grid_y INT NOT NULL,
    grid_z INT NOT NULL,
    velocity_x FLOAT,
    velocity_y FLOAT,
    velocity_z FLOAT,
    wind_speed FLOAT,
    wind_direction FLOAT,
    turbulence_intensity FLOAT,
    particle_concentration FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('wind_field_snapshots', 'time',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ============================================================
-- 初始化数据 - 秦咸阳宫遗址墙体段
-- ============================================================
INSERT INTO wall_segments (name, description, length_m, height_m, thickness_m, 
    position_start_x, position_start_y, position_end_x, position_end_y,
    original_compaction, construction_year) VALUES
('西墙北段', '咸阳宫西城墙北段，保存相对完整', 45.0, 3.2, 2.8, 108.7280, 34.3560, 108.7282, 34.3565, 0.92, -350),
('西墙南段', '咸阳宫西城墙南段，风蚀较为严重', 38.0, 2.5, 2.2, 108.7282, 34.3555, 108.7283, 34.3560, 0.85, -350),
('北墙西段', '咸阳宫北城墙西段，裂缝较多', 52.0, 3.5, 3.0, 108.7278, 34.3567, 108.7283, 34.3568, 0.88, -340),
('北墙东段', '咸阳宫北城墙东段，人为破坏较少', 48.0, 3.8, 3.2, 108.7283, 34.3568, 108.7288, 34.3567, 0.90, -340),
('东墙北段', '咸阳宫东城墙北段，紧邻现代建筑', 42.0, 2.8, 2.5, 108.7290, 34.3565, 108.7290, 34.3560, 0.82, -350),
('东墙南段', '咸阳宫东城墙南段，植被覆盖较多', 35.0, 2.2, 2.0, 108.7288, 34.3555, 108.7290, 34.3560, 0.78, -350),
('南墙西段', '咸阳宫南城墙西段，基础部分暴露', 40.0, 3.0, 2.8, 108.7280, 34.3553, 108.7285, 34.3553, 0.86, -345),
('南墙东段', '咸阳宫南城墙东段，道路施工影响区', 36.0, 2.6, 2.4, 108.7285, 34.3553, 108.7288, 34.3555, 0.80, -345);

-- ============================================================
-- 初始化加固材料数据
-- ============================================================
INSERT INTO reinforcement_materials (material_name, material_code, description, 
    penetration_coefficient, bonding_strength, cost_per_kg, application_method) VALUES
('硅酸乙酯', 'TEOS-01', '正硅酸乙酯，无机硅基加固材料', 0.75, 2.5, 45.0, '高压喷涂渗透'),
('改性硅酸乙酯', 'TEOS-02', '添加纳米二氧化硅的改性硅酸乙酯', 0.68, 3.2, 68.0, '高压喷涂渗透'),
('糯米灰浆', 'GLU-01', '传统糯米灰浆，糯米:石灰=1:3', 0.45, 1.8, 12.0, '抹面+渗透'),
('改性糯米灰浆', 'GLU-02', '添加石灰纳米颗粒的糯米灰浆', 0.52, 2.3, 18.0, '抹面+渗透'),
('复合加固剂', 'COM-01', '硅酸乙酯+糯米灰浆复合体系', 0.60, 2.8, 38.0, '逐层加固');

-- ============================================================
-- 连续聚合视图 - 风蚀速率小时统计
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS erosion_rate_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    segment_id,
    AVG(wind_erosion_depth) AS avg_erosion_depth,
    MAX(wind_erosion_depth) AS max_erosion_depth,
    AVG(wind_speed) AS avg_wind_speed,
    AVG(soil_moisture) AS avg_soil_moisture,
    COUNT(*) AS data_points
FROM sensor_data
GROUP BY bucket, segment_id
WITH NO DATA;

-- ============================================================
-- 连续聚合视图 - 风蚀速率日统计
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS erosion_rate_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    segment_id,
    AVG(wind_erosion_depth) AS avg_erosion_depth,
    MAX(wind_erosion_depth) AS max_erosion_depth,
    AVG(wind_speed) AS avg_wind_speed,
    MAX(wind_speed) AS max_wind_speed,
    AVG(soil_moisture) AS avg_soil_moisture,
    AVG(surface_hardness) AS avg_surface_hardness
FROM sensor_data
GROUP BY bucket, segment_id
WITH NO DATA;
