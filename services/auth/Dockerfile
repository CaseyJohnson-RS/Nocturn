# Используем официальный образ PostgreSQL
FROM postgres:15

# Копируем скрипты для инициализации схемы и ролей
# Они будут выполнены при первом старте контейнера
COPY roles.sql /docker-entrypoint-initdb.d/roles.sql
COPY schema.sql /docker-entrypoint-initdb.d/schema.sql

# Устанавливаем переменные окружения по умолчанию
# Можно переопределить через docker-compose или .env
ENV POSTGRES_DB=auth_db
ENV POSTGRES_USER=auth_service
ENV POSTGRES_PASSWORD=changeme

# Expose порт
EXPOSE 5432
