-- Migration 007: Agent observability tables
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_name      VARCHAR(64) NOT NULL,
    request_id      VARCHAR(64),
    input_summary   TEXT,
    output_summary  TEXT,
    status          VARCHAR(16) DEFAULT 'running',
    latency_ms      INTEGER,
    token_usage     INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name, created_at DESC);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recommendation_id   UUID,
    rating              SMALLINT CHECK (rating >= 1 AND rating <= 5),
    accepted            BOOLEAN,
    comment             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rec_feedback_user ON recommendation_feedback(user_id, created_at DESC);
