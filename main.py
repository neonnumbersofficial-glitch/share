#!/usr/bin/env python3

import os
import sys
import time
import json
import re
import requests
import zipfile
import io
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import platform
from pathlib import Path
import asyncio
import tempfile
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ChatMemberHandler
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8222681776:AAEZoWzGxOc2wXuVKCqQjWwcT6IMxHGMDoM"
OWNER_ID = 8469461108
OWNER_USERNAME = "EXUCODER"

# Global variables
maintenance_mode = False
force_join_enabled = True
total_clones = 0
banned_users = set()
banned_groups = set()
user_data = {}  # Store user's cloned files info
user_channels = {}  # Track which channels users have joined
group_settings = {}  # Store group-specific settings
group_admins = {}  # Store group admins who can use bot features
group_welcome_enabled = {}  # Toggle welcome message per group

# Required channels with display names (what users SEE)
REQUIRED_CHANNELS = [
    {"username": "@exucoder1", "id": "@exucoder1", "display_name": "𝐄𝐗𝐔 𝐂𝐎𝐃𝐄𝐑"},
    {"username": "@exulive", "id": "@exulive", "display_name": "𝐄𝐗𝐔 𝐋𝐈𝐕𝐄"},
    {"username": "@funcodex", "id": "@funcodex", "display_name": "𝐅𝐔𝐍 𝐂𝐎𝐃𝐄𝐗"}
]

# Store user sessions
user_sessions = {}

# Font mapping for stylish text
def style_text(text):
    """Convert text to bold stylish font"""
    font_map = {
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆',
        'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍',
        'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑', 'S': '𝐒', 'T': '𝐓', 'U': '𝐔',
        'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟',
        'g': '𝐠', 'h': '𝐡', 'i': '𝐢', 'j': '𝐣', 'k': '𝐤', 'l': '𝐥',
        'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫',
        's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱',
        'y': '𝐲', 'z': '𝐳',
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔',
        '7': '𝟕', '8': '𝟖', '9': '𝟗',
    }
    
    result = ""
    for char in text:
        if char in font_map:
            result += font_map[char]
        elif char.upper() in font_map:
            result += font_map[char.upper()]
        else:
            result += char
    return result

# Button definitions
BUTTONS = {
    'fetch': style_text("🌐 𝐅𝐞𝐭𝐜𝐡"),
    'my_files': style_text("📂 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬"),
    'help': style_text("ℹ 𝐇𝐞𝐥𝐩"),
    'owner': style_text("👑 𝐎𝐰𝐧𝐞𝐫"),
    'admin_panel': style_text("🛠 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥"),
    'stats': style_text("📊 𝐒𝐭𝐚𝐭𝐬"),
    'broadcast': style_text("📢 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭"),
    'settings': style_text("⚙ 𝐒𝐞𝐭𝐭𝐢𝐧𝐠𝐬"),
    'ban_user': style_text("🚫 𝐁𝐚𝐧 𝐔𝐬𝐞𝐫"),
    'maintenance': style_text("☢️ 𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞"),
    'force_join': style_text("🔐 𝐅𝐨𝐫𝐜𝐞 𝐉𝐨𝐢𝐧"),
    'back': style_text("🔙 𝐁𝐚𝐜𝐤"),
    'download': style_text("📥 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝"),
    'delete': style_text("🗑️ 𝐃𝐞𝐥𝐞𝐭𝐞"),
    'refresh': style_text("🔄 𝐑𝐞𝐟𝐫𝐞𝐬𝐡"),
    'groups': style_text("📢 𝐆𝐫𝐨𝐮𝐩𝐬"),  # New Groups button
    'group_stats': style_text("📊 𝐆𝐫𝐨𝐮𝐩 𝐒𝐭𝐚𝐭𝐬"),
    'group_ban': style_text("🚫 𝐁𝐚𝐧 𝐆𝐫𝐨𝐮𝐩"),
    'group_unban': style_text("✅ 𝐔𝐧𝐛𝐚𝐧 𝐆𝐫𝐨𝐮𝐩"),
    'group_list': style_text("📋 𝐆𝐫𝐨𝐮𝐩 𝐋𝐢𝐬𝐭"),
    'group_settings': style_text("⚙️ 𝐆𝐫𝐨𝐮𝐩 𝐒𝐞𝐭𝐭𝐢𝐧𝐠𝐬"),
}

