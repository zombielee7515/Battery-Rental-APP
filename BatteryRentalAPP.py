from flask import Flask, render_template, request, redirect, session, jsonify
from flask_restful import Api, Resource
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
api = Api(app)
DB = 'battery.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS battery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'available',
            reserved_by INTEGER DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rental_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_id INTEGER,
            user_id INTEGER,
            action TEXT,
            timestamp TEXT,
            start_time TEXT,
            end_time TEXT,
            duration INTEGER,
            fee INTEGER
        )
    """)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, is_admin) VALUES ('admin', 'admin', 1)")
    c.execute("SELECT COUNT(*) FROM battery")
    if c.fetchone()[0] == 0:
        for _ in range(5):
            c.execute("INSERT INTO battery (status) VALUES ('available')")
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB)

def is_admin():
    if 'user_id' not in session:
        return False
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, status, reserved_by FROM battery")
    batteries = c.fetchall()
    conn.close()
    return render_template('index.html', batteries=batteries, user_id=session.get('user_id'), is_admin=is_admin())

@app.route('/rent/<int:battery_id>')
def rent(battery_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    now = datetime.now().isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, reserved_by FROM battery WHERE id = ?", (battery_id,))
    result = c.fetchone()
    if not result:
        return "Battery not found"
    status, reserved_by = result
    if status == 'reserved' and reserved_by != user_id:
        return "This battery is reserved by another user."
    c.execute("UPDATE battery SET status = 'rented', reserved_by = NULL WHERE id = ?", (battery_id,))
    if c.rowcount > 0:
        c.execute("INSERT INTO rental_log (battery_id, user_id, action, timestamp, start_time) VALUES (?, ?, 'rent', ?, ?)",
                  (battery_id, user_id, now, now))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/return/<int:battery_id>')
def return_battery(battery_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    now = datetime.now()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'available' WHERE id = ? AND status = 'rented'", (battery_id,))
    if c.rowcount > 0:
        c.execute("SELECT start_time FROM rental_log WHERE battery_id = ? AND user_id = ? AND action = 'rent' ORDER BY id DESC LIMIT 1", (battery_id, user_id))
        row = c.fetchone()
        if row and row[0]:
            start_dt = datetime.fromisoformat(row[0])
            duration = max(1, int((now - start_dt).total_seconds() // 60))
            fee = max(1000, duration * 100)
            c.execute("INSERT INTO rental_log (battery_id, user_id, action, timestamp, end_time, duration, fee) VALUES (?, ?, 'return', ?, ?, ?, ?)",
                      (battery_id, user_id, now.isoformat(), now.isoformat(), duration, fee))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/reserve/<int:battery_id>')
def reserve_battery(battery_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'reserved', reserved_by = ? WHERE id = ? AND status = 'available'", (user_id, battery_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/cancel_reservation/<int:battery_id>')
def cancel_reservation(battery_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE battery SET status = 'available', reserved_by = NULL WHERE id = ? AND reserved_by = ?", (battery_id, user_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
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
        conn = get_db()
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

@app.route('/admin')
def admin():
    if not is_admin():
        return "Access Denied"
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, status FROM battery")
    batteries = c.fetchall()
    c.execute("SELECT battery_id, user_id, action, timestamp, duration, fee FROM rental_log ORDER BY timestamp DESC")
    logs = c.fetchall()
    conn.close()
    return render_template("admin.html", batteries=batteries, logs=logs)

@app.route('/admin/add_battery', methods=['POST'])
def add_battery():
    if not is_admin():
        return "Access Denied"
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO battery (status) VALUES ('available')")
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/delete_battery/<int:battery_id>')
def delete_battery(battery_id):
    if not is_admin():
        return "Access Denied"
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM battery WHERE id = ?", (battery_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

# ---------- RESTful API ----------
class BatteryList(Resource):
    def get(self):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, status, reserved_by FROM battery")
        rows = c.fetchall()
        conn.close()
        return jsonify([
            {"id": row[0], "status": row[1], "reserved_by": row[2]} for row in rows
        ])

class RentBattery(Resource):
    def post(self):
        user_id = request.json.get("user_id")
        battery_id = request.json.get("battery_id")
        if not user_id or not battery_id:
            return {"error": "Missing user_id or battery_id"}, 400
        now = datetime.now().isoformat()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT status, reserved_by FROM battery WHERE id = ?", (battery_id,))
        result = c.fetchone()
        if not result:
            return {"error": "Battery not found"}, 404
        status, reserved_by = result
        if status == 'reserved' and reserved_by != user_id:
            return {"error": "Battery reserved by another user"}, 403
        c.execute("UPDATE battery SET status = 'rented', reserved_by = NULL WHERE id = ?", (battery_id,))
        c.execute("INSERT INTO rental_log (battery_id, user_id, action, timestamp, start_time) VALUES (?, ?, 'rent', ?, ?)",
                  (battery_id, user_id, now, now))
        conn.commit()
        conn.close()
        return {"message": "Battery rented successfully"}

class ReturnBattery(Resource):
    def post(self):
        user_id = request.json.get("user_id")
        battery_id = request.json.get("battery_id")
        now = datetime.now()
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE battery SET status = 'available' WHERE id = ? AND status = 'rented'", (battery_id,))
        if c.rowcount > 0:
            c.execute("SELECT start_time FROM rental_log WHERE battery_id = ? AND user_id = ? AND action = 'rent' ORDER BY id DESC LIMIT 1", (battery_id, user_id))
            row = c.fetchone()
            if row and row[0]:
                start_dt = datetime.fromisoformat(row[0])
                duration = max(1, int((now - start_dt).total_seconds() // 60))
                fee = max(1000, duration * 100)
                c.execute("INSERT INTO rental_log (battery_id, user_id, action, timestamp, end_time, duration, fee) VALUES (?, ?, 'return', ?, ?, ?, ?)",
                          (battery_id, user_id, now.isoformat(), now.isoformat(), duration, fee))
        conn.commit()
        conn.close()
        return {"message": "Battery returned successfully"}

api.add_resource(BatteryList, '/api/batteries')
api.add_resource(RentBattery, '/api/rent')
api.add_resource(ReturnBattery, '/api/return')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
