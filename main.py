import ssl, certifi, urllib.request, feedparser
from fastapi import FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import sqlite3
import os, json
from dotenv import load_dotenv

load_dotenv() 

DB_PATH = "data/news.db"

def db():
    # Создаем папку data, если ее нет
    os.makedirs("data", exist_ok=True) 
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE
            )
        """)

def get_count():
    with db() as con:
        row = con.execute("SELECT COUNT(*) AS c FROM news").fetchone()
    return row["c"]

init_db()

app = FastAPI()
RSS_URL = 'https://news.google.com/rss/search?q="girls+und+panzer"+site:animenewsnetwork.com'

class News(BaseModel):
    title: str
    link: str     

news_list = []

security = HTTPBasic()

ADMINS = json.loads(os.getenv("ADMINS", "{}"))

def check_admin(creds: HTTPBasicCredentials = Depends(security)):
    login = creds.username.strip()
    password = creds.password.strip()

    if ADMINS.get(login) != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return login

@app.get("/news")
def get_news():
    with db() as con:
        rows = con.execute(
            "SELECT id, title, link FROM news ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]

@app.delete("/news/{news_id}")
def delete_news(news_id: int, user: str = Depends(check_admin)):
    with db() as con:
        cur = con.execute("DELETE FROM news WHERE id = ?", (news_id,))
    if cur.rowcount == 0:
        return {"error": "нет такой новости"}
    return {"status": "удалено"}

@app.get("/")
def root():
    feed = fetch_feed()
    added = 0
    for entry in feed.entries[:105]:
        try:
            with db() as con:
                con.execute(
                    "INSERT INTO news (title, link) VALUES (?,  ?)",
                    (entry.title, entry.link)
                )
            added += 1
        except sqlite3.IntegrityError:
            pass
    return {"добавлено": added, "всего в базе": get_count()}



# Парсер 
def fetch_feed():
    context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, context=context, timeout=30) as response:
        data = response.read()
    return feedparser.parse(data)



