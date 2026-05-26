# StarMIN Cinema Backend

Бэкенд кинотеатра на FastAPI + SQLAlchemy + SQLite.

## Запуск

```bash
cd server
pip install -r requirements.txt
python main.py
```

Тест API: http://localhost:8000/docs

## Структура

```
server/
├── main.py              # FastAPI app
├── config.py            # Настройки (из .env)
├── database.py          # SQLite подключение
├── models.py            # SQLAlchemy модели
├── schemas.py           # Pydantic схемы данных
├── auth.py              # JWT авторизация юзеров
├── session_manager.py   # Автогенерация сеансов посуточно в 12 ночи
├── routers/             # Эндпоинты по темам
│   ├── movies.py
│   ├── sessions.py
│   ├── tickets.py
│   └── users.py
├── .env                 # Локальные настройки (в гитигноре)
└── .env.example         # Шаблон настроек (убрать .example, поменять данные)
../database/
└── cinema.db            # SQLite БД
```

## Модели

- **Movie** — название, жанр, длительность, возрастное ограничение
- **Session** — фильм, дата/время, зал (1/2/vip), цена
- **Ticket** — сеанс, пользователь, место, оплата
- **User** — логин, хеш пароля, is_admin

## Авторизация

JWT Bearer. /docs → Authorize → username/password.

## Конфигурация

Все настройки в `config.py`, переопределяются насильно через `.env`.

## Словарь

- Сеанс/Session - показ определенного фильма в определенное время