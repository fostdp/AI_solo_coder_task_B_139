-- ============================================================
-- 夯土墙风蚀监测系统 - TimescaleDB 初始化脚本
-- 含：建表、Hypertable转换、降采样(Continuous Aggregate)、保留策略
-- ============================================================

-- 启用 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

SET client_min_messages = WARNING;

-- ============================================================
-- 1. 主表结构（原始数据）
-- ============================================================

CREATE TABLE IF NOT EXISTS wall_segments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    position_x DOUBLE PRECISION NOT NULL DEFAULT 0,
    position_y DOUBLE PRECISION NOT NULL DEFAULT 0,
    position_z DOUBLE PRECISION NOT NULL DEFAULT 0,
    width DOUBLE PRECISION NOT NULL DEFAULT 3.0,
    height DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    depth DOUBLE PRECISION NOT NULL DEFAULT 0.8,
    rotation DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    segment_id INTEGER NOT NULL REFERENCES wall_segments(id) ON DELETE CASCADE,
    sensor_id VARCHAR(64) NOT NULL,
    wind_erosion_depth DOUBLE PRECISION,
    soil_moisture DOUBLE PRECISION,
    surface_hardness DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    wind_direction DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    dtu_signal_strength DOUBLE PRECISION,
    PRIMARY KEY (time, segment_id)
);

CREATE TABLE IF NOT EXISTS crack_monitor (
    time TIMESTAMPTZ NOT NULL,
    segment_id INTEGER NOT NULL REFERENCES wall_segments(id) ON DELETE CASCADE,
    crack_id VARCHAR(64) NOT NULL,
    crack_width DOUBLE PRECISION,
    crack_length DOUBLE PRECISION,
    crack_depth DOUBLE PRECISION,
    extension_rate DOUBLE PRECISION,
    location_x DOUBLE PRECISION,
    location_y DOUBLE PRECISION,
    PRIMARY KEY (time, segment_id, crack_id)
);

CREATE TABLE IF NOT EXISTS erosion_simulations (
    id SERIAL PRIMARY KEY,
    segment_id INTEGER NOT NULL REFERENCES wall_segments(id) ON DELETE CASCADE,
    simulation_mode VARCHAR(32) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    prediction_years INTEGER NOT NULL DEFAULT 5,
    erosion_rate_mm_per_year DOUBLE PRECISION,
    max_erosion_depth_mm DOUBLE PRECISION,
    avg_enhancement_factor DOUBLE PRECISION,
    des_applied BOOLEAN DEFAULT FALSE,
    critical_zones JSONB DEFAULT '[]'::jsonb,
    wind_sector_rates JSONB DEFAULT '{}'::jsonb,
    parameters JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reinforcement_plans (
    id SERIAL PRIMARY KEY,
    segment_id INTEGER NOT NULL REFERENCES wall_segments(id) ON DELETE CASCADE,
    plan_name VARCHAR(256) NOT NULL,
    material_code VARCHAR(32) NOT NULL,
    material_ratio VARCHAR(64) NOT NULL,
    penetration_depth DOUBLE PRECISION,
    durability_years DOUBLE PRECISION,
    durability_confidence DOUBLE PRECISION,
    cost_per_sqm DOUBLE PRECISION,
    total_cost DOUBLE PRECISION,
    construction_difficulty DOUBLE PRECISION,
    environmental_impact DOUBLE PRECISION,
    topsis_score DOUBLE PRECISION,
    topsis_rank INTEGER,
    is_selected BOOLEAN DEFAULT FALSE,
    severity VARCHAR(16) DEFAULT 'medium',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    segment_id INTEGER REFERENCES wall_segments(id) ON DELETE SET NULL,
    alert_type VARCHAR(32) NOT NULL,
    alert_level VARCHAR(16) NOT NULL,
    severity_score INTEGER DEFAULT 0,
    message TEXT,
    data JSONB DEFAULT '{}'::jsonb,
    source_channel VARCHAR(32),
    mqtt_published BOOLEAN DEFAULT FALSE,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_level ON alerts(alert_level);

-- ============================================================
-- 2. 转换为 TimescaleDB Hypertable
-- ============================================================

SELECT create_hypertable(
    'sensor_data',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day',
    partitioning_column => 'segment_id',
    number_partitions => 4
);

SELECT create_hypertable(
    'crack_monitor',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '7 days',
    partitioning_column => 'segment_id',
    number_partitions => 4
);

-- ============================================================
-- 3. Continuous Aggregates 降采样聚合
-- ============================================================

-- 3.1 每小时聚合
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    segment_id,
    COUNT(*) AS record_count,
    AVG(wind_erosion_depth) AS avg_erosion_depth,
    MAX(wind_erosion_depth) AS max_erosion_depth,
    MIN(wind_erosion_depth) AS min_erosion_depth,
    AVG(soil_moisture) AS avg_soil_moisture,
    AVG(surface_hardness) AS avg_surface_hardness,
    AVG(wind_speed) AS avg_wind_speed,
    MAX(wind_speed) AS max_wind_speed,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wind_speed) AS median_wind_speed,
    AVG(wind_direction) AS avg_wind_direction,
    AVG(temperature) AS avg_temperature,
    AVG(humidity) AS avg_humidity
FROM sensor_data
GROUP BY bucket, segment_id
WITH NO DATA;

-- 3.2 每日聚合
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    segment_id,
    COUNT(*) AS record_count,
    AVG(wind_erosion_depth) AS avg_erosion_depth,
    MAX(wind_erosion_depth) AS max_erosion_depth,
    MIN(wind_erosion_depth) AS min_erosion_depth,
    AVG(soil_moisture) AS avg_soil_moisture,
    AVG(surface_hardness) AS avg_surface_hardness,
    AVG(wind_speed) AS avg_wind_speed,
    MAX(wind_speed) AS max_wind_speed,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY wind_speed) AS wind_speed_p95,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wind_speed) AS median_wind_speed,
    STDDEV(wind_speed) AS wind_speed_stddev,
    AVG(temperature) AS avg_temperature,
    MAX(temperature) AS max_temperature,
    MIN(temperature) AS min_temperature,
    AVG(humidity) AS avg_humidity
