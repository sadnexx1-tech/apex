# 📊 ПОЛНОЕ РУКОВОДСТВО - Prometheus + Grafana + Telegram Bot

## 🔴 РЕШЕНИЕ ОШИБКИ

**Ошибка:** `Duplicated timeseries in CollectorRegistry`

**Причина:** Метрики регистрировались несколько раз в одном реестре

**Решение:** Используйте **ОДИН** CollectorRegistry и регистрируйте метрики один раз:

```python
# ✅ ПРАВИЛЬНО
registry = CollectorRegistry()

metric = Gauge('name', 'description', registry=registry)  # Один раз!

# ❌ НЕПРАВИЛЬНО
metric1 = Gauge('name', 'description')  # По умолчанию REGISTRY
metric2 = Gauge('name', 'description')  # ОШИБКА: дублирование!
```

---

## 🚀 БЫСТРЫЙ СТАРТ

### Шаг 1: Клонируйте репозиторий
```bash
git clone https://github.com/YOUR_USERNAME/coursebot-monitoring.git
cd coursebot-monitoring
```

### Шаг 2: Создайте файл `.env`
```bash
cp .env.example .env
```

### Шаг 3: Заполните переменные
```
BOT_TOKEN=your_telegram_bot_token
PROMETHEUS_PORT=8000
```

### Шаг 4: Запустите с Docker Compose
```bash
docker-compose up -d
```

### Шаг 5: Проверьте сервисы

| Сервис | URL | Логин | Пароль |
|--------|-----|-------|---------|
| Prometheus | http://localhost:9090 | - | - |
| Grafana | http://localhost:3000 | admin | admin123 |
| Bot Metrics | http://localhost:8000/metrics | - | - |

---

## 📊 АРХИТЕКТУРА

```
┌─────────────────────┐
│   Telegram Bot      │
│  (port 8000)        │
│  /metrics endpoint  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Prometheus        │
│  (port 9090)        │
│ Scrapes every 15s   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Grafana          │
│  (port 3000)        │
│ Visualizes metrics  │
└─────────────────────┘
```

---

## 📈 ДОСТУПНЫЕ МЕТРИКИ

### Основные метрики бота
- `bothost_bots_created_created` - Timestamp создания бота
- `bothost_bots_created_total` - Всего ботов создано
- `bothost_bots_created` - Активные боты сейчас

### Метрики производительности
- `message_processing_time_seconds` - Время обработки сообщений (histogram)
- `users_online` - Пользователей онлайн сейчас

### Метрики платежей
- `payment_transactions_total` - Всего транзакций (с лейблом status)
  - `status="success"` - Успешные платежи
  - `status="failed"` - Ошибки платежей

### Метрики подписок
- `subscription_activations_total` - Активированные подписки (с лейблом plan)
  - `plan="lite"` - Lite подписки
  - `plan="pro"` - Pro подписки
  - `plan="unlimited"` - Unlimited подписки

---

## 🎯 ПРИМЕРЫ ЗАПРОСОВ

### PromQL для Prometheus

```promql
# Все метрики бота
{job="coursebot"}

# Успешные платежи за последний час
rate(payment_transactions_total{status="success"}[1h])

# Время обработки сообщений (95-й перцентиль)
histogram_quantile(0.95, message_processing_time_seconds)

# Пики пользователей онлайн
max_over_time(users_online[1h])

# Средняя нагрузка за 5 минут
avg_over_time(users_online[5m])
```

---

## 📊 СОЗДАНИЕ DASHBOARD В GRAFANA

### 1. Добавьте Data Source
1. Откройте Grafana (localhost:3000)
2. Configuration → Data Sources
3. Add data source → Prometheus
4. URL: `http://prometheus:9090`
5. Save & Test

### 2. Создайте Dashboard
1. Нажмите "+" → Dashboard
2. Add Panel
3. Выберите метрику и график
4. Save

### Полезные панели

**Graph - Users Online**
```
Metric: users_online
Legend: Current online
```

**Stat - Total Payments**
```
Metric: rate(payment_transactions_total{status="success"}[1h])
Decimals: 2
Unit: /s
```

**Table - Recent Transactions**
```
Metric: payment_transactions_total
Group by: status
```

---

