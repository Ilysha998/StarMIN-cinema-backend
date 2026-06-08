import threading
import random
from datetime import datetime, timedelta
from database import SessionLocal, init_db
from models import Movie, Session as SessionModel, Hall
from config import settings, DEFAULT_HALL_LAYOUTS


def seed_halls():
    db = SessionLocal()
    try:
        existing = db.query(Hall).first()
        if existing:
            return

        for name, cfg in DEFAULT_HALL_LAYOUTS.items():
            db.add(Hall(
                name=name,
                layout=cfg["layout"],
                break_minutes=cfg["break_minutes"],
                base_price=cfg["base_price"],
            ))
        db.commit()
        print(f"SM: Залы созданы ({len(DEFAULT_HALL_LAYOUTS)} залов)")
    except Exception as e:
        db.rollback()
        print(f"SM: Ошибка при создании залов: {e}")
    finally:
        db.close()


def seed_movie_pool():
    db = SessionLocal()
    try:
        existing = db.query(Movie).first()
        if existing:
            return

        for movie_data in settings.MOVIE_POOL:
            db.add(Movie(**movie_data))
        db.commit()
        print(f"SM: Пул фильмов заполнен ({len(settings.MOVIE_POOL)} фильмов)")
    except Exception as e:
        db.rollback()
        print(f"SM: Ошибка при заполнении пула: {e}")
    finally:
        db.close()


def _is_age_allowed_at_hour(age_restriction: int, hour: int) -> bool:
    if age_restriction <= 6:
        return True
    if age_restriction <= 12:
        return True
    if age_restriction <= 16:
        return hour >= 16
    return hour >= 21


def generate_sessions_for_date(target_date: datetime):
    db = SessionLocal()
    try:
        existing = db.query(SessionModel).filter(
            SessionModel.datetime >= target_date.replace(hour=0, minute=0, second=0),
            SessionModel.datetime < target_date.replace(hour=0, minute=0, second=0) + timedelta(days=1),
        ).count()
        if existing > 0:
            return 0

        movies = db.query(Movie).all()
        if not movies:
            return 0

        halls = db.query(Hall).all()
        if not halls:
            return 0

        created = 0

        for hall in halls:
            base_price = hall.base_price
            break_min = hall.break_minutes
            current_time = target_date.replace(hour=settings.FIRST_SESSION_HOUR, minute=0, second=0, microsecond=0)
            end_limit = target_date.replace(hour=settings.LAST_SESSION_HOUR, minute=59, second=59, microsecond=0)
            used_movies = []

            while current_time <= end_limit:
                candidates = [
                    m for m in movies
                    if _is_age_allowed_at_hour(m.age_restriction, current_time.hour)
                ]
                if not candidates:
                    current_time += timedelta(minutes=30)
                    continue

                if len(used_movies) >= len(candidates):
                    used_movies = []

                available = [m for m in candidates if m.id not in used_movies]
                if not available:
                    used_movies = []
                    available = candidates

                movie = random.choice(available)
                used_movies.append(movie.id)

                price = base_price
                if current_time.hour >= settings.PRICE_EVENING_AFTER_HOUR:
                    price = round(base_price * settings.PRICE_EVENING_MULTIPLIER)
                if current_time.hour < settings.PRICE_MORNING_BEFORE_HOUR:
                    price = round(base_price * settings.PRICE_MORNING_MULTIPLIER)

                session = SessionModel(
                    movie_id=movie.id,
                    datetime=current_time,
                    hall_id=hall.id,
                    price=float(price),
                )
                db.add(session)
                created += 1

                current_time += timedelta(minutes=movie.duration + break_min)

        db.commit()
        print(f"SM: Сгенерировано {created} сеансов на {target_date.strftime('%Y-%m-%d')}")
        return created
    except Exception as e:
        db.rollback()
        print(f"SM: Ошибка генерации сеансов: {e}")
        return 0
    finally:
        db.close()


def cleanup_past_sessions():
    db = SessionLocal()
    try:
        now = datetime.now()
        cutoff = now - timedelta(hours=settings.CLEANUP_HOURS_AGO)
        old = db.query(SessionModel).filter(SessionModel.datetime < cutoff).all()
        for s in old:
            db.delete(s)
        db.commit()
        if old:
            print(f"SM: Удалено {len(old)} прошедших сеансов")
    except Exception as e:
        db.rollback()
        print(f"SM: Ошибка очистки: {e}")
    finally:
        db.close()


class SessionScheduler:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None

    def _run_daily(self):
        init_db()
        seed_halls()
        seed_movie_pool()
        generate_sessions_for_date(datetime.now())
        generate_sessions_for_date(datetime.now() + timedelta(days=1))

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            next_midnight = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=5, microsecond=0
            )
            wait_seconds = (next_midnight - now).total_seconds()

            if self._stop_event.wait(timeout=min(wait_seconds, 60)):
                break

            if datetime.now().hour == 0 and datetime.now().minute < 5:
                try:
                    cleanup_past_sessions()
                    generate_sessions_for_date(datetime.now() + timedelta(days=1))
                except Exception as e:
                    print(f"SM: Ошибка в полуночной задаче: {e}")
                self._stop_event.wait(timeout=300)

    def start(self):
        print("SM: Запуск...")
        self._run_daily()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        print("SM: Полуночный планировщик активен")

    def stop(self):
        print("SM: Остановка...")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        print("SM: Остановлен")


scheduler = SessionScheduler()