FROM sensor_data
GROUP BY bucket, segment_id
WITH NO DATA;

-- 3.3 每月聚合
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_monthly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 month', time) AS bucket,
    segment_id,
    COUNT(*) AS record_count,
    AVG(wind_erosion_depth) AS avg_erosion_depth,
    MAX(wind_erosion_depth) AS max_erosion_depth,
    AVG(soil_moisture) AS avg_soil_moisture,
    AVG(surface_hardness) AS avg_surface_hardness,
    AVG(wind_speed) AS avg_wind_speed,
    MAX(wind_speed) AS max_wind_speed,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY wind_speed) AS wind_speed_p95,
    STDDEV(wind_speed) AS wind_speed_stddev
FROM sensor_data
GROUP BY bucket, segment_id
WITH NO DATA;

-- ============================================================
-- 4. 连续聚合刷新策略（实时+定时）
-- ============================================================

-- 4.1 每小时聚合 - 每5分钟刷新窗口内最新1小时
SELECT add_continuous_aggregate_policy(
    'sensor_data_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- 4.2 每日聚合 - 每30分钟刷新窗口内最近3天
SELECT add_continuous_aggregate_policy(
    'sensor_data_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);

-- 4.3 每月聚合 - 每天刷新窗口内最近6个月
SELECT add_continuous_aggregate_policy(
    'sensor_data_monthly',
    start_offset => INTERVAL '6 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================================
-- 5. 数据保留策略（Retention Policies）
-- ============================================================

-- 5.1 原始传感器数据：保留90天
SELECT add_retention_policy(
    'sensor_data',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- 5.2 裂缝监测原始数据：保留365天
SELECT add_retention_policy(
    'crack_monitor',
    INTERVAL '365 days',
    if_not_exists => TRUE
);

-- 5.3 小时级聚合：保留2年
ALTER MATERIALIZED VIEW sensor_data_hourly SET (timescaledb.materialized_only = FALSE);
SELECT add_retention_policy(
    'sensor_data_hourly',
    INTERVAL '2 years',
    if_not_exists => TRUE
);

-- 5.4 日级聚合：保留10年
ALTER MATERIALIZED VIEW sensor_data_daily SET (timescaledb.materialized_only = FALSE);
SELECT add_retention_policy(
    'sensor_data_daily',
    INTERVAL '10 years',
    if_not_exists => TRUE
);

-- 5.5 月级聚合：永久保留（不设限制）
ALTER MATERIALIZED VIEW sensor_data_monthly SET (timescaledb.materialized_only = FALSE);

-- ============================================================
-- 6. 默认墙段数据
-- ============================================================

INSERT INTO wall_segments (id, name, position_x, position_y, position_z, width, height, depth, rotation)
VALUES
    (1, '西墙北段', -14, 0, 0, 3, 2.8, 0.8, 0),
    (2, '西墙南段', -10, 0, 0, 3, 2.2, 0.8, 0),
    (3, '北墙西段', -6, 0, 0, 3, 2.5, 0.8, 0),
    (4, '北墙东段', -2, 0, 0, 3, 3.0, 0.8, 0),
    (5, '东墙北段', 2, 0, 0, 3, 2.3, 0.8, 0),
    (6, '东墙南段', 6, 0, 0, 3, 2.0, 0.8, 0),
    (7, '南墙西段', 10, 0, 0, 3, 2.6, 0.8, 0),
    (8, '南墙东段', 14, 0, 0, 3, 2.1, 0.8, 0)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 7. 性能优化索引
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_sensor_data_segment_time
    ON sensor_data (segment_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_crack_monitor_segment_time
    ON crack_monitor (segment_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_erosion_sim_segment_time
    ON erosion_simulations (segment_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reinforce_plans_segment
    ON reinforcement_plans (segment_id, created_at DESC);

-- 分析并更新统计信息
ANALYZE sensor_data;
ANALYZE crack_monitor;
ANALYZE erosion_simulations;
ANALYZE reinforcement_plans;
ANALYZE alerts;