## 🔔 НАСТРОЙКА АЛЕРТОВ

### Встроенные алерты (alerts.yml)

✅ **BotNotResponding** - Бот не отвечает 2 минуты
✅ **HighMessageProcessingTime** - Время обработки > 5s
✅ **PaymentTransactionFailures** - Много ошибок платежей
✅ **HighUserLoad** - Более 1000 пользователей онлайн

### Добавить свой алерт

Отредактируйте `alerts.yml`:

```yaml
- alert: CustomAlert
  expr: metric_name > 100
  for: 5m
  annotations:
    summary: "Alert Description"
```

Перезагрузите Prometheus:
```bash
docker-compose restart prometheus
```

---

## 💾 СТРУКТУРА ФАЙЛОВ

```
coursebot-monitoring/
├── bot_prometheus_fixed.py      # Основной код бота
├── prometheus.yml               # Конфиг Prometheus
├── docker-compose.yml           # Docker Compose
├── Dockerfile                   # Docker image
├── alerts.yml                   # Правила алертов
├── requirements.txt             # Python зависимости
├── .env.example                 # Пример .env
├── .gitignore                   # Git исключения
└── README.md                    # Документация
```

---

## 🐳 DOCKER КОМАНДЫ

```bash
# Запустить все сервисы
docker-compose up -d

# Просмотреть логи бота
docker-compose logs -f coursebot

# Перезапустить определенный сервис
docker-compose restart prometheus

# Остановить все
docker-compose down

# Удалить данные (осторожно!)
docker-compose down -v
```

---

## 🔐 БЕЗОПАСНОСТЬ

### В продакшене

⚠️ **ИЗМЕНИТЬ пароли:**
- Grafana admin password
- Prometheus доступ ограничить
- Bot token в переменных окружения

✅ **ВСЕГДА:**
- Используйте HTTPS/TLS
- Ограничьте доступ по IP
- Регулярно обновляйте образы
- Сохраняйте резервные копии данных

```bash
# Измените пароль Grafana в docker-compose.yml
GF_SECURITY_ADMIN_PASSWORD=very_strong_password_123
```

---

## 📞 РЕШЕНИЕ ПРОБЛЕМ

### Ошибка "Connection refused"
```bash
# Убедитесь что контейнеры запущены
docker-compose ps

# Перезагрузите
docker-compose restart
```

### Prometheus не видит метрики
```bash
# Проверьте /metrics endpoint
curl http://localhost:8000/metrics

# Проверьте prometheus.yml
docker-compose logs prometheus
```

### Grafana не видит Prometheus
1. Откройте Grafana
2. Configuration → Data Sources
3. Проверьте URL: `http://prometheus:9090`
4. Нажмите "Test"

### Метрики не обновляются
- Проверьте `scrape_interval` в prometheus.yml (по умолчанию 15s)
- Дождитесь обновления или перезагрузитесь

---

## 🎓 БОЛЕЕ СЛОЖНЫЕ МЕТРИКИ

### Добавить custom метрику в код

```python
from prometheus_client import Gauge

# Создать метрику
custom_metric = Gauge(
    'name_of_metric',
    'Description of metric',
    registry=registry  # ВАЖНО!
)

# Обновить значение
custom_metric.set(42)
custom_metric.inc()
custom_metric.dec()
```

### Метрика с labels

```python
transactions_by_type = Counter(
    'transactions_total',
    'Total transactions',
    ['type'],  # labels
    registry=registry
)

# Использование
transactions_by_type.labels(type='payment').inc()
transactions_by_type.labels(type='refund').inc()
```

---

## 📈 ПРОИЗВОДИТЕЛЬНОСТЬ

Рекомендуемые ресурсы:

| Сервис | CPU | RAM | Диск |
|--------|-----|-----|------|
| Bot | 0.5 | 128MB | 1GB |
| Prometheus | 1 | 512MB | 10GB |
| Grafana | 0.5 | 256MB | 1GB |
| Total | 2 | 896MB | 12GB |

---

## 📝 ЛИЦЕНЗИЯ

MIT License - используйте свободно!

---

**Версия:** 2.0 Monitoring Edition
**Последнее обновление:** Январь 2026
**Статус:** Production Ready ✅

Для вопросов: support@coursebot.ru
