-- Executado automaticamente pelo container do Postgres na primeira subida.
-- Isolamento multi-tenant com Row-Level Security (RLS).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE restaurants (
    id   text PRIMARY KEY,
    nome text NOT NULL
);

CREATE TABLE documents (
    id        bigserial PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES restaurants(id),
    source    text NOT NULL,
    content   text NOT NULL,
    embedding vector(384) NOT NULL
);
CREATE INDEX documents_tenant_idx ON documents (tenant_id);
CREATE INDEX documents_embedding_idx ON documents USING hnsw (embedding vector_cosine_ops);

CREATE TABLE orders (
    codigo    text PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES restaurants(id),
    status    text NOT NULL,
    previsao  text,
    itens     jsonb NOT NULL DEFAULT '[]',
    total     numeric(10, 2)
);
CREATE INDEX orders_tenant_idx ON orders (tenant_id);

-- RLS: cada consulta só enxerga as linhas do tenant definido em app.tenant_id.
-- current_setting(..., true) devolve NULL quando a variável não foi definida,
-- e "tenant_id = NULL" nunca é verdadeiro -> sem tenant, ZERO linhas (falha fechada).
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY documents_tenant_isolation ON documents
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;
CREATE POLICY orders_tenant_isolation ON orders
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- A aplicação usa um usuário SEM superuser e SEM BYPASSRLS.
-- (Superusuários ignoram RLS, por isso a app nunca deve conectar como postgres.)
CREATE ROLE app_user LOGIN PASSWORD 'app_user_dev' NOSUPERUSER NOBYPASSRLS;
GRANT SELECT, INSERT, UPDATE ON restaurants TO app_user;
GRANT SELECT, INSERT, DELETE ON documents TO app_user;
GRANT SELECT, INSERT ON orders TO app_user;
GRANT USAGE ON SEQUENCE documents_id_seq TO app_user;
