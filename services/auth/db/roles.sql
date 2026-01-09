-- ===============================
-- Auth DB Roles
-- ===============================

-- Роль для суперпользователя / администратора
CREATE ROLE auth_admin
    WITH
        LOGIN
        SUPERUSER
        CREATEDB
        CREATEROLE
        INHERIT
        NOREPLICATION;

-- Роль для сервиса (Auth Service)
CREATE ROLE auth_service
    WITH
        LOGIN
        NOINHERIT
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOREPLICATION;

-- Роль для обычного пользователя (необязательно, если используем только сервис)
CREATE ROLE auth_user
    WITH
        LOGIN
        NOINHERIT
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOREPLICATION;

-- Назначение владельцев схем
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION auth_service;

-- GRANT права для сервиса
GRANT USAGE ON SCHEMA auth TO auth_service;
GRANT CREATE, SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA auth TO auth_service;

-- GRANT default права для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA auth
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO auth_service;

-- Примечание:
-- Пароли для ролей задаются при создании БД или через .env + миграции
