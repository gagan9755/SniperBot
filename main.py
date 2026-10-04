import asyncio
import time
import re
from collections import deque
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, Button
from telethon.tl.types import MessageEntityCode, MessageEntityPre, PeerChannel, PeerChat
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.extensions import html
from flask import Flask
from threading import Thread
import json
import random
import string
import os

# --- 🌐 KEEP-ALIVE SERVER (For 24/7 Hosting) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "🤖 Master Sniper Bot is SECURE and RUNNING 24/7!"
def run_server():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run_server).start()

# --- ⚙️ MASTER CONFIGURATION ---
API_ID = 21601452
API_HASH = 'cc8257993f2553fec9f43bcd6b8f79c4'
BOT_TOKEN = '8546884710:AAF1lcYQwJiu0q0KWpwvK95MxuncBfXzg34' 

MASTER_ID = 8845438009  # Your Admin ID

master_bot = TelegramClient('master_bot_session', API_ID, API_HASH)

# 🌐 MONGODB CONFIGURATION (Long URL)
MONGO_URI = "mongodb://gkgamer12697_db_user:4mUkf5fi0T0MwcrR@ac-dnrbgvj-shard-00-00.4su8lly.mongodb.net:27017,ac-dnrbgvj-shard-00-01.4su8lly.mongodb.net:27017,ac-dnrbgvj-shard-00-02.4su8lly.mongodb.net:27017/?ssl=true&replicaSet=atlas-10pwl1-shard-0&authSource=admin&appName=Cluster0"

# GLOBAL VARIABLES
licenses_col = None
bot_data_col = None
sessions_col = None
MONGO_ERROR_MSG = "Unknown Error"

try:
    from pymongo import MongoClient
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsAllowInvalidCertificates=True)
    db = mongo_client["master_sniper_db"]
    licenses_col = db["licenses"]
    bot_data_col = db["bot_data"]
    sessions_col = db["sessions"]
    mongo_client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")
    MONGO_ERROR_MSG = "Connected"
except ImportError as ie:
    MONGO_ERROR_MSG = f"Library Missing: {ie} (Kripya requirements.txt me 'pymongo' aur 'dnspython' add karein)"
    print(f"❌ {MONGO_ERROR_MSG}")
except Exception as e:
    MONGO_ERROR_MSG = f"Connection Failed: {e}"
    print(f"❌ {MONGO_ERROR_MSG}")

user_states = {}
user_data = {}  
active_snipers_dict = {}

# --- 🔐 DATABASES (Cloud-Backed) ---
def load_licenses():
    if licenses_col is None: return {"keys": {}, "users": {}, "special_keys": {}, "special_users": {}, "settings": {"official_channel": ""}}
    try:
        data = licenses_col.find_one({"_id": "config"})
        if data:
            data.pop("_id", None)
            return data
    except Exception: pass
    return {"keys": {}, "users": {}, "special_keys": {}, "special_users": {}, "settings": {"official_channel": ""}} 

def save_licenses(data):
    if licenses_col is None: return
    try: licenses_col.update_one({"_id": "config"}, {"$set": data}, upsert=True)
    except Exception: pass

license_db = load_licenses()

def load_bot_data():
    if bot_data_col is None: return {}
    try:
        data = bot_data_col.find_one({"_id": "db"})
        if data:
            data.pop("_id", None)
            return data
    except Exception: pass
    return {}

def save_bot_data():
    if bot_data_col is None: return
    try: bot_data_col.update_one({"_id": "db"}, {"$set": bot_db}, upsert=True)
    except Exception: pass

bot_db = load_bot_data()

def init_user_db(user_id):
    uid = str(user_id)
    if uid not in bot_db:
        bot_db[uid] = {
            'dest_dict': {}, 'source_dict': {}, 
            'sniper_mode': 'rush', 'lines_count': 4,
            'is_running': False, 'is_paused': False, 
            'replacer_link': None, 
            'replacer_username': None, 
            'custom_header': None, 
            'custom_footer': None, 
            'use_header': True,
            'use_footer': True,
            'use_over': True,
            'over_timer': 0, 
            'over_text': "❌️❌️ OVER ❌️❌️",
            'presets': {},
            'setup_type': 'normal', 
            'setup_mode_cache': 'rush',
            'setup_lines_cache': 4,
            'stats': {'forwarded': 0}
        }
        save_bot_data()

# --- ☁ STRING SESSION HELPERS ---
def load_user_session(user_id):
    if sessions_col is None: return None
    try:
        res = sessions_col.find_one({"user_id": str(user_id)})
        if res and "session_string" in res: return res["session_string"]
    except Exception: pass
    return None

def save_user_session(user_id, string_session):
    if sessions_col is None: return
    try: sessions_col.update_one({"user_id": str(user_id)}, {"$set": {"session_string": string_session}}, upsert=True)
    except Exception: pass

def delete_user_session(user_id):
    if sessions_col is None: return
    try: sessions_col.delete_one({"user_id": str(user_id)})
    except Exception: pass

async def ensure_client(user_id):
    client = user_data.get(user_id, {}).get('client')
    if client and client.is_connected(): return client
    session_str = load_user_session(user_id)
    if session_str:
        new_c = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        try:
            await new_c.connect()
            if await new_c.is_user_authorized():
                if user_id not in user_data: user_data[user_id] = {}
                user_data[user_id]['client'] = new_c
                return new_c
        except Exception: pass
    return None

# --- 🔐 LICENSE LOGIC ---
def generate_key(days=0, hours=0):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    expiry_dt = datetime.now() + timedelta(days=days, hours=hours)
    license_db["keys"][key] = {"expires": expiry_dt.isoformat(), "used_by": None}
    save_licenses(license_db)
    return key

def generate_special_key(days=0, hours=0):
    key = 'SP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    expiry_dt = datetime.now() + timedelta(days=days, hours=hours)
    license_db["special_keys"][key] = {"expires": expiry_dt.isoformat(), "used_by": None}
    save_licenses(license_db)
    return key

def is_user_authorized(user_id):
    return str(user_id) in license_db["users"]

def check_subscription(user_id):
    if not is_user_authorized(user_id): return False
    expires_str = license_db["users"][str(user_id)]["expires"]
    return datetime.now() < datetime.fromisoformat(expires_str)

def is_special_authorized(user_id):
    uid = str(user_id)
    if uid not in license_db["special_users"]: return False
    expires_str = license_db["special_users"][uid]["expires"]
    return datetime.now() < datetime.fromisoformat(expires_str)

def get_time_left(user_id):
    if not is_user_authorized(user_id): return None
    expires_str = license_db["users"][str(user_id)]["expires"]
    return datetime.fromisoformat(expires_str) - datetime.now()

