from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)
DB = "db.sqlite3"

@app.route("/admin")
def admin_panel():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return render_template("admin.html", rows=rows)

if __name__ == "__main__":
    app.run()
