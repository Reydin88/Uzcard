from flask import Flask, render_template, request, redirect, send_file
import sqlite3
import pandas as pd
from datetime import datetime

app = Flask(__name__)
DB = "db.sqlite3"

@app.route("/")
def index():
    return redirect("/admin")

@app.route("/admin")
def admin():
    status = request.args.get("status")
    query = "SELECT * FROM requests"
    params = ()
    if status:
        query += " WHERE status=?"
        params = (status,)
    query += " ORDER BY created_at DESC"
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return render_template("admin.html", rows=rows, filter=status)

@app.route("/export")
def export_excel():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM requests", conn)
    path = "requests_export.xlsx"
    df.to_excel(path, index=False)
    conn.close()
    return send_file(path, as_attachment=True)

@app.route("/cards", methods=["GET", "POST"])
def cards():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if request.method == "POST":
        action = request.form.get("action")
        card_id = request.form.get("id")
        if action == "toggle":
            c.execute("UPDATE cards SET active = 1 - active WHERE id = ?", (card_id,))
        elif action == "delete":
            c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        elif action == "add":
            number = request.form.get("number")
            c.execute("INSERT INTO cards (number) VALUES (?)", (number,))
        conn.commit()
    c.execute("SELECT * FROM cards")
    cards = c.fetchall()
    conn.close()
    return render_template("cards.html", cards=cards)

if __name__ == "__main__":
    app.run()