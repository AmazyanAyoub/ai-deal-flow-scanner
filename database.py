import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple

DB_NAME = "repo_history.db"

class DatabaseManager:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_name)

    def _init_db(self):
        """Creates the history table if it doesn't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS star_history (
                repo_url TEXT,
                stars INTEGER,
                recorded_at DATETIME,
                PRIMARY KEY (repo_url, recorded_at)
            )
        """)
        conn.commit()
        conn.close()

    def save_snapshot(self, repo_url: str, stars: int):
        """Saves the current star count with a timestamp."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute(
            "INSERT INTO star_history (repo_url, stars, recorded_at) VALUES (?, ?, ?)",
            (repo_url, stars, now)
        )
        conn.commit()
        conn.close()
        print(f"💾 Snapshot saved for {repo_url.split('/')[-1]} ({stars} stars)")

    def get_growth_stats(self, repo_url: str, current_stars: int) -> Tuple[int, bool]:
        """
        Calculates stars gained in the last ~24 hours.
        Returns: (stars_gained, is_real_24h_data)
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Define the '24 Hour' window (18h to 30h ago as per client specs)
        now = datetime.now()
        window_start = now - timedelta(hours=30)
        window_end = now - timedelta(hours=18)
        
        # 2. Find a snapshot in that window
        cursor.execute("""
            SELECT stars, recorded_at FROM star_history
            WHERE repo_url = ? AND recorded_at BETWEEN ? AND ?
            ORDER BY recorded_at DESC
            LIMIT 1
        """, (repo_url, window_start, window_end))
        
        result = cursor.fetchone()
        conn.close()

        if result:
            # Case A: We found a snapshot from yesterday!
            old_stars = result[0]
            growth = current_stars - old_stars
            return growth, True # True = This is real 24h data
        else:
            # Case B: No history (First time seeing this repo)
            # Client Rule: "Temporarily use stars_since_first_seen"
            # Since we just saved the snapshot, current - start = 0, 
            # so for the VERY first run, we might rely on the Adapter to provide "stars_total" as a fallback heuristic
            # BUT per strict logic: Return 0 growth relative to DB, let Adapter handle the heuristic.
            return 0, False # False = This is fallback mode