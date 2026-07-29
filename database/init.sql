-- OptiFlow PostgreSQL Schema Initialization (Version 4.0 Aligned)

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

-- 1. business_goals
CREATE TABLE IF NOT EXISTS business_goals (
    goal_id VARCHAR(100) PRIMARY KEY,
    original_text TEXT NOT NULL,
    structured_goal_json JSONB,
    objective_profile TEXT,
    time_horizon_minutes INTEGER,
    policy_version VARCHAR(100),
    prompt_template_version VARCHAR(50),
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. agent_runs (additive, backward-compatible columns added)
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    scenario_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    goal_text TEXT,
    state_version INTEGER NOT NULL DEFAULT 1,
    plan_version INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- New Additive Version 4 columns (nullable or defaulted to preserve backward compatibility)
    goal_id VARCHAR(100) REFERENCES business_goals(goal_id),
    current_node VARCHAR(100),
    replan_count INTEGER NOT NULL DEFAULT 0,
    recommended_plan_id VARCHAR(100),
    completed_at TIMESTAMPTZ
);

-- 3. run_events
CREATE TABLE IF NOT EXISTS run_events (
    event_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    sequence_number BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    summary TEXT,
    payload JSONB,
    state_version INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. graph_checkpoints
CREATE TABLE IF NOT EXISTS graph_checkpoints (
    checkpoint_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    node_name VARCHAR(100) NOT NULL,
    checkpoint_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. state_snapshots
CREATE TABLE IF NOT EXISTS state_snapshots (
    snapshot_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    state_json JSONB NOT NULL,
    quality_category VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. evidence_items
CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    source_service VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    value_json JSONB NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_updated_at TIMESTAMPTZ,
    freshness_status VARCHAR(50) NOT NULL,
    quality_flags_json JSONB,
    decision_critical BOOLEAN NOT NULL DEFAULT FALSE
);

-- 7. tool_calls (additive, backward-compatible updates)
CREATE TABLE IF NOT EXISTS tool_calls (
    tool_call_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
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
    
    -- New Additive Version 4 columns (nullable)
    request_id VARCHAR(100) UNIQUE,
    service_name VARCHAR(50),
    operation VARCHAR(100),
    http_status INTEGER,
    completed_at TIMESTAMPTZ
);

-- 8. consequence_estimates
CREATE TABLE IF NOT EXISTS consequence_estimates (
    estimate_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    incident_id VARCHAR(100) NOT NULL,
    specialist_id VARCHAR(100),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(14, 2) NOT NULL,
    unit VARCHAR(50),
    confidence VARCHAR(50) NOT NULL,
    evidence_ids_json JSONB NOT NULL,
    assumptions_json JSONB,
    formula_version VARCHAR(50) NOT NULL
);

-- 9. candidate_plans
CREATE TABLE IF NOT EXISTS candidate_plans (
    plan_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    plan_version INTEGER NOT NULL DEFAULT 0,
    profile VARCHAR(50) NOT NULL,
    plan_hash VARCHAR(256) NOT NULL,
    solver_status VARCHAR(50) NOT NULL,
    objective_value NUMERIC(14, 2) NOT NULL,
    metrics_json JSONB NOT NULL,
    validation_status VARCHAR(50) NOT NULL,
    review_trigger_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. plan_allocations
CREATE TABLE IF NOT EXISTS plan_allocations (
    allocation_id VARCHAR(100) PRIMARY KEY,
    plan_id VARCHAR(100) REFERENCES candidate_plans(plan_id),
    incident_id VARCHAR(100) NOT NULL,
    specialist_id VARCHAR(100),
    allocation_status VARCHAR(50) NOT NULL,
    start_at TIMESTAMPTZ,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    expected_effects_json JSONB,
    locked BOOLEAN NOT NULL DEFAULT FALSE
);

-- 11. policy_evaluations
CREATE TABLE IF NOT EXISTS policy_evaluations (
    evaluation_id VARCHAR(100) PRIMARY KEY,
    plan_id VARCHAR(100) REFERENCES candidate_plans(plan_id),
    policy_version VARCHAR(100) NOT NULL,
    result VARCHAR(50) NOT NULL,
    hard_violations_json JSONB,
    warnings_json JSONB,
    fairness_metrics_json JSONB,
    workload_metrics_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. human_decisions
CREATE TABLE IF NOT EXISTS human_decisions (
    decision_id VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    plan_id VARCHAR(100) REFERENCES candidate_plans(plan_id),
    plan_version INTEGER NOT NULL DEFAULT 0,
    plan_hash VARCHAR(256),
    action VARCHAR(50) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,
    reason TEXT,
    changes_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- 13. execution_authorizations
CREATE TABLE IF NOT EXISTS execution_authorizations (
    authorization_id VARCHAR(100) PRIMARY KEY,
    decision_id VARCHAR(100) REFERENCES human_decisions(decision_id),
    run_id VARCHAR(100) REFERENCES agent_runs(run_id),
    plan_id VARCHAR(100) REFERENCES candidate_plans(plan_id),
    state_version INTEGER NOT NULL DEFAULT 1,
    plan_version INTEGER NOT NULL DEFAULT 0,
    plan_hash VARCHAR(256) NOT NULL,
    policy_version VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- 14. execution_actions
CREATE TABLE IF NOT EXISTS execution_actions (
    action_id VARCHAR(100) PRIMARY KEY,
    authorization_id VARCHAR(100) REFERENCES execution_authorizations(authorization_id),
    sequence_no INTEGER NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    target_entity_id VARCHAR(100) NOT NULL,
    payload_json JSONB,
    idempotency_key VARCHAR(256) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 15. execution_receipts
CREATE TABLE IF NOT EXISTS execution_receipts (
    receipt_id VARCHAR(100) PRIMARY KEY,
    action_id VARCHAR(100) REFERENCES execution_actions(action_id),
    tool_request_id VARCHAR(100),
    verification_status VARCHAR(50) NOT NULL,
    authoritative_state_json JSONB,
    error_code VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. fairness_ledger
CREATE TABLE IF NOT EXISTS fairness_ledger (
    ledger_id VARCHAR(100) PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    cumulative_wait_minutes INTEGER NOT NULL DEFAULT 0,
    postponement_count INTEGER NOT NULL DEFAULT 0,
    last_served_at TIMESTAMPTZ,
    treatment_score NUMERIC(14, 2),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 17. objective_profiles
CREATE TABLE IF NOT EXISTS objective_profiles (
    profile_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    weights_json JSONB NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 18. policy_versions
CREATE TABLE IF NOT EXISTS policy_versions (
    policy_version VARCHAR(100) PRIMARY KEY,
    hard_rules_json JSONB,
    soft_rules_json JSONB,
    approved_by VARCHAR(100),
    effective_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at TIMESTAMPTZ
);

-- 19. system_settings
-- Values are encrypted by Core before persistence. API keys never belong in
-- ordinary JSON columns, logs, events, or graph checkpoints.
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    encrypted_value TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed initial schema version
INSERT INTO schema_versions (version) VALUES ('4.0.0') ON CONFLICT DO NOTHING;

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
) ON CONFLICT (user_id) DO NOTHING;

INSERT INTO users (user_id, username, name, role, password_hash, active)
VALUES (
    'USR-ADMIN-01', 
    'admin', 
    'Demo Admin', 
    'ADMIN', 
    '$2b$12$R9h/lIPzMRF.FhL8D3jMBe6vWc1q11x3Qx54R05g4/nC77vA6mK8q', 
    TRUE
) ON CONFLICT (user_id) DO NOTHING;
