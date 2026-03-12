#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
import re
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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
from flask import Flask
import os

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8325285069:AAHLmn__ebAMG7gZy6WL-COq4BbCqvkcVVs"
OWNER_ID = 8469461108  # Updated owner ID
DATABASE_FILE = "bot_database.sqlite3"

# Conversation states
ASK_CHAT_ID, CONFIRM_ADD = range(2)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FLASK KEEP ALIVE ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== UNICODE BOLD CONVERTER ====================
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
                    welcome_enabled INTEGER DEFAULT 1,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
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
        
        return f"""🎉 {bold_unicode('𝐖𝐞𝐥𝐜𝐨𝐦𝐞!')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
🆔 {bold_unicode('𝐔𝐬𝐞𝐫 𝐈𝐃:')} {user_id}
🌟 {bold_unicode('𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:')} @{username}
🍑 {bold_unicode('𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢𝐧𝐤:')} [🔗 {bold_unicode('𝐂𝐥𝐢𝐜𝐤 𝐇𝐞𝐫𝐞')}](tg://user?id={user_data.get('user_id')})
⚡ {bold_unicode('𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨')} {group}
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
   • {bold_unicode('𝐂𝐥𝐢𝐜𝐤')} "➕ {bold_unicode('𝐀𝐝𝐝 𝐆𝐫𝐨𝐮𝐩')}"
   • {bold_unicode('𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩 𝐜𝐡𝐚𝐭 𝐈𝐃')}
   • {bold_unicode('𝐂𝐨𝐧𝐟𝐢𝐫𝐦 𝐭𝐡𝐞 𝐝𝐞𝐭𝐚𝐢𝐥𝐬')}

3️⃣ {bold_unicode('𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐚𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝:')}
   • 🎉 {bold_unicode('𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬 𝐰𝐢𝐭𝐡 𝐩𝐡𝐨𝐭𝐨')}
   • 🔒 {bold_unicode('𝐋𝐢𝐧𝐤 𝐩𝐫𝐨𝐭𝐞𝐜𝐭𝐢𝐨𝐧')}
   • 🚫 {bold_unicode('𝐀𝐮𝐭𝐨 𝐝𝐞𝐥𝐞𝐭𝐞 𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞𝐬/𝐢𝐧𝐯𝐢𝐭𝐞𝐬')}

4️⃣ {bold_unicode('𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬:')}
   • /ban - {bold_unicode('𝐁𝐚𝐧 𝐮𝐬𝐞𝐫 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /unban - {bold_unicode('𝐔𝐧𝐛𝐚𝐧 𝐮𝐬𝐞𝐫 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /kick - {bold_unicode('𝐊𝐢𝐜𝐤 𝐮𝐬𝐞𝐫 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /mute - {bold_unicode('𝐌𝐮𝐭𝐞 𝐮𝐬𝐞𝐫 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /unmute - {bold_unicode('𝐔𝐧𝐦𝐮𝐭𝐞 𝐮𝐬𝐞𝐫 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /warn - {bold_unicode('𝐖𝐚𝐫𝐧 𝐮𝐬𝐞𝐫 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /warns - {bold_unicode('𝐒𝐡𝐨𝐰 𝐮𝐬𝐞𝐫 𝐰𝐚𝐫𝐧𝐬 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /del - {bold_unicode('𝐃𝐞𝐥𝐞𝐭𝐞 𝐫𝐞𝐩𝐥𝐢𝐞𝐝 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /pin - {bold_unicode('𝐏𝐢𝐧 𝐫𝐞𝐩𝐥𝐢𝐞𝐝 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /unpin - {bold_unicode('𝐔𝐧𝐩𝐢𝐧 𝐫𝐞𝐩𝐥𝐢𝐞𝐝 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 (𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲)')}
   • /info - {bold_unicode('𝐆𝐞𝐭 𝐮𝐬𝐞𝐫 𝐢𝐧𝐟𝐨 (𝐄𝐯𝐞𝐫𝐲𝐨𝐧𝐞)')}

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
    def action_message(action: str, user_data: Dict, admin_name: str, duration: str = None) -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        action_bold = bold_unicode(action)
        
        if duration:
            return f"""🔨 {action_bold}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
