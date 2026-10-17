# Mini-CRM (MVP)

Браузерная мини-CRM для учёта клиентов, сделок, заказов и задач
с экспортом таблиц в Google Sheets.

Стек: Python 3.11+, FastAPI, SQLite, SQLAlchemy 2, Alembic,
Jinja2 + HTMX, Google OAuth / Drive / Sheets.
(В Docker — Python 3.12.)

## Быстрый старт (локально)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Секреты
cp .env.example .env
python -m app.cli hash-password   # вставьте хеш в ADMIN_PASSWORD_HASH
# SECRET_KEY — любая строка ≥ 32 символов

mkdir -p data backups
python -m app.cli seed-demo       # опционально
make run                          # host/port из APP_HOST / APP_PORT в .env
```

Откройте URL из `APP_BASE_URL` — логин из `.env`
(`ADMIN_USERNAME` / пароль, для которого сгенерирован хеш).

## Docker

```bash
cp .env.example .env
# заполните SECRET_KEY и ADMIN_PASSWORD_HASH
docker compose up -d --build
```

Миграции и бэкап перед миграцией выполняются в `entrypoint`.

## Google Sheets экспорт

1. В Google Cloud включите Drive API, Sheets API, Picker API.
2. OAuth consent: scopes `openid`, `userinfo.email`, `drive.file`.
3. Для `@gmail.com` переведите приложение в **In production**.
4. OAuth Client (Web) redirect:
   `{APP_BASE_URL}/settings/google/oauth/callback`
5. В `.env`:
   - `GOOGLE_OAUTH_CLIENT_ID` / `SECRET`
   - `GOOGLE_TOKEN_ENCRYPTION_KEY`
     (`python -m app.cli gen-key`)
   - `GOOGLE_PICKER_API_KEY`, `GOOGLE_CLOUD_PROJECT_NUMBER`
6. В UI: **Настройки → Подключить Google**.

Каждая выгрузка создаёт **новый** файл Sheets в папке
«CRM Экспорт» (или выбранной через Picker).

## Резервное копирование

- По расписанию `BACKUP_CRON` (по умолчанию 03:00).
- Вручную: `python -m app.cli backup`
- Восстановление: остановите приложение → распакуйте
  `.sqlite3.gz` в путь БД → запустите снова.

## API

После входа: http://localhost:8000/docs  
Префикс JSON API: `/api/v1`. Изменяющие запросы требуют
заголовок `X-CSRF-Token` (cookie `csrf_token`).

## Тесты

```bash
pytest -q
```

## Упрощения MVP

- Автодополнение клиентов — через поле ID (lookup API есть).
- Часть HTMX-сценариев заменена обычными формами с редиректом.
- CLI `google-auth` (Desktop OAuth) — заглушка; основной поток — UI.
