-- Rode como superusuário do PostgreSQL (ex.: sudo -u postgres psql -f scripts/preparar_banco.sql).
-- Cria o papel dono (migrações), o papel da aplicação (sem privilégios especiais) e os bancos.
CREATE ROLE toqqi LOGIN PASSWORD 'toqqi' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE toqqi_app LOGIN PASSWORD 'toqqi_app' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE DATABASE toqqi_dev OWNER toqqi;
CREATE DATABASE toqqi_test OWNER toqqi;
