-- Initialize CI/CD Dashboard Database

-- Create tables
CREATE TABLE IF NOT EXISTS pipelines (
    id BIGSERIAL PRIMARY KEY,
    github_run_id BIGINT UNIQUE NOT NULL,
    workflow_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    conclusion VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration INTEGER,
    branch VARCHAR(255),
    commit_sha VARCHAR(40),
    commit_message TEXT,
    actor VARCHAR(255),
    html_url TEXT,
    logs_url TEXT,
    created_date DATE GENERATED ALWAYS AS (created_at::date) STORED
);

CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    pipeline_id BIGINT REFERENCES pipelines(id),
    alert_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'sent'
);

CREATE TABLE IF NOT EXISTS metrics_cache (
    id SERIAL PRIMARY KEY,
    metric_key VARCHAR(255) UNIQUE NOT NULL,
    metric_value TEXT NOT NULL,
    period VARCHAR(20) NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_created_at ON pipelines(created_at);
CREATE INDEX IF NOT EXISTS idx_pipelines_workflow ON pipelines(workflow_name);
CREATE INDEX IF NOT EXISTS idx_pipelines_created_date ON pipelines(created_date);
CREATE INDEX IF NOT EXISTS idx_alerts_pipeline_id ON alerts(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts(sent_at);
CREATE INDEX IF NOT EXISTS idx_metrics_cache_expires ON metrics_cache(expires_at);

-- Create views for analytics
CREATE OR REPLACE VIEW daily_metrics AS
SELECT
    created_date,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE status = 'completed' AND conclusion = 'success') as success_count,
    COUNT(*) FILTER (WHERE status = 'completed' AND conclusion = 'failure') as failure_count,
    ROUND(
        (COUNT(*) FILTER (WHERE status = 'completed' AND conclusion = 'success')::DECIMAL /
         COUNT(*) FILTER (WHERE status = 'completed')) * 100, 2
    ) as success_rate,
    AVG(duration) as avg_build_time,
    MIN(duration) as min_build_time,
    MAX(duration) as max_build_time
FROM pipelines
WHERE created_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY created_date
ORDER BY created_date DESC;

CREATE OR REPLACE VIEW workflow_metrics AS
SELECT
    workflow_name,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE status = 'completed' AND conclusion = 'success') as success_count,
    COUNT(*) FILTER (WHERE status = 'completed' AND conclusion = 'failure') as failure_count,
    ROUND(
        (COUNT(*) FILTER (WHERE status = 'completed' AND conclusion = 'success')::DECIMAL /
         COUNT(*) FILTER (WHERE status = 'completed')) * 100, 2
    ) as success_rate,
    AVG(duration) as avg_build_time
FROM pipelines
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY workflow_name
ORDER BY total_executions DESC;

-- Insert sample data for testing (optional)
INSERT INTO workflows (name, description) VALUES
    ('CI/CD Pipeline', 'Main CI/CD pipeline for the project'),
    ('Deployment Pipeline', 'Production deployment pipeline'),
    ('Test Pipeline', 'Automated testing pipeline')
ON CONFLICT (name) DO NOTHING;

