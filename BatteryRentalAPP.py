from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = 'battery.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS battery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'available'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS rental_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_id INTEGER,
            action TEXT,
            timestamp TEXT
        )
    ''')
    
    c.execute("SELECT COUNT(*) FROM battery")
    if c.fetchone()[0] == 0:
        for _ in range(5):
            c.execute("INSERT INTO battery (status) VALUES ('available')")
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, status FROM battery")
    batteries = c.fetchall()
    conn.close()
    return render_template('index.html', batteries=batteries)

@app.route('/rent/<int:battery_id>')
def rent(battery_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'rented' WHERE id = ? AND status = 'available'", (battery_id,))
    if c.rowcount > 0:
        c.execute("INSERT INTO rental_log (battery_id, action, timestamp) VALUES (?, 'rent', ?)",
                  (battery_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/return/<int:battery_id>')
def return_battery(battery_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'available' WHERE id = ? AND status = 'rented'", (battery_id,))
    if c.rowcount > 0:
        c.execute("INSERT INTO rental_log (battery_id, action, timestamp) VALUES (?, 'return', ?)",
                  (battery_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
