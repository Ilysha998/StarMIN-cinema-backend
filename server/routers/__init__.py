from routers.movies import router as movies_router
from routers.sessions import router as sessions_router
from routers.tickets import router as tickets_router
from routers.users import router as users_router

__all__ = [
    "movies_router",
    "sessions_router",
    "tickets_router",
    "users_router"
]
