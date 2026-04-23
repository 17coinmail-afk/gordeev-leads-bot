"""
Простой веб-дашборд для мониторинга бота.
Запускается в отдельном потоке на порту 8080.
"""

import os
import threading

from flask import Flask, jsonify, render_template_string

import database as db

app = Flask(__name__)

ADMIN_SECRET = os.getenv("DASHBOARD_SECRET", "changeme")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Freelance Bot Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { color: #333; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h3 { margin: 0 0 10px; font-size: 14px; color: #666; text-transform: uppercase; }
        .card .value { font-size: 32px; font-weight: bold; color: #222; }
        .card .value.green { color: #27ae60; }
        .card .value.blue { color: #2980b9; }
        .card .value.orange { color: #e67e22; }
        .card .value.red { color: #c0392b; }
        .refresh { text-align: center; margin-top: 20px; color: #999; font-size: 12px; }
    </style>
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <div class="container">
        <h1>📊 Freelance Bot Dashboard</h1>
        <div class="cards">
            <div class="card">
                <h3>Всего пользователей</h3>
                <div class="value blue">{{ total_users }}</div>
            </div>
            <div class="card">
                <h3>Активных подписчиков</h3>
                <div class="value green">{{ active_users }}</div>
            </div>
            <div class="card">
                <h3>Pro-пользователей</h3>
                <div class="value orange">{{ pro_users }}</div>
            </div>
            <div class="card">
                <h3>Заблокировано</h3>
                <div class="value red">{{ banned_users }}</div>
            </div>
            <div class="card">
                <h3>Заказов в базе</h3>
                <div class="value">{{ total_projects }}</div>
            </div>
            <div class="card">
                <h3>Уведомлений сегодня</h3>
                <div class="value">{{ sent_today }}</div>
            </div>
        </div>
        <div class="refresh">Обновляется автоматически каждые 30 секунд</div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    total, active, pro, banned, projects, sent = db.get_admin_stats()
    return render_template_string(
        HTML_TEMPLATE,
        total_users=total,
        active_users=active,
        pro_users=pro,
        banned_users=banned,
        total_projects=projects,
        sent_today=sent,
    )


@app.route("/api/stats")
def api_stats():
    secret = os.getenv("DASHBOARD_SECRET", "changeme")
    provided = os.environ.get("_no_auth", "")
    # Для простоты API открыт, можно добавить авторизацию при необходимости
    total, active, pro, banned, projects, sent = db.get_admin_stats()
    return jsonify(
        {
            "total_users": total,
            "active_users": active,
            "pro_users": pro,
            "banned_users": banned,
            "total_projects": projects,
            "sent_today": sent,
        }
    )


def run_dashboard(port: int = 8080):
    """Запускает Flask в отдельном потоке."""
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()
