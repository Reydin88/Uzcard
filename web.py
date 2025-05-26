from flask import Flask, render_template, request
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "db.sqlite3"

@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM requests ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("admin.html", rows=rows)

@app.route("/cards")
def cards():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM cards")
    cards = c.fetchall()
    conn.close()
    return render_template("cards.html", cards=cards)

@app.route("/users")
def users():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()
    return render_template("users.html", users=users)

@app.route("/stats")
def stats():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*), SUM(amount) FROM requests WHERE DATE(created_at)=?", (today,))
    stats_today = c.fetchone()
    c.execute("SELECT service, COUNT(*) FROM requests GROUP BY service")
    by_service = c.fetchall()
    conn.close()
    return render_template("stats.html", stats=stats_today, services=by_service)

if __name__ == "__main__":
    app.run()