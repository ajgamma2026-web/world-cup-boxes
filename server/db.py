import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "odds.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id      TEXT    NOT NULL,
                fetched_at   TEXT    NOT NULL,
                home_team    TEXT    NOT NULL,
                away_team    TEXT    NOT NULL,
                commence_time TEXT   NOT NULL,
                odds_json    TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_game_id ON snapshots(game_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fetched_at ON snapshots(fetched_at)")


def save_snapshot(game: dict, fetched_at: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO snapshots (game_id, fetched_at, home_team, away_team, commence_time, odds_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                game["id"],
                fetched_at,
                game["home_team"],
                game["away_team"],
                game["commence_time"],
                json.dumps(game["bookmakers"]),
            ),
        )


def get_latest_odds() -> list[dict]:
    """One row per game — the most recent snapshot."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*
            FROM snapshots s
            INNER JOIN (
                SELECT game_id, MAX(fetched_at) AS max_at
                FROM snapshots
                GROUP BY game_id
            ) latest ON s.game_id = latest.game_id AND s.fetched_at = latest.max_at
            ORDER BY s.commence_time
        """).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_history(game_id: str) -> list[dict]:
    """All snapshots for a game, oldest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE game_id = ? ORDER BY fetched_at",
            (game_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["bookmakers"] = json.loads(d.pop("odds_json"))
    d.pop("id", None)           # drop SQLite rowid
    d["id"] = d.pop("game_id")  # expose Odds API game_id as "id"
    return d
