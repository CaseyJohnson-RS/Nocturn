# Runbook: рост 5xx / выгорание бюджета доступности

**Алерты:** `NocturnAvailabilityBudgetBurnFast`, `NocturnAvailabilityBudgetBurnSlow`,
`NocturnAvailabilityBudgetBurnTicket`

## Impact

Часть запросов падает с 5xx. Пользователи видят ошибки при сохранении заметок,
логине или загрузке списка. При burn rate 14.4x весь месячный бюджет
доступности сгорит примерно за два дня.

## 1. Локализовать

Дашборд **Nocturn — Service Overview**, панель *Top endpoints by 5xx rate*.

```promql
# Какие эндпоинты дают ошибки
topk(10, sum by (path, method, status) (rate(nocturn_http_requests_total{status=~"5.."}[5m])))
```

Дальше развилка — **один эндпоинт или все**:

* **Все сразу** → почти всегда зависимость. Переходите к
  [dependency-down.md](dependency-down.md), проверьте панель *Dependencies*.
* **Только `/api/ai/*`** → провайдер LLM, см.
  [llm-provider-outage.md](llm-provider-outage.md). Остальной продукт исправен.
* **Один CRUD-эндпоинт** → скорее всего регрессия последнего деплоя.

## 2. Найти причину в логах

Логи структурные, у каждой строки есть `request_id`. В Grafana → Explore → Loki:

```logql
{compose_service="backend"} | json | level = "ERROR"
```

Взять `request_id` из подозрительной строки и вытащить всю историю запроса:

```logql
{compose_service="backend"} | json | request_id = "<REQUEST_ID>"
```

## 3. Проверить, не деплой ли это

```bash
curl -s localhost:9090/api/v1/query \
  --data-urlencode 'query=nocturn_build_info' | jq '.data.result[].metric'
```

Сопоставьте `commit` с моментом начала роста ошибок на графике. Совпало —
откатывайте, не разбираясь дальше:

```bash
GIT_COMMIT=<предыдущий-sha> make observability-up
```

## 4. Митигация

| Причина | Действие |
|---|---|
| Плохой деплой | Откат на предыдущий образ, разбор потом |
| Исчерпан пул БД | [postgres-saturation.md](postgres-saturation.md) |
| Redis недоступен | [dependency-down.md](dependency-down.md) |
| Внешний LLM | Ограничить `/api/ai/*`, продукт остаётся работоспособным |
| Не воспроизводится | Рестарт `backend`, но обязательно снять логи **до** рестарта |

```bash
# Снять логи перед рестартом — иначе улики потеряны
docker compose logs --no-color backend > incident-$(date +%s).log
docker compose restart backend
```

## Эскалация

Если через 30 минут burn rate не снизился и причина не найдена — переводите
ИИ-функциональность в отключённое состояние (она даёт больше всего 5xx при
проблемах с внешними зависимостями) и заводите постмортем.

## После инцидента

Бюджет ошибок потрачен — это данные, а не позор. Зафиксируйте в
`docs/postmortems/`: таймлайн, сколько процентов бюджета сгорело
(`nocturn:availability:budget_remaining_ratio` до и после), какой сигнал
позволил бы заметить раньше.
