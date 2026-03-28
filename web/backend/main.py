from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, API_HOST, API_PORT
from routers import auth, characters, events, attendance, admin, templates, changelog

app = FastAPI(title="WoW Raid Bot API", version="1.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://raids.wrathofmidnight.org",
        "http://localhost:5173",  # For local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(changelog.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "WoW Raid Bot API", "version": "1.6.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)
