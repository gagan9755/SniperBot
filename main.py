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

# --- 🌐 KEEP-ALIVE SERVER ---
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

MASTER_ID = 8845438009  

master_bot = TelegramClient('master_bot_session', API_ID, API_HASH)

# Databases
user_states = {}
user_data = {}
active_snipers_dict = {}

# --- 🔐 ADVANCED SECURE LICENSE SYSTEM ---
LICENSE_FILE = "licenses.json"

def load_licenses():
    try:
        with open(LICENSE_FILE, 'r') as f:
            data = json.load(f)
            if "settings" not in data:
                data["settings"] = {"official_channel": ""}
            return data
    except FileNotFoundError:
        return {"keys": {}, "users": {}, "settings": {"official_channel": ""}} 

def save_licenses(data):
    with open(LICENSE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

license_db = load_licenses()

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
    expires_dt = datetime.fromisoformat(expires_str)
    return datetime.now() < expires_dt

def get_time_left(user_id):
    if not is_user_authorized(user_id): return None
    expires_str = license_db["users"][str(user_id)]["expires"]
    expires_dt = datetime.fromisoformat(expires_str)
    return expires_dt - datetime.now()

def format_time_left(td):
    if not td: return "Expired"
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0: return "Expired"
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    if days > 0:
        return f"{days} Days"
    else:
        return f"{hours} Hours"

# --- 🧠 UI BUTTON HELPERS ---
def get_official_btn():
    link = license_db.get("settings", {}).get("official_channel", "")
    if link:
        return [Button.url("📢 Join Official Channel", url=link)]
    return []

def get_mode_buttons():
    btns = [
        [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
        [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
    ]
    off_btn = get_official_btn()
    if off_btn: btns.append(off_btn)
    return btns

def get_control_buttons(validity_str):
    btns = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")]
    ]
    off_btn = get_official_btn()
    if off_btn: btns.append(off_btn)
    return btns

def get_admin_buttons():
    return [
        [Button.inline("🔑 Gen 1 Key (30D)", b"adm_gen_1_30"), Button.inline("🔑 Gen 5 Keys (30D)", b"adm_gen_5_30")],
        [Button.inline("⚙️ Custom Key (Days/Hours)", b"adm_custom_key")],
        [Button.inline("👥 View Active Users", b"adm_users"), Button.inline("🔗 Set Official Channel", b"adm_set_channel")],
        [Button.inline("🚫 Ban User", b"adm_ban_prompt"), Button.inline("✅ Unban User", b"adm_unban_prompt")]
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
        self.is_paused = False
        self.sniper_mode = sniper_mode 
        self.lines_count = lines_count 
        
        self.processed_ids_set = set()
        self.processed_ids_queue = deque(maxlen=50)
        self.seen_codes_set = set()
        self.seen_codes_queue = deque(maxlen=100)
        
    async def update_pinned_loop(self):
        if self.source_chat_ids:
            return
        while self.is_running:
            try:
                dialogs = await self.client.get_dialogs(limit=30)
                self.pinned_chats = {d.id for d in dialogs if d.pinned and d.id not in self.destinations}
            except Exception as e:
                pass
            await asyncio.sleep(60)

async def fast_send(client, target_entity, final_msg, start_time, user_id):
    try:
        await client.send_message(target_entity, final_msg, parse_mode='md')
        print(f"⚡ BOOM! User {user_id} | Latency: {time.time() - start_time:.4f}s")
    except Exception as e:
        pass

async def start_sniper_for_user(user_id, client, dest_chats, name, source_chat_ids=None, sniper_mode="rush", lines_count=4):
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_running = False

    sniper = UserSniper(user_id, client, name, source_chat_ids, sniper_mode, lines_count)
    
    for d_chat in dest_chats:
        try:
            target_entity = await client.get_entity(d_chat)
            sniper.destinations[d_chat] = target_entity
        except Exception as e:
            pass

    if not sniper.destinations:
        await master_bot.send_message(user_id, f"❌ Error: Koi bhi valid destination channel nahi mila.")
        return

    active_snipers_dict[user_id] = sniper
    asyncio.create_task(sniper.update_pinned_loop())

    @client.on(events.NewMessage())
    async def handler(event):
        if not sniper.is_running:
            client.remove_event_handler(handler)
            return

        # 🚨 STRICT BACKGROUND EXPIRY CHECK 🚨
        if not check_subscription(user_id):
            sniper.is_running = False
            client.remove_event_handler(handler)
            if user_id in active_snipers_dict:
                del active_snipers_dict[user_id]
            try:
                await master_bot.send_message(user_id, "⚠️ **Aapki License Key expire ho chuki hai!**\nBot automatic stop ho gaya hai. Kripya nayi key dalne ke liye /start dabayein.")
            except:
                pass
            return

        if sniper.is_paused or not sniper.destinations:
            return
            
        if sniper.source_chat_ids:
            if event.chat_id not in sniper.source_chat_ids:
                return
        else:
            if event.chat_id not in sniper.pinned_chats:
                return

        if event.id in sniper.processed_ids_set or not event.message.text:
            return

        extracted_items = []
        text_content = event.message.text

        # 🧠 MODE EXTRACTION LOGIC 🧠
        if sniper.sniper_mode == "link":
            link_pattern = r'(?:\b|https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?(?:#[^\s]*)?'
            found_links = re.findall(link_pattern, text_content)
            
            for ent, ent_text in event.message.get_entities_text():
                if isinstance(ent, (types.MessageEntityUrl, types.MessageEntityTextUrl)):
                    if ent_text not in found_links:
                        found_links.append(ent_text)
                        
            for l in found_links:
                if l not in sniper.seen_codes_set and l not in extracted_items:
                    extracted_items.append(l)
                    
        else:
            for ent, ent_text in event.message.get_entities_text():
                if isinstance(ent, (MessageEntityCode, MessageEntityPre)):
                    # Ignore Telegram links
                    if "t.me/" in ent_text.lower() or "telegram.me/" in ent_text.lower():
                        continue
                    if ent_text not in sniper.seen_codes_set and ent_text not in extracted_items:
                        extracted_items.append(ent_text)

        if not extracted_items: return
        start_time = time.time()
        
        if len(sniper.processed_ids_queue) == 50:
            old_id = sniper.processed_ids_queue.popleft()
            sniper.processed_ids_set.discard(old_id)
        sniper.processed_ids_queue.append(event.id)
        sniper.processed_ids_set.add(event.id)

        for item in extracted_items:
            if len(sniper.seen_codes_queue) == 100:
                old_code = sniper.seen_codes_queue.popleft()
                sniper.seen_codes_set.discard(old_code)
            sniper.seen_codes_queue.append(item)
            sniper.seen_codes_set.add(item)

        messages_to_send = []
        
        # 🎨 FORMATTING & LINE SELECTION LOGIC 🎨
        if sniper.sniper_mode == "rush":
            num = len(extracted_items)
            lines = []
            if num == 1:
                lines = [f"`{extracted_items[0]}`"] * 3
            elif num == 2:
                lines = [f"`{extracted_items[0]}`", f"`{extracted_items[0]}`", f"`{extracted_items[1]}`", f"`{extracted_items[1]}`"]
            else:
                lines = [f"`{c}`" for c in extracted_items]
            messages_to_send.append("\n".join(lines))
            
        elif sniper.sniper_mode == "normal":
            for c in extracted_items:
                messages_to_send.append("\n".join([f"`{c}`"] * sniper.lines_count))
                
        elif sniper.sniper_mode == "link":
            for l in extracted_items:
                messages_to_send.append("\n".join([f"`{l}`"] * sniper.lines_count))

        # Send messages to destinations
        for msg in messages_to_send:
            for d_id, target in sniper.destinations.items():
                asyncio.create_task(fast_send(client, target, msg, start_time, user_id))

    time_left = get_time_left(user_id)
    validity_str = format_time_left(time_left)
    mode_text = f"Multiple Sources ({len(source_chat_ids)})" if source_chat_ids else "Auto Pinned Chats"
    f_mode_name = sniper.sniper_mode.capitalize()
    lines_info = f" ({sniper.lines_count} Lines)" if sniper.sniper_mode != "rush" else ""
    
    await master_bot.send_message(
        user_id, 
        f"✅ **SNIPER ACTIVE!** 🎯\n\n"
        f"🟢 **Target Mode:** {mode_text}\n"
        f"🛠 **Forwarding:** `{f_mode_name} Mode{lines_info}`\n"
        f"🚀 **Destinations:** `{len(sniper.destinations)}`\n"
        f"⏳ **Validity:** `{validity_str}`", 
        buttons=get_control_buttons(validity_str)
    )

# --- 🚀 DIRECT CHANNEL BUTTONS GENERATOR ---
async def get_channel_buttons(client, action_type, require_admin=False, pinned_only=False):
    try:
        dialogs = await client.get_dialogs(limit=200)
        buttons = []
        for d in dialogs:
            if pinned_only and not d.pinned:
                continue
            if d.is_channel or d.is_group:
                if require_admin:
                    is_admin = False
                    if getattr(d.entity, 'creator', False): is_admin = True
                    elif getattr(d.entity, 'admin_rights', None): is_admin = True
                    if not is_admin: continue
                name = d.name[:25] if d.name else "Unnamed"
                buttons.append([Button.inline(name, data=f"{action_type}:{d.id}")])
                if len(buttons) >= 80: break
        return buttons
    except Exception as e:
        return []

async def search_and_send_channels(event, client, action_type, query=""):
    try:
        dialogs = await client.get_dialogs(limit=500)
        buttons = []
        for d in dialogs:
            if d.is_channel or d.is_group:
                name = d.name if d.name else "Unnamed"
                if not query or query.lower() in name.lower():
                    buttons.append([Button.inline(name[:28], data=f"{action_type}:{d.id}")])
                    if len(buttons) >= 15: break
        if not buttons:
            await event.respond(f"❌ '{query}' naam se koi channel nahi mila. Sahi naam likh kar dobara try karein.")
            return
        await event.respond(f"🔍 **Matching Channels:**\nNiche tap karke select karein:", buttons=buttons)
    except Exception as e:
        await event.respond(f"❌ Channels search error: {e}")

# --- 💬 BOT CONVERSATION & LICENSE LOGIC ---
@master_bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    
    if user_id == MASTER_ID:
        user_states[user_id] = None 
        await event.reply("👑 **MASTER ADMIN CONTROL PANEL** 👑\n\nApne kaam ke liye niche buttons me se select karein:", buttons=get_admin_buttons())
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
            buttons = [off_btn] if off_btn else None
            await event.reply("⚠️ **Aapki purani Key Expire ho chuki hai!**\n\nKripya apni **Nayi License Key (PIN)** yahan bhejein:", buttons=buttons)
            return

    user_states[user_id] = 'WAITING_KEY'
    off_btn = get_official_btn()
    buttons = [off_btn] if off_btn else None
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:", buttons=buttons)

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
    
    # 👑 MASTER ADMIN ACTIONS
    if user_id == MASTER_ID:
        if data == "adm_gen_5_30":
            generated = [f"`{generate_key(days=30)}`" for _ in range(5)]
            await event.answer("5 Keys Generated!", alert=True)
            await event.edit("✅ **5 New Keys Generated (30 Days Valid):**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return
        elif data == "adm_gen_1_30":
            key = generate_key(days=30)
            await event.answer("1 Key Generated!", alert=True)
            await event.edit(f"✅ **1 New Key Generated (30 Days Valid):**\n\n`{key}`", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return
        elif data == "adm_custom_key":
            user_states[user_id] = 'WAITING_CUSTOM_KEY'
            await event.edit("⚙️ **Custom Key Generation:**\n\nKripya message me count aur time bhejein format ke hisab se: `<count> <time>`\n\n**Examples:**\n`1 12h` (1 Key, 12 Ghante)\n`5 2d` (5 Keys, 2 Din)\n`10 1d` (10 Keys, 1 Din)", buttons=[[Button.inline("🔙 Cancel & Back", b"adm_back")]])
            return
        elif data == "adm_users":
            if not license_db["users"]:
                await event.answer("No active users!", alert=True)
                return
            msg = "👥 **Active Authorized Users:**\n\n"
            for uid, info in license_db["users"].items():
                expires = datetime.fromisoformat(info['expires'])
                time_left = format_time_left(expires - datetime.now())
                msg += f"👤 `{info['name']}` (ID: `{uid}`)\n   🔑 Key: `{info['key']}`\n   ⏳ Time Left: {time_left}\n\n"
            await event.edit(msg, buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return
        elif data == "adm_set_channel":
            user_states[user_id] = 'WAITING_CHANNEL_LINK'
            await event.edit("🔗 **Official Channel Link Set Karein:**\n\nKripya apne channel ka poora link ya username bhejein (Example: `https://t.me/VvipVoucher` ya `@VvipVoucher`):", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_ban_prompt":
            user_states[user_id] = 'WAITING_BAN_ID'
            await event.edit("🚫 Jis user ko **BAN** karna hai, uski Telegram User ID yahan bhej do:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_unban_prompt":
            user_states[user_id] = 'WAITING_UNBAN_ID'
            await event.edit("✅ Jis user ko **UNBAN** karna hai, uski Telegram User ID yahan bhej do:", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif data == "adm_back":
            user_states[user_id] = None
            await event.edit("👑 **MASTER ADMIN CONTROL PANEL** 👑\n\nApne kaam ke liye niche buttons me se select karein:", buttons=get_admin_buttons())
            return

    # User Control Panel Actions
    if data == "ctl_pause":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_paused = True
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            await event.answer("🔴 Bot Paused Successfully!", alert=True)
            await event.edit(f"🟡 **BOT IS PAUSED (OFF)**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    elif data == "ctl_run":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_paused = False
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            await event.answer("🟢 Bot Resumed!", alert=True)
            await event.edit(f"🟢 **BOT IS ON**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str))
    elif data == "ctl_mykey":
        if is_user_authorized(user_id):
            info = license_db["users"][str(user_id)]
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            await event.answer(f"🔑 Key: {info['key']} | ⏳ Left: {validity_str}", alert=True)
    elif data == "ctl_restart":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_running = False
            del active_snipers_dict[user_id]
        user_states[user_id] = 'CHOOSE_MODE'
        time_left = get_time_left(user_id)
        validity_str = format_time_left(time_left)
        await event.edit(
            f"🔄 **Setup Restarted!** (⏳ `{validity_str}`)\n\n🎯 Apne kaam ke liye **Target Mode** select karein:",
            buttons=get_mode_buttons()
        )

    # 🎯 TARGET CHANNEL SELECTION
    elif data == "mode_pinned":
        user_states[user_id] = {'state': 'SELECT_DEST', 'source_mode': 'pinned', 'dest_list': []}
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            buttons = await get_channel_buttons(client, "add_dest", require_admin=True, pinned_only=False)
            msg = "📌 **Pinned Mode:**\n\n🎯 Niche aapke **Admin Channels** ki list hai. Apna Destination select karein:"
            if not buttons: msg += "\n*(Agar list me naam na aaye toh aap channel ka naam type kar sakte hain)*"
            await event.edit(msg, buttons=buttons)
        else:
            await event.edit("📱 Pehle apna Telegram Phone Number bhejein:")

    elif data == "mode_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES', 'source_list': []}
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            buttons = await get_channel_buttons(client, "add_source", require_admin=False, pinned_only=True)
            msg = "🎯 **Specific Source Mode:**\n\n📥 Niche aapke **PINNED Channels/Groups** ki list hai. Apna Source select karein:"
            if not buttons: msg += "\n*(Aapne koi channel pin nahi kiya hai, ya fetch nahi hua. Kripya channel ka naam type karein)*"
            await event.edit(msg, buttons=buttons)
        else:
            await event.edit("📱 Pehle apna Telegram Phone Number bhejein:")

    elif data.startswith("add_source:"):
        source_id = int(data.split(":")[1])
        if user_id not in user_data: user_data[user_id] = {}
        if 'source_list' not in user_data[user_id]: user_data[user_id]['source_list'] = []
        if source_id not in user_data[user_id]['source_list']: user_data[user_id]['source_list'].append(source_id)
        count = len(user_data[user_id]['source_list'])
        await event.answer(f"Source added! Total: {count}", alert=True)
        await event.edit(
            f"✅ **Source Added Successfully! (Total: {count})**\n\nKya aap aur source add karna chahte hain ya destination select karein?",
            buttons=[
                [Button.inline("➕ Add More Pinned Source", b"more_source")],
                [Button.inline("🎯 Done, Select Destination", b"done_sources")]
            ]
        )

    elif data == "more_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_source", require_admin=False, pinned_only=True)
        await event.edit("🎯 Niche list me se apna agla **PINNED Source Channel** select karein:", buttons=buttons)

    elif data == "done_sources":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM', 'dest_list': []}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=True, pinned_only=False)
        await event.edit("🎯 **Sources Saved!**\n\nAb niche apne **Admin Channels** ki list me se **Destination Channel** select karein:", buttons=buttons)

    elif data.startswith("add_dest:") or data.startswith("add_destcust:"):
        dest_id = int(data.split(":")[1])
        if user_id not in user_data: user_data[user_id] = {}
        if 'dest_list' not in user_data[user_id]: user_data[user_id]['dest_list'] = []
        if dest_id not in user_data[user_id]['dest_list']: user_data[user_id]['dest_list'].append(dest_id)
        count = len(user_data[user_id]['dest_list'])
        await event.answer(f"Destination added! Total: {count}", alert=True)
        await event.edit(
            f"✅ **Destination Added! (Total: {count})**\n\nKya aur destination add karni hai ya mode select karein?",
            buttons=[
                [Button.inline("➕ Add More Destination", b"more_dest")],
                [Button.inline("🚀 Select Forwarding Mode", b"select_fwd_mode")]
            ]
        )

    elif data == "more_dest":
        is_custom = user_data[user_id].get('source_list')
        action_prefix = "add_destcust" if is_custom else "add_dest"
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM' if is_custom else 'SELECT_DEST'}
        client = user_data.get(user_id, {}).get('client')
        buttons = await get_channel_buttons(client, action_prefix, require_admin=True, pinned_only=False)
        await event.edit("🎯 Niche list me se agla **Destination Channel** select karein:", buttons=buttons)

    # 🛠 FORWARDING MODE & LINES SELECTION
    elif data == "select_fwd_mode":
        await event.edit(
            "🛠 **Sniper Forwarding Mode:**\n\nAb choose karein ki bot message kaise format karke bheje:\n\n"
            "1️⃣ **Rush Mode:** 1 msg me saare codes (1=3 lines, 2=4 lines, 3+=1-1 line)\n"
            "2️⃣ **Normal Mode:** Har Mono code ka alag msg (Aap lines select karenge)\n"
            "3️⃣ **Link Forwarder:** Message se URLs nikal kar Mono me bhejna (Aap lines select karenge)",
            buttons=[
                [Button.inline("🚀 Start Rush Mode", b"run_rush_0")],
                [Button.inline("🟢 Normal Mode", b"ask_lines_normal")],
                [Button.inline("🔗 Link Forwarder", b"ask_lines_link")]
            ]
        )

    elif data.startswith("ask_lines_"):
        mode = data.split("_")[2] # normal or link
        mode_name = "Normal" if mode == "normal" else "Link Forwarder"
        await event.edit(
            f"📏 **{mode_name} Mode - Line Settings:**\n\nAapko har item kitni lines me mono format karke bhejna hai?",
            buttons=[
                [Button.inline("1 Line", f"run_{mode}_1".encode()), Button.inline("2 Lines", f"run_{mode}_2".encode())],
                [Button.inline("3 Lines", f"run_{mode}_3".encode()), Button.inline("4 Lines", f"run_{mode}_4".encode())],
                [Button.inline("🔙 Back", b"select_fwd_mode")]
            ]
        )

    elif data.startswith("run_"):
        parts = data.split("_")
        sniper_mode = parts[1] # rush, normal, link
        lines_count = int(parts[2]) # 0, 1, 2, 3, 4
        
        client = user_data.get(user_id, {}).get('client')
        dest_list = user_data[user_id].get('dest_list', [])
        source_list = user_data[user_id].get('source_list', [])
        
        mode_disp = sniper_mode.capitalize()
        if sniper_mode != "rush":
            mode_disp += f" ({lines_count} Lines)"
            
        await event.edit(f"🚀 **Sniper Bot Start ho raha hai [{mode_disp}]...**")
        await start_sniper_for_user(user_id, client, dest_list, "User", source_list if source_list else None, sniper_mode, lines_count)

@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip()
    
    if text.startswith('/'):
        return

    # 👑 MASTER ADMIN TEXT HANDLING
    if user_id == MASTER_ID:
        state = user_states.get(user_id)
        if state == 'WAITING_BAN_ID':
            target_id = text
            if target_id in license_db["users"]:
                del license_db["users"][target_id]
                save_licenses(license_db)
                if int(target_id) in active_snipers_dict:
                    active_snipers_dict[int(target_id)].is_running = False
                user_states[user_id] = None
                await event.reply(f"✅ User `{target_id}` ko successfully BAN kar diya gaya hai!", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            else:
                await event.reply("❌ Ye user list me nahi mila. Dobara sahi ID bhejein.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
            
        elif state == 'WAITING_UNBAN_ID':
            target_id = text
            found_key, key_info = None, None
            for k, info in license_db["keys"].items():
                if str(info.get("used_by")) == target_id:
                    found_key = k
                    key_info = info
                    break
            if found_key:
                license_db["users"][target_id] = {"name": "Unbanned User", "key": found_key, "expires": key_info["expires"]}
                save_licenses(license_db)
                user_states[user_id] = None
                await event.reply(f"✅ User `{target_id}` ko successfully UNBAN kar diya gaya hai!", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            else:
                await event.reply("❌ Is user ki purani key nahi mili. Inhe nayi key generate karke dein.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

        elif state == 'WAITING_CHANNEL_LINK':
            if text.startswith('@'): link = f"https://t.me/{text[1:]}"
            elif text.startswith('t.me/'): link = f"https://{text}"
            elif text.startswith('http'): link = text
            else:
                await event.reply("❌ Link sahi format me nahi hai. (Ex: https://t.me/username ya @username)", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
                return
            license_db["settings"]["official_channel"] = link
            save_licenses(license_db)
            user_states[user_id] = None
            await event.reply(f"✅ Official Channel button update ho gaya hai!\nNaya Link: `{link}`", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            return

        elif state == 'WAITING_CUSTOM_KEY':
            try:
                parts = text.lower().split()
                count = int(parts[0])
                time_str = parts[1]
                if time_str.endswith('h'):
                    hours = int(time_str[:-1])
                    days, validity_txt = 0, f"{hours} Hours"
                elif time_str.endswith('d'):
                    days = int(time_str[:-1])
                    hours, validity_txt = 0, f"{days} Days"
                else:
                    days = int(time_str) 
                    hours, validity_txt = 0, f"{days} Days"
                    
                generated = [f"`{generate_key(days=days, hours=hours)}`" for _ in range(count)]
                user_states[user_id] = None
                await event.reply(f"✅ **{count} New Keys Generated ({validity_txt} Valid):**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            except Exception as e:
                await event.reply("⚠️ Galat format! Kripya aise likhein: `1 12h` ya `5 2d`", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

    state = user_states.get(user_id)

    if state == 'WAITING_KEY':
        if text in license_db["keys"]:
            key_info = license_db["keys"][text]
            if key_info["used_by"] is not None and key_info["used_by"] != user_id:
                await event.reply("❌ Ye key pehle hi kisi aur dwara use ki ja chuki hai!")
                return
            
            license_db["keys"][text]["used_by"] = user_id
            license_db["users"][str(user_id)] = {
                "name": f"{event.sender.first_name or ''} {event.sender.last_name or ''}".strip(),
                "key": text,
                "expires": key_info["expires"]
            }
            save_licenses(license_db)
            
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            
            client = user_data.get(user_id, {}).get('client')
            if client and client.is_connected():
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply(
                    f"✅ **Key Verified Successfully!** (⏳ `{validity_str}`)\n\n🎯 Apne kaam ke liye **Target Mode** select karein:",
                    buttons=get_mode_buttons()
                )
            else:
                user_states[user_id] = 'WAITING_PHONE'
                await event.reply(f"✅ **Key Verified!** (⏳ `{validity_str}`)\n\n📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")
        else:
            await event.reply("❌ **Invalid Key!** Sahi key enter karein ya Admin se contact karein.")

    elif state == 'SELECT_SOURCES':
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            await search_and_send_channels(event, client, "add_source", query=text)
        else:
            await event.reply("📱 Pehle apna Telegram Phone Number bhejein:")

    elif state in ['SELECT_DEST', 'SELECT_DEST_CUSTOM']:
        client = user_data.get(user_id, {}).get('client')
        action_prefix = "add_destcust" if user_data[user_id].get('source_list') else "add_dest"
        if client and client.is_connected():
            await search_and_send_channels(event, client, action_prefix, query=text)
        else:
            await event.reply("📱 Pehle apna Telegram Phone Number bhejein:")

    elif state in ['WAITING_PHONE', 'WAITING_PHONE_FOR_PINNED', 'WAITING_PHONE_FOR_SOURCE']:
        phone = text
        await event.reply("🔄 Connecting... Aapko Telegram par ek **OTP (Code)** aayega, kripya wo yahan bhejein:")
        user_states[user_id] = {'state': 'WAITING_OTP', 'phone': phone}
        
        try:
            client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(phone)
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id]['client'] = client
            user_data[user_id]['phone_code_hash'] = sent.phone_code_hash
        except FloodWaitError as e:
            await event.reply(f"⚠️ Telegram ne FloodWait lagaya hai! Kripya {e.seconds} seconds baad try karein.")
            user_states[user_id] = None
        except Exception as e:
            await event.reply(f"❌ Error: {e}\n/start dabakar fir se koshish karein.")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        otp = text
        phone = state['phone']
        client = user_data[user_id].get('client')
        hash_code = user_data[user_id].get('phone_code_hash')
        
        try:
            await client.sign_in(phone=phone, code=otp, phone_code_hash=hash_code)
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Login Successful! (⏳ `{validity_str}`)\n\n🎯 Ab apna **Target Mode** select karein:", buttons=get_mode_buttons())
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'WAITING_PASSWORD'}
            await event.reply("🔒 Aapke account par **2-Step Verification (Password)** laga hai.\n\nKripya apna Telegram **Cloud Password** yahan bhejein:")
        except Exception as e:
            await event.reply(f"❌ OTP Galat hai ya error aayi: {e}\n/start dabakar fir se try karein.")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_PASSWORD':
        password = text
        client = user_data[user_id].get('client')
        
        try:
            await client.sign_in(password=password)
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Password Verified! (⏳ `{validity_str}`)\n\n🎯 Ab apna **Target Mode** select karein:", buttons=get_mode_buttons())
        except Exception as e:
            await event.reply(f"❌ Password galat hai ya error aayi: {e}\n/start dabakar fir se try karein.")
            user_states[user_id] = None

print("👑 Master Bot Initialized Successfully!")
master_bot.start(bot_token=BOT_TOKEN)
master_bot.run_until_disconnected()
