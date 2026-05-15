from flask import Flask, request, jsonify, render_template
from collections import defaultdict
import os

app = Flask(__name__)

# =========================
# DB切り替え
# =========================

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_SUPABASE = DATABASE_URL is not None
print("DATABASE_URL:", DATABASE_URL)
print("USE_SUPABASE:", USE_SUPABASE)

def get_conn():
    if USE_SUPABASE:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        import sqlite3
        return sqlite3.connect("data.db")


# =========================
# SQLite初期化（ローカルのみ）
# =========================

def init_db():
    if not USE_SUPABASE:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round INTEGER,
            numbers TEXT
        )
        """)
        conn.commit()
        conn.close()


init_db()


# =========================
# 共通：全データ取得
# =========================

def get_all_records():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT round, numbers FROM records")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []
    for r, nums in rows:
        nums = list(map(int, nums.split(",")))
        result.append({"round": r, "numbers": nums})

    return result


# =========================
# ページ
# =========================

@app.route("/")
def index():
    return render_template("index.html")


# =========================
# 記録追加
# =========================

@app.route("/add", methods=["POST"])
def add():
    data = request.json
    nums = data["numbers"]

    conn = get_conn()
    cur = conn.cursor()

    # round取得
    cur.execute("SELECT MAX(round) FROM records")
    r = cur.fetchone()[0]
    r = (r or 0) + 1

    if USE_SUPABASE:
        cur.execute(
            "INSERT INTO records (round, numbers) VALUES (%s, %s)",
            (r, ",".join(map(str, nums)))
        )
    else:
        cur.execute(
            "INSERT INTO records (round, numbers) VALUES (?, ?)",
            (r, ",".join(map(str, nums)))
        )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# 出現確率（3 / 5 / 8）
# =========================

@app.route("/stats")
def stats():
    records = get_all_records()
    n = len(records)

    result = {
        3: {i: 0 for i in range(1, 26)},
        5: {i: 0 for i in range(1, 26)},
        8: {i: 0 for i in range(1, 26)},
    }

    for r in records:
        nums = r["numbers"]

        for limit in [3, 5, 8]:
            subset = nums[:limit]
            for num in subset:
                result[limit][num] += 1

    prob = {}
    for limit in result:
        prob[limit] = {
            k: (result[limit][k] / n * 100) if n else 0
            for k in result[limit]
        }

    return jsonify(prob)


# =========================
# 共起検索（重み付き対応）
# =========================

@app.route("/co_search", methods=["POST"])
def co_search():
    data = request.json
    selected = data["numbers"]
    match_level = data["match"]

    records = get_all_records()

    result = defaultdict(float)

    n = len(selected)

    if match_level == "full":
        threshold = n
    elif match_level == "n-1":
        threshold = n - 1
    elif match_level == "n-2":
        threshold = n - 2
    else:
        threshold = n

    total_weight = 0

    for r in records:
        nums = r["numbers"]
        head = nums[:n]

        match_count = len(set(selected) & set(head))

        if match_count >= threshold:
            weight = match_count / n
            # 強調したい場合
            # weight = (match_count / n) ** 2

            for x in nums[n:]:
                result[x] += weight

            total_weight += weight

    prob = {}
    for k, v in result.items():
        prob[k] = (v / total_weight * 100) if total_weight > 0 else 0

    return jsonify(prob)


# =========================
# PWA
# =========================

@app.route("/manifest.json")
def manifest():
    return {
        "name": "Number Stats",
        "short_name": "Stats",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2196f3"
    }


# =========================
#
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
