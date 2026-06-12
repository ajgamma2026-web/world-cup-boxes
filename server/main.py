import os
import requests
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from db import init_db, save_snapshot, get_latest_odds, get_history

API_KEY = os.environ.get("ODDS_API_KEY", "9d2f7dbad04e89a62bf9fa5973d0a991")
SPORT   = "soccer_fifa_world_cup"
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"


# ── fetch + persist ──────────────────────────────────────────────────────────

def fetch_and_store():
    try:
        res = requests.get(ODDS_URL, params={
            "apiKey": API_KEY,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }, timeout=10)
        res.raise_for_status()
        games = res.json()
        ts = datetime.now(timezone.utc).isoformat()
        for game in games:
            if game.get("bookmakers"):
                save_snapshot(game, ts)
        print(f"[{ts}] Stored {len(games)} games")
    except Exception as e:
        print(f"fetch_and_store error: {e}")


# ── lifespan (startup / shutdown) ────────────────────────────────────────────

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    fetch_and_store()                          # immediate fetch on startup
    scheduler.add_job(fetch_and_store, "interval", minutes=10, id="poll")
    scheduler.start()
    yield
    scheduler.shutdown()


# ── app ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="World Cup Boxes API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your GitHub Pages URL in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/api/odds")
def latest_odds():
    """Latest snapshot for every game."""
    return get_latest_odds()


@app.get("/api/odds/{game_id}/history")
def odds_history(game_id: str):
    """All historical snapshots for one game."""
    rows = get_history(game_id)
    if not rows:
        raise HTTPException(404, "No data for this game")
    return rows


@app.post("/api/refresh")
def manual_refresh():
    """Trigger an immediate odds fetch (used by the live update button)."""
    fetch_and_store()
    return {"ok": True, "fetched_at": datetime.now(timezone.utc).isoformat()}
