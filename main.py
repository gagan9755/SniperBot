import asyncio
import time
import re
from collections import deque
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, Button
from telethon.tl.types import MessageEntityCode, MessageEntityPre
from telethon.errors import SessionPasswordNeededError, FloodWaitError
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
user_data = {}  # Only for temporary auth states (clients)
active_snipers_dict = {}

# --- 🔐 DATABASES (Licenses & Persistent Bot Data) ---
LICENSE_FILE = "licenses.json"
BOT_DATA_FILE = "bot_data.json"

def load_licenses():
    try:
        with open(LICENSE_FILE, 'r') as f:
            data = json.load(f)
            if "settings" not in data: data["settings"] = {"official_channel": ""}
            return data
    except FileNotFoundError:
        return {"keys": {}, "users": {}, "settings": {"official_channel": ""}} 

def save_licenses(data):
    with open(LICENSE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

license_db = load_licenses()

# 🧠 DATA LOSS FIX: Persistent User DB
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

def is_user_authorized(user_id):
    return str(user_id) in license_db["users"]

def check_subscription(user_id):
    if not is_user_authorized(user_id): return False
    expires_str = license_db["users"][str(user_id)]["expires"]
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
def get_official_btn():
    link = license_db.get("settings", {}).get("official_channel", "")
    return [Button.url("📢 Join Official Channel", url=link)] if link else []

def get_mode_buttons():
    btns = [
        [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
        [Button.inline("🎯 Specific Source Channel", b"mode_source")]
    ]
    off_btn = get_official_btn()
    if off_btn: btns.append(off_btn)
    return btns

def get_control_buttons(validity_str):
    btns = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")],
        [Button.inline("📊 My Stats", b"ctl_stats")] # 📊 Stats Button Added
    ]
    off_btn = get_official_btn()
    if off_btn: btns.append(off_btn)
    return btns

def get_admin_buttons():
    return [
        [Button.inline("🔑 Gen 1 Key (30D)", b"adm_gen_1_30"), Button.inline("🔑 Gen 5 Keys (30D)", b"adm_gen_5_30")],
        [Button.inline("⚙️ Custom Key (Days/Hours)", b"adm_custom_key")],
        [Button.inline("👥 View Active Users", b"adm_users"), Button.inline("🔗 Set Official Channel", b"adm_set_channel")],
        [Button.inline("🚫 Ban User", b"adm_ban_prompt"), Button.inline("✅ Unban User", b"adm_unban_prompt")],
        [Button.inline("📢 Broadcast Message", b"adm_broadcast")] # 📢 Broadcast Button Added
    ]

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
            try: await master_bot.send_message(user_id, "⚠️ **Aapki License Key expire ho chuki hai!**\nBot automatic stop ho gaya hai. Kripya nayi key dalne ke liye /start dabayein.")
            except: pass
            return

        if sniper.is_paused or not sniper.destinations: return
            
        if sniper.source_chat_ids:
            if event.chat_id not in sniper.source_chat_ids: return
        else:
            if event.chat_id not in sniper.pinned_chats: return

        if event.id in sniper.processed_ids_set or not event.message.text: return

        extracted_items = []
        text_content = event.message.text

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
        
        if len(sniper.processed_ids_queue) == 50:
            sniper.processed_ids_set.discard(sniper.processed_ids_queue.popleft())
        sniper.processed_ids_queue.append(event.id)
        sniper.processed_ids_set.add(event.id)

        for item in extracted_items:
            if len(sniper.seen_codes_queue) == 100:
                sniper.seen_codes_set.discard(sniper.seen_codes_queue.popleft())
            sniper.seen_codes_queue.append(item)
            sniper.seen_codes_set.add(item)

        messages_to_send = []
        if sniper.sniper_mode == "rush":
            num = len(extracted_items)
            lines = [f"`{extracted_items[0]}`"] * 3 if num == 1 else [f"`{extracted_items[0]}`"] * 2 + [f"`{extracted_items[1]}`"] * 2 if num == 2 else [f"`{c}`" for c in extracted_items]
            messages_to_send.append("\n".join(lines))
        else:
            for c in extracted_items: messages_to_send.append("\n".join([f"`{c}`"] * sniper.lines_count))

        # Send and update Stats
        sent_count = 0
        for msg in messages_to_send:
            for d_id, target in sniper.destinations.items():
                try:
                    await client.send_message(target, msg, parse_mode='md')
                    sent_count += 1
                except: pass
        
        if sent_count > 0:
            bot_db[uid]['stats']['forwarded'] += len(extracted_items)
            save_bot_data()

    try:
        time_left = get_time_left(user_id)
        validity_str = format_time_left(time_left)
        mode_text = f"Multiple Sources ({len(source_chat_ids)})" if source_chat_ids else "Auto Pinned Chats"
        lines_info = f" ({sniper.lines_count} Lines)" if sniper.sniper_mode != "rush" else ""
        await master_bot.send_message(
            user_id, 
            f"✅ **SNIPER ACTIVE!** 🎯\n\n🟢 **Target Mode:** {mode_text}\n🛠 **Forwarding:** `{sniper.sniper_mode.capitalize()} Mode{lines_info}`\n🚀 **Destinations:** `{len(sniper.destinations)}`\n⏳ **Validity:** `{validity_str}`", 
            buttons=get_control_buttons(validity_str)
        )
    except: pass

# --- 🚀 AUTO RESUME ON RESTART ---
async def auto_resume_snipers():
    await asyncio.sleep(2)
    print("🔄 Checking for active snipers to resume...")
    for uid_str, data in bot_db.items():
        if data.get('is_running') and check_subscription(uid_str):
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
                    print(f"✅ Auto-resumed Sniper for {user_id}")
            except Exception as e:
                print(f"❌ Failed to resume {user_id}: {e}")

# --- 🚀 DIRECT CHANNEL BUTTONS GENERATOR ---
async def get_channel_buttons(client, action_type, require_admin=False, pinned_only=False):
    try:
        dialogs = await client.get_dialogs(limit=200)
        buttons = []
        for d in dialogs:
            if pinned_only and not d.pinned: continue
            if d.is_channel or d.is_group:
                if require_admin and not (getattr(d.entity, 'creator', False) or getattr(d.entity, 'admin_rights', None)): continue
                name = d.name[:25] if d.name else "Unnamed"
                buttons.append([Button.inline(name, data=f"{action_type}:{d.id}:{name}")])
                if len(buttons) >= 80: break
        return buttons
    except: return []

# --- 💬 BOT CONVERSATION & LICENSE LOGIC ---
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
            if client and client.is_connected():
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply(f"✅ **Welcome Back!** (⏳ `{validity_str}`)\n\n🎯 Apne kaam ke liye **Target Mode** select karein:", buttons=get_mode_buttons())
            else:
                user_states[user_id] = 'WAITING_PHONE'
                await event.reply(f"✅ **Welcome Back!** (⏳ `{validity_str}`)\n\n📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")
            return
        else:
            user_states[user_id] = 'WAITING_KEY'
            off_btn = get_official_btn()
            await event.reply("⚠️ **Aapki purani Key Expire ho chuki hai!**\n\nKripya apni **Nayi License Key (PIN)** yahan bhejein:", buttons=[off_btn] if off_btn else None)
            return

    user_states[user_id] = 'WAITING_KEY'
    off_btn = get_official_btn()
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:", buttons=[off_btn] if off_btn else None)

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
    uid = str(user_id)
    init_user_db(user_id)

    # 👑 MASTER ADMIN ACTIONS
    if user_id == MASTER_ID:
        if data == "adm_gen_5_30":
            generated = [f"`{generate_key(days=30)}`" for _ in range(5)]
            await event.edit("✅ **5 New Keys Generated (30 Days Valid):**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return
        elif data == "adm_gen_1_30":
            key = generate_key(days=30)
            await event.edit(f"✅ **1 New Key Generated (30 Days Valid):**\n\n`{key}`", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return
        elif data == "adm_custom_key":
            user_states[user_id] = 'WAITING_CUSTOM_KEY'
            await event.edit("⚙️ **Custom Key Generation:**\n\nKripya message me count aur time bhejein (Example: `1 12h` ya `5 2d`)", buttons=[[Button.inline("🔙 Cancel & Back", b"adm_back")]])
            return
        elif data == "adm_users":
            msg = "👥 **Active Authorized Users:**\n\n"
            for u, info in license_db["users"].items():
                expires = datetime.fromisoformat(info['expires'])
                time_left = format_time_left(expires - datetime.now())
                msg += f"👤 `{info['name']}` (ID: `{u}`)\n   🔑 Key: `{info['key']}`\n   ⏳ Time Left: {time_left}\n\n"
            await event.edit(msg if license_db["users"] else "No active users!", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_set_channel":
            user_states[user_id] = 'WAITING_CHANNEL_LINK'
            await event.edit("🔗 **Official Channel Link Set Karein:**\n\nApne channel ka poora link ya username bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_broadcast": # 📢 BROADCAST BUTTON LOGIC
            user_states[user_id] = 'WAITING_BROADCAST'
            await event.edit("📢 **Broadcast Message:**\n\nJo message aap sabhi users ko bhejna chahte hain, wo type karke yahan bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_ban_prompt":
            user_states[user_id] = 'WAITING_BAN_ID'
            await event.edit("🚫 Jis user ko **BAN** karna hai, uski User ID bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_unban_prompt":
            user_states[user_id] = 'WAITING_UNBAN_ID'
            await event.edit("✅ Jis user ko **UNBAN** karna hai, uski User ID bhejein:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_back":
            user_states[user_id] = None
            await event.edit("👑 **MASTER ADMIN CONTROL PANEL** 👑", buttons=get_admin_buttons())
            return

    # User Control Panel Actions
    if data == "ctl_pause":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = True
        bot_db[uid]['is_paused'] = True
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.edit(f"🟡 **BOT IS PAUSED (OFF)**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    
    elif data == "ctl_run":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = False
        bot_db[uid]['is_paused'] = False
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.edit(f"🟢 **BOT IS ON**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    
    elif data == "ctl_mykey":
        if is_user_authorized(user_id):
            info = license_db["users"][str(user_id)]
            await event.answer(f"🔑 Key: {info['key']} | ⏳ Left: {format_time_left(get_time_left(user_id))}", alert=True)
            
    elif data == "ctl_stats": # 📊 STATS INLINE BUTTON LOGIC
        fwd_count = bot_db[uid].get('stats', {}).get('forwarded', 0)
        await event.answer(f"📊 Aapke bot ne ab tak {fwd_count} codes successfully forward kiye hain!", alert=True)
        
    elif data == "ctl_restart":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_running = False
            del active_snipers_dict[user_id]
        bot_db[uid]['is_running'] = False
        save_bot_data()
        user_states[user_id] = 'CHOOSE_MODE'
        await event.edit(f"🔄 **Setup Restarted!**\n\n🎯 Apne kaam ke liye **Target Mode** select karein:", buttons=get_mode_buttons())

    elif data == "back_to_mode":
        user_states[user_id] = 'CHOOSE_MODE'
        await event.edit(f"🎯 Apne kaam ke liye **Target Mode** select karein:", buttons=get_mode_buttons())

    # 🎯 PINNED MODE
    elif data == "mode_pinned":
        user_states[user_id] = {'state': 'SELECT_DEST'}
        bot_db[uid]['source_dict'] = {} # Clear sources for pinned
        save_bot_data()
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            buttons = await get_channel_buttons(client, "add_dest", require_admin=True)
            buttons.append([Button.inline("🔙 Back", b"back_to_mode")])
            await event.edit("📌 **Pinned Mode:**\n🎯 Apna Destination select karein:", buttons=buttons)
        else: await event.edit("📱 Pehle apna Telegram Phone Number bhejein:")

    # 🎯 SOURCE MODE
    elif data == "mode_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            buttons = await get_channel_buttons(client, "add_source", pinned_only=True)
            buttons.append([Button.inline("🔙 Back", b"back_to_mode")])
            await event.edit("🎯 **Specific Source Mode:**\n📥 Apna Source select karein:", buttons=buttons)
        else: await event.edit("📱 Pehle apna Telegram Phone Number bhejein:")

    # ADD / REMOVE SOURCE
    elif data.startswith("add_source:") or data.startswith("rem_source:"):
        action, s_id = data.split(":")[0], data.split(":")[1]
        
        if action == "add_source":
            s_name = data.split(":")[2] if len(data.split(":")) > 2 else "Channel"
            bot_db[uid]['source_dict'][str(s_id)] = s_name
        else:
            bot_db[uid]['source_dict'].pop(str(s_id), None)
            
        save_bot_data()
        src_msg = "✅ **Selected Source Channels:**\n"
        src_buttons = []
        for sid, sname in bot_db[uid]['source_dict'].items():
            src_msg += f"• `{sname}`\n"
            src_buttons.append([Button.inline(f"❌ Remove {sname}", f"rem_source:{sid}".encode())])
            
        if not bot_db[uid]['source_dict']: src_msg += "*(Koi source baki nahi hai)*\n"
        src_buttons.append([Button.inline("➕ Add Source", b"more_source")])
        if bot_db[uid]['source_dict']: src_buttons.append([Button.inline("🎯 Done, Select Destination", b"done_sources")])
        src_buttons.append([Button.inline("🔙 Back", b"back_to_mode")])
        
        await event.edit(src_msg, buttons=src_buttons)

    elif data == "more_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_source", pinned_only=True)
        buttons.append([Button.inline("🔙 Back", b"mode_source")])
        await event.edit("🎯 Agla **PINNED Source Channel** select karein:", buttons=buttons)

    elif data == "done_sources":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=True)
        buttons.append([Button.inline("🔙 Back", b"mode_source")])
        await event.edit("🎯 **Sources Saved!**\n\nAb **Destination Channel** select karein:", buttons=buttons)

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
        
        dest_msg = "✅ **Selected Destination Channels:**\n"
        dest_buttons = []
        for did, dname in bot_db[uid]['dest_dict'].items():
            dest_msg += f"• `{dname}`\n"
            dest_buttons.append([Button.inline(f"❌ Remove {dname}", f"rem_dest:{did}".encode())])
            
        if not bot_db[uid]['dest_dict']: dest_msg += "*(Koi destination baki nahi hai)*\n"
        dest_buttons.append([Button.inline("➕ Add Destination", more_action)])
        if bot_db[uid]['dest_dict']: dest_buttons.append([Button.inline("🚀 Select Forwarding Mode", b"select_fwd_mode")])
        dest_buttons.append([Button.inline("🔙 Back", b"back_to_mode")])
        
        await event.edit(dest_msg, buttons=dest_buttons)

    elif data in ["more_dest", "more_destcust"]:
        is_custom = (data == "more_destcust")
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM' if is_custom else 'SELECT_DEST'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_destcust" if is_custom else "add_dest", require_admin=True)
        buttons.append([Button.inline("🔙 Back", b"back_to_mode")])
        await event.edit("🎯 Agla **Destination Channel** select karein:", buttons=buttons)

    # 🛠 FORWARDING MODE SELECTION
    elif data == "select_fwd_mode":
        await event.edit(
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
        await event.edit(
            f"📏 **{mode.capitalize()} Mode - Line Settings:**\nAapko har item kitni lines me bhejna hai?",
            buttons=[
                [Button.inline("1 Line", f"run_{mode}_1".encode()), Button.inline("2 Lines", f"run_{mode}_2".encode())],
                [Button.inline("3 Lines", f"run_{mode}_3".encode()), Button.inline("4 Lines", f"run_{mode}_4".encode())],
                [Button.inline("🔙 Back", b"select_fwd_mode")]
            ]
        )

    elif data.startswith("run_"):
        parts = data.split("_")
        sniper_mode, lines_count = parts[1], int(parts[2])
        client = user_data.get(user_id, {}).get('client')
        
        dest_list = list(bot_db[uid]['dest_dict'].keys())
        src_keys = list(bot_db[uid]['source_dict'].keys())
        source_list = [int(s) for s in src_keys] if src_keys else None
            
        await event.edit(f"🚀 **Sniper Bot Start ho raha hai [{sniper_mode.capitalize()}]...**")
        await start_sniper_for_user(user_id, client, dest_list, "User", source_list, sniper_mode, lines_count)

@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip()
    if text.startswith('/'): return

    # 👑 MASTER ADMIN TEXT HANDLING
    if user_id == MASTER_ID:
        state = user_states.get(user_id)
        
        if state == 'WAITING_BROADCAST':
            msg_count = 0
            for u_id in license_db["users"].keys():
                try:
                    await master_bot.send_message(int(u_id), f"📢 **Admin Message:**\n\n{text}")
                    msg_count += 1
                except: pass
            user_states[user_id] = None
            await event.reply(f"✅ **Broadcast Successful!**\nYe message {msg_count} users ko bhej diya gaya hai.", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return

        elif state == 'WAITING_BAN_ID':
            if text in license_db["users"]:
                del license_db["users"][text]
                save_licenses(license_db)
                if int(text) in active_snipers_dict: active_snipers_dict[int(text)].is_running = False
                user_states[user_id] = None
                await event.reply(f"✅ User `{text}` successfully BAN!", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            else: await event.reply("❌ Ye user list me nahi mila.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
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
                await event.reply(f"✅ User `{text}` successfully UNBAN!", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            else: await event.reply("❌ Is user ki purani key nahi mili.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

        elif state == 'WAITING_CHANNEL_LINK':
            link = f"https://t.me/{text[1:]}" if text.startswith('@') else f"https://{text}" if text.startswith('t.me/') else text
            license_db["settings"]["official_channel"] = link
            save_licenses(license_db)
            user_states[user_id] = None
            await event.reply(f"✅ Official Channel button update ho gaya hai!", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return

        elif state == 'WAITING_CUSTOM_KEY':
            try:
                parts = text.lower().split()
                count, time_str = int(parts[0]), parts[1]
                hours = int(time_str[:-1]) if time_str.endswith('h') else 0
                days = int(time_str[:-1]) if time_str.endswith('d') else int(time_str) if not hours else 0
                generated = [f"`{generate_key(days=days, hours=hours)}`" for _ in range(count)]
                user_states[user_id] = None
                await event.reply(f"✅ **{count} New Keys Generated:**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            except: await event.reply("⚠️ Galat format! (Ex: `1 12h` ya `5 2d`)", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

    # 👤 USER TEXT HANDLING (LOGIN)
    state = user_states.get(user_id)

    if state == 'WAITING_KEY':
        if text in license_db["keys"]:
            k_info = license_db["keys"][text]
            if k_info["used_by"] and k_info["used_by"] != user_id:
                await event.reply("❌ Ye key kisi aur dwara use ho chuki hai!")
                return
            license_db["keys"][text]["used_by"] = user_id
            license_db["users"][str(user_id)] = {"name": event.sender.first_name, "key": text, "expires": k_info["expires"]}
            save_licenses(license_db)
            
            if user_data.get(user_id, {}).get('client', TelegramClient(None,None,None)).is_connected():
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply("✅ **Key Verified!**\n🎯 Target Mode select karein:", buttons=get_mode_buttons())
            else:
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
            await event.reply(f"⚠️ Telegram FloodWait: {e.seconds} seconds baad try karein.")
            user_states[user_id] = None
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        try:
            await user_data[user_id]['client'].sign_in(phone=state['phone'], code=text, phone_code_hash=user_data[user_id]['phone_code_hash'])
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Login Successful!\n🎯 Ab Target Mode select karein:", buttons=get_mode_buttons())
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'WAITING_PASSWORD'}
            await event.reply("🔒 2-Step Verification Password bhejein:")
        except Exception as e:
            await event.reply(f"❌ OTP Galat: {e}")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_PASSWORD':
        try:
            await user_data[user_id]['client'].sign_in(password=text)
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Password Verified!\n🎯 Target Mode select karein:", buttons=get_mode_buttons())
        except Exception as e:
            await event.reply(f"❌ Password galat: {e}")
            user_states[user_id] = None

print("👑 Master Bot Initialized Successfully!")
master_bot.start(bot_token=BOT_TOKEN)

# START AUTO RESUME BACKGROUND TASK
master_bot.loop.create_task(auto_resume_snipers())

master_bot.run_until_disconnected()
