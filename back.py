from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pandas as pd
import os
import sys
import threading
import webbrowser
import time
from pathlib import Path
import pymysql
import re

# -----------------------------
# RESOURCE PATH (PyInstaller safe)
# -----------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).resolve().parent
    return Path(base_path) / relative_path

# -----------------------------
# BASE PATH SETUP
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

RAW_FOLDER = BASE_DIR / "uploads/Raw"
CLEAN_FOLDER = BASE_DIR / "uploads/Cleaned"
TEMPLATE_DIR = str(resource_path("templates"))

os.makedirs(RAW_FOLDER, exist_ok=True)
os.makedirs(CLEAN_FOLDER, exist_ok=True)

# -----------------------------
# FLASK APP
# -----------------------------
app = Flask(__name__, template_folder=TEMPLATE_DIR)
CORS(app)

ALLOWED_EXTENSIONS = {"xlsx", "csv"}

# -----------------------------
# MODULE → TABLE MAP
# -----------------------------
MODULE_CONFIG = {
    "sales": "sales_orders",
    "purchase": "purchase_orders",
    "bills": "bills",
    "invoices": "invoices",
    "quote": "quote_details_3"
}

# -----------------------------
# HELPERS
# -----------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_col_name(col):
    s = str(col).lower().strip()
    s = s.replace("\n", " ")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")[:40]

def clean_dataframe(df):
    clean_cols = []
    count = {}

    for col in df.columns:
        base = sanitize_col_name(col) or "col"
        if base in count:
            count[base] += 1
            base = f"{base}_{count[base]}"
        else:
            count[base] = 0
        clean_cols.append(base)

    df.columns = clean_cols

    # KEEP empty values → fill later
    df = df.fillna("UNKNOWN")

    # Remove lbv_automation column if exists
    if "lbv_automation" in df.columns:
        df = df.drop(columns=["lbv_automation"])

    return df

def detect_module(filename):
    f = filename.lower()
    if "quote" in f: return "quote"
    if "sales" in f or "order" in f: return "sales"
    if "purchase" in f: return "purchase"
    if "bill" in f: return "bills"
    if "invoice" in f: return "invoices"
    return None

# -----------------------------
# MYSQL CONFIG
# -----------------------------
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your password",
    "database": "your database",
    "cursorclass": pymysql.cursors.Cursor
}

def get_connection():
    conn = pymysql.connect(**MYSQL_CONFIG)
    with conn.cursor() as cursor:
        cursor.execute("USE ats_project")
    return conn

# -----------------------------
# DATABASE FUNCTIONS
# -----------------------------
def ensure_table(connection, table_name, df_cols):
    with connection.cursor() as cursor:
        cols_def = ", ".join([f"`{c}` TEXT" for c in df_cols])
        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({cols_def})")

        cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
        existing = [row[0] for row in cursor.fetchall()]

        for c in df_cols:
            if c not in existing:
                cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{c}` TEXT")

    connection.commit()

def insert_rows(df, table_name):
    connection = get_connection()
    ensure_table(connection, table_name, df.columns.tolist())

    with connection.cursor() as cursor:
        cols = ", ".join([f"`{c}`" for c in df.columns])
        placeholders = ", ".join(["%s"] * len(df.columns))
        sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})"
        cursor.executemany(sql, df.values.tolist())

    connection.commit()
    connection.close()

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template("analy.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    print("Upload request received")
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Empty filename"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Unsupported file"}), 400

        original_filename = file.filename
        filename = secure_filename(original_filename)
        raw_path = RAW_FOLDER / filename
        file.save(raw_path)

        # -----------------------------
        # READ FILE (ZOHO BOOKS FIX)
        # -----------------------------
        if filename.lower().endswith(".xlsx"):
            df = pd.read_excel(raw_path, header=None)
        else:
            df = pd.read_csv(raw_path, header=None)

        # Row 0 -> Company name & date
        # Row 1 -> Actual headers
        df.columns = df.iloc[1]
        df = df.iloc[2:].reset_index(drop=True)

        # Clean dataframe
        df = clean_dataframe(df)

        # Save cleaned file
        df.to_excel(CLEAN_FOLDER / f"cleaned_{filename}", index=False)

        module = detect_module(original_filename)
        if module not in MODULE_CONFIG:
            return jsonify({
                "error": f"Cannot map file '{original_filename}' to any module"
            }), 400

        table = MODULE_CONFIG[module]

        print("UPLOAD DEBUG:", original_filename, table, len(df))

        # REPLACE MODE
        conn = get_connection()
        ensure_table(conn, table, df.columns.tolist())
        with conn.cursor() as cursor:
            cursor.execute(f"DELETE FROM `{table}`")
        conn.commit()
        conn.close()

        insert_rows(df, table)

        return jsonify({
            "status": "success",
            "table": table,
            "rows_inserted": len(df)
        }), 200

    except Exception as e:
        print("UPLOAD ERROR:", str(e))
        return jsonify({
            "status": "failed",
            "error": str(e)
        }), 500

# -----------------------------
# AUTO OPEN BROWSER
# -----------------------------
def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    threading.Thread(target=open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)

