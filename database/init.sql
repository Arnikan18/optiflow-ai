CREATE TABLE IF NOT EXISTS schema_versions (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(100) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    role VARCHAR(50) NOT NULL,
    password_hash TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    scenario_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    goal_text TEXT,
    state_version INTEGER NOT NULL DEFAULT 1,
    plan_version INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_events (
    event_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100),
    sequence_number BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    summary TEXT,
    payload JSONB,
    state_version INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
    tool_call_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100),
    tool_name VARCHAR(100) NOT NULL,
    endpoint TEXT NOT NULL,
    method VARCHAR(20) NOT NULL,
    purpose TEXT,
    reason_selected TEXT,
    status VARCHAR(50) NOT NULL,
    latency_ms INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    request_summary JSONB,
    response_summary JSONB,
    error_category VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
);

-- Seed initial schema version
INSERT INTO schema_versions (version) VALUES ('1.0.0') ON CONFLICT DO NOTHING;

-- Seed default demo users (password is 'demo-password')
-- Standard bcrypt hash for 'demo-password' is '$2b$12$R9h/lIPzMRF.FhL8D3jMBe6vWc1q11x3Qx54R05g4/nC77vA6mK8q'
INSERT INTO users (user_id, username, name, role, password_hash, active)
VALUES (
    'USR-MANAGER-01', 
    'manager', 
    'Demo Manager', 
    'MANAGER', 
    '$2b$12$R9h/lIPzMRF.FhL8D3jMBe6vWc1q11x3Qx54R05g4/nC77vA6mK8q', 
    TRUE
) ON CONFLICT DO NOTHING;

INSERT INTO users (user_id, username, name, role, password_hash, active)
VALUES (
    'USR-ADMIN-01', 
    'admin', 
    'Demo Admin', 
    'ADMIN', 
    '$2b$12$R9h/lIPzMRF.FhL8D3jMBe6vWc1q11x3Qx54R05g4/nC77vA6mK8q', 
    TRUE
) ON CONFLICT DO NOTHING;
