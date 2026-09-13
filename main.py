import asyncio
import time
import re
from collections import deque
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, Button
from telethon.tl.types import MessageEntityCode, MessageEntityPre
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

user_states = {}
user_data = {}  
active_snipers_dict = {}

# --- 🔐 DATABASES ---
LICENSE_FILE = "licenses.json"
BOT_DATA_FILE = "bot_data.json"

def load_licenses():
    try:
        with open(LICENSE_FILE, 'r') as f:
            data = json.load(f)
            if "settings" not in data: data["settings"] = {"official_channel": ""}
            if "special_keys" not in data: data["special_keys"] = {}
            if "special_users" not in data: data["special_users"] = {}
            return data
    except FileNotFoundError:
        return {"keys": {}, "users": {}, "special_keys": {}, "special_users": {}, "settings": {"official_channel": ""}} 

def save_licenses(data):
    with open(LICENSE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

license_db = load_licenses()

def load_bot_data():
    try:
        with open(BOT_DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bot_data():
    with open(BOT_DATA_FILE, 'w') as f:
        json.dump(bot_db, f, indent=4)

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
            'over_timer': 0, 
            'over_text': "❌️❌️ OVER ❌️❌️",
            'presets': {},
            'setup_type': 'normal', 
            'setup_mode_cache': 'normal',
            'setup_lines_cache': 4,
            'stats': {'forwarded': 0}
        }
        save_bot_data()

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

def get_special_time_left(user_id):
    uid = str(user_id)
    if uid not in license_db["special_users"]: return None
    expires_str = license_db["special_users"][uid]["expires"]
    return datetime.fromisoformat(expires_str) - datetime.now()

def format_time_left(td):
    if not td or int(td.total_seconds()) <= 0: return "Expired"
    days, hours = int(td.total_seconds()) // 86400, (int(td.total_seconds()) % 86400) // 3600
    return f"{days} Days" if days > 0 else f"{hours} Hours"

# --- 🧠 UI BUTTON HELPERS ---
def get_official_btn_row():
    link = license_db.get("settings", {}).get("official_channel", "")
    if link: return [[Button.url("📢 Join Official Channel", url=link)]]
    return None

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
        [Button.inline("📂 Saved Presets / Setups", b"list_presets")]
    ]
    off_btn = get_official_btn_single()
    if off_btn: btns.append(off_btn)
    return btns

def get_control_buttons(validity_str):
    btns = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline("💾 Save Current Setup", b"save_current_preset"), Button.inline("📂 Load Preset", b"list_presets")],
        [Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")],
        [Button.inline("📊 My Stats", b"ctl_stats")]
    ]
    off_btn = get_official_btn_single()
    if off_btn: btns.append(off_btn)
    return btns

def get_admin_buttons():
    return [
        [Button.inline("🔑 Gen 1 Key (30D)", b"adm_gen_1_30"), Button.inline("🔑 Gen 5 Keys (30D)", b"adm_gen_5_30")],
        [Button.inline("🔐 Gen Special Key (30D)", b"adm_gen_sp_30"), Button.inline("👥 View Special Users", b"adm_special_users")],
        [Button.inline("⚙️ Custom Key (Days/Hours)", b"adm_custom_key")],
        [Button.inline("👥 View Active Users", b"adm_users"), Button.inline("🔗 Set Official Channel", b"adm_set_channel")],
        [Button.inline("🚫 Ban User", b"adm_ban_prompt"), Button.inline("✅ Unban User", b"adm_unban_prompt")],
        [Button.inline("📢 Broadcast Message", b"adm_broadcast")]
    ]

# --- 🚀 DATA FETCHING (1000 LIMIT) ---
async def get_channel_buttons(client, action_type, require_admin=False, pinned_only=False):
    try:
        dialogs = await client.get_dialogs(limit=1000)
        buttons = []
        for d in dialogs:
            if pinned_only and not d.pinned: continue
            if d.is_channel or d.is_group:
                if require_admin and not (getattr(d.entity, 'creator', False) or getattr(d.entity, 'admin_rights', None)): continue
                name = d.name[:20] if d.name else "Unnamed"
                buttons.append([Button.inline(name, data=f"{action_type}:{d.id}:{name[:15]}")])
                if len(buttons) >= 60: break
        return buttons
    except: return []

# --- 🧠 SAFE USERNAME REPLACER ---
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

# --- 🧠 USER SNIPER CLASS ---
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
        self.processed_ids_queue = deque(maxlen=50)
        self.seen_codes_set = set()
        self.seen_codes_queue = deque(maxlen=100)
        
        self.msg_map = {} 
        self.msg_map_keys = deque(maxlen=1000)
        
    async def update_pinned_loop(self):
        if self.source_chat_ids: return
        while self.is_running:
            try:
                dialogs = await self.client.get_dialogs(limit=30)
                self.pinned_chats = {d.id for d in dialogs if d.pinned and d.id not in self.destinations}
            except: pass
            await asyncio.sleep(60)

