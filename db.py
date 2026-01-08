import sqlite3
from datetime import date

DB = "data.db"

def conn():
    return sqlite3.connect(DB)

def init_db():
    c = conn().cursor()
    # Maçlar tablosu
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            league TEXT,
            home TEXT,
            away TEXT,
            hg INTEGER DEFAULT 0,
            ag INTEGER DEFAULT 0,
            played INTEGER DEFAULT 0
        )
    """)
    # Bahis tablosu
    c.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            market TEXT,
            prob REAL,
            result INTEGER DEFAULT 0,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    conn().commit()

# ------------------ KAYIT FONKSIYONLARI ------------------

def save_match(match_date, league, home, away, markets_json=None):
    c = conn().cursor()
    c.execute("INSERT INTO matches (date, league, home, away) VALUES (?,?,?,?)",
              (match_date, league, home, away))
    mid = c.lastrowid
    conn().commit()
    return mid

def save_bet(match_id, market, prob):
    c = conn().cursor()
    c.execute("INSERT INTO bets (match_id, market, prob) VALUES (?,?,?)",
              (match_id, market, prob))
    conn().commit()

def get_pending_matches():
    c = conn().cursor()
    c.execute("SELECT id, date, league, home, away FROM matches WHERE played=0")
    return c.fetchall()

def save_score(match_id, hg, ag):
    c = conn().cursor()
    c.execute("UPDATE matches SET hg=?, ag=?, played=1 WHERE id=?", (hg, ag, match_id))
    conn().commit()

def settle_bets(match_id, hg, ag):
    c = conn().cursor()
    # Örnek: MS1, MS2, X için basit sonuç hesaplama
    c.execute("SELECT id, market FROM bets WHERE match_id=?", (match_id,))
    rows = c.fetchall()
    for bid, market in rows:
        if market=="MS1":
            res = 1 if hg>ag else 0
        elif market=="MS2":
            res = 1 if hg<ag else 0
        elif market=="X":
            res = 1 if hg==ag else 0
        else:
            res = 0
        c.execute("UPDATE bets SET result=? WHERE id=?", (res, bid))
    conn().commit()

def get_dashboard_data():
    c = conn().cursor()
    c.execute("""
        SELECT matches.date, league, home, away, hg, ag, market, prob, result
        FROM bets JOIN matches ON bets.match_id=matches.id
        WHERE played=1
        ORDER BY matches.date DESC
    """)
    return c.fetchall()
