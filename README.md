# Server Monitor

Микросервисный монитор состояния серверов на Python + Flask.

## Структура
- **central** — центральный сервер с дашбордом и API
- **node** — агент для сбора метрик с серверов

## Быстрый старт (Автоматическая установка)

### 1. Запустите установщик
```bash
./install.sh
```

Скрипт автоматически:
- Сгенерирует JWT секрет и пароль админа
- Создаст конфигурацию Docker
- Запустит центральный сервер на порту 5000
- Покажет данные для входа

### 2. Доступ к панели
- URL: `http://<server-ip>:5000`
- Username: `admin`
- Password: сгенерирован автоматически (см. вывод install.sh)

## Функции
- **Веб-аутентификация** — защита панели паролем
- **CPU/RAM мониторинг** — графики в реальном времени
- **Топ-10 процессов** — по нагрузке на CPU
- **Сетевые метрики** — графики трафика
- **Настраиваемый poll interval** — через UI
- **JWT аутентификация** — между нодами и центральным сервером
- **Поддержка IPv4** — подключение по IP или hostname
- **TLS шифрование** — для подключения к внешним серверам
- **Добавление серверов** — через UI без перезапуска

## API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Web | Dashboard (login required) |
| POST | `/login` | — | Web authentication |
| GET | `/api/nodes` | Web | List all nodes |
| GET | `/api/nodes/<id>` | Web | Node details |
| POST | `/api/nodes/<id>/config` | Web | Update node config |
| POST | `/api/metrics` | JWT | Receive metrics from agents |

## Настройка ноды

### Через Docker (рекомендуется)
```bash
cd node
# Отредактируй .env
docker build -t monitor-node .
docker run -d \
  -e CENTRAL_URL=http://<central-ip>:5000 \
  -e NODE_ID=web-server-01 \
  -e JWT_SECRET=<secret> \
  -v /proc:/host/proc:ro \
  --privileged \
  monitor-node
```

### Локальный запуск
```bash
cd node
python3 -m venv venv
source venv/bin/venv/activate
pip install -r requirements.txt

export CENTRAL_URL=http://localhost:5000
export NODE_ID=local-node
export JWT_SECRET=your-secret-here
export POLL_INTERVAL=5

python agent.py
```

## Добавление внешних серверов

1. Нажмите **"+ Add Server"** в панели
2. Введите адрес (IPv4 или hostname): `192.168.1.100:5000`
3. Укажите JWT Secret сервера
4. Сервер появится в списке

**Примечание:** Используется обычный TLS (не mTLS). IPv4 полностью поддерживается.

## Переменные окружения

### Central Server
| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | generated | Секрет для нод |
| `ADMIN_PASSWORD` | generated | Пароль админа |
| `DATA_DIR` | ./data | Директория данных |
| `FLASK_SECRET_KEY` | random | Секрет сессий |

### Node Agent
| Variable | Default | Description |
|----------|---------|-------------|
| `CENTRAL_URL` | required | URL центрального сервера |
| `NODE_ID` | hostname | ID ноды |
| `JWT_SECRET` | required | JWT секрет |
| `POLL_INTERVAL` | 5 | Частота опроса (сек) |

## Безопасность
- Веб-панель защищена аутентификацией
- API между нодами защищено JWT
- Поддержка TLS для внешних подключений
- Все секреты генерируются автоматически при установке
