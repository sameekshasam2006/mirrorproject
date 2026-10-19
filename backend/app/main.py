from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.calendar import router as calendar_router
from app.api.notifications import router as notifications_router
from app.api.simulations import router as simulations_router
from app.api.tasks import router as tasks_router
from app.api.users import router as users_router
from app.config import settings
from app.db import Base, ensure_database_schema, engine

app = FastAPI(title="MIRROR API", version="1.0.0")

allowed_origins = [settings.frontend_origin]
if settings.app_env.lower() != "production":
    allowed_origins.extend(
        [
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
ensure_database_schema()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(calendar_router, prefix="/calendar", tags=["calendar"])
app.include_router(simulations_router, prefix="/simulations", tags=["simulations"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name}
