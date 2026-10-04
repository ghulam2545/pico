-- DROP TABLE workspaces;
-- DROP TABLE document_data;
-- DROP TABLE conversations;

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    api_key_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_workspaces_identifier
    ON workspaces (identifier);

CREATE INDEX IF NOT EXISTS ix_workspaces_api_key_hash
    ON workspaces (api_key_hash);


CREATE TABLE IF NOT EXISTS document_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL
        REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id VARCHAR(200) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    chunk_count INTEGER NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_doc_workspace_user_hash
        UNIQUE (workspace_id, user_id, file_hash)
);

CREATE INDEX IF NOT EXISTS ix_document_data_workspace_id
    ON document_data (workspace_id);

CREATE INDEX IF NOT EXISTS ix_document_data_user_id
    ON document_data (user_id);


CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL
        REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id VARCHAR(200) NOT NULL,
    name VARCHAR(300) NOT NULL DEFAULT 'New conversation',
    pinned BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_conversations_workspace_id
    ON conversations (workspace_id);

CREATE INDEX IF NOT EXISTS ix_conversations_user_id
    ON conversations (user_id);

CREATE EXTENSION IF NOT EXISTS vector;