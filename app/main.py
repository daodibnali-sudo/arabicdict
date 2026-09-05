from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .morphology.analyzer import analyze

app = FastAPI(title="Arabic-English Dictionary")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.middleware("http")
async def no_cache(request, call_next):
    # This app is under active iteration — a stale cached app.js/style.css after
    # an update is a worse failure mode (silently missing features) than the
    # minor cost of always refetching on a local dev server.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/search")
def search(q: str):
    return analyze(q)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