def format_time_left(td):
    if not td or int(td.total_seconds()) <= 0: return "Expired"
    days, hours = int(td.total_seconds()) // 86400, (int(td.total_seconds()) % 86400) // 3600
    return f"{days} Days" if days > 0 else f"{hours} Hours"

# --- 🧠 UI BUTTON HELPERS ---
def get_official_btn_single():
    link = license_db.get("settings", {}).get("official_channel", "")
    if link: return [Button.url("📢 Join Official Channel", url=link)]
    return []

def get_mode_buttons(user_id):
    btns = [
        [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
        [Button.inline("🎯 Specific Source Channel", b"mode_source")],
        [Button.inline("⚡ GOD MODE (Clone + Stickers + Auto-Reply)", b"mode_god_start")],
        [Button.inline("🔐 Special Code Mode (Secret)", b"mode_special_start")],
        [Button.inline("📂 Saved Presets / Setups", b"list_presets")],
        [Button.inline("🔄 Change Number / Account", b"change_phone_number")]
    ]
    off_btn = get_official_btn_single()
    if off_btn: btns.append(off_btn)
    return btns

def get_control_buttons(validity_str):
    btns = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline("⚙️ Manage Sources/Dest", b"manage_channels"), Button.inline("💾 Save Setup", b"save_current_preset")],
        [Button.inline("📂 Load Preset", b"list_presets"), Button.inline("🔄 Restart Setup", b"ctl_restart")],
        [Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey"), Button.inline("🔄 Change Number", b"change_phone_number")]
    ]
    off_btn = get_official_btn_single()
    if off_btn: btns.append(off_btn)
    return btns

def get_admin_buttons():
    return [
        [Button.inline("🔑 Gen 1 Key (30D)", b"adm_gen_1_30"), Button.inline("🔑 Gen 5 Keys (30D)", b"adm_gen_5_30")],
        [Button.inline("🔐 Gen Special Key (30D)", b"adm_gen_sp_30"), Button.inline("⚙️ Custom Special Key", b"adm_custom_sp_key")],
        [Button.inline("👥 View Special Users", b"adm_special_users"), Button.inline("⚙ Custom Key (Days/Hours)", b"adm_custom_key")],
        [Button.inline("👥 View Active Users", b"adm_users"), Button.inline("🔗 Set Official Channel", b"adm_set_channel")],
        [Button.inline("🚫 Ban User", b"adm_ban_prompt"), Button.inline("✅ Unban User", b"adm_unban_prompt")],
        [Button.inline("📢 Broadcast Message", b"adm_broadcast")],
        [Button.inline("👤 OPEN USER PANEL (My Sniper)", b"open_user_panel")]
    ]

async def get_channel_buttons(client, action_type, require_admin=False, pinned_only=False):
    try:
        dialogs = await client.get_dialogs(limit=500)
        buttons = []
        for d in dialogs:
            if pinned_only and not d.pinned: continue
            if d.is_channel or d.is_group:
                # Removed strict require_admin block for reliability, allowing all groups/channels user is in.
                name = d.name[:20] if d.name else "Unnamed"
                buttons.append([Button.inline(name, data=f"{action_type}:{d.id}:{name[:15]}")])
                if len(buttons) >= 60: break
        return buttons
    except: return []

def safe_replace_username(text, new_username):
    if not new_username: return text
    code_blocks = []
    def save_code(match):
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"
    protected_text = re.sub(r'<(code|pre>).*?<\/\1>', save_code, text, flags=re.DOTALL)
    protected_text = re.sub(r'(?<![a-zA-Z0-9_])@[a-zA-Z0-9_]+', new_username, protected_text)
    for i, block in enumerate(code_blocks):
        protected_text = protected_text.replace(f"__CODE_BLOCK_{i}__", block)
    return protected_text

class UserSniper:
    def __init__(self, user_id, client, name, source_chat_ids=None, sniper_mode="rush", lines_count=4):
        self.user_id = user_id
        self.client = client
        self.name = name
        self.destinations = {} 
        self.source_chat_ids = source_chat_ids if source_chat_ids else []
        self.pinned_chats = set()
        self.is_running = True
        self.is_paused = bot_db[str(user_id)].get('is_paused', False)
        self.sniper_mode = sniper_mode 
        self.lines_count = lines_count
        self.processed_ids_set = set()
        self.special_triggered = False 
        self.msg_map = {} 
        self.msg_map_keys = deque(maxlen=1000)
        self.handlers = [] 
        
    async def update_pinned_loop(self):
        if self.source_chat_ids: return
        while self.is_running:
            try:
                dialogs = await self.client.get_dialogs(limit=30)
                self.pinned_chats = {d.id for d in dialogs if d.pinned and d.id not in self.destinations}
            except: pass
            await asyncio.sleep(30)

