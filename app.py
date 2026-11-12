import os
import sqlite3
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_socketio import SocketIO, emit
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "burner_vault_secret_998877"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
DB_NAME = "burner_vault.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploader TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()
connected_nodes = 0

@app.route("/")
def index():
    if "username" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, sender, content FROM notes ORDER BY id DESC")
    notes = cursor.fetchall()
    cursor.execute("SELECT filename, uploader, timestamp FROM files ORDER BY id DESC")
    files = cursor.fetchall()
    conn.close()
    return render_template("index.html", username=session["username"], notes=notes, files=files)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="වැරදි පරිශීලක නාමයක් හෝ මුරපදයකි!")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        hashed_pw = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except:
            return render_template("register.html", error="මෙම නම දැනටමත් භාවිතා කර ඇත.")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@socketio.on("connect")
def handle_connect():
    global connected_nodes
    connected_nodes += 1
    emit("node_update", {"nodes": connected_nodes}, broadcast=True)

@socketio.on("disconnect")
def handle_disconnect():
    global connected_nodes
    connected_nodes = max(0, connected_nodes - 1)
    emit("node_update", {"nodes": connected_nodes}, broadcast=True)

@app.route("/add_note", methods=["POST"])
def add_note():
    if "username" not in session:
        return redirect(url_for("login"))
    content = request.form["content"].strip()
    if content:
        sender = session["username"]
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (sender, content) VALUES (?, ?)", (sender, content))
        conn.commit()
        note_id = cursor.lastrowid
        conn.close()
        socketio.emit("new_note", {"id": note_id, "sender": sender, "content": content}, broadcast=True)
    return redirect(url_for("index"))

@app.route("/burn_note/<int:note_id>", methods=["POST"])
def burn_note(note_id):
    if "username" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    socketio.emit("note_burned", {"id": note_id}, broadcast=True)
    return redirect(url_for("index"))

@app.route("/upload", methods=["POST"])
def upload_file():
    if "username" not in session:
        return redirect(url_for("login"))
    file = request.files.get("file")
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        uploader = session["username"]
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO files (filename, uploader) VALUES (?, ?)", (filename, uploader))
        conn.commit()
        conn.close()
        socketio.emit("new_file", {"filename": filename, "uploader": uploader}, broadcast=True)
    return redirect(url_for("index"))

@app.route("/uploads/<filename>")
def downloaded_file(filename):
    if "username" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    print("[*] Burner Vault Server active on http://127.0.0.1:5000")
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