👮 {bold_unicode('𝐀𝐝𝐦𝐢𝐧:')} {admin}
⏱️ {bold_unicode('𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧:')} {duration}"""
        else:
            return f"""🔨 {action_bold}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
👮 {bold_unicode('𝐀𝐝𝐦𝐢𝐧:')} {admin}"""

    @staticmethod
    def warn_message(user_data: Dict, admin_name: str, warn_count: int, max_warns: int = 3) -> str:
        full_name = user_data.get('full_name', 'User')
        admin = admin_name
        
        return f"""⚠️ {bold_unicode('𝐖𝐚𝐫𝐧𝐢𝐧𝐠')}
👤 {bold_unicode('𝐔𝐬𝐞𝐫:')} {full_name}
👮 {bold_unicode('𝐀𝐝𝐦𝐢𝐧:')} {admin}
🔢 {bold_unicode('𝐖𝐚𝐫𝐧𝐬:')} {warn_count}/{max_warns}"""

    @staticmethod
    def user_info(user_data: Dict, chat_title: str, warn_count: int = 0) -> str:
        full_name = user_data.get('full_name', 'User')
        user_id = str(user_data.get('user_id', 'N/A'))
        username = user_data.get('username', 'N/A')
        chat = chat_title
        
        return f"""📋 {bold_unicode('𝐔𝐬𝐞𝐫 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧')}
