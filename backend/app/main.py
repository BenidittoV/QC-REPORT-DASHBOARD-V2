from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.routers import admin, auth, dashboard
from app.seed import seed_default_users


def _get_cors_origins() -> list[str]:
    raw = settings.cors_origins.strip()
    if raw == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(title=settings.app_name, version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        seed_default_users(db)
    finally:
        db.close()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    simplified = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "Input tidak valid")
        simplified.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=422,
        content={
            "detail": "; ".join(simplified) or "Request tidak valid",
            "errors": exc.errors(),
        },
    )


@app.get("/")
def root():
    return {
        "ok": True,
        "message": "QC Dashboard API aktif",
        "docs": "/docs",
    }
