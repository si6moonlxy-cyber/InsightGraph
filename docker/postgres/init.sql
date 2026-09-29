-- ================================================================
-- InsightGraph 数据库初始化脚本
-- 由 docker-compose.yml 在 PostgreSQL 首次启动时自动执行
-- ================================================================
-- 此文件只创建实例级基础结构（扩展等）；
-- 表结构由后端 Alembic 迁移管理，不在此文件中创建。
-- ================================================================

-- UUID 生成
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 加密函数
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 向量扩展（pgvector：Embedding 列 + HNSW 索引，供语义检索）
CREATE EXTENSION IF NOT EXISTS "vector";

-- ================================================================
-- 留档：alembic_version 列宽教训（来自 CoSense 实测，2026-09-29 记录）
-- ================================================================
-- Alembic 自动创建的 alembic_version.version_num 是 VARCHAR(32)；
-- 当 revision id 超过 32 字符时，全新库初始化会在该迁移处抛出
-- "value too long for type character varying(32)" 而中断。
--
-- 表已存在时 Alembic 直接沿用（不比较列宽），因此解法是：
--   CREATE TABLE IF NOT EXISTS alembic_version (
--       version_num VARCHAR(64) NOT NULL,
--       CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
--   );
--
-- InsightGraph 的规避策略：revision id 规范 ≤ 32 字符；
-- 若未来仍出现同类问题，在此预建 VARCHAR(64) 版本表即可。
-- ================================================================
