# Server Monitor

Микросервисный монитор состояния серверов на Python + Flask.

## Структура
- **central** — центральный сервер с дашбордом и API
- **node** — агент для сбора метрик с серверов

## Быстрый старт

### 1. Генерация сертификатов (для mTLS)
```bash
python3 generate_certs.py
```

### 2. Настройка окружения
```bash
cp .env.example .env
# Отредактируй .env
```

### 3. Запуск через Docker
```bash
docker-compose up --build
```

### 4. Дашборд
Открой http://localhost:5000

## Функции
- CPU usage с графиками
- Топ-10 процессов по нагрузке
- Сетевые метрики
- Настраиваемая частота опроса
- JWT аутентификация между нодами
- Поддержка нескольких нод

## API
- `GET /api/nodes` — список нод
- `GET /api/nodes/<id>` — детали ноды
- `POST /api/nodes/<id>/config` — обновление конфигурации
- `POST /api/metrics` — endpoint для приема метрик от нод

## Локальный запуск (без Docker)

### Центральный сервер
```bash
cd central
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Нода
```bash
cd node
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
CENTRAL_URL=http://localhost:5000 python agent.py
```
