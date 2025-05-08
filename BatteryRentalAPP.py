from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB = 'battery.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS battery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'available'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rental_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_id INTEGER,
            user_id INTEGER,
            action TEXT,
            timestamp TEXT
        )
    """)
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
    return render_template('index.html', batteries=batteries, user_id=session.get('user_id'))

@app.route('/rent/<int:battery_id>')
def rent(battery_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'rented' WHERE id = ? AND status = 'available'", (battery_id,))
    if c.rowcount > 0:
        c.execute("INSERT INTO rental_log (battery_id, user_id, action, timestamp) VALUES (?, ?, 'rent', ?)",
                  (battery_id, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/return/<int:battery_id>')
def return_battery(battery_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'available' WHERE id = ? AND status = 'rented'", (battery_id,))
    if c.rowcount > 0:
        c.execute("INSERT INTO rental_log (battery_id, user_id, action, timestamp) VALUES (?, ?, 'return', ?)",
                  (battery_id, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username already exists"
        conn.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            return redirect('/')
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