async def start_sniper_for_user(user_id, client, dest_chats, name, source_chat_ids=None, sniper_mode="rush", lines_count=4):
    if user_id in active_snipers_dict:
        old_sniper = active_snipers_dict[user_id]
        old_sniper.is_running = False
        for h in getattr(old_sniper, 'handlers', []):
            try: client.remove_event_handler(h)
            except: pass
        del active_snipers_dict[user_id]

    init_user_db(user_id)
    uid = str(user_id)
    bot_db[uid]['is_running'] = True
    bot_db[uid]['sniper_mode'] = sniper_mode
    bot_db[uid]['lines_count'] = lines_count
    save_bot_data()

    sniper = UserSniper(user_id, client, name, source_chat_ids, sniper_mode, lines_count)
    
    for d_chat in dest_chats:
        try:
            target_entity = await client.get_entity(int(d_chat))
            sniper.destinations[int(d_chat)] = target_entity
        except: pass

    if not sniper.destinations:
        bot_db[uid]['is_running'] = False
        save_bot_data()
        await master_bot.send_message(user_id, f"❌ Error: Koi bhi valid destination channel nahi mila.")
        return

    active_snipers_dict[user_id] = sniper
    asyncio.create_task(sniper.update_pinned_loop())

    async def new_msg_handler(event):
        if not sniper.is_running: return

        if not check_subscription(user_id):
            sniper.is_running = False
            bot_db[uid]['is_running'] = False
            save_bot_data()
            for h in sniper.handlers:
                try: client.remove_event_handler(h)
                except: pass
            if user_id in active_snipers_dict: del active_snipers_dict[user_id]
            try: await master_bot.send_message(user_id, "⚠️ **Aapki License Key expire ho chuki hai!**")
            except: pass
            return

        if sniper.is_paused or not sniper.destinations: return
            
        current_sources = [int(s) for s in bot_db[uid].get('source_dict', {}).keys()]
        if current_sources:
            if event.chat_id not in current_sources: return
        else:
            if event.chat_id not in sniper.pinned_chats: return

        if event.id in sniper.processed_ids_set: return
        sniper.processed_ids_set.add(event.id)

        text_content = event.message.message or ""
        messages_to_send = []

        if sniper.sniper_mode == "special":
            if not is_special_authorized(user_id): return
            if sniper.special_triggered: return
            if not text_content: return
            extracted_items = []
            for ent, ent_text in event.message.get_entities_text():
                if isinstance(ent, (MessageEntityCode, MessageEntityPre)):
                    if ent_text not in extracted_items: extracted_items.append(ent_text)
            if not extracted_items: return
            sniper.special_triggered = True
            c = extracted_items[0]
            messages_to_send.append({'text': f"`{c}`", 'media': None, 'is_special': True})

        elif sniper.sniper_mode == "god":
            if not text_content and not event.message.media: return
            replacer_link = bot_db[uid].get('replacer_link')
            replacer_uname = bot_db[uid].get('replacer_username')
            
            if not replacer_link and not replacer_uname:
                messages_to_send.append({'is_pure_god': True, 'msg_obj': event.message})
            else:
                try: msg_html = html.unparse(text_content, event.message.entities)
                except: msg_html = text_content
                if replacer_link: 
                    msg_html = re.sub(r'(https?://)?t\.me/\+[a-zA-Z0-9_-]+', replacer_link, msg_html)
                    msg_html = re.sub(r'(https?://)?t\.me/joinchat/[a-zA-Z0-9_-]+', replacer_link, msg_html)
                    msg_html = re.sub(r'https?://[^\s]+', replacer_link, msg_html)
                if replacer_uname: 
                    msg_html = safe_replace_username(msg_html, replacer_uname)
                messages_to_send.append({'text': msg_html, 'media': event.message.media, 'is_god': True})

        else:
            if not text_content and not event.message.media: return
            extracted_items = []
            if sniper.sniper_mode == "link":
                link_pattern = r'(?:\b|https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'
                found_links = re.findall(link_pattern, text_content)
                for l in found_links:
                    if l not in extracted_items: extracted_items.append(l)
            else:
                for ent, ent_text in event.message.get_entities_text():
                    if isinstance(ent, (MessageEntityCode, MessageEntityPre, types.MessageEntityUrl, types.MessageEntityTextUrl)):
                        if ent_text not in extracted_items: extracted_items.append(ent_text)

            if not extracted_items and text_content: extracted_items = [text_content]
            if not extracted_items: return

            body_texts = []
            if sniper.sniper_mode == "rush":
                num = len(extracted_items)
                lines = [f"`{extracted_items[0]}`"] * 3 if num == 1 else [f"`{extracted_items[0]}`"] * 2 + [f"`{extracted_items[1]}`"] * 2 if num == 2 else [f"`{c}`" for c in extracted_items]
                body_texts = lines
            else:
                for item in extracted_items:
                    if item.startswith("http://") or item.startswith("https://"): body_texts.append(item)
                    else:
                        repeated_lines = [f"`{item}`"] * sniper.lines_count
                        body_texts.extend(repeated_lines)

            final_body = "\n".join(body_texts)
            final_text = ""
            if bot_db[uid].get('use_header', True) and bot_db[uid].get('custom_header'): final_text += bot_db[uid]['custom_header'] + "\n\n"
            final_text += final_body
            if bot_db[uid].get('use_footer', True) and bot_db[uid].get('custom_footer'): final_text += "\n\n" + bot_db[uid]['custom_footer']

            messages_to_send.append({'text': final_text, 'media': event.message.media if not text_content else None, 'is_god': False})

        async def send_to_destination(target, item):
            try:
                kwargs = {'link_preview': True}
                if item.get('is_pure_god'):
                    msg_text = item['msg_obj'].message or ""
                    if item['msg_obj'].entities: kwargs['formatting_entities'] = item['msg_obj'].entities
                    if item['msg_obj'].media: kwargs['file'] = item['msg_obj'].media
                else:
                    msg_text = item['text'] or ""
                    kwargs['parse_mode'] = 'html' if item.get('is_god') else 'md'
                    if item.get('media'): kwargs['file'] = item['media']

                sent_msg = await client.send_message(target, msg_text, **kwargs)
                if sent_msg and bot_db[uid].get('use_over', True):
                    timer_sec = bot_db[uid].get('over_timer', 0)
                    if timer_sec > 0 and not item.get('is_god') and not item.get('is_pure_god') and not item.get('is_special'):
                        custom_over = bot_db[uid].get('over_text', "❌️❌ OVER ❌️❌️")
                        asyncio.create_task(auto_over_message(client, target, sent_msg.id, timer_sec, custom_over))
                return sent_msg.id if sent_msg else None
            except Exception: return None

        sent_msgs_this_event = {}
        for d_id, target in sniper.destinations.items():
            res_id = await send_to_destination(target, messages_to_send[0])
            if res_id: sent_msgs_this_event[d_id] = res_id

        if sent_msgs_this_event:
            if len(sniper.msg_map_keys) >= 1000:
                old_id = sniper.msg_map_keys.popleft()
                sniper.msg_map.pop(old_id, None)
            sniper.msg_map_keys.append(event.id)
            sniper.msg_map[event.id] = sent_msgs_this_event
            bot_db[uid]['stats']['forwarded'] += 1
            save_bot_data()

        if sniper.sniper_mode == "special":
            sniper.is_running = False
            bot_db[uid]['is_running'] = False
            save_bot_data()
            for h in sniper.handlers:
                try: client.remove_event_handler(h)
                except: pass
            if user_id in active_snipers_dict: del active_snipers_dict[user_id]
            try: await master_bot.send_message(user_id, "🎯 **1st Special Code successfully forwarded!**")
            except: pass

    async def edit_handler(event):
        if not sniper.is_running or sniper.is_paused or sniper.sniper_mode != "god": return
        if sniper.source_chat_ids and event.chat_id not in sniper.source_chat_ids: return
        elif not sniper.source_chat_ids and event.chat_id not in sniper.pinned_chats: return
        if event.id not in sniper.msg_map: return
        
        text_content = event.message.message or ""
        replacer_link = bot_db[uid].get('replacer_link')
        replacer_uname = bot_db[uid].get('replacer_username')
        
        try:
            if not replacer_link and not replacer_uname:
                for d_id, dest_msg_id in sniper.msg_map[event.id].items():
                    target = sniper.destinations.get(int(d_id))
                    if target:
                        edit_kwargs = {'text': text_content, 'file': event.message.media}
                        if event.message.entities: edit_kwargs['formatting_entities'] = event.message.entities
                        await client.edit_message(target, dest_msg_id, **edit_kwargs)
            else:
                msg_html = text_content
                try: msg_html = html.unparse(text_content, event.message.entities)
                except: pass
                
                if replacer_link: 
                    msg_html = re.sub(r'(https?://)?t\.me/\+[a-zA-Z0-9_-]+', replacer_link, msg_html)
                    msg_html = re.sub(r'(https?://)?t\.me/joinchat/[a-zA-Z0-9_-]+', replacer_link, msg_html)
                    msg_html = re.sub(r'https?://[^\s]+', replacer_link, msg_html)
                if replacer_uname: msg_html = safe_replace_username(msg_html, replacer_uname)
                
                for d_id, dest_msg_id in sniper.msg_map[event.id].items():
                    target = sniper.destinations.get(int(d_id))
                    if target: await client.edit_message(target, dest_msg_id, text=msg_html, parse_mode='html', file=event.message.media)
        except Exception: pass

    async def delete_handler(event):
        if not sniper.is_running or sniper.is_paused or sniper.sniper_mode != "god": return
        for deleted_id in event.deleted_ids:
            if deleted_id in sniper.msg_map:
                for d_id, dest_msg_id in sniper.msg_map[deleted_id].items():
                    target = sniper.destinations.get(int(d_id))
                    if target:
                        try: await client.delete_messages(target, dest_msg_id)
                        except: pass

    client.add_event_handler(new_msg_handler, events.NewMessage())
    client.add_event_handler(edit_handler, events.MessageEdited())
    client.add_event_handler(delete_handler, events.MessageDeleted())
    sniper.handlers.extend([new_msg_handler, edit_handler, delete_handler])

    try:
        time_left = get_time_left(user_id)
        validity_str = format_time_left(time_left)
        await master_bot.send_message(user_id, f"✅ **SNIPER ACTIVE!** 🎯\n🚀 **Destinations:** `{len(sniper.destinations)}`\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    except: pass

async def auto_over_message(client, target, msg_id, delay, custom_over_text):
    await asyncio.sleep(delay)
    try: await client.edit_message(target, msg_id, custom_over_text)
    except: pass

async def auto_resume_snipers():
    await asyncio.sleep(2)
    for uid_str, data in bot_db.items():
        if data.get('is_running') and check_subscription(uid_str) and data.get('sniper_mode') != 'special':
            user_id = int(uid_str)
            client = await ensure_client(user_id)
            if client:
                dests = list(data.get('dest_dict', {}).keys())
                sources = [int(s) for s in data.get('source_dict', {}).keys()] if data.get('source_dict') else None
                await start_sniper_for_user(user_id, client, dests, "User", sources, data.get('sniper_mode', 'rush'), data.get('lines_count', 4))

@master_bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    init_user_db(user_id)
    if user_id == MASTER_ID:
        user_states[user_id] = None 
        db_status = "🟢 MongoDB Cloud se Connected hai!" if MONGO_ERROR_MSG == "Connected" else f"🔴 MONGODB ERROR:\n`{MONGO_ERROR_MSG}`"
        await event.reply(f"👑 **MASTER ADMIN CONTROL PANEL** 👑\n\n📊 **Database Status:** {db_status}", buttons=get_admin_buttons())
        return
        
    if is_user_authorized(user_id) and check_subscription(user_id):
        client = await ensure_client(user_id)
        if client:
            user_states[user_id] = 'CHOOSE_MODE'
            time_left = get_time_left(user_id)
            await event.reply(f"✅ **Welcome Back!** (⏳ `{format_time_left(time_left)}`)\n🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))
        else:
            user_states[user_id] = 'WAITING_PHONE'
            await event.reply("📱 Apna **Telegram Phone Number** bhejein:", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]] )
        return
    user_states[user_id] = 'WAITING_KEY'
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:")

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
    uid = str(user_id)
    init_user_db(user_id)
    try: await event.delete()
    except: pass

    if data == "open_user_panel":
        if not is_user_authorized(user_id) or not check_subscription(user_id):
            license_db["users"][str(user_id)] = {"name": "Master Admin", "key": "ADMIN-MASTER", "expires": (datetime.now() + timedelta(days=3650)).isoformat()}
            save_licenses(license_db)
        client = await ensure_client(user_id)
        if client:
            user_states[user_id] = 'CHOOSE_MODE'
            time_left = get_time_left(user_id)
            await event.respond(f"✅ **Welcome Admin to User Panel!** (⏳ `{format_time_left(time_left)}`)\n🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))
        else:
            user_states[user_id] = 'WAITING_PHONE'
            await event.respond("📱 Apna **Telegram Phone Number** bhejein:", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        return

    if data == "change_phone_number":
        if user_id in active_snipers_dict:
            old_sniper = active_snipers_dict[user_id]
            old_sniper.is_running = False
            for h in getattr(old_sniper, 'handlers', []):
                try: user_data.get(user_id, {}).get('client').remove_event_handler(h)
                except: pass
            del active_snipers_dict[user_id]
        bot_db[uid]['is_running'] = False
        save_bot_data()
        delete_user_session(user_id)
        if user_id in user_data: user_data[user_id].pop('client', None)
        user_states[user_id] = 'WAITING_PHONE'
        await event.respond("🔄 **Change Number / Account:**\nPurana session hata diya gaya hai.\n\n📱 Apna naya **Telegram Phone Number** bhejein:", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]] )
        return

    if data == "list_presets":
        presets = bot_db[uid].get('presets', {})
        if not presets:
            await event.respond("📂 **Aapke paas koi saved preset nahi hai!**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
            return
        btns = []
        for pname in presets.keys():
            btns.append([Button.inline(f"📂 Load: {pname}", f"load_preset:{pname}".encode()), Button.inline(f"❌ Delete", f"del_preset:{pname}".encode())])
        btns.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond("📂 **Aapke Saved Presets:**", buttons=btns)
        return

    if data == "save_current_preset":
        prompt_msg = await event.respond("💾 **Save Preset:**\n\nApne is setup ke liye ek pyara sa **Name** type karke bhejein:", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_PRESET_NAME', 'prompt_id': prompt_msg.id}
        return

    if data.startswith("load_preset:"):
        pname = data.split(":")[1]
        presets = bot_db[uid].get('presets', {})
        if pname in presets:
            pdata = presets[pname]
            bot_db[uid]['dest_dict'] = dict(pdata.get('dest_dict', {}))
            bot_db[uid]['source_dict'] = dict(pdata.get('source_dict', {}))
            bot_db[uid]['sniper_mode'] = pdata.get('sniper_mode', 'rush')
            bot_db[uid]['lines_count'] = pdata.get('lines_count', 4)
            save_bot_data()

            client = await ensure_client(user_id)
            dest_list = list(bot_db[uid]['dest_dict'].keys())
            src_keys = list(bot_db[uid]['source_dict'].keys())
            source_list = [int(s) for s in src_keys] if src_keys else None
            await event.respond(f"✅ **Preset '{pname}' Loaded!**\n🚀 Bot Start ho raha hai...")
            await start_sniper_for_user(user_id, client, dest_list, "User", source_list, bot_db[uid]['sniper_mode'], bot_db[uid]['lines_count'])
        return

    if data.startswith("del_preset:"):
        pname = data.split(":")[1]
        presets = bot_db[uid].get('presets', {})
        if pname in presets:
            del presets[pname]
            save_bot_data()
            await event.answer(f"Preset '{pname}' deleted!", alert=True)
            if not presets: await event.respond("📂 **Aapke paas koi saved preset nahi hai!**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
            else:
                btns = [[Button.inline(f"📂 Load: {pn}", f"load_preset:{pn}".encode()), Button.inline(f"❌ Delete", f"del_preset:{pn}".encode())] for pn in presets.keys()]
                btns.append([Button.inline("🏠 Home", b"back_to_mode")])
                await event.respond("📂 **Aapke Saved Presets:**", buttons=btns)
        return

    if data == "manage_channels":
        src_dict, dest_dict = bot_db[uid].get('source_dict', {}), bot_db[uid].get('dest_dict', {})
        msg = "⚙️ **Manage Sources & Destinations:**\n\n📥 **Current Sources:**\n"
        btns = []
        for sid, sname in src_dict.items():
            msg += f"• `{sname}`\n"
            btns.append([Button.inline(f"❌ Remove Source: {sname}", f"rem_src:{sid}".encode())])
        if not src_dict: msg += "*(Koi source nahi hai)*\n"
        
        msg += "\n🚀 **Current Destinations:**\n"
        for did, dname in dest_dict.items():
            msg += f"• `{dname}`\n"
            btns.append([Button.inline(f"❌ Remove Dest: {dname}", f"rem_dest:{did}".encode())])
        if not dest_dict: msg += "*(Koi destination nahi hai)*\n"
        
        btns.append([Button.inline("📥 Add Source", b"manage_add_source"), Button.inline("🚀 Add Destination", b"manage_add_dest")])
        btns.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond(msg, buttons=btns)
        return

    if data.startswith("rem_src:"):
        bot_db[uid]['source_dict'].pop(data.split(":")[1], None)
        save_bot_data()
        await callback_handler(events.CallbackQuery.Event(data=b"manage_channels", sender_id=user_id))
        return

    if data.startswith("rem_dest:"):
        bot_db[uid]['dest_dict'].pop(data.split(":")[1], None)
        save_bot_data()
        await callback_handler(events.CallbackQuery.Event(data=b"manage_channels", sender_id=user_id))
        return

    if data == "manage_add_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_source", pinned_only=True) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode"), Button.inline("🔙 Back", b"manage_channels")])
        await event.respond("📥 **Manage Sources:**\nNaya Source select karein ya us channel ka ek message forward karein:", buttons=buttons)
        return

    if data == "manage_add_dest":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=False) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode"), Button.inline("🔙 Back", b"manage_channels")])
        await event.respond("🚀 **Manage Destinations:**\nNaya Destination select karein **ya destination channel se koi ek message forward karein:**", buttons=buttons)
        return

    if data == "mode_god_start":
        await event.respond("⚡ **GOD MODE Setup:**\nApna Source mode select karein:", buttons=[[Button.inline("📌 Auto Pinned Chats Mode", b"god_mode_pinned")], [Button.inline("🎯 Specific Source Channel", b"god_mode_source")], [Button.inline("🏠 Home", b"back_to_mode")]])
        return

    if data == "mode_special_start":
        if not is_special_authorized(user_id):
            prompt_msg = await event.respond("🔐 **Special Code Mode (Secret):**\n\nKripya apni Special Key yahan bhejein:", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
            user_states[user_id] = {'state': 'WAITING_SPECIAL_KEY', 'prompt_id': prompt_msg.id}
            return
        await event.respond("🔐 **Special Code Mode Setup:**", buttons=[[Button.inline("📌 Auto Pinned Chats Mode", b"sp_mode_pinned")], [Button.inline("🎯 Specific Source Channel", b"sp_mode_source")], [Button.inline("🏠 Home", b"back_to_mode")]])
        return

    if data in ["god_mode_pinned", "sp_mode_pinned"]:
        bot_db[uid]['setup_type'] = 'special' if data == "sp_mode_pinned" else 'god'
        bot_db[uid]['source_dict'] = {}
        save_bot_data()
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=False) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond("📌 **Pinned Mode:**\n🎯 Apna Destination Channel select karein **ya channel se koi message forward karein:**", buttons=buttons)
        return

    if data in ["god_mode_source", "sp_mode_source"]:
        bot_db[uid]['setup_type'] = 'special' if data == "sp_mode_source" else 'god'
        save_bot_data()
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_source", pinned_only=True) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond("🎯 **Specific Source Mode:**\n📥 Apna Source select karein\n**(Ya us channel se koi message forward karein):**", buttons=buttons)
        return

    if user_id == MASTER_ID:
        if data == "adm_gen_5_30":
            generated = [f"`{generate_key(days=30)}`" for _ in range(5)]
            await event.respond("✅ **5 New Keys Generated:**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_gen_1_30":
            await event.respond(f"✅ **1 New Key Generated:**\n\n`{generate_key(days=30)}`", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_gen_sp_30":
            await event.respond(f"🔐 **1 New Special Key Generated:**\n\n`{generate_special_key(days=30)}`", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_custom_sp_key":
            user_states[user_id] = 'WAITING_CUSTOM_SP_KEY'
            await event.respond("⚙️ **Custom Special Key:**\nFormat: `<count> <time>`", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_special_users":
            msg = "🔐 **Active Special Code Users:**\n\n"
            for su, sinfo in license_db.get("special_users", {}).items():
                msg += f"👤 User ID: `{su}`\n   🔑 Key: `{sinfo['key']}`\n   ⏳ Left: {format_time_left(datetime.fromisoformat(sinfo['expires']) - datetime.now())}\n\n"
            await event.respond(msg if license_db.get("special_users") else "No active special users right now!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_custom_key":
            user_states[user_id] = 'WAITING_CUSTOM_KEY'
            await event.respond("⚙️ **Custom Key:**\nFormat: `<count> <time>`", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_users":
            msg = "👥 **Active Users:**\n\n"
            for u, info in license_db.get("users", {}).items():
                msg += f"👤 `{info['name']}` (ID: `{u}`)\n   🔑 `{info['key']}`\n   ⏳ {format_time_left(datetime.fromisoformat(info['expires']) - datetime.now())}\n\n"
            await event.respond(msg if license_db.get("users") else "No active users!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_set_channel":
            user_states[user_id] = 'WAITING_CHANNEL_LINK'
            await event.respond("🔗 **Official Channel Link:** Bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_broadcast": 
            user_states[user_id] = 'WAITING_BROADCAST'
            await event.respond("📢 **Broadcast Message:** Type karke bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_ban_prompt":
            user_states[user_id] = 'WAITING_BAN_ID'
            await event.respond("🚫 Jis user ko BAN karna hai, uski ID bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_unban_prompt":
            user_states[user_id] = 'WAITING_UNBAN_ID'
            await event.respond("✅ UNBAN ke liye User ID bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_back":
            user_states[user_id] = None
            db_status = "🟢 MongoDB Cloud se Connected hai!" if MONGO_ERROR_MSG == "Connected" else f"🔴 MONGODB ERROR:\n`{MONGO_ERROR_MSG}`"
            await event.respond(f"👑 **MASTER ADMIN CONTROL PANEL** 👑\n\n📊 **Database Status:** {db_status}", buttons=get_admin_buttons())
            return

    if data == "ctl_pause":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = True
        bot_db[uid]['is_paused'] = True
        save_bot_data()
        await event.respond("🟡 **BOT IS PAUSED**", buttons=get_control_buttons(format_time_left(get_time_left(user_id))))
    elif data == "ctl_run":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = False
        bot_db[uid]['is_paused'] = False
        save_bot_data()
        await event.respond("🟢 **BOT IS ON**", buttons=get_control_buttons(format_time_left(get_time_left(user_id))))
    
    elif data == "ctl_restart":
        if user_id in active_snipers_dict:
            old_sniper = active_snipers_dict[user_id]
            old_sniper.is_running = False
            for h in getattr(old_sniper, 'handlers', []):
                try: user_data.get(user_id, {}).get('client').remove_event_handler(h)
                except: pass
            del active_snipers_dict[user_id]
        bot_db[uid]['is_running'] = False
        save_bot_data()
        user_states[user_id] = 'CHOOSE_MODE'
        await event.respond("🔄 **Setup Restarted!**\n\n🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))
        return

    elif data == "back_to_mode":
        user_states[user_id] = 'CHOOSE_MODE'
        await event.respond("🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))
    
    elif data == "mode_pinned":
        bot_db[uid]['setup_type'] = 'normal'
        bot_db[uid]['source_dict'] = {}
        save_bot_data()
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=False) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond("📌 **Auto Pinned Chats Mode:**\n🎯 Apna Destination Channel select karein **ya channel se koi message forward karein:**", buttons=buttons)

    elif data == "mode_source":
        bot_db[uid]['setup_type'] = 'normal'
        save_bot_data()
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_source", pinned_only=True) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond("🎯 **Specific Source Mode:**\n📥 Apna Source select karein\n**(Ya channel se koi message forward karein):*", buttons=buttons)
    
    elif data.startswith("add_source:"):
        _, s_id, s_name = data.split(":")
        bot_db[uid]['source_dict'][str(s_id)] = s_name
        save_bot_data()
        await event.respond(f"✅ Source Added: `{s_name}`", buttons=[[Button.inline("🎯 Done, Select Destination", b"done_sources"), Button.inline("🏠 Home", b"back_to_mode")]])
    
    elif data == "done_sources":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = await ensure_client(user_id)
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=False) if client else []
        buttons.append([Button.inline("🏠 Home", b"back_to_mode")])
        await event.respond("📌 Ab **Destination Channel** select karein **ya channel se koi message forward karein:**", buttons=buttons)
    
    elif data.startswith("add_destcust:"):
        _, d_id, d_name = data.split(":")
        bot_db[uid]['dest_dict'][str(d_id)] = d_name
        save_bot_data()
        st_type = bot_db[uid].get('setup_type', 'normal')
        if st_type == 'god':
            await event.respond("⚡ **GOD MODE Setup:**\nKya aapko Custom Link ya Username change karna hai?", buttons=[[Button.inline("🔗 Set/Change Link", b"ask_replacer_link"), Button.inline("👤 Set/Change Username", b"ask_replacer_username")], [Button.inline("🚀 Run GOD MODE", b"run_god_0")], [Button.inline("🏠 Home", b"back_to_mode")]])
        elif st_type == 'special':
            await event.respond("🔐 **Special Code Mode Setup:**\n🚀 Bot Start karne ke liye taiyar hain?", buttons=[[Button.inline("🚀 Start Special Code Bot", b"run_special_1")], [Button.inline("🏠 Home", b"back_to_mode")]])
        else:
            await event.respond("🛠 **Sniper Forwarding Mode select karein:**", buttons=[[Button.inline("🚀 Start Rush Mode", b"run_rush_0")], [Button.inline("🟢 Normal Mode", b"ask_lines_normal")], [Button.inline("🔗 Link Forwarder", b"ask_lines_link")], [Button.inline("🏠 Home", b"back_to_mode")]])

    elif data.startswith("ask_lines_"):
        mode = data.split("_")[2]
        bot_db[uid]['setup_mode_cache'] = mode
        save_bot_data()
        await event.respond(f"📏 **{mode.capitalize()} Mode - Line Settings:**\nAap messages ko kitni lines me bhejna chahte hain?", buttons=[[Button.inline("1 Line", f"format_{mode}_1".encode()), Button.inline("2 Lines", f"format_{mode}_2".encode())], [Button.inline("3 Lines", f"format_{mode}_3".encode()), Button.inline("4 Lines", f"format_{mode}_4".encode())], [Button.inline("🏠 Home", b"back_to_mode")]])

    elif data.startswith("format_"):
        parts = data.split("_")
        mode_cache, lines_cache = parts[1], int(parts[2])
        bot_db[uid]['setup_mode_cache'] = mode_cache
        bot_db[uid]['lines_count'] = lines_cache
        save_bot_data()
        await event.respond("⚙️ **Setup Options:**\nKya aapko Header, Footer ya Over text rakhna hai?", buttons=[[Button.inline("🔝 Edit/Set Header", b"ask_header"), Button.inline("🔚 Edit/Set Footer", b"ask_footer")], [Button.inline("✏️ Edit Over Text", b"ask_over_text"), Button.inline(f"🚀 Run Bot Now", f"run_{mode_cache}_{lines_cache}".encode())], [Button.inline("🏠 Home", b"back_to_mode")]])

    elif data == "ask_header":
        prompt_msg = await event.respond("🔝 **Send Custom Header:**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_HEADER', 'prompt_id': prompt_msg.id}
    elif data == "ask_footer":
        prompt_msg = await event.respond("🔚 **Send Custom Footer:**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_FOOTER', 'prompt_id': prompt_msg.id}
    elif data == "ask_over_text":
        prompt_msg = await event.respond("✏️ **Send Custom Over Text:**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_OVER_TEXT', 'prompt_id': prompt_msg.id}
    elif data == "ask_replacer_link":
        prompt_msg = await event.respond("🔗 **Send Custom Link:**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_CLONE_LINK', 'prompt_id': prompt_msg.id}
    elif data == "ask_replacer_username":
        prompt_msg = await event.respond("👤 **Send Custom @Username:**", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_CLONE_USERNAME', 'prompt_id': prompt_msg.id}
    
    elif data.startswith("run_"):
        parts = data.split("_")
        sniper_mode, lines = parts[1], int(parts[2])
        client = await ensure_client(user_id)
        if client:
            dests = list(bot_db[uid]['dest_dict'].keys())
            sources = [int(s) for s in bot_db[uid]['source_dict'].keys()] if bot_db[uid]['source_dict'] else None
            lines_count = bot_db[uid].get('lines_count', lines if lines > 0 else 4)
            await event.respond("🚀 **Bot Start ho raha hai...**")
            await start_sniper_for_user(user_id, client, dests, "User", sources, sniper_mode, lines_count)

@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip() if event.message.text else ""
    if text.startswith('/'): return
    uid = str(user_id)
    state = user_states.get(user_id)

    if user_id == MASTER_ID:
        if state == 'WAITING_BROADCAST':
            msg_count = 0
            for u_id in license_db.get("users", {}).keys():
                try:
                    await master_bot.send_message(int(u_id), f"📢 **Admin Message:**\n\n{text}")
                    msg_count += 1
                except: pass
            user_states[user_id] = None
            await event.reply(f"✅ **Broadcast Successful!** Sent to {msg_count} users.", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif state == 'WAITING_BAN_ID':
            if text in license_db.get("users", {}):
                del license_db["users"][text]
                save_licenses(license_db)
                if int(text) in active_snipers_dict:
                    old_sniper = active_snipers_dict[int(text)]
                    old_sniper.is_running = False
                    for h in getattr(old_sniper, 'handlers', []):
                        try: user_data.get(int(text), {}).get('client').remove_event_handler(h)
                        except: pass
                    del active_snipers_dict[int(text)]
                user_states[user_id] = None
                await event.reply(f"✅ User `{text}` BAN!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            else: await event.reply("❌ User not found.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif state == 'WAITING_UNBAN_ID':
            found_key, key_info = None, None
            for k, info in license_db.get("keys", {}).items():
                if str(info.get("used_by")) == text:
                    found_key, key_info = k, info
                    break
            if found_key:
                license_db["users"][text] = {"name": "Unbanned User", "key": found_key, "expires": key_info["expires"]}
                save_licenses(license_db)
                user_states[user_id] = None
                await event.reply(f"✅ User `{text}` UNBAN!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            else: await event.reply("❌ Key not found.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif state == 'WAITING_CHANNEL_LINK':
            link = f"https://t.me/{text[1:]}" if text.startswith('@') else f"https://{text}" if text.startswith('t.me/') else text
            license_db["settings"]["official_channel"] = link
            save_licenses(license_db)
            user_states[user_id] = None
            await event.reply("✅ Official Channel updated!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif state == 'WAITING_CUSTOM_KEY':
            try:
                parts = text.lower().split()
                count, time_str = int(parts[0]), parts[1]
                hours = int(time_str[:-1]) if time_str.endswith('h') else 0
                days = int(time_str[:-1]) if time_str.endswith('d') else int(time_str) if not hours else 0
                generated = [f"`{generate_key(days=days, hours=hours)}`" for _ in range(count)]
                user_states[user_id] = None
                await event.reply(f"✅ **{count} New Keys Generated:**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            except: await event.reply("⚠️ Format Error!", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

    if isinstance(state, dict) and state.get('state') == 'WAITING_SPECIAL_KEY':
        clean_text = text.strip()
        if clean_text in license_db["special_keys"]:
            sk_info = license_db["special_keys"][clean_text]
            license_db["special_keys"][clean_text]["used_by"] = user_id
            license_db["special_users"][uid] = {"key": clean_text, "expires": sk_info["expires"]}
            save_licenses(license_db)
            user_states[user_id] = None
            await event.respond("✅ **Special Key Verified!**", buttons=[[Button.inline("🔐 Open Special Code Setup", b"mode_special_start")]])
            return
        else:
            await event.reply("❌ **Invalid Special Key!**")
            return

    if isinstance(state, dict) and state.get('state') == 'WAITING_PRESET_NAME':
        pname = text
        if "presets" not in bot_db[uid]: bot_db[uid]['presets'] = {}
        bot_db[uid]['presets'][pname] = {
            'dest_dict': dict(bot_db[uid].get('dest_dict', {})),
            'source_dict': dict(bot_db[uid].get('source_dict', {})),
            'sniper_mode': bot_db[uid].get('sniper_mode', 'rush'),
            'lines_count': bot_db[uid].get('lines_count', 4),
        }
        save_bot_data()
        try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
        except: pass
        user_states[user_id] = None
        await event.respond(f"✅ **Preset '{pname}' Saved Successfully!**", buttons=[[Button.inline("📂 View Presets", b"list_presets"), Button.inline("🏠 Home", b"back_to_mode")]])
        return

    if isinstance(state, dict) and state.get('state') in ['WAITING_HEADER', 'WAITING_FOOTER', 'WAITING_OVER_TEXT']:
        st = state.get('state')
        if st == 'WAITING_HEADER':
            bot_db[uid]['custom_header'] = text
            bot_db[uid]['use_header'] = True
            msg_succ = "✅ **Header Saved!**"
        elif st == 'WAITING_FOOTER':
            bot_db[uid]['custom_footer'] = text
            bot_db[uid]['use_footer'] = True
            msg_succ = "✅ **Footer Saved!**"
        else:
            bot_db[uid]['over_text'] = text
            bot_db[uid]['use_over'] = True
            msg_succ = "✅ **Over Text Saved!**"
        save_bot_data()
        user_states[user_id] = None
        mode_c = bot_db[uid].get('setup_mode_cache', 'rush')
        lines_c = bot_db[uid].get('lines_count', 4)
        await event.respond(f"{msg_succ}\n\nKya aapko aur kuch set karna hai?", buttons=[[Button.inline("🔝 Header", b"ask_header"), Button.inline("🔚 Footer", b"ask_footer")], [Button.inline("✏️ Over Text", b"ask_over_text"), Button.inline(f"🚀 Run Bot", f"run_{mode_c}_{lines_c}".encode())], [Button.inline("🏠 Home", b"back_to_mode")]])
        return

    if isinstance(state, dict) and state.get('state') in ['WAITING_CLONE_LINK', 'WAITING_CLONE_USERNAME']:
        if state.get('state') == 'WAITING_CLONE_LINK': bot_db[uid]['replacer_link'] = text
        else: bot_db[uid]['replacer_username'] = text if text.startswith('@') else '@' + text
        save_bot_data()
        user_states[user_id] = None
        await event.respond("✅ **Saved Successfully!**", buttons=[[Button.inline("🚀 Run GOD MODE", b"run_god_0"), Button.inline("🏠 Home", b"back_to_mode")]])
        return

    # 🔥 NEW FEATURE: Forward message to Add BOTH Source and Destination!
    if isinstance(state, dict) and state.get('state') in ['SELECT_SOURCES', 'SELECT_DEST_CUSTOM']:
        client = await ensure_client(user_id)
        if not client: return
        forwarded_chat_id = None
        forwarded_chat_title = None
        fwd = getattr(event.message, 'forward', None)
        if fwd:
            if getattr(fwd, 'chat', None):
                forwarded_chat_id = fwd.chat.id
                forwarded_chat_title = getattr(fwd.chat, 'title', 'Chat')
            elif getattr(fwd, 'from_id', None):
                if isinstance(fwd.from_id, PeerChannel): 
                    forwarded_chat_id = fwd.from_id.channel_id
                    forwarded_chat_title = "Forwarded Channel"
        if forwarded_chat_id:
            full_dest_id = int(f"-100{abs(forwarded_chat_id)}") if not str(forwarded_chat_id).startswith("-100") else forwarded_chat_id
            
            if state.get('state') == 'SELECT_SOURCES':
                bot_db[uid]['source_dict'][str(full_dest_id)] = forwarded_chat_title[:15]
                save_bot_data()
                await event.reply(f"✅ **Source Auto-Added:** `{forwarded_chat_title}`", buttons=[[Button.inline("🎯 Done, Select Destination", b"done_sources"), Button.inline("🏠 Home", b"back_to_mode")]])
            
            elif state.get('state') == 'SELECT_DEST_CUSTOM':
                bot_db[uid]['dest_dict'][str(full_dest_id)] = forwarded_chat_title[:15]
                save_bot_data()
                st_type = bot_db[uid].get('setup_type', 'normal')
                if st_type == 'god':
                    next_btns = [[Button.inline("🔗 Set/Change Link", b"ask_replacer_link"), Button.inline("👤 Set/Change Username", b"ask_replacer_username")], [Button.inline("🚀 Run GOD MODE", b"run_god_0")], [Button.inline("🏠 Home", b"back_to_mode")]]
                    msg = f"✅ **Destination Auto-Added:** `{forwarded_chat_title}`\n\n⚡ **GOD MODE Setup:**\nKya aapko Custom Link ya Username change karna hai?"
                elif st_type == 'special':
                    next_btns = [[Button.inline("🚀 Start Special Code Bot", b"run_special_1")], [Button.inline("🏠 Home", b"back_to_mode")]]
                    msg = f"✅ **Destination Auto-Added:** `{forwarded_chat_title}`\n\n🔐 **Special Code Mode Setup:**\n🚀 Bot Start karne ke liye taiyar hain?"
                else:
                    next_btns = [[Button.inline("🚀 Start Rush Mode", b"run_rush_0")], [Button.inline("🟢 Normal Mode", b"ask_lines_normal")], [Button.inline("🔗 Link Forwarder", b"ask_lines_link")], [Button.inline("🏠 Home", b"back_to_mode")]]
                    msg = f"✅ **Destination Auto-Added:** `{forwarded_chat_title}`\n\n🛠 **Sniper Forwarding Mode select karein:**"
                await event.reply(msg, buttons=next_btns)
            return

    if state == 'WAITING_KEY':
        if text in license_db["keys"]:
            k_info = license_db["keys"][text]
            license_db["keys"][text]["used_by"] = user_id
            license_db["users"][str(user_id)] = {"name": event.sender.first_name, "key": text, "expires": k_info["expires"]}
            save_licenses(license_db)
            client = await ensure_client(user_id)
            if client:
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply("✅ **Key Verified!**", buttons=get_mode_buttons(user_id))
            else:
                user_states[user_id] = 'WAITING_PHONE'
                await event.reply("📱 Apna **Telegram Phone Number** bhejein:", buttons=[[Button.inline("🏠 Home", b"back_to_mode")]] )
        else: await event.reply("❌ **Invalid Key!**")

    elif state in ['WAITING_PHONE']:
        user_states[user_id] = {'state': 'WAITING_OTP', 'phone': text}
        await event.reply("🔄 OTP bhej rahe hain...")
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(text)
            user_data[user_id] = {'client': client, 'phone_code_hash': sent.phone_code_hash}
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        try:
            client = user_data[user_id]['client']
            await client.sign_in(phone=state['phone'], code=text, phone_code_hash=user_data[user_id]['phone_code_hash'])
            save_user_session(user_id, client.session.save())
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply("✅ **Login Successful! Session Cloud par save ho gaya hai! ☁**", buttons=get_mode_buttons(user_id))
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'WAITING_PASSWORD'}
            await event.reply("🔒 2-Step Verification Password bhejein:")
        except Exception as e:
            await event.reply(f"❌ OTP Error: {e}")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_PASSWORD':
        try:
            client = user_data[user_id]['client']
            await client.sign_in(password=text)
            save_user_session(user_id, client.session.save())
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply("✅ **Password Verified! Session Cloud par save ho gaya hai! ☁**", buttons=get_mode_buttons(user_id))
        except Exception as e:
            await event.reply(f"❌ Password Error: {e}")
            user_states[user_id] = None

print("👑 Master Bot Initialized Successfully with MongoDB Cloud!")
master_bot.start(bot_token=BOT_TOKEN)
master_bot.loop.create_task(auto_resume_snipers())
master_bot.run_until_disconnected()