def create_main_menu_keyboard(is_owner=False):
    """Create main menu keyboard with exact layout"""
    keyboard = [
        # Row 1: Fetch and My Files
        [KeyboardButton(BUTTONS['fetch']), KeyboardButton(BUTTONS['my_files'])],
        
        # Row 2: Help (centered)
        [KeyboardButton(BUTTONS['help'])],
    ]
    
    # Row 3: Owner button (if owner)
    if is_owner:
        keyboard.append([KeyboardButton(BUTTONS['owner'])])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_admin_panel_keyboard():
    """Create admin panel keyboard with exact layout including Groups button"""
    keyboard = [
        # Row 1: Stats and Broadcast
        [KeyboardButton(BUTTONS['stats']), KeyboardButton(BUTTONS['broadcast'])],
        
        # Row 2: Settings and Ban User
        [KeyboardButton(BUTTONS['settings']), KeyboardButton(BUTTONS['ban_user'])],
        
        # Row 3: Maintenance and Force Join
        [KeyboardButton(BUTTONS['maintenance']), KeyboardButton(BUTTONS['force_join'])],
        
        # Row 4: Groups button (NEW)
        [KeyboardButton(BUTTONS['groups'])],
        
        # Row 5: Back button
        [KeyboardButton(BUTTONS['back'])]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_groups_menu_keyboard():
    """Create groups management keyboard"""
    keyboard = [
        # Row 1: Group Stats and List
        [KeyboardButton(BUTTONS['group_stats']), KeyboardButton(BUTTONS['group_list'])],
        
        # Row 2: Ban/Unban Group
        [KeyboardButton(BUTTONS['group_ban']), KeyboardButton(BUTTONS['group_unban'])],
        
        # Row 3: Group Settings
        [KeyboardButton(BUTTONS['group_settings'])],
        
        # Row 4: Back to Admin Panel
        [KeyboardButton(BUTTONS['back'])]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_files_keyboard(user_id):
    """Create keyboard for user's files"""
    keyboard = []
    
    if user_id in user_data and user_data[user_id]:
        for i, file_info in enumerate(user_data[user_id][-10:]):  # Show last 10 files
            btn_text = f"{i+1}. {file_info['name'][:20]}"
            keyboard.append([KeyboardButton(f"📁 {btn_text}")])
    
    keyboard.append([KeyboardButton(BUTTONS['back'])])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

class WebsiteCloner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    async def clone_website(self, url, user_id):
        """Clone a website and return zip file"""
        global total_clones
        
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            
            # Fetch website
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Save HTML
            html_path = os.path.join(temp_dir, "index.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Create asset folders
            js_folder = os.path.join(temp_dir, "js")
            css_folder = os.path.join(temp_dir, "css")
            img_folder = os.path.join(temp_dir, "images")
            os.makedirs(js_folder, exist_ok=True)
            os.makedirs(css_folder, exist_ok=True)
            os.makedirs(img_folder, exist_ok=True)
            
            # Download JavaScript
            js_count = 0
            for script in soup.find_all('script'):
                if script.get('src'):
                    js_url = urljoin(url, script['src'])
                    try:
                        js_data = self.session.get(js_url, timeout=10).content
                        js_name = os.path.basename(urlparse(js_url).path) or f"script_{js_count}.js"
                        with open(os.path.join(js_folder, js_name), 'wb') as f:
                            f.write(js_data)
                        js_count += 1
                    except:
                        pass
            
            # Download CSS
            css_count = 0
            for link in soup.find_all('link', rel='stylesheet'):
                if link.get('href'):
                    css_url = urljoin(url, link['href'])
                    try:
                        css_data = self.session.get(css_url, timeout=10).content
                        css_name = os.path.basename(urlparse(css_url).path) or f"style_{css_count}.css"
                        with open(os.path.join(css_folder, css_name), 'wb') as f:
                            f.write(css_data)
                        css_count += 1
                    except:
                        pass
            
            # Download Images
            img_count = 0
            for img in soup.find_all('img', src=True):
                img_url = urljoin(url, img['src'])
                try:
                    img_data = self.session.get(img_url, timeout=10).content
                    img_name = os.path.basename(urlparse(img_url).path) or f"image_{img_count}.jpg"
                    with open(os.path.join(img_folder, img_name), 'wb') as f:
                        f.write(img_data)
                    img_count += 1
                except:
                    pass
            
            # Create metadata
            metadata = {
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'title': soup.title.string if soup.title else 'No title',
                'js': js_count,
                'css': css_count,
                'images': img_count
            }
            
            # Save metadata
            with open(os.path.join(temp_dir, "metadata.json"), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Create zip file
            zip_filename = f"website_{int(time.time())}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file != zip_filename:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
            
            total_clones += 1
            
            # Store file info for user
            file_info = {
                'name': f"{urlparse(url).netloc}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'files': {
                    'html': 1,
                    'js': js_count,
                    'css': css_count,
                    'images': img_count
                },
                'zip_path': zip_path
            }
            
            if user_id not in user_data:
                user_data[user_id] = []
            
            user_data[user_id].append(file_info)
            
            # Keep only last 20 files per user
            if len(user_data[user_id]) > 20:
                old_file = user_data[user_id].pop(0)
                try:
                    os.remove(old_file['zip_path'])
                    shutil.rmtree(os.path.dirname(old_file['zip_path']))
                except:
                    pass
            
            return zip_path, metadata
        
        except Exception as e:
            # Clean up temp directory on error
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            raise Exception(f"Failed to clone website: {str(e)}")

async def check_subscription(user_id, context):
    """Check if user is subscribed to all required channels"""
    if not force_join_enabled:
        return True, []
    
    missing_channels = []
    joined_channels = []
    
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel['id'], user_id=user_id)
            if member.status in ['left', 'kicked']:
                missing_channels.append(channel)
            else:
                joined_channels.append(channel['display_name'])
        except Exception as e:
            logger.error(f"Error checking channel {channel.get('username')}: {e}")
            missing_channels.append(channel)
    
    # Store which channels user has joined
    if user_id not in user_channels:
        user_channels[user_id] = []
    user_channels[user_id] = joined_channels
    
    return len(missing_channels) == 0, missing_channels

async def handle_channel_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when user joins or leaves a channel"""
    chat_member = update.chat_member
    user = chat_member.new_chat_member.user
    chat = chat_member.chat
    
    # Find the channel display name
    channel_display = chat.title
    for channel in REQUIRED_CHANNELS:
        if channel['username'] == f"@{chat.username}":
            channel_display = channel['display_name']
            break
    
    # Only notify for the required channels
    channel_usernames = [c['username'] for c in REQUIRED_CHANNELS]
    if f"@{chat.username}" not in channel_usernames:
        return
    
    # Check if user joined
    if chat_member.new_chat_member.status in ['member', 'administrator', 'creator']:
        if chat_member.old_chat_member.status in ['left', 'kicked']:
            # User joined the channel
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"✅ {style_text('𝐔𝐬𝐞𝐫 𝐉𝐨𝐢𝐧𝐞𝐝 𝐂𝐡𝐚𝐧𝐧𝐞𝐥')}\n\n"
                    f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {user.first_name}\n"
                    f"🆔 {style_text('𝐈𝐃')}: {user.id}\n"
                    f"📢 {style_text('𝐂𝐡𝐚𝐧𝐧𝐞𝐥')}: {channel_display}\n"
                    f"⏰ {style_text('𝐓𝐢𝐦𝐞')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
    
    # Check if user left
    elif chat_member.new_chat_member.status in ['left', 'kicked']:
        if chat_member.old_chat_member.status in ['member', 'administrator', 'creator']:
            # User left the channel
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"❌ {style_text('𝐔𝐬𝐞𝐫 𝐋𝐞𝐟𝐭 𝐂𝐡𝐚𝐧𝐧𝐞𝐥')}\n\n"
                    f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {user.first_name}\n"
                    f"🆔 {style_text('𝐈𝐃')}: {user.id}\n"
                    f"📢 {style_text('𝐂𝐡𝐚𝐧𝐧𝐞𝐥')}: {channel_display}\n"
                    f"⏰ {style_text('𝐓𝐢𝐦𝐞')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )

async def force_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force user to subscribe to channels"""
    user = update.effective_user
    
    # Check which channels are missing
    is_subscribed, missing_channels = await check_subscription(user.id, context)
    
    if is_subscribed:
        # User is subscribed to all, proceed to main menu
        is_owner = (user.id == OWNER_ID)
        await update.message.reply_text(
            style_text('✅ 𝐕𝐞𝐫𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥! 𝐀𝐜𝐜𝐞𝐬𝐬 𝐠𝐫𝐚𝐧𝐭𝐞𝐝.'),
            reply_markup=create_main_menu_keyboard(is_owner)
        )
        return
    
    # Create keyboard with join buttons for missing channels
    keyboard = []
    for channel in missing_channels:
        keyboard.append([InlineKeyboardButton(
            f"📢 Join {channel['display_name']}", 
            url=f"https://t.me/{channel['username'][1:]}"
        )])
    
    # Add refresh button
    keyboard.append([InlineKeyboardButton(
        BUTTONS['refresh'],
        callback_data="verify_sub"
    )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create message listing missing channels with DISPLAY NAMES only
    missing_list = ""
    for i, channel in enumerate(missing_channels, 1):
        missing_list += f"{i}. 📢 {channel['display_name']}\n"
    
    message = (
        f"╔═══《 {style_text('𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐑𝐄𝐐𝐔𝐈𝐑𝐄𝐃')} 》═══╗\n\n"
        f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {style_text(user.first_name)}\n"
        f"🆔 {style_text('𝐔𝐬𝐞𝐫 𝐈𝐃')}: {user.id}\n\n"
        f"╰═══════《 {style_text('𝐌𝐈𝐒𝐒𝐈𝐍𝐆 𝐂𝐇𝐀𝐍𝐍𝐄𝐋𝐒')} 》═══════╝\n\n"
        f"{style_text('𝐘𝐨𝐮 𝐬𝐭𝐢𝐥𝐥 𝐧𝐞𝐞𝐝 𝐭𝐨 𝐣𝐨𝐢𝐧')}:\n\n"
        f"{missing_list}\n"
        f"{style_text('𝐏𝐥𝐞𝐚𝐬𝐞 𝐣𝐨𝐢𝐧 𝐚𝐧𝐝 𝐭𝐡𝐞𝐧 𝐜𝐥𝐢𝐜𝐤')} {BUTTONS['refresh']} ✅\n"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in groups"""
    chat = update.effective_chat
    user = update.effective_user
    
    # Check if group is banned
    if chat.id in banned_groups:
        return
    
    # Store group info
    if chat.id not in group_settings:
        group_settings[chat.id] = {
            'title': chat.title,
            'first_seen': datetime.now().isoformat(),
            'member_count': await chat.get_member_count() if hasattr(chat, 'get_member_count') else 0,
            'welcome_enabled': True
        }
    
    # Check if user is admin in this group
    try:
        chat_member = await chat.get_member(user.id)
        is_group_admin = chat_member.status in ['administrator', 'creator']
        
        if is_group_admin and user.id not in group_admins.get(chat.id, []):
            if chat.id not in group_admins:
                group_admins[chat.id] = []
            group_admins[chat.id].append(user.id)
    except:
        is_group_admin = False
    
    # Handle group commands
    if update.message and update.message.text:
        text = update.message.text
        
        # Show chat ID command
        if text == '/chatid' or text == '/id':
            await update.message.reply_text(
                f"╔═══《 {style_text('𝐂𝐇𝐀𝐓 𝐈𝐍𝐅𝐎𝐑𝐌𝐀𝐓𝐈𝐎𝐍')} 》═══╗\n\n"
                f"💬 {style_text('𝐂𝐡𝐚𝐭 𝐍𝐚𝐦𝐞')}: {chat.title}\n"
                f"🆔 {style_text('𝐂𝐡𝐚𝐭 𝐈𝐃')}: `{chat.id}`\n"
                f"👥 {style_text('𝐓𝐲𝐩𝐞')}: {chat.type}\n\n"
                f"👤 {style_text('𝐘𝐨𝐮𝐫 𝐈𝐃')}: `{user.id}`\n"
                f"👑 {style_text('𝐀𝐝𝐦𝐢𝐧')}: {'✅' if is_group_admin else '❌'}\n"
                f"╰═══════《 🤖 》═══════╝"
            )
        
        # Group welcome toggle for admins
        elif text == '/togglewelcome' and is_group_admin:
            group_settings[chat.id]['welcome_enabled'] = not group_settings[chat.id]['welcome_enabled']
            status = "𝐄𝐧𝐚𝐛𝐥𝐞𝐝" if group_settings[chat.id]['welcome_enabled'] else "𝐃𝐢𝐬𝐚𝐛𝐥𝐞𝐝"
            await update.message.reply_text(
                f"✅ {style_text(f'𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 {status} 𝐢𝐧 𝐭𝐡𝐢𝐬 𝐠𝐫𝐨𝐮𝐩')}"
            )
        
        # Show group stats (admin only)
        elif text == '/groupstats' and is_group_admin:
            await show_group_stats(update, context, chat.id)

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when new members join a group"""
    chat = update.effective_chat
    
    # Check if group is banned
    if chat.id in banned_groups:
        return
    
    # Check if welcome is enabled for this group
    if not group_settings.get(chat.id, {}).get('welcome_enabled', True):
        return
    
    for new_member in update.message.new_chat_members:
        # Don't welcome bots (including itself)
        if new_member.is_bot:
            continue
        
        welcome_msg = (
            f"╔═══《 {style_text('𝐖𝐄𝐋𝐂𝐎𝐌𝐄')} 》═══╗\n\n"
            f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {style_text(new_member.first_name)}\n"
            f"🆔 {style_text('𝐈𝐃')}: {new_member.id}\n\n"
            f"📢 {style_text('𝐆𝐫𝐨𝐮𝐩')}: {chat.title}\n"
            f"🆔 {style_text('𝐂𝐡𝐚𝐭 𝐈𝐃')}: `{chat.id}`\n\n"
            f"{style_text('𝐓𝐲𝐩𝐞')} /id {style_text('𝐭𝐨 𝐠𝐞𝐭 𝐲𝐨𝐮𝐫 𝐈𝐃')}\n"
            f"╰═══════《 🎉 》═══════╝"
        )
        
        await update.message.reply_text(welcome_msg)

async def show_group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id):
    """Show statistics for a specific group"""
    if chat_id not in group_settings:
        await update.message.reply_text(f"{style_text('❌ 𝐍𝐨 𝐬𝐭𝐚𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞 𝐟𝐨𝐫 𝐭𝐡𝐢𝐬 𝐠𝐫𝐨𝐮𝐩')}")
        return
    
    settings = group_settings[chat_id]
    admins = group_admins.get(chat_id, [])
    
    stats_msg = (
        f"╔═══《 {style_text('𝐆𝐑𝐎𝐔𝐏 𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒')} 》═══╗\n\n"
        f"📢 {style_text('𝐆𝐫𝐨𝐮𝐩')}: {settings['title']}\n"
        f"🆔 {style_text('𝐂𝐡𝐚𝐭 𝐈𝐃')}: `{chat_id}`\n"
        f"👥 {style_text('𝐌𝐞𝐦𝐛𝐞𝐫𝐬')}: {settings.get('member_count', 'N/A')}\n"
        f"📅 {style_text('𝐀𝐝𝐝𝐞𝐝')}: {settings['first_seen'][:10]}\n"
        f"👑 {style_text('𝐀𝐝𝐦𝐢𝐧𝐬')}: {len(admins)}\n"
        f"🔔 {style_text('𝐖𝐞𝐥𝐜𝐨𝐦𝐞')}: {'𝐎𝐍' if settings.get('welcome_enabled', True) else '𝐎𝐅𝐅'}\n\n"
        f"{style_text('𝐀𝐝𝐦𝐢𝐧 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬')}:\n"
        f"/togglewelcome - {style_text('𝐎𝐧/𝐎𝐟𝐟 𝐰𝐞𝐥𝐜𝐨𝐦𝐞')}\n"
        f"/groupstats - {style_text('𝐒𝐡𝐨𝐰 𝐭𝐡𝐢𝐬 𝐦𝐞𝐧𝐮')}\n"
        f"/id - {style_text('𝐒𝐡𝐨𝐰 𝐜𝐡𝐚𝐭 𝐈𝐃')}\n"
    )
    
    await update.message.reply_text(stats_msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    chat = update.effective_chat
    
    # If in group, show group info
    if chat.type != 'private':
        await handle_group_message(update, context)
        return
    
    # Private chat logic (existing)
    # Check if user is banned
    if user.id in banned_users:
        await update.message.reply_text(f"{style_text('❌ 𝐘𝐨𝐮 𝐚𝐫𝐞 𝐛𝐚𝐧𝐧𝐞𝐝 𝐟𝐫𝐨𝐦 𝐮𝐬𝐢𝐧𝐠 𝐭𝐡𝐢𝐬 𝐛𝐨𝐭')}")
        return
    
    # Check maintenance mode
    if maintenance_mode and user.id != OWNER_ID:
        await update.message.reply_text(
            f"{style_text('☢️ 𝐁𝐨𝐭 𝐢𝐬 𝐮𝐧𝐝𝐞𝐫 𝐦𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞')}\n"
            f"{style_text('𝐏𝐥𝐞𝐚𝐬𝐞 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧 𝐥𝐚𝐭𝐞𝐫')}"
        )
        return
    
    # Check subscription
    is_subscribed, missing_channels = await check_subscription(user.id, context)
    
    if not is_subscribed and force_join_enabled:
        await force_subscribe(update, context)
        return
    
    # If subscribed, show welcome message
    welcome_msg = (
        f"╔═══《 {style_text('𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐄𝐗𝐔 𝐂𝐎𝐃𝐄𝐗')} 》═══╗\n\n"
        f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {style_text(user.first_name)}\n"
        f"🆔 {style_text('𝐔𝐬𝐞𝐫 𝐈𝐃')}: {user.id}\n"
        f"🌟 {style_text('𝐒𝐭𝐚𝐭𝐮𝐬')}: {style_text('𝐀𝐜𝐭𝐢𝐯𝐞')}\n\n"
        f"╰═══════《 {style_text('𝐁𝐎𝐓 𝐅𝐄𝐀𝐓𝐔𝐑𝐄𝐒')} 》═══════╝\n\n"
        f"📌 {style_text('𝐀𝐛𝐨𝐮𝐭 𝐓𝐡𝐢𝐬 𝐁𝐨𝐭')}:\n"
        f"• {style_text('🌐 𝐖𝐞𝐛𝐬𝐢𝐭𝐞 𝐂𝐥𝐨𝐧𝐢𝐧𝐠 𝐁𝐨𝐭')}\n"
        f"• {style_text('📥 𝐂𝐥𝐨𝐧𝐞 𝐚𝐧𝐲 𝐰𝐞𝐛𝐬𝐢𝐭𝐞 𝐚𝐧𝐝 𝐠𝐞𝐭 𝐙𝐈𝐏 𝐟𝐢𝐥𝐞')}\n"
        f"• {style_text('💾 𝐀𝐥𝐥 𝐟𝐢𝐥𝐞𝐬 (𝐇𝐓𝐌𝐋, 𝐂𝐒𝐒, 𝐉𝐒, 𝐢𝐦𝐚𝐠𝐞𝐬)')}\n"
        f"• {style_text('📂 𝐒𝐚𝐯𝐞 𝐟𝐢𝐥𝐞𝐬 𝐢𝐧 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬 𝐟𝐨𝐫 𝐥𝐚𝐭𝐞𝐫')}\n"
        f"• {style_text('⚡ 𝐅𝐚𝐬𝐭 𝐩𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐬𝐩𝐞𝐞𝐝')}\n\n"
        f"╔═══《 {style_text('𝐇𝐎𝐖 𝐓𝐎 𝐔𝐒𝐄')} 》═══╗\n\n"
        f"1️⃣ {style_text('𝐂𝐥𝐢𝐜𝐤 𝐨𝐧')} {BUTTONS['fetch']} {style_text('𝐛𝐮𝐭𝐭𝐨𝐧')}\n"
        f"2️⃣ {style_text('𝐒𝐞𝐧𝐝 𝐚𝐧𝐲 𝐰𝐞𝐛𝐬𝐢𝐭𝐞 𝐔𝐑𝐋')}\n"
        f"3️⃣ {style_text('𝐆𝐞𝐭 𝐙𝐈𝐏 𝐟𝐢𝐥𝐞 𝐰𝐢𝐭𝐡 𝐚𝐥𝐥 𝐬𝐨𝐮𝐫𝐜𝐞𝐬')}\n"
        f"4️⃣ {style_text('𝐂𝐡𝐞𝐜𝐤')} {BUTTONS['my_files']} {style_text('𝐟𝐨𝐫 𝐬𝐚𝐯𝐞𝐝 𝐟𝐢𝐥𝐞𝐬')}\n\n"
        f"╰═══════《 {style_text('𝐄𝐍𝐉𝐎𝐘 𝐂𝐋𝐎𝐍𝐈𝐍𝐆')} 》═══════╝"
    )
    
    is_owner = (user.id == OWNER_ID)
    await update.message.reply_text(
        welcome_msg, 
        reply_markup=create_main_menu_keyboard(is_owner)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "verify_sub":
        # Check subscription again
        is_subscribed, missing_channels = await check_subscription(user_id, context)
        
        if is_subscribed:
            success_msg = (
                f"╔═══《 {style_text('✅ 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋')} 》═══╗\n\n"
                f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {style_text(query.from_user.first_name)}\n"
                f"🆔 {style_text('𝐔𝐬𝐞𝐫 𝐈𝐃')}: {user_id}\n\n"
                f"╰═══════《 {style_text('𝐀𝐂𝐂𝐄𝐒𝐒 𝐆𝐑𝐀𝐍𝐓𝐄𝐃')} 》═══════╝\n\n"
                f"{style_text('✅ 𝐘𝐨𝐮 𝐡𝐚𝐯𝐞 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲 𝐯𝐞𝐫𝐢𝐟𝐢𝐞𝐝!')}\n"
                f"{style_text('📌 𝐘𝐨𝐮 𝐜𝐚𝐧 𝐧𝐨𝐰 𝐮𝐬𝐞 𝐭𝐡𝐞 𝐛𝐨𝐭')}\n"
            )
            await query.edit_message_text(success_msg)
            
            # Send main menu
            is_owner = (user_id == OWNER_ID)
            await query.message.reply_text(
                style_text('📋 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮'),
                reply_markup=create_main_menu_keyboard(is_owner)
            )
        else:
            # Show which channels are still missing with DISPLAY NAMES
            missing_list = ""
            for i, channel in enumerate(missing_channels, 1):
                missing_list += f"{i}. 📢 {channel['display_name']}\n"
            
            # Create keyboard with join buttons
            keyboard = []
            for channel in missing_channels:
                keyboard.append([InlineKeyboardButton(
                    f"📢 Join {channel['display_name']}", 
                    url=f"https://t.me/{channel['username'][1:]}"
                )])
            
            keyboard.append([InlineKeyboardButton(
                BUTTONS['refresh'],
                callback_data="verify_sub"
            )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            fail_msg = (
                f"╔═══《 {style_text('❌ 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐅𝐀𝐈𝐋𝐄𝐃')} 》═══╗\n\n"
                f"👤 {style_text('𝐔𝐬𝐞𝐫')}: {style_text(query.from_user.first_name)}\n"
                f"🆔 {style_text('𝐔𝐬𝐞𝐫 𝐈𝐃')}: {user_id}\n\n"
                f"╰═══════《 {style_text('𝐌𝐈𝐒𝐒𝐈𝐍𝐆 𝐂𝐇𝐀𝐍𝐍𝐄𝐋𝐒')} 》═══════╝\n\n"
                f"{style_text('𝐘𝐨𝐮 𝐬𝐭𝐢𝐥𝐥 𝐧𝐞𝐞𝐝 𝐭𝐨 𝐣𝐨𝐢𝐧')}:\n\n"
                f"{missing_list}\n"
                f"{style_text('𝐏𝐥𝐞𝐚𝐬𝐞 𝐣𝐨𝐢𝐧 𝐚𝐧𝐝 𝐭𝐡𝐞𝐧 𝐜𝐥𝐢𝐜𝐤')} {BUTTONS['refresh']} ✅\n"
            )
            await query.edit_message_text(fail_msg, reply_markup=reply_markup)
    
    elif query.data.startswith("download_"):
        index = int(query.data.split("_")[1])
        if user_id in user_data and 0 <= index < len(user_data[user_id][-10:]):
            file_info = user_data[user_id][-10:][index]
            
            try:
                with open(file_info['zip_path'], 'rb') as f:
                    await query.message.reply_document(
                        document=f,
                        filename=os.path.basename(file_info['zip_path']),
                        caption=f"✅ {style_text('𝐅𝐢𝐥𝐞:')} {file_info['name']}"
                    )
            except:
                await query.message.reply_text(
                    f"{style_text('❌ 𝐅𝐢𝐥𝐞 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝')}"
                )
    
    elif query.data.startswith("delete_"):
        index = int(query.data.split("_")[1])
        if user_id in user_data and 0 <= index < len(user_data[user_id][-10:]):
            file_info = user_data[user_id].pop(-10 + index)
            try:
                os.remove(file_info['zip_path'])
                shutil.rmtree(os.path.dirname(file_info['zip_path']))
            except:
                pass
            
            await query.message.edit_text(
                f"{style_text('✅ 𝐅𝐢𝐥𝐞 𝐝𝐞𝐥𝐞𝐭𝐞𝐝 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲')}"
            )
    
    elif query.data == "back_to_files":
        if user_id in user_data and user_data[user_id]:
            msg = f"{style_text('📂 𝐘𝐨𝐮𝐫 𝐬𝐚𝐯𝐞𝐝 𝐰𝐞𝐛𝐬𝐢𝐭𝐞𝐬')}:\n\n"
            for i, file_info in enumerate(user_data[user_id][-10:]):
                msg += f"{i+1}. {file_info['name']}\n"
            
            await query.message.edit_text(
                msg,
                reply_markup=create_files_keyboard(user_id)
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages"""
    global maintenance_mode, force_join_enabled
    
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    
    # Handle group messages first
    if chat.type != 'private':
        await handle_group_message(update, context)
        
        # Don't process further commands in groups unless it's a command
        if not text.startswith('/'):
            return
    
    # Private chat logic (existing)
    # Check if user is banned
    if user.id in banned_users:
        await update.message.reply_text(f"{style_text('❌ 𝐘𝐨𝐮 𝐚𝐫𝐞 𝐛𝐚𝐧𝐧𝐞𝐝 𝐟𝐫𝐨𝐦 𝐮𝐬𝐢𝐧𝐠 𝐭𝐡𝐢𝐬 𝐛𝐨𝐭')}")
        return
    
    # Check maintenance mode
    if maintenance_mode and user.id != OWNER_ID:
        await update.message.reply_text(
            f"{style_text('☢️ 𝐁𝐨𝐭 𝐢𝐬 𝐮𝐧𝐝𝐞𝐫 𝐦𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞')}\n"
            f"{style_text('𝐏𝐥𝐞𝐚𝐬𝐞 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧 𝐥𝐚𝐭𝐞𝐫')}"
        )
        return
    
    # Check subscription
    is_subscribed, missing_channels = await check_subscription(user.id, context)
    if not is_subscribed and force_join_enabled:
        await force_subscribe(update, context)
        return
    
    # Initialize cloner if not exists
    if 'cloner' not in context.chat_data:
        context.chat_data['cloner'] = WebsiteCloner()
    
    cloner = context.chat_data['cloner']
    
    # Handle button clicks
    if text == BUTTONS['fetch']:
        await update.message.reply_text(
            f"{style_text('🌐 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐦𝐞 𝐭𝐡𝐞 𝐰𝐞𝐛𝐬𝐢𝐭𝐞 𝐔𝐑𝐋 𝐲𝐨𝐮 𝐰𝐚𝐧𝐭 𝐭𝐨 𝐜𝐥𝐨𝐧𝐞')}\n\n"
            f"{style_text('𝐄𝐱𝐚𝐦𝐩𝐥𝐞')}: https://example.com"
        )
        user_sessions[user.id] = 'waiting_for_url'
    
    elif text == BUTTONS['my_files']:
        if user.id in user_data and user_data[user.id]:
            msg = f"{style_text('📂 𝐘𝐨𝐮𝐫 𝐬𝐚𝐯𝐞𝐝 𝐰𝐞𝐛𝐬𝐢𝐭𝐞𝐬')}:\n\n"
            for i, file_info in enumerate(user_data[user.id][-10:]):
                msg += f"{i+1}. {file_info['name']}\n"
                msg += f"   📅 {file_info['timestamp'][:10]}\n"
                msg += f"   📄 HTML | ⚡ JS: {file_info['files']['js']} | 🎨 CSS: {file_info['files']['css']} | 🖼️ Images: {file_info['files']['images']}\n\n"
            
            await update.message.reply_text(
                msg,
                reply_markup=create_files_keyboard(user.id)
            )
        else:
            await update.message.reply_text(
                f"{style_text('📂 𝐍𝐨 𝐬𝐚𝐯𝐞𝐝 𝐰𝐞𝐛𝐬𝐢𝐭𝐞𝐬 𝐲𝐞𝐭')}\n\n"
                f"{style_text('𝐔𝐬𝐞')} {BUTTONS['fetch']} {style_text('𝐭𝐨 𝐜𝐥𝐨𝐧𝐞 𝐚 𝐰𝐞𝐛𝐬𝐢𝐭𝐞')}"
            )
    
    elif text.startswith("📁 "):
        # Handle file selection from My Files
        try:
            index = int(text.split(". ")[0].replace("📁 ", "")) - 1
            if user.id in user_data and 0 <= index < len(user_data[user.id][-10:]):
                file_info = user_data[user.id][-10:][index]
                
                # Create inline keyboard for file options
                keyboard = [
                    [InlineKeyboardButton(BUTTONS['download'], callback_data=f"download_{index}")],
                    [InlineKeyboardButton(BUTTONS['delete'], callback_data=f"delete_{index}")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_files")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"📁 {style_text('𝐅𝐢𝐥𝐞 𝐈𝐧𝐟𝐨')}:\n\n"
                    f"📌 {style_text('𝐍𝐚𝐦𝐞')}: {file_info['name']}\n"
                    f"🌐 {style_text('𝐔𝐑𝐋')}: {file_info['url']}\n"
                    f"📅 {style_text('𝐃𝐚𝐭𝐞')}: {file_info['timestamp']}\n\n"
                    f"{style_text('𝐂𝐡𝐨𝐨𝐬𝐞 𝐚𝐧 𝐨𝐩𝐭𝐢𝐨𝐧')}:",
                    reply_markup=reply_markup
                )
        except:
            pass
    
    elif text == BUTTONS['help']:
        help_msg = (
            f"╔═══《 {style_text('𝐇𝐄𝐋𝐏 𝐌𝐄𝐍𝐔')} 》═══╗\n\n"
            f"{BUTTONS['fetch']} - {style_text('𝐂𝐥𝐨𝐧𝐞 𝐚 𝐰𝐞𝐛𝐬𝐢𝐭𝐞')}\n"
            f"{BUTTONS['my_files']} - {style_text('𝐕𝐢𝐞𝐰 𝐬𝐚𝐯𝐞𝐝 𝐟𝐢𝐥𝐞𝐬')}\n"
            f"{BUTTONS['help']} - {style_text('𝐒𝐡𝐨𝐰 𝐭𝐡𝐢𝐬 𝐦𝐞𝐧𝐮')}\n"
            f"{BUTTONS['owner']} - {style_text('𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐨𝐰𝐧𝐞𝐫')}\n\n"
            f"{style_text('𝐇𝐨𝐰 𝐭𝐨 𝐮𝐬𝐞')}:\n"
            f"1. {style_text('𝐂𝐥𝐢𝐜𝐤')} {BUTTONS['fetch']}\n"
            f"2. {style_text('𝐒𝐞𝐧𝐝 𝐚 𝐔𝐑𝐋')}\n"
            f"3. {style_text('𝐆𝐞𝐭 𝐙𝐈𝐏 𝐟𝐢𝐥𝐞')}\n"
            f"4. {style_text('𝐅𝐢𝐥𝐞𝐬 𝐚𝐮𝐭𝐨-𝐬𝐚𝐯𝐞𝐝 𝐢𝐧')} {BUTTONS['my_files']}\n\n"
            f"{style_text('𝐍𝐨𝐭𝐞')}: {style_text('𝐌𝐚𝐱 𝐟𝐢𝐥𝐞 𝐬𝐢𝐳𝐞 50𝐌𝐁')}\n"
        )
        await update.message.reply_text(help_msg)
    
    elif text == BUTTONS['owner'] and user.id == OWNER_ID:
        # Show admin panel for owner
        admin_msg = (
            f"╔═══《 {style_text('🛠 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋')} 》═══╗\n\n"
            f"👑 {style_text('𝐎𝐰𝐧𝐞𝐫')}: @{OWNER_USERNAME}\n"
            f"🆔 {style_text('𝐈𝐃')}: {OWNER_ID}\n\n"
            f"╰═══════《 {style_text('𝐀𝐃𝐌𝐈𝐍 𝐌𝐄𝐍𝐔')} 》═══════╝\n\n"
            f"{style_text('𝐒𝐞𝐥𝐞𝐜𝐭 𝐚𝐧 𝐨𝐩𝐭𝐢𝐨𝐧 𝐛𝐞𝐥𝐨𝐰')}:\n"
        )
        await update.message.reply_text(admin_msg, reply_markup=create_admin_panel_keyboard())
    
    elif text == BUTTONS['owner']:
        # Contact owner for normal users
        await update.message.reply_text(
            f"╔═══《 {style_text('👑 𝐂𝐎𝐍𝐓𝐀𝐂𝐓 𝐎𝐖𝐍𝐄𝐑')} 》═══╗\n\n"
            f"📢 {style_text('𝐎𝐰𝐧𝐞𝐫')}: @{OWNER_USERNAME}\n\n"
            f"{style_text('𝐅𝐨𝐫 𝐚𝐧𝐲 𝐢𝐬𝐬𝐮𝐞𝐬 𝐨𝐫 𝐪𝐮𝐞𝐫𝐢𝐞𝐬')}\n"
            f"{style_text('𝐏𝐥𝐞𝐚𝐬𝐞 𝐜𝐨𝐧𝐭𝐚𝐜𝐭 𝐭𝐡𝐞 𝐨𝐰𝐧𝐞𝐫')}\n"
        )
    
    elif text == BUTTONS['back']:
        is_owner = (user.id == OWNER_ID)
        await update.message.reply_text(
            style_text('🔙 𝐑𝐞𝐭𝐮𝐫𝐧𝐢𝐧𝐠 𝐭𝐨 𝐦𝐚𝐢𝐧 𝐦𝐞𝐧𝐮'),
            reply_markup=create_main_menu_keyboard(is_owner)
        )
    
    # Groups button handler
    elif text == BUTTONS['groups'] and user.id == OWNER_ID:
        await show_groups_menu(update, context)
    
    # Groups submenu handlers
    elif text == BUTTONS['group_stats'] and user.id == OWNER_ID:
        await show_all_groups_stats(update, context)
    
    elif text == BUTTONS['group_list'] and user.id == OWNER_ID:
        await show_groups_list(update, context)
    
    elif text == BUTTONS['group_ban'] and user.id == OWNER_ID:
        await update.message.reply_text(
            f"{style_text('🚫 𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩 𝐈𝐃 𝐭𝐨 𝐛𝐚𝐧')}\n"
            f"{style_text('𝐅𝐨𝐫𝐦𝐚𝐭')}: /bangroup -100123456789"
        )
    
    elif text == BUTTONS['group_unban'] and user.id == OWNER_ID:
        await update.message.reply_text(
            f"{style_text('✅ 𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐠𝐫𝐨𝐮𝐩 𝐈𝐃 𝐭𝐨 𝐮𝐧𝐛𝐚𝐧')}\n"
            f"{style_text('𝐅𝐨𝐫𝐦𝐚𝐭')}: /unbangroup -100123456789"
        )
    
    elif text == BUTTONS['group_settings'] and user.id == OWNER_ID:
        await show_group_settings_menu(update, context)
    
    # Admin panel buttons (existing)
    elif text == BUTTONS['stats'] and user.id == OWNER_ID:
        total_users = len(user_data)
        total_files = sum(len(files) for files in user_data.values())
        total_groups = len(group_settings)
        banned_groups_count = len(banned_groups)
        
        # Get channel join statistics
        total_channel_members = {}
        for channel in REQUIRED_CHANNELS:
            try:
                chat = await context.bot.get_chat(chat_id=channel['id'])
                total_channel_members[channel['display_name']] = chat.get_member_count()
            except:
                total_channel_members[channel['display_name']] = 'N/A'
        
        stats_msg = (
            f"╔═══《 {style_text('📊 𝐁𝐎𝐓 𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒')} 》═══╗\n\n"
            f"👥 {style_text('𝐁𝐨𝐭 𝐔𝐬𝐞𝐫𝐬')}: {total_users}\n"
            f"📁 {style_text('𝐓𝐨𝐭𝐚𝐥 𝐅𝐢𝐥𝐞𝐬')}: {total_files}\n"
            f"📥 {style_text('𝐓𝐨𝐭𝐚𝐥 𝐂𝐥𝐨𝐧𝐞𝐬')}: {total_clones}\n"
            f"🚫 {style_text('𝐁𝐚𝐧𝐧𝐞𝐝 𝐔𝐬𝐞𝐫𝐬')}: {len(banned_users)}\n\n"
            f"📢 {style_text('𝐆𝐫𝐨𝐮𝐩 𝐒𝐭𝐚𝐭𝐬')}:\n"
            f"   {style_text('𝐓𝐨𝐭𝐚𝐥 𝐆𝐫𝐨𝐮𝐩𝐬')}: {total_groups}\n"
            f"   {style_text('𝐁𝐚𝐧𝐧𝐞𝐝 𝐆𝐫𝐨𝐮𝐩𝐬')}: {banned_groups_count}\n\n"
            f"📢 {style_text('𝐂𝐡𝐚𝐧𝐧𝐞𝐥 𝐒𝐭𝐚𝐭𝐬')}:\n"
        )
        
        for channel in REQUIRED_CHANNELS:
            stats_msg += f"   {channel['display_name']}: {total_channel_members.get(channel['display_name'], 'N/A')} members\n"
        
        stats_msg += (
            f"\n⚙️ {style_text('𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞')}: {'𝐎𝐍' if maintenance_mode else '𝐎𝐅𝐅'}\n"
            f"🔐 {style_text('𝐅𝐨𝐫𝐜𝐞 𝐉𝐨𝐢𝐧')}: {'𝐎𝐍' if force_join_enabled else '𝐎𝐅𝐅'}\n"
        )
        
        await update.message.reply_text(stats_msg)
    
    elif text == BUTTONS['broadcast'] and user.id == OWNER_ID:
        await update.message.reply_text(
            f"{style_text('📢 𝐒𝐞𝐧𝐝 𝐦𝐞 𝐭𝐡𝐞 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐭𝐨 𝐛𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭')}\n"
            f"{style_text('𝐓𝐨 𝐚𝐥𝐥 𝐛𝐨𝐭 𝐮𝐬𝐞𝐫𝐬 𝐚𝐧𝐝 𝐠𝐫𝐨𝐮𝐩𝐬')}"
        )
        user_sessions[user.id] = 'waiting_for_broadcast'
    
    elif text == BUTTONS['settings'] and user.id == OWNER_ID:
        settings_msg = (
            f"╔═══《 {style_text('⚙️ 𝐁𝐎𝐓 𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒')} 》═══╗\n\n"
            f"📢 {style_text('𝐑𝐞𝐪𝐮𝐢𝐫𝐞𝐝 𝐂𝐡𝐚𝐧𝐧𝐞𝐥𝐬')}: {len(REQUIRED_CHANNELS)}\n"
        )
        
        for channel in REQUIRED_CHANNELS:
            settings_msg += f"   {channel['display_name']}\n"
        
        settings_msg += (
            f"\n🔐 {style_text('𝐅𝐨𝐫𝐜𝐞 𝐉𝐨𝐢𝐧')}: {'𝐄𝐧𝐚𝐛𝐥𝐞𝐝' if force_join_enabled else '𝐃𝐢𝐬𝐚𝐛𝐥𝐞𝐝'}\n"
            f"☢️ {style_text('𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞')}: {'𝐄𝐧𝐚𝐛𝐥𝐞𝐝' if maintenance_mode else '𝐃𝐢𝐬𝐚𝐛𝐥𝐞𝐝'}\n"
            f"📁 {style_text('𝐌𝐚𝐱 𝐅𝐢𝐥𝐞𝐬 𝐩𝐞𝐫 𝐔𝐬𝐞𝐫')}: 20\n"
            f"👥 {style_text('𝐆𝐫𝐨𝐮𝐩 𝐖𝐞𝐥𝐜𝐨𝐦𝐞')}: {'𝐄𝐧𝐚𝐛𝐥𝐞𝐝 𝐛𝐲 𝐝𝐞𝐟𝐚𝐮𝐥𝐭'}\n"
        )
        
        await update.message.reply_text(settings_msg)
    
    elif text == BUTTONS['ban_user'] and user.id == OWNER_ID:
        await update.message.reply_text(
            f"{style_text('🚫 𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐮𝐬𝐞𝐫 𝐈𝐃 𝐭𝐨 𝐛𝐚𝐧')}\n"
            f"{style_text('𝐅𝐨𝐫𝐦𝐚𝐭')}: /ban 123456789"
        )
    
    elif text == BUTTONS['maintenance'] and user.id == OWNER_ID:
        maintenance_mode = not maintenance_mode
        status = "𝐄𝐧𝐚𝐛𝐥𝐞𝐝" if maintenance_mode else "𝐃𝐢𝐬𝐚𝐛𝐥𝐞𝐝"
        await update.message.reply_text(
            f"{style_text(f'☢️ 𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞 𝐦𝐨𝐝𝐞 {status}')}"
        )
    
    elif text == BUTTONS['force_join'] and user.id == OWNER_ID:
        force_join_enabled = not force_join_enabled
        status = "𝐄𝐧𝐚𝐛𝐥𝐞𝐝" if force_join_enabled else "𝐃𝐢𝐬𝐚𝐛𝐥𝐞𝐝"
        await update.message.reply_text(
            f"{style_text(f'🔐 𝐅𝐨𝐫𝐜𝐞 𝐣𝐨𝐢𝐧 {status}')}"
        )
    
    # Handle URL input
    elif user.id in user_sessions and user_sessions[user.id] == 'waiting_for_url':
        url = text.strip()
        status_msg = await update.message.reply_text(
            f"{style_text('⏳ 𝐂𝐥𝐨𝐧𝐢𝐧𝐠 𝐰𝐞𝐛𝐬𝐢𝐭𝐞, 𝐩𝐥𝐞𝐚𝐬𝐞 𝐰𝐚𝐢𝐭...')}\n"
            f"{style_text('🌐 𝐔𝐑𝐋')}: {url}"
        )
        
        try:
            zip_path, metadata = await cloner.clone_website(url, user.id)
            
            # Send zip file
            with open(zip_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(zip_path),
                    caption=(
                        f"✅ {style_text('𝐖𝐞𝐛𝐬𝐢𝐭𝐞 𝐜𝐥𝐨𝐧𝐞𝐝 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲!')}\n\n"
                        f"🌐 {style_text('𝐔𝐑𝐋')}: {url}\n"
                        f"📄 {style_text('𝐓𝐢𝐭𝐥𝐞')}: {metadata['title'][:50]}\n"
                        f"⚡ {style_text('𝐉𝐒')}: {metadata['js']} | 🎨 {style_text('𝐂𝐒𝐒')}: {metadata['css']} | 🖼️ {style_text('𝐈𝐦𝐚𝐠𝐞𝐬')}: {metadata['images']}\n\n"
                        f"📂 {style_text('𝐒𝐚𝐯𝐞𝐝 𝐢𝐧')} {BUTTONS['my_files']}"
                    )
                )
            
            # Clean up temp file after sending
            try:
                os.remove(zip_path)
                shutil.rmtree(os.path.dirname(zip_path))
            except:
                pass
            
        except Exception as e:
            await update.message.reply_text(
                f"{style_text('❌ 𝐄𝐫𝐫𝐨𝐫')}: {str(e)}"
            )
        
        del user_sessions[user.id]
    
    # Handle broadcast message
    elif user.id in user_sessions and user_sessions[user.id] == 'waiting_for_broadcast' and user.id == OWNER_ID:
        broadcast_msg = text
        success_users = 0
        failed_users = 0
        success_groups = 0
        failed_groups = 0
        
        # Broadcast to users
        all_users = set(user_data.keys())
        for uid in all_users:
            try:
                await context.bot.send_message(chat_id=uid, text=broadcast_msg)
                success_users += 1
                await asyncio.sleep(0.05)
            except:
                failed_users += 1
        
        # Broadcast to groups (except banned ones)
        for gid in group_settings.keys():
            if gid not in banned_groups:
                try:
                    await context.bot.send_message(chat_id=gid, text=broadcast_msg)
                    success_groups += 1
                    await asyncio.sleep(0.05)
                except:
                    failed_groups += 1
        
        await update.message.reply_text(
            f"{style_text('📢 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞')}\n\n"
            f"👤 {style_text('𝐔𝐬𝐞𝐫𝐬')}:\n"
            f"✅ {style_text('𝐒𝐮𝐜𝐜𝐞𝐬𝐬')}: {success_users}\n"
            f"❌ {style_text('𝐅𝐚𝐢𝐥𝐞𝐝')}: {failed_users}\n\n"
            f"👥 {style_text('𝐆𝐫𝐨𝐮𝐩𝐬')}:\n"
            f"✅ {style_text('𝐒𝐮𝐜𝐜𝐞𝐬𝐬')}: {success_groups}\n"
            f"❌ {style_text('𝐅𝐚𝐢𝐥𝐞𝐝')}: {failed_groups}"
        )
        
        del user_sessions[user.id]

async def show_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show groups management menu"""
    await update.message.reply_text(
        f"╔═══《 {style_text('📢 𝐆𝐑𝐎𝐔𝐏 𝐌𝐀𝐍𝐀𝐆𝐄𝐌𝐄𝐍𝐓')} 》═══╗\n\n"
        f"{style_text('𝐒𝐞𝐥𝐞𝐜𝐭 𝐚𝐧 𝐨𝐩𝐭𝐢𝐨𝐧')}:\n\n"
        f"{BUTTONS['group_stats']} - {style_text('𝐕𝐢𝐞𝐰 𝐚𝐥𝐥 𝐠𝐫𝐨𝐮𝐩 𝐬𝐭𝐚𝐭𝐬')}\n"
        f"{BUTTONS['group_list']} - {style_text('𝐋𝐢𝐬𝐭 𝐚𝐥𝐥 𝐠𝐫𝐨𝐮𝐩𝐬')}\n"
        f"{BUTTONS['group_ban']} - {style_text('𝐁𝐚𝐧 𝐚 𝐠𝐫𝐨𝐮𝐩')}\n"
        f"{BUTTONS['group_unban']} - {style_text('𝐔𝐧𝐛𝐚𝐧 𝐚 𝐠𝐫𝐨𝐮𝐩')}\n"
        f"{BUTTONS['group_settings']} - {style_text('𝐆𝐫𝐨𝐮𝐩 𝐬𝐞𝐭𝐭𝐢𝐧𝐠𝐬')}\n",
        reply_markup=create_groups_menu_keyboard()
    )

async def show_all_groups_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show statistics for all groups"""
    total_groups = len(group_settings)
    active_groups = total_groups - len(banned_groups)
    
    msg = f"╔═══《 {style_text('📊 𝐀𝐋𝐋 𝐆𝐑𝐎𝐔𝐏 𝐒𝐓𝐀𝐓𝐒')} 》═══╗\n\n"
    msg += f"📊 {style_text('𝐓𝐨𝐭𝐚𝐥 𝐆𝐫𝐨𝐮𝐩𝐬')}: {total_groups}\n"
    msg += f"✅ {style_text('𝐀𝐜𝐭𝐢𝐯𝐞')}: {active_groups}\n"
    msg += f"🚫 {style_text('𝐁𝐚𝐧𝐧𝐞𝐝')}: {len(banned_groups)}\n\n"
    
    if group_settings:
        msg += f"{style_text('𝐑𝐞𝐜𝐞𝐧𝐭 𝐆𝐫𝐨𝐮𝐩𝐬')}:\n"
        sorted_groups = sorted(group_settings.items(), key=lambda x: x[1]['first_seen'], reverse=True)[:5]
        for gid, settings in sorted_groups:
            status = "🚫" if gid in banned_groups else "✅"
            msg += f"{status} {settings['title'][:20]}... (`{gid}`)\n"
    
    await update.message.reply_text(msg)

async def show_groups_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of all groups"""
    if not group_settings:
        await update.message.reply_text(f"{style_text('📭 𝐍𝐨 𝐠𝐫𝐨𝐮𝐩𝐬 𝐟𝐨𝐮𝐧𝐝')}")
        return
    
    msg = f"╔═══《 {style_text('📋 𝐆𝐑𝐎𝐔𝐏 𝐋𝐈𝐒𝐓')} 》═══╗\n\n"
    
    for gid, settings in group_settings.items():
        status = "🚫 𝐁𝐀𝐍𝐍𝐄𝐃" if gid in banned_groups else "✅ 𝐀𝐂𝐓𝐈𝐕𝐄"
        msg += f"📢 {settings['title']}\n"
        msg += f"🆔 `{gid}`\n"
        msg += f"📊 {status}\n"
        msg += f"👥 {style_text('𝐌𝐞𝐦𝐛𝐞𝐫𝐬')}: {settings.get('member_count', 'N/A')}\n\n"
        
        if len(msg) > 3500:  # Telegram message limit
            msg += f"... {style_text('𝐚𝐧𝐝 𝐦𝐨𝐫𝐞')}"
            break
    
    await update.message.reply_text(msg)

async def show_group_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group settings menu"""
    settings_msg = (
        f"╔═══《 {style_text('⚙️ 𝐆𝐑𝐎𝐔𝐏 𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒')} 》═══╗\n\n"
        f"{style_text('𝐃𝐞𝐟𝐚𝐮𝐥𝐭 𝐬𝐞𝐭𝐭𝐢𝐧𝐠𝐬')}:\n"
        f"• {style_text('𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐦𝐞𝐬𝐬𝐚𝐠𝐞')}: 𝐎𝐍\n"
        f"• {style_text('𝐆𝐫𝐨𝐮𝐩 𝐚𝐝𝐦𝐢𝐧𝐬 𝐜𝐚𝐧 𝐭𝐨𝐠𝐠𝐥𝐞')}\n\n"
        f"{style_text('𝐆𝐫𝐨𝐮𝐩 𝐜𝐨𝐦𝐦𝐚𝐧𝐝𝐬')}:\n"
        f"/id - {style_text('𝐒𝐡𝐨𝐰 𝐜𝐡𝐚𝐭 𝐈𝐃')}\n"
        f"/togglewelcome - {style_text('𝐎𝐧/𝐎𝐟𝐟 𝐰𝐞𝐥𝐜𝐨𝐦𝐞')}\n"
        f"/groupstats - {style_text('𝐆𝐫𝐨𝐮𝐩 𝐬𝐭𝐚𝐭𝐬')}\n\n"
        f"{style_text('𝐎𝐰𝐧𝐞𝐫 𝐜𝐨𝐦𝐦𝐚𝐧𝐝𝐬')}:\n"
        f"/bangroup <id> - {style_text('𝐁𝐚𝐧 𝐠𝐫𝐨𝐮𝐩')}\n"
        f"/unbangroup <id> - {style_text('𝐔𝐧𝐛𝐚𝐧 𝐠𝐫𝐨𝐮𝐩')}"
    )
    
    await update.message.reply_text(settings_msg)

async def ban_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a group from using the bot"""
    if update.effective_user.id != OWNER_ID:
        return
    
    try:
        group_id = int(context.args[0])
        banned_groups.add(group_id)
        
        # Try to get group name
        group_name = "Unknown"
        if group_id in group_settings:
            group_name = group_settings[group_id]['title']
        
        await update.message.reply_text(
            f"{style_text(f'🚫 𝐆𝐫𝐨𝐮𝐩 {group_name} 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐛𝐚𝐧𝐧𝐞𝐝')}\n"
            f"🆔 `{group_id}`"
        )
    except:
        await update.message.reply_text(
            f"{style_text('❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐠𝐫𝐨𝐮𝐩 𝐈𝐃')}\n"
            f"{style_text('𝐔𝐬𝐞')}: /bangroup -100123456789"
        )

async def unban_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a group"""
    if update.effective_user.id != OWNER_ID:
        return
    
    try:
        group_id = int(context.args[0])
        if group_id in banned_groups:
            banned_groups.remove(group_id)
            
            # Try to get group name
            group_name = "Unknown"
            if group_id in group_settings:
                group_name = group_settings[group_id]['title']
            
            await update.message.reply_text(
                f"{style_text(f'✅ 𝐆𝐫𝐨𝐮𝐩 {group_name} 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐮𝐧𝐛𝐚𝐧𝐧𝐞𝐝')}\n"
                f"🆔 `{group_id}`"
            )
        else:
            await update.message.reply_text(
                f"{style_text('❌ 𝐆𝐫𝐨𝐮𝐩 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝 𝐢𝐧 𝐛𝐚𝐧 𝐥𝐢𝐬𝐭')}"
            )
    except:
        await update.message.reply_text(
            f"{style_text('❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐠𝐫𝐨𝐮𝐩 𝐈𝐃')}\n"
            f"{style_text('𝐔𝐬𝐞')}: /unbangroup -100123456789"
        )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user command"""
    if update.effective_user.id != OWNER_ID:
        return
    
    try:
        user_id = int(context.args[0])
        banned_users.add(user_id)
        await update.message.reply_text(
            f"{style_text(f'✅ 𝐔𝐬𝐞𝐫 {user_id} 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐛𝐚𝐧𝐧𝐞𝐝')}"
        )
    except:
        await update.message.reply_text(
            f"{style_text('❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃')}"
        )

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user command"""
    if update.effective_user.id != OWNER_ID:
        return
    
    try:
        user_id = int(context.args[0])
        if user_id in banned_users:
            banned_users.remove(user_id)
            await update.message.reply_text(
                f"{style_text(f'✅ 𝐔𝐬𝐞𝐫 {user_id} 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐮𝐧𝐛𝐚𝐧𝐧𝐞𝐝')}"
            )
        else:
            await update.message.reply_text(
                f"{style_text('❌ 𝐔𝐬𝐞𝐫 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝 𝐢𝐧 𝐛𝐚𝐧 𝐥𝐢𝐬𝐭')}"
            )
    except:
        await update.message.reply_text(
            f"{style_text('❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃')}"
        )

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("bangroup", ban_group_command))
    application.add_handler(CommandHandler("unbangroup", unban_group_command))
    application.add_handler(CommandHandler("id", handle_group_message))
    application.add_handler(CommandHandler("chatid", handle_group_message))
    application.add_handler(CommandHandler("togglewelcome", handle_group_message))
    application.add_handler(CommandHandler("groupstats", handle_group_message))
    application.add_handler(ChatMemberHandler(handle_channel_member_update, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    
    # Start bot
    print(f"{style_text('🤖 𝐄𝐗𝐔 𝐂𝐎𝐃𝐄𝐗 𝐁𝐨𝐭 𝐢𝐬 𝐬𝐭𝐚𝐫𝐭𝐢𝐧𝐠...')}")
    print(f"{style_text('👑 𝐎𝐰𝐧𝐞𝐫')}: @{OWNER_USERNAME}")
    print(f"{style_text('📢 𝐑𝐞𝐪𝐮𝐢𝐫𝐞𝐝 𝐂𝐡𝐚𝐧𝐧𝐞𝐥𝐬')}:")
    for channel in REQUIRED_CHANNELS:
        print(f"   {channel['display_name']} (@{channel['username'][1:]})")
    print(f"{style_text('👥 𝐆𝐫𝐨𝐮𝐩 𝐌𝐨𝐝𝐞')}: {style_text('𝐀𝐜𝐭𝐢𝐯𝐞')}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()