async def start_sniper_for_user(user_id, client, dest_chats, name, source_chat_ids=None, sniper_mode="rush", lines_count=4):
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_running = False

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

    @client.on(events.NewMessage())
    async def handler(event):
        if not sniper.is_running:
            client.remove_event_handler(handler)
            return

        if not check_subscription(user_id):
            sniper.is_running = False
            bot_db[uid]['is_running'] = False
            save_bot_data()
            client.remove_event_handler(handler)
            if user_id in active_snipers_dict: del active_snipers_dict[user_id]
            try: await master_bot.send_message(user_id, "⚠️ **Aapki License Key expire ho chuki hai!**\nBot automatic stop ho gaya hai.")
            except: pass
            return

        if sniper.is_paused or not sniper.destinations: return
            
        if sniper.source_chat_ids:
            if event.chat_id not in sniper.source_chat_ids: return
        else:
            if event.chat_id not in sniper.pinned_chats: return

        if event.id in sniper.processed_ids_set: return
        sniper.processed_ids_set.add(event.id)

        text_content = event.message.message or ""
        messages_to_send = []

        # 🔐 SPECIAL CODE MODE (Full Power, 1 Message, Auto-Stop)
        if sniper.sniper_mode == "special":
            if not is_special_authorized(user_id):
                sniper.is_running = False
                bot_db[uid]['is_running'] = False
                save_bot_data()
                if user_id in active_snipers_dict: del active_snipers_dict[user_id]
                try: await master_bot.send_message(user_id, "⚠️ **Aapki Special Key expire ho chuki hai ya authorized nahi hai!**\nSpecial Code mode stop ho gaya hai.")
                except: pass
                return

            if not text_content: return
            extracted_items = []
            for ent, ent_text in event.message.get_entities_text():
                if isinstance(ent, (MessageEntityCode, MessageEntityPre)):
                    if "t.me/" in ent_text.lower() or "telegram.me/" in ent_text.lower(): continue
                    if ent_text not in extracted_items:
                        extracted_items.append(ent_text)

            if not extracted_items: return
            
            # Format according to user lines count
            c = extracted_items[0]
            body_text = "\n".join([f"`{c}`"] * sniper.lines_count)
            messages_to_send.append({'text': body_text, 'media': None, 'is_special': True})

        # ⚡ GOD MODE
        elif sniper.sniper_mode == "god":
            if not text_content and not event.message.media: return
            try:
                msg_html = html.unparse(text_content, event.message.entities)
            except:
                msg_html = text_content
                
            replacer_link = bot_db[uid].get('replacer_link')
            replacer_uname = bot_db[uid].get('replacer_username')
            if replacer_link: msg_html = re.sub(r'(https?://)?t\.me/\+[a-zA-Z0-9_-]+', replacer_link, msg_html)
            if replacer_uname: msg_html = safe_replace_username(msg_html, replacer_uname)
                
            messages_to_send.append({'text': msg_html, 'media': event.message.media, 'is_god': True})

        else:
            if not text_content: return
            extracted_items = []
            if sniper.sniper_mode == "link":
                link_pattern = r'(?:\b|https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?(?:#[^\s]*)?'
                found_links = re.findall(link_pattern, text_content)
                for ent, ent_text in event.message.get_entities_text():
                    if isinstance(ent, (types.MessageEntityUrl, types.MessageEntityTextUrl)) and ent_text not in found_links:
                        found_links.append(ent_text)
                for l in found_links:
                    if l not in sniper.seen_codes_set and l not in extracted_items: extracted_items.append(l)
            else:
                for ent, ent_text in event.message.get_entities_text():
                    if isinstance(ent, (MessageEntityCode, MessageEntityPre)):
                        if "t.me/" in ent_text.lower() or "telegram.me/" in ent_text.lower(): continue
                        if ent_text not in sniper.seen_codes_set and ent_text not in extracted_items:
                            extracted_items.append(ent_text)

            if not extracted_items: return
            for item in extracted_items:
                if len(sniper.seen_codes_queue) == 100:
                    sniper.seen_codes_set.discard(sniper.seen_codes_queue.popleft())
                sniper.seen_codes_queue.append(item)
                sniper.seen_codes_set.add(item)

            if sniper.sniper_mode == "rush":
                num = len(extracted_items)
                lines = [f"`{extracted_items[0]}`"] * 3 if num == 1 else [f"`{extracted_items[0]}`"] * 2 + [f"`{extracted_items[1]}`"] * 2 if num == 2 else [f"`{c}`" for c in extracted_items]
                messages_to_send.append({'text': "\n".join(lines), 'media': None, 'is_god': False})
            else:
                for c in extracted_items: 
                    body_text = "\n".join([f"`{c}`"] * sniper.lines_count)
                    final_text = ""
                    if bot_db[uid].get('custom_header'): final_text += bot_db[uid]['custom_header'] + "\n\n"
                    final_text += body_text
                    if bot_db[uid].get('custom_footer'): final_text += "\n\n" + bot_db[uid]['custom_footer']
                    messages_to_send.append({'text': final_text, 'media': None, 'is_god': False})

        sent_msgs_this_event = {}
        
        async def send_to_single_destination(d_id, target, item):
            try:
                kwargs = {'link_preview': True}
                if item.get('is_special') or item.get('is_god'):
                    kwargs['parse_mode'] = 'html' if item.get('is_god') else 'md'
                    if item.get('media'): kwargs['file'] = item['media']
                    sent_msg = await client.send_message(target, item['text'], **kwargs)
                else:
                    kwargs['parse_mode'] = 'md'
                    if item.get('media'): kwargs['file'] = item['media']
                    sent_msg = await client.send_message(target, item['text'], **kwargs)
                    
                if sent_msg:
                    timer_sec = bot_db[uid].get('over_timer', 0)
                    if timer_sec > 0 and not item.get('is_god') and not item.get('is_special'):
                        custom_over = bot_db[uid].get('over_text', "❌️❌️ OVER ❌️❌️")
                        asyncio.create_task(auto_over_message(client, target, sent_msg.id, timer_sec, custom_over))
                    return d_id, sent_msg.id
            except: pass
            return None

        for item in messages_to_send:
            if len(sniper.destinations) == 1:
                for d_id, target in sniper.destinations.items():
                    await send_to_single_destination(d_id, target, item)
            else:
                tasks = [send_to_single_destination(d_id, target, item) for d_id, target in sniper.destinations.items()]
                await asyncio.gather(*tasks)

        # 🛑 IF SPECIAL CODE MODE: FORWARD 1 MESSAGE AND STOP INSTANTLY
        if sniper.sniper_mode == "special":
            sniper.is_running = False
            bot_db[uid]['is_running'] = False
            save_bot_data()
            if user_id in active_snipers_dict: del active_snipers_dict[user_id]
            try:
                await master_bot.send_message(user_id, "🎯 **Special Code successfully forwarded!**\n\nBot automatically stop ho gaya hai. Dobara use karne ke liye naya setup karein.")
            except: pass
            return

    try:
        time_left = get_time_left(user_id)
        validity_str = format_time_left(time_left)
        mode_text = f"Multiple Sources ({len(source_chat_ids)})" if source_chat_ids else "Auto Pinned Chats"
        lines_info = f" ({sniper.lines_count} Lines)" if sniper.sniper_mode not in ["rush", "god", "special"] else ""
        mode_name = "🔐 SPECIAL" if sniper.sniper_mode == "special" else "⚡ GOD" if sniper.sniper_mode == "god" else sniper.sniper_mode.capitalize()
        await master_bot.send_message(
            user_id, 
            f"✅ **SNIPER ACTIVE!** 🎯\n\n🟢 **Target Mode:** {mode_text}\n🛠 **Forwarding:** `{mode_name} Mode{lines_info}`\n🚀 **Destinations:** `{len(sniper.destinations)}`\n⏳ **Validity:** `{validity_str}`", 
            buttons=get_control_buttons(validity_str)
        )
    except: pass

async def auto_over_message(client, target, msg_id, delay, custom_over_text):
    await asyncio.sleep(delay)
    try:
        await client.edit_message(target, msg_id, custom_over_text)
    except: pass

async def auto_resume_snipers():
    await asyncio.sleep(2)
    for uid_str, data in bot_db.items():
        if data.get('is_running') and check_subscription(uid_str) and data.get('sniper_mode') != 'special':
            user_id = int(uid_str)
            client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
            try:
                await client.connect()
                if await client.is_user_authorized():
                    if user_id not in user_data: user_data[user_id] = {}
                    user_data[user_id]['client'] = client
                    dests = list(data.get('dest_dict', {}).keys())
                    sources = list(data.get('source_dict', {}).keys())
                    sources = [int(s) for s in sources] if sources else None
                    mode = data.get('sniper_mode', 'rush')
                    lines = data.get('lines_count', 4)
                    await start_sniper_for_user(user_id, client, dests, "User", sources, mode, lines)
            except: pass

