import sqlite3
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self, db_name="investment_signals.db"):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            # Pour calculer les deltas (Point 4 & 6.1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_history (
                    url TEXT, stars INTEGER, forks INTEGER, recorded_at DATETIME,
                    PRIMARY KEY (url, recorded_at)
                )
            """)
            # Pour éviter les doublons IA (Point 2)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_items (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    stars_total INTEGER,
                    velocity INTEGER,  -- This represents stars_24h/daily_average
                    prod_score INTEGER,
                    raw_text TEXT,
                    decision TEXT,     -- 'PUBLISH' or 'REJECT'
                    score INTEGER,     -- The VC Score (0-30)
                    processed_at DATETIME
                )
            """)
    def save_snapshot(self, url, stars, forks):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("INSERT OR REPLACE INTO metrics_history VALUES (?, ?, ?, ?)",
                        (url, stars, forks, datetime.now()))

    def get_deltas(self, url, current_stars, current_forks):
        now = datetime.now()
        # Fenêtre exigée par le client : 18-30h (Point 4)
        start, end = now - timedelta(hours=30), now - timedelta(hours=18)
        
        with sqlite3.connect(self.db_name) as conn:
            res = conn.execute("""
                SELECT stars, forks FROM metrics_history 
                WHERE url=? AND recorded_at BETWEEN ? AND ? 
                ORDER BY recorded_at DESC LIMIT 1
            """, (url, start, end)).fetchone()
            
            if res:
                return (max(0, current_stars - res[0]), max(0, current_forks - res[1]), True)
            
            # Fallback : stars_since_first_seen (Point 4)
            first = conn.execute("SELECT stars, forks FROM metrics_history WHERE url=? ORDER BY recorded_at ASC LIMIT 1", (url,)).fetchone()
            if first:
                return (max(0, current_stars - first[0]), max(0, current_forks - first[1]), False)
            return (0, 0, False)

    def is_judged(self, url):
        with sqlite3.connect(self.db_name) as conn:
            return conn.execute("SELECT url FROM processed_items WHERE url=?", (url,)).fetchone() is not None

    def mark_processed(self, project, decision, score):
        """
        Saves the full project details + verdict to the archive.
        """
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO processed_items 
                (url, title, description, stars_total, velocity, prod_score, raw_text, decision, score, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.url,
                project.title,
                project.description,
                project.metrics.stars_total,
                project.metrics.stars_24h,       # This is the Velocity
                project.signals.production_signals, # The Score
                project.raw_text,
                decision,
                score,
                datetime.now()
            ))

    # Add this inside DatabaseManager class in database.py
    def has_history(self, url):
        with sqlite3.connect(self.db_name) as conn:
            # Check if we have ANY snapshot for this url
            return conn.execute("SELECT 1 FROM metrics_history WHERE url=? LIMIT 1", (url,)).fetchone() is not None
        
    def is_waiting_room(self, url):
        # Returns True if we saw this project less than 18 hours ago.
        # This means it is still "Incubating" and we should silently skip it.
        limit = datetime.now() - timedelta(hours=18)
        with sqlite3.connect(self.db_name) as conn:
            # Check if we have a record NEWER than the limit
            return conn.execute(
                "SELECT 1 FROM metrics_history WHERE url=? AND recorded_at > ? LIMIT 1", 
                (url, limit)
            ).fetchone() is not None