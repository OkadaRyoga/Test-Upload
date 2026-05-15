from flask import Flask, request, jsonify, render_template
import sqlite3
from collections import defaultdict

app = Flask(__name__)
DB = "data.db"


# ------------------------
# DB初期化
# ------------------------
def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round INTEGER,
            numbers TEXT
        )
        """)

init_db()


# ------------------------
# 共通関数
# ------------------------
def get_all_records():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT round, numbers FROM records")
        rows = c.fetchall()

    result = []
    for r, nums in rows:
        nums = list(map(int, nums.split(",")))
        result.append({"round": r, "numbers": nums})

    return result


def get_next_round():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(round) FROM records")
        r = c.fetchone()[0]
        return (r or 0) + 1


# ------------------------
# 画面
# ------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ------------------------
# 記録
# ------------------------
@app.route("/add", methods=["POST"])
def add():
    data = request.json
    nums = data["numbers"]

    r = get_next_round()

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO records (round, numbers) VALUES (?, ?)",
            (r, ",".join(map(str, nums)))
        )

    return jsonify({"status": "ok"})


# ------------------------
# 出現確率
# ------------------------
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

        # 各範囲でチェック
        for limit in [3, 5, 8]:
            subset = nums[:limit]

            for num in subset:
                result[limit][num] += 1

    # 確率化（試行数で割る）
    prob = {}
    for limit in result:
        prob[limit] = {
            k: (result[limit][k] / n * 100) if n else 0
            for k in result[limit]
        }

    return jsonify(prob)


# ------------------------
# 条件付き共起
# ------------------------
@app.route("/co_search", methods=["POST"])
def co_search():
    data = request.json
    selected = data["numbers"]
    match_level = data["match"]

    records = get_all_records()

    result = defaultdict(float)

    n = len(selected)

    # 一致条件
    if match_level == "full":
        threshold = n
    elif match_level == "n-1":
        threshold = n - 1
    elif match_level == "n-2":
        threshold = n - 2
    else:
        threshold = n

    total_weight = 0  # ← 全体重み（確率化用）

    for r in records:
        nums = r["numbers"]
        head = nums[:n]

        match_count = len(set(selected) & set(head))

        if match_count >= threshold:
            # ✅ 重み（ここが重要）
            weight = match_count / n

            # ← ここを変えることで精度調整可能
            # weight = (match_count / n) ** 2  # 強めたいならこれ

            for x in nums[n:]:
                result[x] += weight

            total_weight += weight

    # ✅ 出やすさを確率（％）に変換
    prob = {}
    for k, v in result.items():
        prob[k] = (v / total_weight * 100) if total_weight > 0 else 0

    return jsonify(prob)


# ------------------------
# PWA manifest
# ------------------------
@app.route("/manifest.json")
def manifest():
    return {
        "name": "AnimaLotta Statistics",
        "short_name": "ALS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#FFFFFF",
        "theme_color": "#2196f3"
    }


# ------------------------
#if __name__ == "__main__":
#    app.run(debug=True)
import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))