# --- 💬 COMMAND HANDLERS & SMART LOGIN ---
@master_bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    init_user_db(user_id)
    
    if user_id == MASTER_ID:
        user_states[user_id] = None 
        await event.reply("👑 **MASTER ADMIN CONTROL PANEL** 👑", buttons=get_admin_buttons())
        return
        
    if is_user_authorized(user_id):
        if check_subscription(user_id):
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)

            if user_id in active_snipers_dict:
                sniper = active_snipers_dict[user_id]
                status_txt = "🟢 **BOT IS ON**" if not sniper.is_paused else "🟡 **BOT IS PAUSED**"
                await event.reply(f"{status_txt}\n\n⏳ **Validity:** `{validity_str}`\nApna bot control karne ke liye niche buttons use karein:", buttons=get_control_buttons(validity_str))
                return

            client = user_data.get(user_id, {}).get('client')
            if not client:
                client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
                await client.connect()
                
            if await client.is_user_authorized():
                if user_id not in user_data: user_data[user_id] = {}
                user_data[user_id]['client'] = client
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply(f"✅ **Welcome Back!** (⏳ `{validity_str}`)\n\n🎯 Apne kaam ke liye **Target Mode** select karein:", buttons=get_mode_buttons(user_id))
            else:
                if user_id not in user_data: user_data[user_id] = {}
                user_data[user_id]['client'] = client
                user_states[user_id] = 'WAITING_PHONE'
                await event.reply(f"✅ **Welcome Back!** (⏳ `{validity_str}`)\n\n📱 Pehle apna **Telegram Phone Number** bhejein:")
            return
        else:
            user_states[user_id] = 'WAITING_KEY'
            await event.reply("⚠️ **Aapki purani Key Expire ho chuki hai!**\n\nKripya apni **Nayi License Key (PIN)** yahan bhejein:", buttons=get_official_btn_row())
            return

    user_states[user_id] = 'WAITING_KEY'
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:", buttons=get_official_btn_row())

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
    uid = str(user_id)
    init_user_db(user_id)

    try: await event.delete()
    except: pass

    # 👑 ADMIN ACTIONS
    if user_id == MASTER_ID:
        if data == "adm_gen_5_30":
            generated = [f"`{generate_key(days=30)}`" for _ in range(5)]
            await event.respond("✅ **5 New Keys Generated:**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_gen_1_30":
            key = generate_key(days=30)
            await event.respond(f"✅ **1 New Key Generated:**\n\n`{key}`", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_gen_sp_30":
            skey = generate_special_key(days=30)
            await event.respond(f"🔐 **1 New Special Key Generated:**\n\n`{skey}`", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_special_users":
            msg = "🔐 **Active Special Code Users:**\n\n"
            for su, sinfo in license_db["special_users"].items():
                exp = datetime.fromisoformat(sinfo['expires'])
                msg += f"👤 User ID: `{su}`\n   🔑 Key: `{sinfo['key']}`\n   ⏳ Left: {format_time_left(exp - datetime.now())}\n\n"
            await event.respond(msg if license_db["special_users"] else "No active special users right now!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_custom_key":
            user_states[user_id] = 'WAITING_CUSTOM_KEY'
            await event.respond("⚙️ **Custom Key:**\nFormat: `<count> <time>` (e.g. `1 12h` or `5 2d`)", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_users":
            msg = "👥 **Active Users:**\n\n"
            for u, info in license_db["users"].items():
                expires = datetime.fromisoformat(info['expires'])
                msg += f"👤 `{info['name']}` (ID: `{u}`)\n   🔑 `{info['key']}`\n   ⏳ {format_time_left(expires - datetime.now())}\n\n"
            await event.respond(msg if license_db["users"] else "No users!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
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
            await event.respond("👑 **MASTER ADMIN CONTROL PANEL** 👑", buttons=get_admin_buttons())
            return

    # USER CONTROL ACTIONS
    if data == "ctl_pause":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = True
        bot_db[uid]['is_paused'] = True
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.respond(f"🟡 **BOT IS PAUSED (OFF)**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    
    elif data == "ctl_run":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = False
        bot_db[uid]['is_paused'] = False
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.respond(f"🟢 **BOT IS ON**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    
    elif data == "save_current_preset":
        prompt_msg = await event.respond("💾 **Save Preset:**\n\nApne is setup ke liye ek pyara sa **Name** type karke bhejein (jaise `RummyVIP`):", buttons=[[Button.inline("🔙 Back", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_PRESET_NAME', 'prompt_id': prompt_msg.id}
        return

    elif data == "list_presets":
        presets = bot_db[uid].get('presets', {})
        if not presets:
            await event.respond("📂 **Aapke paas koi saved preset nahi hai!**\nPehle apna setup karke use save karein.", buttons=[[Button.inline("🔙 Back", b"back_to_mode")]])
            return
        
        btns = []
        for pname in presets.keys():
            btns.append([Button.inline(f"📂 Load: {pname}", f"load_preset:{pname}".encode()), Button.inline(f"❌ Delete", f"del_preset:{pname}".encode())])
        btns.append([Button.inline("🔙 Back", b"back_to_mode")])
        await event.respond("📂 **Aapke Saved Presets:**\nNiche se apna setup select karein:", buttons=btns)
        return

    elif data.startswith("load_preset:"):
        pname = data.split(":")[1]
        presets = bot_db[uid].get('presets', {})
        if pname in presets:
            pdata = presets[pname]
            bot_db[uid]['dest_dict'] = pdata.get('dest_dict', {})
            bot_db[uid]['source_dict'] = pdata.get('source_dict', {})
            bot_db[uid]['sniper_mode'] = pdata.get('sniper_mode', 'rush')
            bot_db[uid]['lines_count'] = pdata.get('lines_count', 4)
            bot_db[uid]['replacer_link'] = pdata.get('replacer_link')
            bot_db[uid]['replacer_username'] = pdata.get('replacer_username')
            bot_db[uid]['custom_header'] = pdata.get('custom_header')
            bot_db[uid]['custom_footer'] = pdata.get('custom_footer')
            bot_db[uid]['over_timer'] = pdata.get('over_timer', 0)
            bot_db[uid]['over_text'] = pdata.get('over_text', "❌️❌️ OVER ❌️❌️")
            save_bot_data()

            client = user_data.get(user_id, {}).get('client')
            dest_list = list(bot_db[uid]['dest_dict'].keys())
            src_keys = list(bot_db[uid]['source_dict'].keys())
            source_list = [int(s) for s in src_keys] if src_keys else None
            mode = bot_db[uid]['sniper_mode']
            lines = bot_db[uid]['lines_count']

            if mode == 'special' and not is_special_authorized(user_id):
                await event.respond("❌ Is preset ke liye Special Key required hai, lekin aapke paas active Special Key nahi hai!")
                return

            await event.respond(f"✅ **Preset '{pname}' Loaded Successfully!**\n🚀 Bot Start ho raha hai...")
            await start_sniper_for_user(user_id, client, dest_list, "User", source_list, mode, lines)
        else:
            await event.respond("❌ Preset nahi mila!", buttons=[[Button.inline("🔙 Back", b"list_presets")]])
        return

    elif data.startswith("del_preset:"):
        pname = data.split(":")[1]
        presets = bot_db[uid].get('presets', {})
        if pname in presets:
            del presets[pname]
            save_bot_data()
            await event.answer(f"Preset '{pname}' deleted!", alert=True)
            await callback_handler(events.CallbackQuery.Event(data=b"list_presets", sender_id=user_id))
        return

    elif data == "ctl_mykey":
        if is_user_authorized(user_id):
            info = license_db["users"][str(user_id)]
            sp_time = get_special_time_left(user_id)
            sp_str = format_time_left(sp_time) if is_special_authorized(user_id) else "Not Active"
            await event.answer(f"🔑 Key: {info['key']} | ⏳ Left: {format_time_left(get_time_left(user_id))}\n🔐 Special Key: {sp_str}", alert=True)
            
    elif data == "ctl_stats": 
        fwd_count = bot_db[uid].get('stats', {}).get('forwarded', 0)
        await event.answer(f"📊 Aapke bot ne ab tak {fwd_count} messages forward kiye hain!", alert=True)
        
    elif data == "ctl_restart":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_running = False
            del active_snipers_dict[user_id]
        bot_db[uid]['is_running'] = False
        save_bot_data()
        user_states[user_id] = 'CHOOSE_MODE'
        await event.respond(f"🔄 **Setup Restarted!**\n\n🎯 Apne kaam ke liye Target Mode select karein:", buttons=get_mode_buttons(user_id))

    elif data == "back_to_mode":
        user_states[user_id] = 'CHOOSE_MODE'
        await event.respond(f"🎯 Apne kaam ke liye Target Mode select karein:", buttons=get_mode_buttons(user_id))

    # 🔐 SPECIAL CODE MODE START
    elif data == "mode_special_start":
        if not is_special_authorized(user_id):
            prompt_msg = await event.respond(
                "🔐 **Special Code Mode:**\n\nYeh ek secret mode hai jiske liye **Special Key** ki zaroorat padti hai.\n\nKripya apni Special Key yahan bhejein:",
                buttons=[[Button.inline("🔙 Back", b"back_to_mode")]]
            )
            user_states[user_id] = {'state': 'WAITING_SPECIAL_KEY', 'prompt_id': prompt_msg.id}
            return

        await event.respond(
            "🔐 **Special Code Mode Setup:**\n\nAap messages kahan se uthana chahte hain?",
            buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"sp_mode_pinned")],
                [Button.inline("🎯 Specific Source Channel", b"sp_mode_source")],
                [Button.inline("🔙 Back", b"back_to_mode")]
            ]
        )

    elif data in ["sp_mode_pinned", "sp_mode_source"]:
        is_source_mode = (data == "sp_mode_source")
        bot_db[uid]['setup_type'] = 'special'
        bot_db[uid]['source_dict'] = {}
        save_bot_data()
        
        if is_source_mode:
            user_states[user_id] = {'state': 'SELECT_SOURCES_SP'}
            client = user_data.get(user_id, {}).get('client')
            if client and client.is_connected():
                buttons = await get_channel_buttons(client, "add_source_sp", pinned_only=True)
                buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
                await event.respond("🎯 **Special Code Mode:**\n📥 Apna Source Channel select karein:", buttons=buttons)
        else:
            user_states[user_id] = {'state': 'SELECT_DEST_SP'}
            client = user_data.get(user_id, {}).get('client')
            if client and client.is_connected():
                buttons = await get_channel_buttons(client, "add_dest_sp", require_admin=True)
                buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
                await event.respond("🎯 **Special Code Mode:**\n📌 Apna Destination Channel select karein:", buttons=buttons)

    # ⚡ GOD MODE START
    elif data == "mode_god_start":
        await event.respond(
            "⚡ **GOD MODE Setup:**\n\nAap messages kahan se uthana chahte hain?",
            buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"god_mode_pinned")],
                [Button.inline("🎯 Specific Source Channel", b"god_mode_source")],
                [Button.inline("🔙 Back", b"back_to_mode")]
            ]
        )

    # 🎯 TARGET SELECTION
    elif data in ["mode_pinned", "god_mode_pinned"]:
        is_god = data.startswith("god_")
        bot_db[uid]['setup_type'] = 'god' if is_god else 'normal'
        bot_db[uid]['source_dict'] = {}
        save_bot_data()
        
        user_states[user_id] = {'state': 'SELECT_DEST'}
        client = user_data.get(user_id, {}).get('client')
        
        if client and client.is_connected():
            buttons = await get_channel_buttons(client, "add_dest", require_admin=True)
            buttons.append([Button.inline("🔙 Back", b"mode_god_start" if is_god else b"back_to_mode")])
            title_prefix = "⚡ GOD MODE: " if is_god else ""
            await event.respond(f"{title_prefix}📌 **Pinned Mode:**\n🎯 Apna Destination select karein:", buttons=buttons)
        else: await event.respond("📱 Pehle apna Telegram Phone Number bhejein:")

    elif data in ["mode_source", "god_mode_source"]:
        is_god = data.startswith("god_")
        bot_db[uid]['setup_type'] = 'god' if is_god else 'normal'
        save_bot_data()
        
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = user_data.get(user_id, {}).get('client')
        
        if client and client.is_connected():
            buttons = await get_channel_buttons(client, "add_source", pinned_only=True)
            buttons.append([Button.inline("🔙 Back", b"mode_god_start" if is_god else b"back_to_mode")])
            title_prefix = "⚡ GOD MODE: " if is_god else ""
            await event.respond(f"{title_prefix}🎯 **Specific Source Mode:**\n📥 Apna Source select karein:", buttons=buttons)
        else: await event.respond("📱 Pehle apna Telegram Phone Number bhejein:")

    # SPECIAL SOURCE / DESTINATION CALLBACKS
    elif data.startswith("add_source_sp:") or data.startswith("rem_source_sp:"):
        action, s_id = data.split(":")[0], data.split(":")[1]
        if action == "add_source_sp":
            s_name = data.split(":")[2] if len(data.split(":")) > 2 else "Channel"
            bot_db[uid]['source_dict'][str(s_id)] = s_name
        else:
            bot_db[uid]['source_dict'].pop(str(s_id), None)
            
        save_bot_data()
        src_msg = "✅ **Selected Source Channels:**\n"
        src_buttons = []
        for sid, sname in bot_db[uid]['source_dict'].items():
            src_msg += f"• `{sname}`\n"
            src_buttons.append([Button.inline(f"❌ Remove {sname}", f"rem_source_sp:{sid}".encode())])
            
        if not bot_db[uid]['source_dict']: src_msg += "*(Koi source baki nahi hai)*\n"
        src_buttons.append([Button.inline("➕ Add Source", b"more_source_sp")])
        if bot_db[uid]['source_dict']: src_buttons.append([Button.inline("🎯 Done, Select Destination", b"done_sources_sp")])
        src_buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
        await event.respond(src_msg, buttons=src_buttons)

    elif data == "more_source_sp":
        user_states[user_id] = {'state': 'SELECT_SOURCES_SP'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_source_sp", pinned_only=True)
        buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
        await event.respond("🎯 Agla **PINNED Source Channel** select karein:", buttons=buttons)

    elif data == "done_sources_sp":
        user_states[user_id] = {'state': 'SELECT_DEST_SP'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_dest_sp", require_admin=True)
        buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
        await event.respond("🎯 **Sources Saved!**\n\nAb **Destination Channel** select karein:", buttons=buttons)

    elif data.startswith("add_dest_sp:") or data.startswith("rem_dest_sp:"):
        action, d_id = data.split(":")[0], data.split(":")[1]
        if action.startswith("add_"):
            d_name = data.split(":")[2] if len(data.split(":")) > 2 else "Channel"
            bot_db[uid]['dest_dict'][str(d_id)] = d_name
        else:
            bot_db[uid]['dest_dict'].pop(str(d_id), None)
            
        save_bot_data()
        dest_msg = "✅ **Selected Destination Channels:**\n"
        dest_buttons = []
        for did, dname in bot_db[uid]['dest_dict'].items():
            dest_msg += f"• `{dname}`\n"
            dest_buttons.append([Button.inline(f"❌ Remove {dname}", f"rem_dest_sp:{did}".encode())])
            
        if not bot_db[uid]['dest_dict']: dest_msg += "*(Koi destination baki nahi hai)*\n"
        dest_buttons.append([Button.inline("➕ Add Destination", b"more_dest_sp")])
        if bot_db[uid]['dest_dict']: dest_buttons.append([Button.inline("🚀 Select Line Setting", b"ask_lines_special")])
        dest_buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
        await event.respond(dest_msg, buttons=dest_buttons)

    elif data == "more_dest_sp":
        user_states[user_id] = {'state': 'SELECT_DEST_SP'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_dest_sp", require_admin=True)
        buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
        await event.respond("🎯 Agla **Destination Channel** select karein:", buttons=buttons)

    elif data == "ask_lines_special":
        await event.respond(
            "📏 **Special Code Mode - Line Settings:**\nAapko har code kitni lines me bhejna hai?",
            buttons=[
                [Button.inline("1 Line", b"run_special_1"), Button.inline("2 Lines", b"run_special_2")],
                [Button.inline("3 Lines", b"run_special_3"), Button.inline("4 Lines", b"run_special_4")],
                [Button.inline("🔙 Back", b"mode_special_start")]
            ]
        )

    # ADD / REMOVE NORMAL SOURCE
    elif data.startswith("add_source:") or data.startswith("rem_source:"):
        action, s_id = data.split(":")[0], data.split(":")[1]
        if action == "add_source":
            s_name = data.split(":")[2] if len(data.split(":")) > 2 else "Channel"
            bot_db[uid]['source_dict'][str(s_id)] = s_name
        else:
            bot_db[uid]['source_dict'].pop(str(s_id), None)
            
        save_bot_data()
        is_god = (bot_db[uid].get('setup_type') == 'god')
        
        src_msg = "✅ **Selected Source Channels:**\n"
        src_buttons = []
        for sid, sname in bot_db[uid]['source_dict'].items():
            src_msg += f"• `{sname}`\n"
            src_buttons.append([Button.inline(f"❌ Remove {sname}", f"rem_source:{sid}".encode())])
            
        if not bot_db[uid]['source_dict']: src_msg += "*(Koi source baki nahi hai)*\n"
        src_buttons.append([Button.inline("➕ Add Source", b"more_source")])
        if bot_db[uid]['source_dict']: src_buttons.append([Button.inline("🎯 Done, Select Destination", b"done_sources")])
        src_buttons.append([Button.inline("🔙 Back", b"mode_god_start" if is_god else b"back_to_mode")])
        await event.respond(src_msg, buttons=src_buttons)

    elif data == "more_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = user_data.get(user_id, {}).get('client')
        is_god = (bot_db[uid].get('setup_type') == 'god')
        buttons = await get_channel_buttons(client, "add_source", pinned_only=True)
        buttons.append([Button.inline("🔙 Back", b"god_mode_source" if is_god else b"mode_source")])
        await event.respond("🎯 Agla **PINNED Source Channel** select karein:", buttons=buttons)

    elif data == "done_sources":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = user_data.get(user_id, {}).get('client')
        is_god = (bot_db[uid].get('setup_type') == 'god')
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=True)
        buttons.append([Button.inline("🔙 Back", b"god_mode_source" if is_god else b"mode_source")])
        await event.respond("🎯 **Sources Saved!**\n\nAb **Destination Channel** select karein:", buttons=buttons)

    # ADD / REMOVE DESTINATION
    elif data.startswith("add_dest:") or data.startswith("add_destcust:") or data.startswith("rem_dest:"):
        action, d_id = data.split(":")[0], data.split(":")[1]
        if action.startswith("add_"):
            d_name = data.split(":")[2] if len(data.split(":")) > 2 else "Channel"
            bot_db[uid]['dest_dict'][str(d_id)] = d_name
        else:
            bot_db[uid]['dest_dict'].pop(str(d_id), None)
            
        save_bot_data()
        is_custom = bool(bot_db[uid].get('source_dict'))
        more_action = b"more_destcust" if is_custom else b"more_dest"
        is_god = (bot_db[uid].get('setup_type') == 'god')
        back_route = b"mode_god_start" if is_god else b"back_to_mode"
        
        dest_msg = "✅ **Selected Destination Channels:**\n"
        dest_buttons = []
        for did, dname in bot_db[uid]['dest_dict'].items():
            dest_msg += f"• `{dname}`\n"
            dest_buttons.append([Button.inline(f"❌ Remove {dname}", f"rem_dest:{did}".encode())])
            
        if not bot_db[uid]['dest_dict']: dest_msg += "*(Koi destination baki nahi hai)*\n"
        dest_buttons.append([Button.inline("➕ Add Destination", more_action)])
        
        if bot_db[uid]['dest_dict']: 
            if is_god:
                dest_buttons.append([Button.inline("🚀 Next: GOD MODE Settings", b"setup_god_mode")])
            else:
                dest_buttons.append([Button.inline("🚀 Select Forwarding Mode", b"select_fwd_mode")])
                
        dest_buttons.append([Button.inline("🔙 Back", back_route)])
        await event.respond(dest_msg, buttons=dest_buttons)

    elif data in ["more_dest", "more_destcust"]:
        is_custom = (data == "more_destcust")
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM' if is_custom else 'SELECT_DEST'}
        client = user_data.get(user_id, {}).get('client')
        is_god = (bot_db[uid].get('setup_type') == 'god')
        back_route = b"mode_god_start" if is_god else b"back_to_mode"
        
        buttons = await get_channel_buttons(client, "add_destcust" if is_custom else "add_dest", require_admin=True)
        buttons.append([Button.inline("🔙 Back", back_route)])
        await event.respond("🎯 Agla **Destination Channel** select karein:", buttons=buttons)

    # 🛠 FORWARDING MODE MENU
    elif data == "select_fwd_mode":
        await event.respond(
            "🛠 **Sniper Forwarding Mode:**\n\nAb choose karein format:\n"
            "1️⃣ **Rush Mode:** 1 msg me saare codes\n"
            "2️⃣ **Normal Mode:** Har Mono code ka alag msg\n"
            "3️⃣ **Link Forwarder:** Message se URLs in Mono",
            buttons=[
                [Button.inline("🚀 Start Rush Mode", b"run_rush_0")], 
                [Button.inline("🟢 Normal Mode", b"ask_lines_normal")],
                [Button.inline("🔗 Link Forwarder", b"ask_lines_link")],
                [Button.inline("🔙 Back", b"back_to_mode")]
            ]
        )

    elif data.startswith("ask_lines_"):
        mode = data.split("_")[2]
        await event.respond(
            f"📏 **{mode.capitalize()} Mode - Line Settings:**\nAapko har item kitni lines me bhejna hai?",
            buttons=[
                [Button.inline("1 Line", f"format_{mode}_1".encode()), Button.inline("2 Lines", f"format_{mode}_2".encode())],
                [Button.inline("3 Lines", f"format_{mode}_3".encode()), Button.inline("4 Lines", f"format_{mode}_4".encode())],
                [Button.inline("🔙 Back", b"select_fwd_mode")]
            ]
        )

    # ⏱️ AUTO-OVER TIMER SETUP MENU
    elif data.startswith("format_"):
        parts = data.split("_")
        mode_cache = parts[1]
        lines_cache = int(parts[2])
        
        bot_db[uid]['setup_mode_cache'] = mode_cache
        bot_db[uid]['setup_lines_cache'] = lines_cache
        save_bot_data()
        
        await event.respond(
            "⏱️ **Auto-Over Timer Setup:**\n\nKitne time baad message par OVER text likh kar aana chahiye?",
            buttons=[
                [Button.inline("⏳ 10 Seconds", b"timer_10"), Button.inline("⏳ 30 Seconds", b"timer_30")],
                [Button.inline("⏱️ 1 Minute", b"timer_60"), Button.inline("⏱️ 5 Minutes", b"timer_300")],
                [Button.inline("❌ No Timer", b"timer_0")],
                [Button.inline("🔙 Back", b"select_fwd_mode")]
            ]
        )

    elif data.startswith("timer_"):
        timer_val = int(data.split("_")[1])
        bot_db[uid]['over_timer'] = timer_val
        save_bot_data()
        
        header = bot_db[uid].get('custom_header')
        footer = bot_db[uid].get('custom_footer')
        over_text = bot_db[uid].get('over_text', "❌️❌️ OVER ❌️❌️")
        mode_cache = bot_db[uid].get('setup_mode_cache', 'normal')
        lines_cache = bot_db[uid].get('setup_lines_cache', 4)

        msg = f"📝 **{mode_cache.capitalize()} Mode Setup:**\n\n"
        msg += f"🔝 **Header:** `{header}`\n" if header else "🔝 **Header:** ❌ Not Set\n"
        msg += f"🔚 **Footer:** `{footer}`\n" if footer else "🔚 **Footer:** ❌ Not Set\n"
        msg += f"⏰ **Over Text:** `{over_text}`\n\n"
        
        btns = [
            [Button.inline("🔝 Set Header", b"ask_header"), Button.inline("🗑️ Remove Header", b"rem_header")],
            [Button.inline("🔚 Set Footer", b"ask_footer"), Button.inline("🗑️ Remove Footer", b"rem_footer")],
            [Button.inline("✏️ Set Custom Over Text", b"ask_over_text")],
            [Button.inline("🚀 Start Bot", f"run_{mode_cache}_{lines_cache}".encode())],
            [Button.inline("🔙 Cancel", b"select_fwd_mode")]
        ]
        
        await event.respond(msg, buttons=btns)

    elif data == "show_format_menu":
        header = bot_db[uid].get('custom_header')
        footer = bot_db[uid].get('custom_footer')
        over_text = bot_db[uid].get('over_text', "❌️❌️ OVER ❌️❌️")
        mode_cache = bot_db[uid].get('setup_mode_cache', 'normal')
        lines_cache = bot_db[uid].get('setup_lines_cache', 4)

        msg = f"📝 **{mode_cache.capitalize()} Mode Setup:**\n\n"
        msg += f"🔝 **Header:** `{header}`\n" if header else "🔝 **Header:** ❌ Not Set\n"
        msg += f"🔚 **Footer:** `{footer}`\n" if footer else "🔚 **Footer:** ❌ Not Set\n"
        msg += f"⏰ **Over Text:** `{over_text}`\n\n"
        
        btns = [
            [Button.inline("🔝 Set Header", b"ask_header"), Button.inline("🗑️ Remove Header", b"rem_header")],
            [Button.inline("🔚 Set Footer", b"ask_footer"), Button.inline("🗑️ Remove Footer", b"rem_footer")],
            [Button.inline("✏️ Set Custom Over Text", b"ask_over_text")],
            [Button.inline("🚀 Start Bot", f"run_{mode_cache}_{lines_cache}".encode())],
            [Button.inline("🔙 Cancel", b"select_fwd_mode")]
        ]
        
        await event.respond(msg, buttons=btns)

    elif data == "rem_header":
        bot_db[uid]['custom_header'] = None
        save_bot_data()
        await event.answer("Header Removed!", alert=True)
        await callback_handler(events.CallbackQuery.Event(data=b"show_format_menu", sender_id=user_id))
        
    elif data == "rem_footer":
        bot_db[uid]['custom_footer'] = None
        save_bot_data()
        await event.answer("Footer Removed!", alert=True)
        await callback_handler(events.CallbackQuery.Event(data=b"show_format_menu", sender_id=user_id))

    elif data == "ask_header":
        prompt_msg = await event.respond("🔝 **Send Custom Header:**\n\nJo text aapko message ke sabse upar likhna hai, wo type karke bhejein:", buttons=[[Button.inline("🔙 Cancel", b"show_format_menu")]])
        user_states[user_id] = {'state': 'WAITING_HEADER', 'prompt_id': prompt_msg.id}
        
    elif data == "ask_footer":
        prompt_msg = await event.respond("🔚 **Send Custom Footer:**\n\nJo text aapko message ke sabse niche likhna hai, wo type karke bhejein:", buttons=[[Button.inline("🔙 Cancel", b"show_format_menu")]])
        user_states[user_id] = {'state': 'WAITING_FOOTER', 'prompt_id': prompt_msg.id}

    elif data == "ask_over_text":
        prompt_msg = await event.respond("✏️ **Send Custom Over Text:**\n\nTimer khatam hone par jo text likh kar aana chahiye, wo bhejein:", buttons=[[Button.inline("🔙 Cancel", b"show_format_menu")]])
        user_states[user_id] = {'state': 'WAITING_OVER_TEXT', 'prompt_id': prompt_msg.id}

    # ⚡ GOD MODE DASHBOARD
    elif data == "setup_god_mode":
        link = bot_db[uid].get('replacer_link')
        uname = bot_db[uid].get('replacer_username')
        
        msg = "⚡ **GOD MODE Setup:**\n\nIs mode me messages exactly same format me copy honge (Auto-replies, Auto-Edit & Auto-Delete included).\n\n"
        link_str = f"`{link}`" if link else "❌ Not Set"
        uname_str = f"`{uname}`" if uname else "❌ Not Set"
        msg += f"🔗 **Private Link:** {link_str}\n👤 **@Username:** {uname_str}\n\n"
        
        btns = [
            [Button.inline("🔗 Change Link", b"ask_replacer_link"), Button.inline("🗑️ Remove Link", b"rem_replacer_link")],
            [Button.inline("👤 Change @Username", b"ask_replacer_username"), Button.inline("🗑️ Remove User", b"rem_replacer_username")],
            [Button.inline("🚀 Start GOD MODE", b"run_god_0")],
            [Button.inline("🔙 Cancel Setup", b"mode_god_start")]
        ]
        await event.respond(msg, buttons=btns)

    elif data == "rem_replacer_link":
        bot_db[uid]['replacer_link'] = None
        save_bot_data()
        await event.answer("Link Removed!", alert=True)
        await callback_handler(events.CallbackQuery.Event(data=b"setup_god_mode", sender_id=user_id))

    elif data == "rem_replacer_username":
        bot_db[uid]['replacer_username'] = None
        save_bot_data()
        await event.answer("Username Removed!", alert=True)
        await callback_handler(events.CallbackQuery.Event(data=b"setup_god_mode", sender_id=user_id))

    elif data == "ask_replacer_link":
        prompt_msg = await event.respond("🔗 **Send Custom Link:**\n\nKripya chat me apni wo Custom Link paste karke bhejein:", buttons=[[Button.inline("🔙 Cancel", b"setup_god_mode")]])
        user_states[user_id] = {'state': 'WAITING_CLONE_LINK', 'prompt_id': prompt_msg.id}

    elif data == "ask_replacer_username":
        prompt_msg = await event.respond("👤 **Send Custom @Username:**\n\nKripya chat me apna `@username` bhejein:", buttons=[[Button.inline("🔙 Cancel", b"setup_god_mode")]])
        user_states[user_id] = {'state': 'WAITING_CLONE_USERNAME', 'prompt_id': prompt_msg.id}

    # START RUN
    elif data.startswith("run_"):
        parts = data.split("_")
        sniper_mode, lines_count = parts[1], int(parts[2])
        client = user_data.get(user_id, {}).get('client')
        
        dest_list = list(bot_db[uid]['dest_dict'].keys())
        src_keys = list(bot_db[uid]['source_dict'].keys())
        source_list = [int(s) for s in src_keys] if src_keys else None
            
        mode_disp = "🔐 Special Code" if sniper_mode == "special" else "⚡ GOD" if sniper_mode == "god" else sniper_mode.capitalize()
        await event.respond(f"🚀 **Sniper Bot Start ho raha hai [{mode_disp} Mode]...**")
        await start_sniper_for_user(user_id, client, dest_list, "User", source_list, sniper_mode, lines_count)

# --- 💬 TEXT HANDLER ---
@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip()
    if text.startswith('/'): return
    uid = str(user_id)
    state = user_states.get(user_id)

    # 👑 ADMIN TEXT
    if user_id == MASTER_ID:
        if state == 'WAITING_BROADCAST':
            msg_count = 0
            for u_id in license_db["users"].keys():
                try:
                    await master_bot.send_message(int(u_id), f"📢 **Admin Message:**\n\n{text}")
                    msg_count += 1
                except: pass
            user_states[user_id] = None
            await event.reply(f"✅ **Broadcast Successful!**\nSent to {msg_count} users.", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif state == 'WAITING_BAN_ID':
            if text in license_db["users"]:
                del license_db["users"][text]
                save_licenses(license_db)
                if int(text) in active_snipers_dict: active_snipers_dict[int(text)].is_running = False
                user_states[user_id] = None
                await event.reply(f"✅ User `{text}` BAN!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            else: await event.reply("❌ User not found.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif state == 'WAITING_UNBAN_ID':
            found_key, key_info = None, None
            for k, info in license_db["keys"].items():
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
            except: await event.reply("⚠️ Format Error! (Ex: `1 12h`)", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

    # 🔐 SPECIAL KEY VERIFICATION
    if state == 'WAITING_SPECIAL_KEY':
        if text in license_db["special_keys"]:
            sk_info = license_db["special_keys"][text]
            if sk_info["used_by"] and sk_info["used_by"] != user_id:
                await event.reply("❌ Ye Special Key pehle hi kisi aur dwara use ki ja chuki hai!")
                return
            license_db["special_keys"][text]["used_by"] = user_id
            license_db["special_users"][str(user_id)] = {"key": text, "expires": sk_info["expires"]}
            save_licenses(license_db)
            user_states[user_id] = None
            try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
            except: pass
            await event.respond(
                "✅ **Special Key Verified Successfully!**\n🔐 Ab aap Special Code Mode use kar sakte hain.",
                buttons=[[Button.inline("🔐 Open Special Code Setup", b"mode_special_start")]]
            )
            return
        else:
            await event.reply("❌ **Invalid Special Key!** Sahi key enter karein.")
            return

    # 💾 PRESET NAME SAVER
    if isinstance(state, dict) and state.get('state') == 'WAITING_PRESET_NAME':
        pname = text
        if "presets" not in bot_db[uid]: bot_db[uid]['presets'] = {}
        
        bot_db[uid]['presets'][pname] = {
            'dest_dict': bot_db[uid].get('dest_dict', {}),
            'source_dict': bot_db[uid].get('source_dict', {}),
            'sniper_mode': bot_db[uid].get('sniper_mode', 'rush'),
            'lines_count': bot_db[uid].get('lines_count', 4),
            'replacer_link': bot_db[uid].get('replacer_link'),
            'replacer_username': bot_db[uid].get('replacer_username'),
            'custom_header': bot_db[uid].get('custom_header'),
            'custom_footer': bot_db[uid].get('custom_footer'),
            'over_timer': bot_db[uid].get('over_timer', 0),
            'over_text': bot_db[uid].get('over_text', "❌️❌️ OVER ❌️❌️")
        }
        save_bot_data()
        try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
        except: pass
        user_states[user_id] = None
        await event.respond(f"✅ **Preset '{pname}' Saved Successfully!**", buttons=[[Button.inline("📂 View Presets", b"list_presets"), Button.inline("🔙 Back", b"back_to_mode")]])
        return

    # 🔍 TEXT SEARCH FOR CHANNELS
    if isinstance(state, dict) and state.get('state') in ['SELECT_SOURCES', 'SELECT_DEST', 'SELECT_DEST_CUSTOM', 'SELECT_SOURCES_SP', 'SELECT_DEST_SP']:
        client = user_data.get(user_id, {}).get('client')
        if not client: return
        query = text.lower()
        st = state.get('state')
        
        if st == 'SELECT_SOURCES_SP': action_prefix = "add_source_sp"
        elif st == 'SELECT_DEST_SP': action_prefix = "add_dest_sp"
        elif st == 'SELECT_DEST_CUSTOM': action_prefix = "add_destcust"
        elif st == 'SELECT_DEST': action_prefix = "add_dest"
        else: action_prefix = "add_source"
        
        require_admin = st in ['SELECT_DEST', 'SELECT_DEST_CUSTOM', 'SELECT_DEST_SP']
        
        try: await event.delete()
        except: pass
        try:
            dialogs = await client.get_dialogs(limit=1000)
            buttons = []
            for d in dialogs:
                if d.is_channel or d.is_group:
                    if require_admin and not (getattr(d.entity, 'creator', False) or getattr(d.entity, 'admin_rights', None)): continue
                    name = d.name if d.name else "Unnamed"
                    uname = getattr(d.entity, 'username', '') or ''
                    if query in name.lower() or query in uname.lower():
                        buttons.append([Button.inline(name[:20], data=f"{action_prefix}:{d.id}:{name[:15]}")])
                        if len(buttons) >= 15: break
            
            if buttons:
                back_rt = b"mode_special_start" if 'SP' in st else b"back_to_mode"
                buttons.append([Button.inline("🔙 Back", back_rt)])
                await event.respond(f"🔍 **Search Results for '{text}':**\nSelect your channel below:", buttons=buttons)
            else:
                await event.respond(f"❌ Koi channel nahi mila '{text}' ke naam se. Kripya sahi spelling ya @username bhejein.")
        except Exception as e: pass
        return

    # 📝 CUSTOM HEADER / FOOTER / OVER TEXT SAVER
    if isinstance(state, dict) and state.get('state') in ['WAITING_HEADER', 'WAITING_FOOTER', 'WAITING_OVER_TEXT']:
        st = state.get('state')
        if st == 'WAITING_HEADER':
            bot_db[uid]['custom_header'] = text
            success_txt = "✅ **Header Saved Successfully!**"
        elif st == 'WAITING_FOOTER':
            bot_db[uid]['custom_footer'] = text
            success_txt = "✅ **Footer Saved Successfully!**"
        else:
            bot_db[uid]['over_text'] = text
            success_txt = "✅ **Over Text Saved Successfully!**"
            
        save_bot_data()
        try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
        except: pass
        user_states[user_id] = None
        
        header = bot_db[uid].get('custom_header')
        footer = bot_db[uid].get('custom_footer')
        over_text = bot_db[uid].get('over_text', "❌️❌️ OVER ❌️❌️")
        mode_cache = bot_db[uid].get('setup_mode_cache', 'normal')
        lines_cache = bot_db[uid].get('setup_lines_cache', 4)

        msg = f"📝 **{mode_cache.capitalize()} Mode Setup:**\n\n"
        msg += f"🔝 **Header:** `{header}`\n" if header else "🔝 **Header:** ❌ Not Set\n"
        msg += f"🔚 **Footer:** `{footer}`\n" if footer else "🔚 **Footer:** ❌ Not Set\n"
        msg += f"⏰ **Over Text:** `{over_text}`\n\n"
        
        btns = [
            [Button.inline("🔝 Set Header", b"ask_header"), Button.inline("🗑️ Remove Header", b"rem_header")],
            [Button.inline("🔚 Set Footer", b"ask_footer"), Button.inline("🗑️ Remove Footer", b"rem_footer")],
            [Button.inline("✏️ Set Custom Over Text", b"ask_over_text")],
            [Button.inline("🚀 Start Bot", f"run_{mode_cache}_{lines_cache}".encode())],
            [Button.inline("🔙 Cancel", b"select_fwd_mode")]
        ]
        await event.respond(f"{success_txt}\n\n{msg}", buttons=btns)
        return

    # 🔗 CUSTOM LINK/USERNAME SAVER (GOD MODE)
    if isinstance(state, dict) and state.get('state') in ['WAITING_CLONE_LINK', 'WAITING_CLONE_USERNAME']:
        is_link = state.get('state') == 'WAITING_CLONE_LINK'
        if is_link:
            bot_db[uid]['replacer_link'] = text
            success_txt = "✅ **Link Saved Successfully!**"
        else:
            if not text.startswith('@'): text = '@' + text
            bot_db[uid]['replacer_username'] = text
            success_txt = "✅ **Username Saved Successfully!**"
            
        save_bot_data()
        try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
        except: pass
        user_states[user_id] = None
        
        link = bot_db[uid].get('replacer_link')
        uname = bot_db[uid].get('replacer_username')
        
        msg = "⚡ **GOD MODE Setup:**\n\nIs mode me messages exactly same format me copy honge (Auto-replies, Auto-Edit & Auto-Delete included).\n\n"
        msg += f"🔗 **Private Link:** {link if link else '❌ Not Set'}\n👤 **@Username:** {uname if uname else '❌ Not Set'}\n\n"
        
        btns = [
            [Button.inline("🔗 Change Link", b"ask_replacer_link"), Button.inline("🗑️ Remove Link", b"rem_replacer_link")],
            [Button.inline("👤 Change @Username", b"ask_replacer_username"), Button.inline("🗑️ Remove User", b"rem_replacer_username")],
            [Button.inline("🚀 Start GOD MODE", b"run_god_0")],
            [Button.inline("🔙 Cancel Setup", b"mode_god_start")]
        ]
        await event.respond(f"{success_txt}\n\n{msg}", buttons=btns)
        return

    # LOGIN LOGIC
    if state == 'WAITING_KEY':
        if text in license_db["keys"]:
            k_info = license_db["keys"][text]
            if k_info["used_by"] and k_info["used_by"] != user_id:
                await event.reply("❌ Ye key use ho chuki hai!")
                return
            license_db["keys"][text]["used_by"] = user_id
            license_db["users"][str(user_id)] = {"name": event.sender.first_name, "key": text, "expires": k_info["expires"]}
            save_licenses(license_db)
            
            client = user_data.get(user_id, {}).get('client')
            if not client:
                client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
                await client.connect()
                
            if await client.is_user_authorized():
                if user_id not in user_data: user_data[user_id] = {}
                user_data[user_id]['client'] = client
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply("✅ **Key Verified!**\n🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))
            else:
                if user_id not in user_data: user_data[user_id] = {}
                user_data[user_id]['client'] = client
                user_states[user_id] = 'WAITING_PHONE'
                await event.reply("✅ **Key Verified!**\n📱 Apna **Telegram Phone Number** bhejein:")
        else: await event.reply("❌ **Invalid Key!**")

    elif state in ['WAITING_PHONE']:
        user_states[user_id] = {'state': 'WAITING_OTP', 'phone': text}
        await event.reply("🔄 OTP bhej rahe hain...")
        try:
            client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(text)
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id].update({'client': client, 'phone_code_hash': sent.phone_code_hash})
        except FloodWaitError as e:
            await event.reply(f"⚠️ FloodWait: {e.seconds}s baad try karein.")
            user_states[user_id] = None
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        try:
            await user_data[user_id]['client'].sign_in(phone=state['phone'], code=text, phone_code_hash=user_data[user_id]['phone_code_hash'])
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Login Successful!\n🎯 Ab Target Mode select karein:", buttons=get_mode_buttons(user_id))
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'WAITING_PASSWORD'}
            await event.reply("🔒 2-Step Verification Password bhejein:")
        except Exception as e:
            await event.reply(f"❌ OTP Error: {e}")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_PASSWORD':
        try:
            await user_data[user_id]['client'].sign_in(password=text)
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Password Verified!\n🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))
        except Exception as e:
            await event.reply(f"❌ Password Error: {e}")
            user_states[user_id] = None

print("👑 Master Bot Initialized Successfully!")
master_bot.start(bot_token=BOT_TOKEN)
master_bot.loop.create_task(auto_resume_snipers())
master_bot.run_until_disconnected()
