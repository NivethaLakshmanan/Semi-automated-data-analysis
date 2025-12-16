from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pandas as pd
import os
import threading
import webbrowser
import time
from pathlib import Path
import mysql.connector
from mysql.connector import Error
import re

# -----------------------------
# BASE PATH SETUP
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

RAW_FOLDER = BASE_DIR / "uploads/Raw"
CLEAN_FOLDER = BASE_DIR / "uploads/Cleaned"
TEMPLATE_DIR = BASE_DIR / "templates"

os.makedirs(RAW_FOLDER, exist_ok=True)
os.makedirs(CLEAN_FOLDER, exist_ok=True)

# -----------------------------
# FLASK APP
# -----------------------------
app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
CORS(app)

ALLOWED_EXTENSIONS = {"xlsx", "csv"}

# -----------------------------
# MODULE → FIXED TABLE NAME
# -----------------------------
MODULE_CONFIG = {
    "sales": "sales_orders",
    "purchase": "purchase_orders",
    "bills": "bills",
    "invoices": "invoices",
    "quotation": "quotations"
}

# -----------------------------
# HELPERS
# -----------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_col_name(col):
    s = str(col).lower()
    s = s.replace("\n", " ")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s[:40]

def clean_dataframe(df):
    clean_cols = []
    count = {}

    for col in df.columns:
        base = sanitize_col_name(col)
        if not base:
            base = "col"

        if base in count:
            count[base] += 1
            new = f"{base}_{count[base]}"
        else:
            count[base] = 0
            new = base

        clean_cols.append(new)

    df.columns = clean_cols
    df = df.fillna("UNKNOWN")
    return df

def detect_module(filename):
    f = filename.lower()
    if "sales" in f: return "sales"
    if "purchase" in f: return "purchase"
    if "bill" in f: return "bills"
    if "invoice" in f: return "invoices"
    if "quotation" in f or "estimate" in f: return "quotation"
    return None

# -----------------------------
# MYSQL CONFIG
# -----------------------------
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "Nivema@2005"
MYSQL_DATABASE = "ats_project"

def ensure_table(connection, table_name, df_cols):
    cursor = connection.cursor()

    cols_def = ", ".join([f"`{c}` TEXT" for c in df_cols])
    cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({cols_def})")

    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    existing = [row[0] for row in cursor.fetchall()]

    for c in df_cols:
        if c not in existing:
            cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{c}` TEXT")

    cursor.close()

def insert_rows(df, table_name):
    connection = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

    ensure_table(connection, table_name, df.columns.tolist())
    cursor = connection.cursor()

    cols = ", ".join([f"`{c}`" for c in df.columns])
    ph = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({ph})"

    for _, row in df.iterrows():
        cursor.execute(sql, tuple(row.values))

    connection.commit()
    cursor.close()
    connection.close()

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template("analy.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file"}), 400

    filename = secure_filename(file.filename)
    raw_path = RAW_FOLDER / filename
    file.save(raw_path)

    # Read file
    try:
        if filename.lower().endswith(".xlsx"):
            df = pd.read_excel(raw_path, header=1)
        else:
            df = pd.read_csv(raw_path)
    except Exception as e:
        return jsonify({"error": f"Read error: {e}"}), 400

    df = clean_dataframe(df)

    cleaned_path = CLEAN_FOLDER / f"cleaned_{filename}"
    df.to_excel(cleaned_path, index=False)

    # Detect module
    module = detect_module(filename)
    if module and module in MODULE_CONFIG:
        table = MODULE_CONFIG[module]
    else:
        # Auto table
        table = re.sub(r"[^a-z0-9]+", "_", filename.rsplit(".", 1)[0].lower())[:30]

    # REPLACE MODE FIX (Create-before-delete)
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

    ensure_table(conn, table, df.columns.tolist())

    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM `{table}`")
    conn.commit()
    cursor.close()
    conn.close()

    # Insert new data
    insert_rows(df, table)

    return jsonify({"message": f"Replaced data in table: {table}"}), 200

def open_browser():
    time.sleep(1.5)
    webbrowser.get("windows-default").open("http://127.0.0.1:5000")

if __name__ == "__main__":
    threading.Thread(target=open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
