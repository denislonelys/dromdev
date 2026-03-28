-- IIStudio — PostgreSQL инициализация
-- Выполняется при первом запуске контейнера

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Схема
CREATE SCHEMA IF NOT EXISTS iistudio;

-- Комментарий
COMMENT ON DATABASE iistudio IS 'IIStudio AI Orchestrator Database';