👤 {bold_unicode('𝐍𝐚𝐦𝐞:')} {full_name}
🆔 {bold_unicode('𝐈𝐃:')} {user_id}
🌟 {bold_unicode('𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:')} @{username}
💬 {bold_unicode('𝐆𝐫𝐨𝐮𝐩:')} {chat}
⚠️ {bold_unicode('𝐖𝐚𝐫𝐧𝐬:')} {warn_count}
🔗 {bold_unicode('𝐋𝐢𝐧𝐤:')} [👤 {bold_unicode('𝐏𝐫𝐨𝐟𝐢𝐥𝐞')}](tg://user?id={user_data.get('user_id')})"""

# ==================== BOT HANDLERS ====================
class BotHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.formatter = MessageFormatter()
        self.link_pattern = re.compile(r'(https?://|www\.|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?|t\.me/|@\w+)', re.IGNORECASE)
        self.pending_confirmation = {}
        self.user_warns = {}  # Store warns: {chat_id: {user_id: count}}
        self.muted_users = {}  # Store muted users with expiration
    
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
    
    async def extract_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Extract user from reply or username/ID in command"""
        user = None
        
        # Check if replying to a message
        if update.message.reply_to_message:
            user = update.message.reply_to_message.from_user
            return user
        
        # Check if command has arguments (username or ID)
        if context.args:
            arg = context.args[0]
            # Check if it's a username (starts with @)
            if arg.startswith('@'):
                username = arg[1:]
                try:
                    # Try to get user by username in this chat
                    chat = update.effective_chat
                    async for member in context.bot.get_chat_administrators(chat.id):
                        if member.user.username and member.user.username.lower() == username.lower():
                            user = member.user
                            break
                except:
                    pass
            # Check if it's a user ID
            elif arg.lstrip('-').isdigit():
                user_id = int(arg)
                try:
                    # Try to get chat member
                    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                    user = chat_member.user
                except:
                    pass
        
        return user
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban a user - works with reply or username/ID"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        
        try:
            await context.bot.ban_chat_member(chat_id, target_user.id)
            user_data = {
                'full_name': target_user.full_name,
                'user_id': target_user.id,
                'username': target_user.username or "N/A"
            }
            await update.message.reply_text(
                self.formatter.action_message("𝐁𝐚𝐧𝐧𝐞𝐝", user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban a user - works with reply or username/ID"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        
        try:
            await context.bot.unban_chat_member(chat_id, target_user.id)
            user_data = {
                'full_name': target_user.full_name,
                'user_id': target_user.id,
                'username': target_user.username or "N/A"
            }
            await update.message.reply_text(
                self.formatter.action_message("𝐔𝐧𝐛𝐚𝐧𝐧𝐞𝐝", user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kick a user - works with reply or username/ID"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        
        try:
            await context.bot.ban_chat_member(chat_id, target_user.id)
            await context.bot.unban_chat_member(chat_id, target_user.id)
            user_data = {
                'full_name': target_user.full_name,
                'user_id': target_user.id,
                'username': target_user.username or "N/A"
            }
            await update.message.reply_text(
                self.formatter.action_message("𝐊𝐢𝐜𝐤𝐞𝐝", user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mute a user - works with reply or username/ID, optional duration"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        
        # Parse duration (default: 1 hour)
        duration_minutes = 60
        duration_text = "1 hour"
        
        if context.args and len(context.args) > 1:
            try:
                duration_minutes = int(context.args[1])
                if duration_minutes < 1:
                    duration_minutes = 1
                if duration_minutes > 43200:  # Max 30 days
                    duration_minutes = 43200
                duration_text = f"{duration_minutes} minutes"
            except:
                pass
        
        until_date = datetime.now() + timedelta(minutes=duration_minutes)
        permissions = ChatPermissions(can_send_messages=False)
        
        try:
            await context.bot.restrict_chat_member(chat_id, target_user.id, permissions, until_date=until_date)
            
            # Store in muted_users
            if chat_id not in self.muted_users:
                self.muted_users[chat_id] = {}
            self.muted_users[chat_id][target_user.id] = until_date
            
            user_data = {
                'full_name': target_user.full_name,
                'user_id': target_user.id,
                'username': target_user.username or "N/A"
            }
            await update.message.reply_text(
                self.formatter.action_message("𝐌𝐮𝐭𝐞𝐝", user_data, update.effective_user.full_name, duration_text),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unmute a user - works with reply or username/ID"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        try:
            await context.bot.restrict_chat_member(chat_id, target_user.id, permissions)
            
            # Remove from muted_users
            if chat_id in self.muted_users and target_user.id in self.muted_users[chat_id]:
                del self.muted_users[chat_id][target_user.id]
            
            user_data = {
                'full_name': target_user.full_name,
                'user_id': target_user.id,
                'username': target_user.username or "N/A"
            }
            await update.message.reply_text(
                self.formatter.action_message("𝐔𝐧𝐦𝐮𝐭𝐞𝐝", user_data, update.effective_user.full_name),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Warn a user - works with reply or username/ID"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        
        # Initialize warns for this chat
        if chat_id not in self.user_warns:
            self.user_warns[chat_id] = {}
        
        # Get current warn count
        current_warns = self.user_warns[chat_id].get(target_user.id, 0)
        current_warns += 1
        self.user_warns[chat_id][target_user.id] = current_warns
        
        user_data = {
            'full_name': target_user.full_name,
            'user_id': target_user.id,
            'username': target_user.username or "N/A"
        }
        
        # Auto-ban after 3 warns
        if current_warns >= 3:
            try:
                await context.bot.ban_chat_member(chat_id, target_user.id)
                await update.message.reply_text(
                    self.formatter.action_message("𝐁𝐚𝐧𝐧𝐞𝐝 (3 𝐰𝐚𝐫𝐧𝐬)", user_data, update.effective_user.full_name),
                    parse_mode=ParseMode.MARKDOWN
                )
                # Reset warns
                self.user_warns[chat_id][target_user.id] = 0
            except Exception as e:
                await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐛𝐚𝐧: {str(e)}"))
        else:
            await update.message.reply_text(
                self.formatter.warn_message(user_data, update.effective_user.full_name, current_warns),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def warns_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show warns for a user"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            await update.message.reply_text(
                self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐮𝐬𝐞𝐫'𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐨𝐫 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 @𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞/𝐈𝐃!")
            )
            return
        
        chat_id = update.effective_chat.id
        warn_count = self.user_warns.get(chat_id, {}).get(target_user.id, 0)
        
        user_data = {
            'full_name': target_user.full_name,
            'user_id': target_user.id,
            'username': target_user.username or "N/A"
        }
        
        await update.message.reply_text(
            self.formatter.user_info(user_data, update.effective_chat.title, warn_count),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def del_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete the replied message"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐝𝐞𝐥𝐞𝐭𝐞!"))
            return
        
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def pin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pin the replied message"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐩𝐢𝐧!"))
            return
        
        try:
            await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
            await update.message.reply_text(self.formatter.success_message("𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐩𝐢𝐧𝐧𝐞𝐝!"))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def unpin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unpin the replied message"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        if not await self.is_admin(context, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(self.formatter.error_message("𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝!"))
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(self.formatter.error_message("𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐮𝐧𝐩𝐢𝐧!"))
            return
        
        try:
            await context.bot.unpin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
            await update.message.reply_text(self.formatter.success_message("𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐮𝐧𝐩𝐢𝐧𝐧𝐞𝐝!"))
        except Exception as e:
            await update.message.reply_text(self.formatter.error_message(f"𝐅𝐚𝐢𝐥𝐞𝐝: {str(e)}"))
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user info - works with reply or username/ID"""
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        target_user = await self.extract_user(update, context)
        if not target_user:
            target_user = update.effective_user
        
        chat_id = update.effective_chat.id
        warn_count = self.user_warns.get(chat_id, {}).get(target_user.id, 0)
        
        user_data = {
            'full_name': target_user.full_name or "User",
            'user_id': target_user.id,
            'username': target_user.username or "N/A"
        }
        
        await update.message.reply_text(
            self.formatter.user_info(user_data, update.effective_chat.title or "Group", warn_count),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in groups - Link Protection"""
        if not update.message or not update.message.text:
            return
        
        chat = update.effective_chat
        user = update.effective_user
        
        # Check if user is muted
        if chat.id in self.muted_users and user.id in self.muted_users[chat.id]:
            expiry = self.muted_users[chat.id][user.id]
            if datetime.now() < expiry:
                try:
                    await update.message.delete()
                except:
                    pass
                return
            else:
                # Remove expired mute
                del self.muted_users[chat.id][user.id]
        
        group = self.db.get_group(chat.id)
        if not group:
            return
        
        if await self.is_admin(context, chat.id, user.id):
            return
        
        if self.contains_link(update.message.text):
            try:
                await update.message.delete()
                logger.info(f"Deleted link message from {user.id} in {chat.id}")
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining"""
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
        """Handle button presses from ReplyKeyboardMarkup"""
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
        """Handle chat ID input for adding group"""
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
        """Handle confirmation callback"""
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
        """Handle owner panel inline callbacks"""
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
    
    # Command handlers for group moderation
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("ban", handlers.ban_command))
    application.add_handler(CommandHandler("unban", handlers.unban_command))
    application.add_handler(CommandHandler("kick", handlers.kick_command))
    application.add_handler(CommandHandler("mute", handlers.mute_command))
    application.add_handler(CommandHandler("unmute", handlers.unmute_command))
    application.add_handler(CommandHandler("warn", handlers.warn_command))
    application.add_handler(CommandHandler("warns", handlers.warns_command))
    application.add_handler(CommandHandler("del", handlers.del_command))
    application.add_handler(CommandHandler("pin", handlers.pin_command))
    application.add_handler(CommandHandler("unpin", handlers.unpin_command))
    application.add_handler(CommandHandler("info", handlers.info_command))
    
    # Conversation handler for adding group
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f'^➕ {bold_unicode("Add Group")}$') & filters.ChatType.PRIVATE, handlers.handle_reply_keyboard)],
        states={
            ASK_CHAT_ID: [MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handlers.handle_chat_id_input)],
            CONFIRM_ADD: [CallbackQueryHandler(handlers.handle_confirmation, pattern='^(confirm_add|cancel_add)$')],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^🔙 {bold_unicode("Back to Dashboard")}$') & filters.ChatType.PRIVATE, handlers.handle_reply_keyboard)]
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
    print("🌐 Flask server running - Bot is alive!")
    print("Press Ctrl+C to stop")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
