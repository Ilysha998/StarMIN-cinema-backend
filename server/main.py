from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import movies_router, sessions_router, tickets_router, users_router
from session_manager import scheduler
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Инициализация базы данных...")
    init_db()
    print("База данных инициализирована!")
    scheduler.start()
    yield
    scheduler.stop()
    print("Приложение остановлено")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",
    openapi_url="/openapi.json",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

app.include_router(movies_router)
app.include_router(sessions_router)
app.include_router(tickets_router)
app.include_router(users_router)


@app.get("/", tags=["Info"])
def read_root():
    return {
        "message": f"Добро пожаловать в {settings.APP_NAME}!",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "openapi_schema": "/openapi.json"
    }


@app.get("/health", tags=["Info"])
def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
