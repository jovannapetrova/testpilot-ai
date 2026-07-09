CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500),
    created_at TIMESTAMP NOT NULL,
    last_login_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(40) NOT NULL DEFAULT 'upload',
    source_url VARCHAR(1000),
    filename VARCHAR(255),
    language VARCHAR(100) NOT NULL DEFAULT 'Unknown',
    total_files INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    upload_blob BYTEA,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_projects_user_id ON projects (user_id);
CREATE INDEX IF NOT EXISTS ix_projects_status ON projects (status);

CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    project_name VARCHAR(255) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'completed',
    language VARCHAR(100) NOT NULL DEFAULT 'unknown',
    overall_score FLOAT NOT NULL DEFAULT 0,
    quality_score FLOAT NOT NULL DEFAULT 0,
    security_score FLOAT NOT NULL DEFAULT 0,
    test_score FLOAT NOT NULL DEFAULT 0,
    report_json TEXT NOT NULL,
    pdf_blob BYTEA,
    markdown_text TEXT,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_reports_project_id ON reports (project_id);
CREATE INDEX IF NOT EXISTS ix_reports_user_id ON reports (user_id);
