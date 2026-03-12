#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
import re
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ChatMember, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Flask for keeping the bot alive
from flask import Flask, jsonify, render_template_string
import os

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8325285069:AAHLmn__ebAMG7gZy6WL-COq4BbCqvkcVVs"  # Replace with your actual token
OWNER_ID = 8469461108
DATABASE_FILE = "bot_database.sqlite3"

# Conversation states
ASK_CHAT_ID, CONFIRM_ADD = range(2)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FLASK DASHBOARD ====================
app = Flask(__name__)

def bold_unicode(text: str) -> str:
    bold_map = {
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆',
        'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍',
        'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑', 'S': '𝐒', 'T': '𝐓', 'U': '𝐔',
        'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟', 'g': '𝐠',
        'h': '𝐡', 'i': '𝐢', 'j': '𝐣', 'k': '𝐤', 'l': '𝐥', 'm': '𝐦', 'n': '𝐧',
        'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫', 's': '𝐬', 't': '𝐭', 'u': '𝐮',
        'v': '𝐯', 'w': '𝐰', 'x': '𝐱', 'y': '𝐲', 'z': '𝐳',
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔',
        '7': '𝟕', '8': '𝟖', '9': '𝟗'
    }
    result = ""
    for char in text:
        result += bold_map.get(char, char)
    return result

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .dashboard {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
            width: 90%;
            max-width: 800px;
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        .stat-card h3 {
            margin: 0;
            font-size: 1.2em;
            opacity: 0.9;
        }
        .stat-card .value {
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }
        .status {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            border-left: 5px solid #28a745;
        }
        .status.online {
            border-left-color: #28a745;
        }
        .refresh-btn {
            display: block;
            width: 200px;
            margin: 0 auto;
            padding: 12px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
            text-decoration: none;
        }
        .refresh-btn:hover {
            background: #764ba2;
            transform: scale(1.05);
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 0.9em;
        }
        .bot-name {
            font-weight: bold;
            color: #667eea;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #667eea;
            color: white;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .section-title {
            font-size: 1.5em;
            margin: 20px 0 10px;
            color: #333;
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <h1>🤖 Bot Control Panel</h1>
        
        <div class="status online">
            <strong>🟢 Bot Status:</strong> Online and running smoothly
        </div>
        
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <h3>Total Users</h3>
                <div class="value" id="total-users">{{ total_users_bold }}</div>
            </div>
            <div class="stat-card">
                <h3>Total Groups</h3>
                <div class="value" id="total-groups">{{ total_groups_bold }}</div>
            </div>
            <div class="stat-card">
                <h3>Maintenance</h3>
                <div class="value" id="maintenance">{{ maintenance_bold }}</div>
            </div>
            <div class="stat-card">
                <h3>Uptime</h3>
                <div class="value" id="uptime">{{ uptime_bold }}</div>
            </div>
        </div>

        <div class="section-title">📊 Recent Groups</div>
        <table id="groups-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Owner ID</th>
                    <th>Added Date</th>
                </tr>
            </thead>
            <tbody>
                {% for group in recent_groups %}
                <tr>
                    <td>{{ group.group_id }}</td>
                    <td>{{ group.title }}</td>
                    <td>{{ group.owner_id }}</td>
                    <td>{{ group.added_date[:10] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <a href="/" class="refresh-btn">🔄 Refresh Dashboard</a>
        
        <div class="footer">
            <span class="bot-name">Premium Group Bot</span> | Powered by Telegram
        </div>
    </div>
</body>
</html>
"""

def get_db_stats():
    """Fetch stats from database for dashboard"""
    db = DatabaseManager(DATABASE_FILE)
    stats = db.get_stats()
    recent_groups = db.get_all_groups()[:5]
    stats['total_users_bold'] = bold_unicode(str(stats['total_users']))
    stats['total_groups_bold'] = bold_unicode(str(stats['total_groups']))
    stats['maintenance_bold'] = bold_unicode("✅ Active" if stats['maintenance'] else "❌ Inactive")
    stats['uptime_bold'] = bold_unicode("24/7")
    return stats, recent_groups

@app.route('/')
def dashboard():
    stats, recent_groups = get_db_stats()
    return render_template_string(
        DASHBOARD_HTML,
        total_users_bold=stats['total_users_bold'],
        total_groups_bold=stats['total_groups_bold'],
        maintenance_bold=stats['maintenance_bold'],
        uptime_bold=stats['uptime_bold'],
        recent_groups=recent_groups
    )

@app.route('/stats')
def stats_json():
    stats, recent_groups = get_db_stats()
    return jsonify({
        'stats': stats,
        'recent_groups': [dict(group) for group in recent_groups]
    })

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== DATABASE MANAGER ====================
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    join_date TEXT NOT NULL,
                    username TEXT,
                    full_name TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    group_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    added_date TEXT NOT NULL,
                    locked INTEGER DEFAULT 0,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    admin_id INTEGER NOT NULL,
                    reason TEXT,
                    date TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value) 
                VALUES ('maintenance_mode', 'false')
            """)
            conn.commit()
    
    def add_user(self, user_id: int, username: str = None, full_name: str = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, join_date, username, full_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, datetime.now().isoformat(), username, full_name))
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_users(self) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY join_date DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def add_group(self, group_id: int, title: str, owner_id: int) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO groups (group_id, title, owner_id, added_date)
                    VALUES (?, ?, ?, ?)
                """, (group_id, title, owner_id, datetime.now().isoformat()))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_group(self, group_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))
            conn.commit()
    
    def get_user_groups(self, owner_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM groups 
                WHERE owner_id = ? 
                ORDER BY added_date DESC
            """, (owner_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_groups(self) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM groups 
                ORDER BY added_date DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_group(self, group_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def set_group_lock(self, group_id: int, locked: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE groups SET locked = ? WHERE group_id = ?", (1 if locked else 0, group_id))
            conn.commit()
    
    def is_group_locked(self, group_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT locked FROM groups WHERE group_id = ?", (group_id,))
            row = cursor.fetchone()
            return row and row['locked'] == 1
    
    def add_warning(self, user_id: int, group_id: int, admin_id: int, reason: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO warnings (user_id, group_id, admin_id, reason, date)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, group_id, admin_id, reason, datetime.now().isoformat()))
            conn.commit()
    
    def get_warnings(self, user_id: int, group_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM warnings 
                WHERE user_id = ? AND group_id = ?
                ORDER BY date DESC
            """, (user_id, group_id))
            return [dict(row) for row in cursor.fetchall()]
    
    def clear_warnings(self, user_id: int, group_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM warnings WHERE user_id = ? AND group_id = ?", (user_id, group_id))
            conn.commit()
    
    def is_maintenance_mode(self) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'maintenance_mode'")
            row = cursor.fetchone()
            return row['value'] == 'true' if row else False
    
    def set_maintenance_mode(self, enabled: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE settings SET value = ? WHERE key = 'maintenance_mode'",
                ('true' if enabled else 'false',)
            )
            conn.commit()
    
    def get_stats(self) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            total_users = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) as count FROM groups")
            total_groups = cursor.fetchone()['count']
            maintenance = self.is_maintenance_mode()
            return {
                'total_users': total_users,
                'total_groups': total_groups,
                'maintenance': maintenance
            }

# ==================== MESSAGE FORMATTER ====================
class MessageFormatter:
    @staticmethod
    def welcome_message(user_data: Dict, group_title: str) -> str:
        full_name = user_data.get('full_name', 'User')
        user_id = str(user_data.get('user_id', 'N/A'))
        username = user_data.get('username', 'N/A')
        group = group_title
        
        profile_link = f"[🔗 {bold_unicode('Click Here')}](tg://user?id={user_data.get('user_id')})"
        
        return f"""╔═══《 🎉 {bold_unicode('𝐖𝐞𝐥𝐜𝐨𝐦𝐞!')} 》═══╗
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
🆔 {bold_unicode('𝐔𝐬𝐞𝐫 𝐈𝐃:')} {user_id}
🌟 {bold_unicode('𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:')} @{username}
🍑 {bold_unicode('𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢𝐧𝐤:')} {profile_link}
╰═══════《 ⚡ 》═══════╝
{bold_unicode('𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨')} {group}
━━━━━━━━━━━━━━━━━━━━━━
{bold_unicode('𝐘𝐨𝐮 𝐡𝐚𝐯𝐞 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲 𝐣𝐨𝐢𝐧𝐞𝐝 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩!')}"""

    @staticmethod
    def dashboard_text(user_id: int) -> str:
        return f"""╔═══《 🎛 {bold_unicode('𝐔𝐬𝐞𝐫 𝐃𝐚𝐬𝐡𝐛𝐨𝐚𝐫𝐝')} 》═══╗
👤 {bold_unicode('𝐔𝐬𝐞𝐫 𝐈𝐃:')} {user_id}
╰═══════《 ⚡ 》═══════╝

{bold_unicode('𝐒𝐞𝐥𝐞𝐜𝐭 𝐚𝐧 𝐨𝐩𝐭𝐢𝐨𝐧 𝐟𝐫𝐨𝐦 𝐭𝐡𝐞 𝐦𝐞𝐧𝐮 𝐛𝐞𝐥𝐨𝐰:')}"""

    @staticmethod
    def owner_panel_text(stats: Dict) -> str:
        return f"""╔═══《 👑 {bold_unicode('𝐎𝐰𝐧𝐞𝐫 𝐏𝐚𝐧𝐞𝐥')} 》═══╗
📊 {bold_unicode('𝐓𝐨𝐭𝐚𝐥 𝐆𝐫𝐨𝐮𝐩𝐬:')} {stats['total_groups']}
👥 {bold_unicode('𝐓𝐨𝐭𝐚𝐥 𝐔𝐬𝐞𝐫𝐬:')} {stats['total_users']}
⚙️ {bold_unicode('𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞 𝐌𝐨𝐝𝐞:')} {bold_unicode('𝐀𝐜𝐭𝐢𝐯𝐞' if stats['maintenance'] else '𝐈𝐧𝐚𝐜𝐭𝐢𝐯𝐞')}
╰═══════《 ⚡ 》═══════╝"""

    @staticmethod
    def group_info(group_id: int, title: str, owner_id: int, added_date: str) -> str:
        return f"""📌 {bold_unicode('𝐆𝐫𝐨𝐮𝐩:')} {title}
🆔 {bold_unicode('𝐈𝐃:')} {group_id}
👤 {bold_unicode('𝐎𝐰𝐧𝐞𝐫:')} {owner_id}
📅 {bold_unicode('𝐀𝐝𝐝𝐞𝐝:')} {added_date}
━━━━━━━━━━━━━━━━━━━━━━"""

    @staticmethod
    def help_text() -> str:
        return f"""📖 {bold_unicode('𝐆𝐮𝐢𝐝𝐞 / 𝐇𝐞𝐥𝐩')}

{bold_unicode('𝐇𝐨𝐰 𝐭𝐨 𝐮𝐬𝐞 𝐭𝐡𝐞 𝐛𝐨𝐭:')}

1️⃣ {bold_unicode('𝐀𝐝𝐝 𝐭𝐡𝐞 𝐛𝐨𝐭 𝐭𝐨 𝐲𝐨𝐮𝐫 𝐠𝐫𝐨𝐮𝐩')}
   {bold_unicode('𝐌𝐚𝐤𝐞 𝐬𝐮𝐫𝐞 𝐭𝐨 𝐚𝐝𝐦𝐢𝐧 𝐢𝐭!')}

2️⃣ {bold_unicode('𝐑𝐞𝐠𝐢𝐬𝐭𝐞𝐫 𝐲𝐨𝐮𝐫 𝐠𝐫𝐨𝐮𝐩')}
   • {bold_unicode('𝐂𝐥𝐢𝐜𝐤')} "➕ {bold_unicode('Add Group')}"
   • {bold_unicode('𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩 𝐜𝐡𝐚𝐭 𝐈𝐃')}
   • {bold_unicode('𝐂𝐨𝐧𝐟𝐢𝐫𝐦 𝐭𝐡𝐞 𝐝𝐞𝐭𝐚𝐢𝐥𝐬')}

3️⃣ {bold_unicode('𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐚𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝:')}
   • 🎉 {bold_unicode('𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬 𝐰𝐢𝐭𝐡 𝐩𝐡𝐨𝐭𝐨')}
   • 🔒 {bold_unicode('𝐋𝐢𝐧𝐤 𝐩𝐫𝐨𝐭𝐞𝐜𝐭𝐢𝐨𝐧')}
   • 🚫 {bold_unicode('𝐀𝐮𝐭𝐨 𝐝𝐞𝐥𝐞𝐭𝐞 𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞𝐬/𝐢𝐧𝐯𝐢𝐭𝐞𝐬')}

4️⃣ {bold_unicode('𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲):')}
   • /mute [time] - {bold_unicode('Mute user (e.g. 1h, 30m)')}
   • /unmute - {bold_unicode('Unmute user')}
   • /kick - {bold_unicode('Kick user')}
   • /ban - {bold_unicode('Ban user')}
   • /unban <id> - {bold_unicode('Unban user by ID')}
   • /warn [reason] - {bold_unicode('Warn user')}
   • /warnings - {bold_unicode('Show warnings')}
   • /del - {bold_unicode('Delete replied message')}
   • /pin - {bold_unicode('Pin message')}
   • /unpin - {bold_unicode('Unpin message')}
   • /purge [N] - {bold_unicode('Delete N messages')}
   • /lock - {bold_unicode('Lock group (only admins)')}
   • /unlock - {bold_unicode('Unlock group')}
   • /settings - {bold_unicode('Show group settings')}

5️⃣ {bold_unicode('𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬 (𝐄𝐯𝐞𝐫𝐲𝐨𝐧𝐞):')}
   • /info - {bold_unicode('Get user info')}
   • /warnings - {bold_unicode('See your warnings')}

{bold_unicode('𝐍𝐞𝐞𝐝 𝐡𝐞𝐥𝐩? 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 @𝐚𝐝𝐦𝐢𝐧')}"""

    @staticmethod
    def add_group_instructions() -> str:
        return f"""➕ {bold_unicode('𝐀𝐝𝐝 𝐆𝐫𝐨𝐮𝐩')}

{bold_unicode('𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩 𝐜𝐡𝐚𝐭 𝐈𝐃:')}

{bold_unicode('𝐄𝐱𝐚𝐦𝐩𝐥𝐞:')} -1001234567890

⚠️ {bold_unicode('𝐈𝐦𝐩𝐨𝐫𝐭𝐚𝐧𝐭:')}
• {bold_unicode('𝐁𝐨𝐭 𝐦𝐮𝐬𝐭 𝐛𝐞 𝐚𝐝𝐦𝐢𝐧 𝐢𝐧 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩')}
• {bold_unicode('𝐘𝐨𝐮 𝐦𝐮𝐬𝐭 𝐛𝐞 𝐚𝐧 𝐚𝐝𝐦𝐢𝐧 𝐢𝐧 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩')}
• {bold_unicode('𝐔𝐬𝐞 𝐧𝐞𝐠𝐚𝐭𝐢𝐯𝐞 𝐈𝐃 𝐟𝐨𝐫 𝐬𝐮𝐩𝐞𝐫𝐠𝐫𝐨𝐮𝐩𝐬')}"""

    @staticmethod
    def confirm_group(group_info: Dict) -> str:
        return f"""🔍 {bold_unicode('𝐆𝐫𝐨𝐮𝐩 𝐅𝐨𝐮𝐧𝐝')}

{bold_unicode('𝐓𝐢𝐭𝐥𝐞:')} {group_info['title']}
🆔 {bold_unicode('𝐈𝐃:')} {group_info['id']}
👥 {bold_unicode('𝐓𝐲𝐩𝐞:')} {group_info['type']}

{bold_unicode('𝐃𝐨 𝐲𝐨𝐮 𝐰𝐚𝐧𝐭 𝐭𝐨 𝐚𝐝𝐝 𝐭𝐡𝐢𝐬 𝐠𝐫𝐨𝐮𝐩?')}"""

    @staticmethod
    def link_deleted_message() -> str:
        return f"""🚫 {bold_unicode('𝐋𝐢𝐧𝐤 𝐏𝐫𝐨𝐭𝐞𝐜𝐭𝐢𝐨𝐧')}
{bold_unicode('𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐰𝐢𝐭𝐡 𝐥𝐢𝐧𝐤 𝐰𝐚𝐬 𝐝𝐞𝐥𝐞𝐭𝐞𝐝')}"""

    @staticmethod
    def erotic_message(user_data: Dict) -> str:
        full_name = user_data.get('full_name', 'User')
        user_id = str(user_data.get('user_id', 'N/A'))
        username = user_data.get('username', 'N/A')
        
        return f"""╔══════《 🔥 {bold_unicode('𝐏𝐫𝐢𝐯𝐚𝐭𝐞 𝐌𝐨𝐦𝐞𝐧𝐭')} 》══════╗
👤 {bold_unicode('𝐍𝐚𝐦𝐞:')} {full_name}
🆔 {bold_unicode('𝐈𝐃:')} {user_id}
🌟 {bold_unicode('𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:')} @{username}
💋 {bold_unicode('𝐒𝐞𝐜𝐫𝐞𝐭 𝐋𝐢𝐧𝐤:')} [🔞 {bold_unicode('𝐓𝐨𝐮𝐜𝐡 𝐌𝐞')}](tg://user?id={user_data.get('user_id')})
╰═══════《 💕 𝐄𝐧𝐣𝐨𝐲 》═══════╝"""

    @staticmethod
    def error_message(text: str) -> str:
        return f"""❌ {bold_unicode(text)}"""

    @staticmethod
    def info_message(text: str) -> str:
        return f"""ℹ️ {bold_unicode(text)}"""

    @staticmethod
    def success_message(text: str) -> str:
        return f"""✅ {bold_unicode(text)}"""

    @staticmethod
    def ban_message(user_data: Dict, admin_name: str) -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        return f"""🔨 {bold_unicode('𝐔𝐬𝐞𝐫 𝐁𝐚𝐧𝐧𝐞𝐝')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
👮 {bold_unicode('𝐁𝐚𝐧𝐧𝐞𝐝 𝐛𝐲:')} {admin}"""

    @staticmethod
    def user_info(user_data: Dict, chat_title: str, warnings: int = 0) -> str:
        full_name = user_data.get('full_name', 'User')
        user_id = str(user_data.get('user_id', 'N/A'))
        username = user_data.get('username', 'N/A')
        chat = chat_title
        
        return f"""📋 {bold_unicode('𝐔𝐬𝐞𝐫 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧')}
👤 {bold_unicode('𝐍𝐚𝐦𝐞:')} {full_name}
🆔 {bold_unicode('𝐈𝐃:')} {user_id}
🌟 {bold_unicode('𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:')} @{username}
💬 {bold_unicode('𝐆𝐫𝐨𝐮𝐩:')} {chat}
⚠️ {bold_unicode('𝐖𝐚𝐫𝐧𝐢𝐧𝐠𝐬:')} {warnings}
🔗 {bold_unicode('𝐋𝐢𝐧𝐤:')} [👤 {bold_unicode('𝐏𝐫𝐨𝐟𝐢𝐥𝐞')}](tg://user?id={user_data.get('user_id')})"""

    @staticmethod
    def mute_message(user_data: Dict, admin_name: str, duration: str = "") -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        duration_text = f" for {duration}" if duration else ""
        return f"""🔇 {bold_unicode('𝐔𝐬𝐞𝐫 𝐌𝐮𝐭𝐞𝐝')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
⏱️ {bold_unicode('𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧:')} {duration if duration else 'Indefinite'}
👮 {bold_unicode('𝐌𝐮𝐭𝐞𝐝 𝐛𝐲:')} {admin}"""

    @staticmethod
    def unmute_message(user_data: Dict, admin_name: str) -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        return f"""🔊 {bold_unicode('𝐔𝐬𝐞𝐫 𝐔𝐧𝐦𝐮𝐭𝐞𝐝')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
👮 {bold_unicode('𝐔𝐧𝐦𝐮𝐭𝐞𝐝 𝐛𝐲:')} {admin}"""

    @staticmethod
    def kick_message(user_data: Dict, admin_name: str) -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        return f"""👢 {bold_unicode('𝐔𝐬𝐞𝐫 𝐊𝐢𝐜𝐤𝐞𝐝')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
👮 {bold_unicode('𝐊𝐢𝐜𝐤𝐞𝐝 𝐛𝐲:')} {admin}"""

    @staticmethod
    def warn_message(user_data: Dict, admin_name: str, reason: str, warn_count: int) -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        return f"""⚠️ {bold_unicode('𝐔𝐬𝐞𝐫 𝐖𝐚𝐫𝐧𝐞𝐝')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
📝 {bold_unicode('𝐑𝐞𝐚𝐬𝐨𝐧:')} {reason if reason else 'No reason'}
🔢 {bold_unicode('𝐖𝐚𝐫𝐧𝐢𝐧𝐠𝐬:')} {warn_count}
👮 {bold_unicode('𝐖𝐚𝐫𝐧𝐞𝐝 𝐛𝐲:')} {admin}"""

    @staticmethod
    def warnings_list(user_data: Dict, warnings: List[Dict]) -> str:
        full_name = user_data.get('full_name', 'User')
        if not warnings:
            return f"""📋 {bold_unicode('𝐖𝐚𝐫𝐧𝐢𝐧𝐠𝐬')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
✅ {bold_unicode('𝐍𝐨 𝐰𝐚𝐫𝐧𝐢𝐧𝐠𝐬.')}"""
        
        text = f"""📋 {bold_unicode('𝐖𝐚𝐫𝐧𝐢𝐧𝐠𝐬')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
━━━━━━━━━━━━━━━━━━━━━━\n"""
        for i, w in enumerate(warnings, 1):
            date = w['date'][:16].replace('T', ' ')
            reason = w['reason'] if w['reason'] else 'No reason'
            text += f"{i}. {date} - {reason}\n"
        return text

    @staticmethod
    def purge_message(count: int) -> str:
        return f"""🧹 {bold_unicode('𝐌𝐞𝐬𝐬𝐚𝐠𝐞𝐬 𝐏𝐮𝐫𝐠𝐞𝐝')}
{bold_unicode('𝐃𝐞𝐥𝐞𝐭𝐞𝐝')} {count} {bold_unicode('𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬.')}"""

    @staticmethod
    def settings_text(group_id: int, locked: bool) -> str:
        lock_status = bold_unicode('𝐋𝐨𝐜𝐤𝐞𝐝') if locked else bold_unicode('𝐔𝐧𝐥𝐨𝐜𝐤𝐞𝐝')
        return f"""⚙️ {bold_unicode('𝐆𝐫𝐨𝐮𝐩 𝐒𝐞𝐭𝐭𝐢𝐧𝐠𝐬')}
🆔 {bold_unicode('𝐆𝐫𝐨𝐮𝐩 𝐈𝐃:')} {group_id}
🔒 {bold_unicode('𝐒𝐭𝐚𝐭𝐮𝐬:')} {lock_status}"""

# ==================== BOT HANDLERS ====================
class BotHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.formatter = MessageFormatter()
        self.link_pattern = re.compile(r'(https?://|www\.|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?|t\.me/|@\w+)', re.IGNORECASE)
        self.pending_confirmation = {}
    
    # ---------- Helper Methods ----------
    async def is_admin(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except:
            return False
    
    async def get_user_profile_photo(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        try:
            photos = await context.bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                return photos.photos[0][-1].file_id
        except:
            pass
        return None
    
    def contains_link(self, text: str) -> bool:
        if not text:
            return False
        return bool(self.link_pattern.search(text))
    
    async def get_target_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str) -> Tuple[Optional[int], Optional[str]]:
        if update.message.reply_to_message:
            return update.message.reply_to_message.from_user.id, None
        
        args = context.args
        if not args:
            return None, self.formatter.error_message("𝐏𝐥𝐞𝐚𝐬𝐞 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃.")
        
        target = args[0]
        if target.startswith('@'):
            username = target[1:]
            try:
                chat = await context.bot.get_chat(username)
                return chat.id, None
            except:
                return None, self.formatter.error_message("𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝.")
        else:
            try:
                return int(target), None
            except ValueError:
                return None, self.formatter.error_message("𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃.")
    
    async def check_group_registered(self, update: Update) -> bool:
        chat = update.effective_chat
        if chat.type not in ["group", "supergroup"]:
            return False
        group = self.db.get_group(chat.id)
        if not group:
            await update.message.reply_text(self.formatter.error_message("𝐓𝐡𝐢𝐬 𝐠𝐫𝐨𝐮𝐩 𝐢𝐬 𝐧𝐨𝐭 𝐫𝐞𝐠𝐢𝐬𝐭𝐞𝐫𝐞𝐝. 𝐏𝐥𝐞𝐚𝐬𝐞 𝐚𝐬𝐤 𝐚𝐧 𝐚𝐝𝐦𝐢𝐧 𝐭𝐨 𝐚𝐝𝐝 𝐢𝐭 𝐢𝐧 𝐩𝐫𝐢𝐯𝐚𝐭𝐞 𝐜𝐡𝐚𝐭."))
            return False
        return True
    
    async def check_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return False
        return True
    
    # ---------- Group Moderation Commands ----------
    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        user_id, error = await self.get_target_user(update, context, "mute")
        if error:
            await update.message.reply_text(error)
            return
        
        args = context.args
        duration_str = None
        if len(args) > 1:
            duration_str = args[1]
        elif update.message.reply_to_message and len(args) > 0:
            duration_str = args[0] if args else None
        
        until_date = None
        if duration_str:
            match = re.match(r'^(\d+)([hmd])$', duration_str.lower())
            if match:
                num, unit = int(match.group(1)), match.group(2)
                if unit == 'h':
                    until_date = datetime.now() + timedelta(hours=num)
                elif unit == 'm':
                    until_date = datetime.now() + timedelta(minutes=num)
                elif unit == 'd':
                    until_date = datetime.now() + timedelta(days=num)
            else:
                await update.message.reply_text(self.formatter.error_message("𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐝𝐮𝐫𝐚𝐭𝐢𝐨𝐧. 𝐔𝐬𝐞 𝐞.𝐠. 1h, 30m, 2d"))
                return
        
        try:
            permissions = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user_id,
                permissions=permissions,
                until_date=until_date
            )
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_data = {
                'full_name': user.user.full_name,
                'user_id': user.user.id,
                'username': user.user.username
            }
            duration_display = duration_str if duration_str else ""
            await update.message.reply_text(
                self.formatter.mute_message(user_data, update.effective_user.full_name, duration_display),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐦𝐮𝐭𝐞: {str(e)}"))
    
    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        user_id, error = await self.get_target_user(update, context, "unmute")
        if error:
            await update.message.reply_text(error)
            return
        
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user_id,
                permissions=permissions
            )
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_data = {
                'full_name': user.user.full_name,
                'user_id': user.user.id,
                'username': user.user.username
            }
            await update.message.reply_text(
                self.formatter.unmute_message(user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐮𝐧𝐦𝐮𝐭𝐞: {str(e)}"))
    
    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        user_id, error = await self.get_target_user(update, context, "kick")
        if error:
            await update.message.reply_text(error)
            return
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_data = {
                'full_name': user.user.full_name,
                'user_id': user.user.id,
                'username': user.user.username
            }
            await update.message.reply_text(
                self.formatter.kick_message(user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐤𝐢𝐜𝐤: {str(e)}"))
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        user_id, error = await self.get_target_user(update, context, "ban")
        if error:
            await update.message.reply_text(error)
            return
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_data = {
                'full_name': user.user.full_name,
                'user_id': user.user.id,
                'username': user.user.username
            }
            await update.message.reply_text(
                self.formatter.ban_message(user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐛𝐚𝐧: {str(e)}"))
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(self.formatter.error_message("𝐏𝐫𝐨𝐯𝐢𝐝𝐞 𝐮𝐬𝐞𝐫 𝐈𝐃: /unban 123456789"))
            return
        try:
            user_id = int(args[0])
        except ValueError:
            await update.message.reply_text(self.formatter.error_message("𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃."))
            return
        
        try:
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(self.formatter.success_message(f"𝐔𝐬𝐞𝐫 {user_id} 𝐮𝐧𝐛𝐚𝐧𝐧𝐞𝐝."))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐮𝐧𝐛𝐚𝐧: {str(e)}"))
    
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        user_id, error = await self.get_target_user(update, context, "warn")
        if error:
            await update.message.reply_text(error)
            return
        
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        try:
            self.db.add_warning(user_id, update.effective_chat.id, update.effective_user.id, reason)
            warnings = self.db.get_warnings(user_id, update.effective_chat.id)
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_data = {
                'full_name': user.user.full_name,
                'user_id': user.user.id,
                'username': user.user.username
            }
            await update.message.reply_text(
                self.formatter.warn_message(user_data, update.effective_user.full_name, reason, len(warnings)),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐰𝐚𝐫𝐧: {str(e)}"))
    
    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        
        if await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            user_id, error = await self.get_target_user(update, context, "warnings")
            if error:
                user_id = update.effective_user.id
        else:
            user_id = update.effective_user.id
        
        try:
            warnings = self.db.get_warnings(user_id, update.effective_chat.id)
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_data = {
                'full_name': user.user.full_name,
                'user_id': user.user.id,
                'username': user.user.username
            }
            await update.message.reply_text(
                self.formatter.warnings_list(user_data, warnings),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐠𝐞𝐭 𝐰𝐚𝐫𝐧𝐢𝐧𝐠𝐬: {str(e)}"))
    
    async def del_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐝𝐞𝐥𝐞𝐭𝐞 𝐢𝐭."))
            return
        
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐝𝐞𝐥𝐞𝐭𝐞: {str(e)}"))
    
    async def pin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐩𝐢𝐧 𝐢𝐭."))
            return
        
        try:
            await update.message.reply_to_message.pin(disable_notification=True)
            await update.message.reply_text(self.formatter.success_message("𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐩𝐢𝐧𝐧𝐞𝐝."))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐩𝐢𝐧: {str(e)}"))
    
    async def unpin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        try:
            if update.message.reply_to_message:
                await update.message.reply_to_message.unpin()
            else:
                await context.bot.unpin_chat_message(update.effective_chat.id)
            await update.message.reply_text(self.formatter.success_message("𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐮𝐧𝐩𝐢𝐧𝐧𝐞𝐝."))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐮𝐧𝐩𝐢𝐧: {str(e)}"))
    
    async def purge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐩𝐮𝐫𝐠𝐞 𝐟𝐫𝐨𝐦 𝐭𝐡𝐞𝐫𝐞 𝐮𝐩𝐰𝐚𝐫𝐝𝐬."))
            return
        
        args = context.args
        count = 10
        if args:
            try:
                count = int(args[0])
                if count < 1 or count > 100:
                    count = 10
            except:
                pass
        
        try:
            start_msg = update.message.reply_to_message.message_id
            end_msg = update.message.message_id
            deleted = 0
            for msg_id in range(start_msg, end_msg):
                try:
                    await context.bot.delete_message(update.effective_chat.id, msg_id)
                    deleted += 1
                except:
                    pass
            await update.message.reply_text(self.formatter.purge_message(deleted))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐩𝐮𝐫𝐠𝐞: {str(e)}"))
    
    async def lock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        try:
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            await context.bot.set_chat_permissions(update.effective_chat.id, permissions)
            self.db.set_group_lock(update.effective_chat.id, True)
            await update.message.reply_text(self.formatter.success_message("𝐆𝐫𝐨𝐮𝐩 𝐥𝐨𝐜𝐤𝐞𝐝. 𝐎𝐧𝐥𝐲 𝐚𝐝𝐦𝐢𝐧𝐬 𝐜𝐚𝐧 𝐬𝐞𝐧𝐝 𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬 𝐧𝐨𝐰."))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐥𝐨𝐜𝐤: {str(e)}"))
    
    async def unlock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            await context.bot.set_chat_permissions(update.effective_chat.id, permissions)
            self.db.set_group_lock(update.effective_chat.id, False)
            await update.message.reply_text(self.formatter.success_message("𝐆𝐫𝐨𝐮𝐩 𝐮𝐧𝐥𝐨𝐜𝐤𝐞𝐝. 𝐄𝐯𝐞𝐫𝐲𝐨𝐧𝐞 𝐜𝐚𝐧 𝐬𝐞𝐧𝐝 𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬."))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐮𝐧𝐥𝐨𝐜𝐤: {str(e)}"))
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        if not await self.check_admin(update, context):
            return
        
        locked = self.db.is_group_locked(update.effective_chat.id)
        await update.message.reply_text(
            self.formatter.settings_text(update.effective_chat.id, locked),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_group_registered(update):
            return
        
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        else:
            target_user = update.effective_user
        
        user_data = {
            'full_name': target_user.full_name or "User",
            'user_id': target_user.id,
            'username': target_user.username or "N/A"
        }
        warnings = len(self.db.get_warnings(target_user.id, update.effective_chat.id))
        
        await update.message.reply_text(
            self.formatter.user_info(user_data, update.effective_chat.title or "Group", warnings),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ---------- Group Message Handlers ----------
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return
        
        chat = update.effective_chat
        user = update.effective_user
        
        group = self.db.get_group(chat.id)
        if not group:
            return
        
        if self.db.is_group_locked(chat.id) and not await self.is_admin(context, chat.id, user.id):
            try:
                await update.message.delete()
                logger.info(f"Deleted message from non-admin {user.id} in locked group {chat.id}")
            except:
                pass
            return
        
        if not await self.is_admin(context, chat.id, user.id) and self.contains_link(update.message.text):
            try:
                await update.message.delete()
                logger.info(f"Deleted link message from {user.id} in {chat.id}")
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message.new_chat_members:
            return
            
        chat = update.effective_chat
        
        group = self.db.get_group(chat.id)
        if not group:
            logger.info(f"New member in unregistered group {chat.id}, skipping welcome")
            return
        
        for new_member in update.message.new_chat_members:
            if new_member.id == context.bot.id:
                continue
            
            user_data = {
                'full_name': new_member.full_name or "User",
                'user_id': new_member.id,
                'username': new_member.username or "N/A"
            }
            
            photo_id = await self.get_user_profile_photo(context, new_member.id)
            welcome_text = self.formatter.welcome_message(user_data, chat.title or "Group")
            
            try:
                if photo_id:
                    await context.bot.send_photo(
                        chat.id,
                        photo=photo_id,
                        caption=welcome_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await context.bot.send_message(
                        chat.id,
                        welcome_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                logger.info(f"Welcome message sent to {new_member.id} in {chat.id}")
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")
    
    # ---------- Private Chat Handlers ----------
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        self.db.add_user(user.id, user.username, user.full_name)
        
        if update.effective_chat.type != "private":
            return
        
        if self.db.is_maintenance_mode() and user.id != OWNER_ID:
            await update.message.reply_text(
                self.formatter.error_message("𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞 𝐦𝐨𝐝𝐞 𝐢𝐬 𝐚𝐜𝐭𝐢𝐯𝐞. 𝐏𝐥𝐞𝐚𝐬𝐞 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧 𝐥𝐚𝐭𝐞𝐫.")
            )
            return
        
        keyboard = [
            [KeyboardButton(f"➕ {bold_unicode('Add Group')}"), KeyboardButton(f"📂 {bold_unicode('View Groups')}")],
            [KeyboardButton(f"📖 {bold_unicode('Guide / Help')}"), KeyboardButton(f"🔥 {bold_unicode('Private')}")],
        ]
        
        if user.id == OWNER_ID:
            keyboard.append([KeyboardButton(f"👑 {bold_unicode('Owner Panel')}")])
        
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
        
        await update.message.reply_text(
            self.formatter.dashboard_text(user.id),
            reply_markup=reply_markup
        )
    
    async def handle_reply_keyboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type != "private":
            return
        
        text = update.message.text
        user_id = update.effective_user.id
        
        if context.user_data.get("in_conversation"):
            return
        
        if text == f"➕ {bold_unicode('Add Group')}":
            context.user_data["in_conversation"] = True
            await update.message.reply_text(
                self.formatter.add_group_instructions(),
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton(f"🔙 {bold_unicode('Back to Dashboard')}")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
            return ASK_CHAT_ID
        
        elif text == f"📂 {bold_unicode('View Groups')}":
            groups = self.db.get_user_groups(user_id)
            
            if not groups:
                reply = f"📂 {bold_unicode('Your Groups')}\n\n{bold_unicode('No groups registered yet.')}"
            else:
                reply = f"📂 {bold_unicode('Your Groups')}\n\n"
                for group in groups:
                    reply += self.formatter.group_info(
                        group['group_id'],
                        group['title'],
                        group['owner_id'],
                        group['added_date'][:10]
                    ) + "\n"
            
            await update.message.reply_text(
                reply,
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton(f"🔙 {bold_unicode('Back to Dashboard')}")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
        
        elif text == f"📖 {bold_unicode('Guide / Help')}":
            await update.message.reply_text(
                self.formatter.help_text(),
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton(f"🔙 {bold_unicode('Back to Dashboard')}")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
        
        elif text == f"🔥 {bold_unicode('Private')}":
            user_data = {
                'full_name': update.effective_user.full_name,
                'user_id': update.effective_user.id,
                'username': update.effective_user.username or "N/A"
            }
            await update.message.reply_text(
                self.formatter.erotic_message(user_data),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton(f"🔙 {bold_unicode('Back to Dashboard')}")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
        
        elif text == f"👑 {bold_unicode('Owner Panel')}" and user_id == OWNER_ID:
            stats = self.db.get_stats()
            text = self.formatter.owner_panel_text(stats)
            
            keyboard = [
                [InlineKeyboardButton(f"📊 {bold_unicode('Total Groups')}", callback_data="owner_total_groups")],
                [InlineKeyboardButton(f"👥 {bold_unicode('Total Users')}", callback_data="owner_total_users")],
                [InlineKeyboardButton(f"📃 {bold_unicode('Group List')}", callback_data="owner_group_list")],
                [InlineKeyboardButton(f"🛠 {bold_unicode('Maintenance Mode')}", callback_data="owner_maintenance")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                text,
                reply_markup=reply_markup
            )
        
        elif text == f"🔙 {bold_unicode('Back to Dashboard')}":
            keyboard = [
                [KeyboardButton(f"➕ {bold_unicode('Add Group')}"), KeyboardButton(f"📂 {bold_unicode('View Groups')}")],
                [KeyboardButton(f"📖 {bold_unicode('Guide / Help')}"), KeyboardButton(f"🔥 {bold_unicode('Private')}")],
            ]
            if user_id == OWNER_ID:
                keyboard.append([KeyboardButton(f"👑 {bold_unicode('Owner Panel')}")])
            
            reply_markup = ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            await update.message.reply_text(
                self.formatter.dashboard_text(user_id),
                reply_markup=reply_markup
            )
        
        return ConversationHandler.END
    
    async def handle_chat_id_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        if text == f"🔙 {bold_unicode('Back to Dashboard')}":
            context.user_data["in_conversation"] = False
            keyboard = [
                [KeyboardButton(f"➕ {bold_unicode('Add Group')}"), KeyboardButton(f"📂 {bold_unicode('View Groups')}")],
                [KeyboardButton(f"📖 {bold_unicode('Guide / Help')}"), KeyboardButton(f"🔥 {bold_unicode('Private')}")],
            ]
            if user_id == OWNER_ID:
                keyboard.append([KeyboardButton(f"👑 {bold_unicode('Owner Panel')}")])
            
            reply_markup = ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=False
            )
            await update.message.reply_text(
                self.formatter.dashboard_text(user_id),
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        try:
            chat_id = int(text)
        except ValueError:
            await update.message.reply_text(
                self.formatter.error_message("𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐜𝐡𝐚𝐭 𝐈𝐃. 𝐏𝐥𝐞𝐚𝐬𝐞 𝐞𝐧𝐭𝐞𝐫 𝐚 𝐧𝐮𝐦𝐛𝐞𝐫.")
            )
            return ASK_CHAT_ID
        
        existing = self.db.get_group(chat_id)
        if existing:
            await update.message.reply_text(
                self.formatter.error_message("𝐓𝐡𝐢𝐬 𝐠𝐫𝐨𝐮𝐩 𝐢𝐬 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐫𝐞𝐠𝐢𝐬𝐭𝐞𝐫𝐞𝐝.")
            )
            return ASK_CHAT_ID
        
        user_groups = self.db.get_user_groups(user_id)
        if len(user_groups) >= 10:
            await update.message.reply_text(
                self.formatter.error_message("𝐘𝐨𝐮 𝐜𝐚𝐧 𝐨𝐧𝐥𝐲 𝐫𝐞𝐠𝐢𝐬𝐭𝐞𝐫 𝐮𝐩 𝐭𝐨 𝟏𝟎 𝐠𝐫𝐨𝐮𝐩𝐬.")
            )
            return ASK_CHAT_ID
        
        try:
            chat = await context.bot.get_chat(chat_id)
            if not await self.is_admin(context, chat_id, user_id):
                await update.message.reply_text(
                    self.formatter.error_message("𝐘𝐨𝐮 𝐚𝐫𝐞 𝐧𝐨𝐭 𝐚𝐧 𝐚𝐝𝐦𝐢𝐧 𝐢𝐧 𝐭𝐡𝐢𝐬 𝐠𝐫𝐨𝐮𝐩.")
                )
                return ASK_CHAT_ID
            
            group_info = {
                'id': chat_id,
                'title': chat.title,
                'type': chat.type
            }
            self.pending_confirmation[user_id] = group_info
            
            keyboard = [
                [
                    InlineKeyboardButton(f"✅ {bold_unicode('Yes, Add')}", callback_data="confirm_add"),
                    InlineKeyboardButton(f"❌ {bold_unicode('No, Cancel')}", callback_data="cancel_add")
                ]
            ]
            await update.message.reply_text(
                self.formatter.confirm_group(group_info),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CONFIRM_ADD
            
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            await update.message.reply_text(
                self.formatter.error_message("𝐂𝐨𝐮𝐥𝐝 𝐧𝐨𝐭 𝐟𝐞𝐭𝐜𝐡 𝐠𝐫𝐨𝐮𝐩 𝐢𝐧𝐟𝐨. 𝐌𝐚𝐤𝐞 𝐬𝐮𝐫𝐞 𝐭𝐡𝐞 𝐈𝐃 𝐢𝐬 𝐜𝐨𝐫𝐫𝐞𝐜𝐭 𝐚𝐧𝐝 𝐛𝐨𝐭 𝐢𝐬 𝐢𝐧 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩.")
            )
            return ASK_CHAT_ID
    
    async def handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "confirm_add":
            if user_id in self.pending_confirmation:
                group_info = self.pending_confirmation[user_id]
                if self.db.add_group(group_info['id'], group_info['title'], user_id):
                    await query.edit_message_text(
                        self.formatter.success_message(f"𝐆𝐫𝐨𝐮𝐩 𝐚𝐝𝐝𝐞𝐝 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲!\n\n{group_info['title']}")
                    )
                else:
                    await query.edit_message_text(
                        self.formatter.error_message("𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐚𝐝𝐝 𝐠𝐫𝐨𝐮𝐩.")
                    )
                del self.pending_confirmation[user_id]
            else:
                await query.edit_message_text(
                    self.formatter.error_message("𝐍𝐨 𝐩𝐞𝐧𝐝𝐢𝐧𝐠 𝐜𝐨𝐧𝐟𝐢𝐫𝐦𝐚𝐭𝐢𝐨𝐧.")
                )
        
        elif data == "cancel_add":
            if user_id in self.pending_confirmation:
                del self.pending_confirmation[user_id]
            await query.edit_message_text(
                self.formatter.info_message("𝐀𝐝𝐝 𝐠𝐫𝐨𝐮𝐩 𝐜𝐚𝐧𝐜𝐞𝐥𝐞𝐝.")
            )
        
        context.user_data["in_conversation"] = False
        
        keyboard = [
            [KeyboardButton(f"➕ {bold_unicode('Add Group')}"), KeyboardButton(f"📂 {bold_unicode('View Groups')}")],
            [KeyboardButton(f"📖 {bold_unicode('Guide / Help')}"), KeyboardButton(f"🔥 {bold_unicode('Private')}")],
        ]
        if user_id == OWNER_ID:
            keyboard.append([KeyboardButton(f"👑 {bold_unicode('Owner Panel')}")])
        
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=self.formatter.dashboard_text(user_id),
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
    
    async def handle_owner_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if user_id != OWNER_ID:
            await query.edit_message_text("⛔ Unauthorized")
            return
        
        data = query.data
        
        if data == "owner_total_groups":
            stats = self.db.get_stats()
            await query.answer(f"Total Groups: {stats['total_groups']}", show_alert=True)
        
        elif data == "owner_total_users":
            stats = self.db.get_stats()
            await query.answer(f"Total Users: {stats['total_users']}", show_alert=True)
        
        elif data == "owner_group_list":
            groups = self.db.get_all_groups()
            if not groups:
                text = f"📃 {bold_unicode('All Groups')}\n\n{bold_unicode('No groups registered yet.')}"
            else:
                text = f"📃 {bold_unicode('All Groups')}\n\n"
                for group in groups[:10]:
                    text += self.formatter.group_info(
                        group['group_id'],
                        group['title'],
                        group['owner_id'],
                        group['added_date'][:10]
                    ) + "\n"
                if len(groups) > 10:
                    text += f"\n{bold_unicode('And')} {len(groups) - 10} {bold_unicode('more...')}"
            
            await query.edit_message_text(text)
        
        elif data == "owner_maintenance":
            current = self.db.is_maintenance_mode()
            new_status = not current
            self.db.set_maintenance_mode(new_status)
            status_text = bold_unicode("enabled" if new_status else "disabled")
            await query.answer(f"Maintenance mode {status_text}!", show_alert=True)
            
            stats = self.db.get_stats()
            text = self.formatter.owner_panel_text(stats)
            await query.edit_message_text(text)

# ==================== MAIN APPLICATION ====================
def main():
    db = DatabaseManager(DATABASE_FILE)
    handlers = BotHandlers(db)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("info", handlers.info_command))
    
    # Admin commands
    application.add_handler(CommandHandler("mute", handlers.mute_command))
    application.add_handler(CommandHandler("unmute", handlers.unmute_command))
    application.add_handler(CommandHandler("kick", handlers.kick_command))
    application.add_handler(CommandHandler("ban", handlers.ban_command))
    application.add_handler(CommandHandler("unban", handlers.unban_command))
    application.add_handler(CommandHandler("warn", handlers.warn_command))
    application.add_handler(CommandHandler("warnings", handlers.warnings_command))
    application.add_handler(CommandHandler("del", handlers.del_command))
    application.add_handler(CommandHandler("pin", handlers.pin_command))
    application.add_handler(CommandHandler("unpin", handlers.unpin_command))
    application.add_handler(CommandHandler("purge", handlers.purge_command))
    application.add_handler(CommandHandler("lock", handlers.lock_command))
    application.add_handler(CommandHandler("unlock", handlers.unlock_command))
    application.add_handler(CommandHandler("settings", handlers.settings_command))
    
    # Conversation handler for adding group
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f'^➕ {bold_unicode("Add Group")}$') & filters.ChatType.PRIVATE, handlers.handle_reply_keyboard)],
        states={
            ASK_CHAT_ID: [MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handlers.handle_chat_id_input)],
            CONFIRM_ADD: [CallbackQueryHandler(handlers.handle_confirmation, pattern='^(confirm_add|cancel_add)$')],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^🔙 {bold_unicode("Back to Dashboard")}$') & filters.ChatType.PRIVATE, handlers.handle_reply_keyboard)],
        per_message=False  # Add this to suppress warning
    )
    application.add_handler(conv_handler)
    
    # General reply keyboard handler (for non-conversation messages)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handlers.handle_reply_keyboard
    ))
    
    # Owner panel callbacks
    application.add_handler(CallbackQueryHandler(handlers.handle_owner_callbacks, pattern='^owner_'))
    
    # Group message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        handlers.handle_group_message
    ))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handlers.handle_new_member
    ))
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print(f"🤖 Bot started! Owner ID: {OWNER_ID}")
    print(f"📁 Database: {DATABASE_FILE}")
    print("🌐 Flask dashboard running on http://localhost:8080")
    print("Press Ctrl+C to stop")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        print("Please check your internet connection and bot token.")

if __name__ == "__main__":
    main()
