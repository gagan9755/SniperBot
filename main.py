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
            return json.load(f)
    except FileNotFoundError:
        return {"keys": {}, "users": {}} 

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

# --- 🧠 USER SNIPER CLASS ---
class UserSniper:
    def __init__(self, user_id, client, name, source_chat_ids=None):
        self.user_id = user_id
        self.client = client
        self.name = name
        self.destinations = {} 
        self.source_chat_ids = source_chat_ids if source_chat_ids else []
        self.pinned_chats = set()
        self.is_running = True
        self.is_paused = False
        
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

async def start_sniper_for_user(user_id, client, dest_chats, name, source_chat_ids=None):
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_running = False

    sniper = UserSniper(user_id, client, name, source_chat_ids)
    
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
        if sniper.is_paused or not sniper.destinations:
            return
            
        if sniper.source_chat_ids:
            if event.chat_id not in sniper.source_chat_ids:
                return
        else:
            if event.chat_id not in sniper.pinned_chats:
                return

        if event.id in sniper.processed_ids_set or not event.message.entities:
            return

        extracted_codes = []
        for entity, text in event.message.get_entities_text():
            if isinstance(entity, (MessageEntityCode, MessageEntityPre)):
                if "t.me/" in text.lower() or "telegram.me/" in text.lower():
                    continue
                if text not in sniper.seen_codes_set and text not in extracted_codes: 
                    extracted_codes.append(text)
                    if len(sniper.seen_codes_queue) == 100:
                        old_code = sniper.seen_codes_queue.popleft()
                        sniper.seen_codes_set.discard(old_code)
                    sniper.seen_codes_queue.append(text)
                    sniper.seen_codes_set.add(text)

        if not extracted_codes: return
        start_time = time.time()
        if len(sniper.processed_ids_queue) == 50:
            old_id = sniper.processed_ids_queue.popleft()
            sniper.processed_ids_set.discard(old_id)
        sniper.processed_ids_queue.append(event.id)
        sniper.processed_ids_set.add(event.id)

        num_codes = len(extracted_codes)
        final_lines = [f"{num_codes} Code"]
        if num_codes == 1:
            c = extracted_codes[0]
            final_lines.extend([f"`{c}`", f"`{c}`", f"`{c}`"])
        elif num_codes == 2:
            for c in extracted_codes: final_lines.extend([f"`{c}`", f"`{c}`"])
        else:
            for c in extracted_codes: final_lines.append(f"`{c}`")
        final_msg = "\n".join(final_lines)
        for d_id, target in sniper.destinations.items():
            asyncio.create_task(fast_send(client, target, final_msg, start_time, user_id))

    time_left = get_time_left(user_id)
    validity_str = format_time_left(time_left)
    mode_text = f"Multiple Sources ({len(source_chat_ids)})" if source_chat_ids else "Auto Pinned Chats"
    
    control_buttons = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")]
    ]
    await master_bot.send_message(
        user_id, 
        f"✅ **SNIPER ACTIVE!** 🎯\n\n🟢 **Mode:** {mode_text}\n🚀 **Destinations:** `{len(sniper.destinations)}`\n⏳ **Validity:** `{validity_str}`", 
        buttons=control_buttons
    )

async def search_and_send_channels(event, client, action_type, query=""):
    try:
        dialogs = await client.get_dialogs(limit=500)
        buttons = []
        for d in dialogs:
            if d.is_channel or d.is_group:
                name = d.name if d.name else "Unnamed"
                if not query or query.lower() in name.lower():
                    buttons.append([Button.inline(name[:28], data=f"{action_type}:{d.id}")])
                    if len(buttons) >= 15:
                        break
        
        if not buttons:
            await event.respond(f"❌ '{query}' naam se koi channel nahi mila. Sahi naam likh kar dobara try karein.")
            return
            
        await event.respond(f"🔍 **Matching Channels:**\nNiche tap karke select karein:", buttons=buttons)
    except Exception as e:
        await event.respond(f"❌ Channels search karne me error aayi: {e}")

def get_admin_buttons():
    return [
        [Button.inline("🔑 Gen 1 Key (30 Days)", b"adm_gen_1_30"), Button.inline("🔑 Gen 5 Keys (30 Days)", b"adm_gen_5_30")],
        [Button.inline("⚙️ Custom Key (Days/Hours)", b"adm_custom_key")],
        [Button.inline("👥 View Active Users", b"adm_users")],
        [Button.inline("🚫 Ban User", b"adm_ban_prompt"), Button.inline("✅ Unban User", b"adm_unban_prompt")]
    ]

# --- 💬 BOT CONVERSATION & LICENSE LOGIC ---
@master_bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    
    # 👑 MASTER ADMIN BUTTON PANEL
    if user_id == MASTER_ID:
        user_states[user_id] = None # Clear any pending states
        await event.reply("👑 **MASTER ADMIN CONTROL PANEL** 👑\n\nApne kaam ke liye niche buttons me se select karein:", buttons=get_admin_buttons())
        return
        
    if is_user_authorized(user_id):
        if check_subscription(user_id):
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)

            if user_id in active_snipers_dict:
                sniper = active_snipers_dict[user_id]
                control_buttons = [
                    [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
                    [Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")]
                ]
                status_txt = "🟢 **BOT IS ON**" if not sniper.is_paused else "🟡 **BOT IS PAUSED**"
                await event.reply(f"{status_txt}\n\n⏳ **Validity:** `{validity_str}`\nApna bot control karne ke liye niche buttons use karein:", buttons=control_buttons)
                return

            client = user_data.get(user_id, {}).get('client')
            if client and client.is_connected():
                user_states[user_id] = 'CHOOSE_MODE'
                await event.reply(
                    f"✅ **Welcome Back!** (⏳ `{validity_str}`)\n\n🎯 Apne kaam ke liye **Sniper Mode** select karein:",
                    buttons=[
                        [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                        [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
                    ]
                )
            else:
                user_states[user_id] = 'WAITING_PHONE'
                await event.reply(f"✅ **Welcome Back!** (⏳ `{validity_str}`)\n\n📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")
        else:
            await event.reply("⚠️ **Aapki Key Expire ho chuki hai!** Nayi key ke liye Admin se contact karein.")
        return

    user_states[user_id] = 'WAITING_KEY'
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:")

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
            await event.edit(f"🟡 **BOT IS PAUSED (OFF)**\n\n⏳ **Validity:** `{validity_str}`", buttons=[
                [Button.inline("🟢 Resume Bot", b"ctl_run"), Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey")],
                [Button.inline("🔄 Restart Setup", b"ctl_restart")]
            ])
    elif data == "ctl_run":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_paused = False
            time_left = get_time_left(user_id)
            validity_str = format_time_left(time_left)
            await event.answer("🟢 Bot Resumed!", alert=True)
            await event.edit(f"🟢 **BOT IS ON**\n\n⏳ **Validity:** `{validity_str}`", buttons=[
                [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline(f"⏳ Expiry: {validity_str}", b"ctl_mykey")],
                [Button.inline("🔄 Restart Setup", b"ctl_restart")]
            ])
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
            f"🔄 **Setup Restarted!** (⏳ `{validity_str}`)\n\n🎯 Apne kaam ke liye **Sniper Mode** select karein:",
            buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
            ]
        )

    elif data == "mode_pinned":
        user_states[user_id] = {'state': 'SELECT_DEST', 'source_mode': 'pinned', 'dest_list': []}
        await event.edit("📌 **Pinned Mode Selected.**\n\nAb apna **Destination Channel** search karne ke liye naam ya keyword type karke bhejein:")

    elif data == "mode_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES', 'source_list': []}
        await event.edit("🎯 **Specific Source Mode Selected.**\n\nAb apne **Source Channel** ka naam ya keyword type karke bhejein (Aap ek se zyada source add kar sakte hain):")

    elif data.startswith("add_source:"):
        source_id = int(data.split(":")[1])
        if user_id not in user_data: user_data[user_id] = {}
        if 'source_list' not in user_data[user_id]: user_data[user_id]['source_list'] = []
        
        if source_id not in user_data[user_id]['source_list']:
            user_data[user_id]['source_list'].append(source_id)
            
        count = len(user_data[user_id]['source_list'])
        await event.answer(f"Source added! Total: {count}", alert=True)
        await event.edit(
            f"✅ **Source Added Successfully! (Total: {count})**\n\nKya aap aur source add karna chahte hain ya destination select karein?",
            buttons=[
                [Button.inline("➕ Add More Source", b"more_source")],
                [Button.inline("🎯 Done, Select Destination", b"done_sources")]
            ]
        )

    elif data == "more_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        await event.edit("🎯 Agle **Source Channel** ka naam ya keyword type karke bhejein:")

    elif data == "done_sources":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM', 'dest_list': []}
        await event.edit("🎯 **Sources Saved!**\n\nAb apna **Destination Channel** search karne ke liye naam ya keyword type karke bhejein:")

    elif data.startswith("add_dest:") or data.startswith("add_destcust:"):
        dest_id = int(data.split(":")[1])
        if user_id not in user_data: user_data[user_id] = {}
        if 'dest_list' not in user_data[user_id]: user_data[user_id]['dest_list'] = []
        
        if dest_id not in user_data[user_id]['dest_list']:
            user_data[user_id]['dest_list'].append(dest_id)
            
        count = len(user_data[user_id]['dest_list'])
        await event.answer(f"Destination added! Total: {count}", alert=True)
        await event.edit(
            f"✅ **Destination Added! (Total: {count})**\n\nKya aur destination add karni hai ya sniper start karein?",
            buttons=[
                [Button.inline("➕ Add More Destination", b"more_dest")],
                [Button.inline("🚀 Start Sniper Bot Now", b"start_sniper_final")]
            ]
        )

    elif data == "more_dest":
        is_custom = user_data[user_id].get('source_list')
        action_prefix = "add_destcust" if is_custom else "add_dest"
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM' if is_custom else 'SELECT_DEST'}
        await event.edit("🎯 Agle **Destination Channel** ka naam ya keyword type karke bhejein:")

    elif data == "start_sniper_final":
        client = user_data.get(user_id, {}).get('client')
        dest_list = user_data[user_id].get('dest_list', [])
        source_list = user_data[user_id].get('source_list', [])
        
        await event.edit("🚀 **Sniper Bot Start ho raha hai...**")
        await start_sniper_for_user(user_id, client, dest_list, "User", source_list if source_list else None)

@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip()
    
    if text.startswith('/'):
        return

    # 👑 MASTER ADMIN TEXT HANDLING (Ban, Unban & Custom Key Input)
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
            found_key = None
            key_info = None
            # Search if user had an active key previously
            for k, info in license_db["keys"].items():
                if str(info.get("used_by")) == target_id:
                    found_key = k
                    key_info = info
                    break
            
            if found_key:
                license_db["users"][target_id] = {
                    "name": "Unbanned User",
                    "key": found_key,
                    "expires": key_info["expires"]
                }
                save_licenses(license_db)
                user_states[user_id] = None
                await event.reply(f"✅ User `{target_id}` ko successfully UNBAN kar diya gaya hai!\nWo apni purani key se direct continue kar sakte hain.", buttons=[[Button.inline("🔙 Back to Admin Menu", b"adm_back")]])
            else:
                await event.reply("❌ Is user ki koi purani key nahi mili. Kripya inhe nayi key generate karke dein.", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

        elif state == 'WAITING_CUSTOM_KEY':
            try:
                parts = text.lower().split()
                count = int(parts[0])
                time_str = parts[1]
                
                if time_str.endswith('h'):
                    hours = int(time_str[:-1])
                    days = 0
                    validity_txt = f"{hours} Hours"
                elif time_str.endswith('d'):
                    days = int(time_str[:-1])
                    hours = 0
                    validity_txt = f"{days} Days"
                else:
                    days = int(time_str) # Default to days
                    hours = 0
                    validity_txt = f"{days} Days"
                    
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
            user_states[user_id] = 'WAITING_PHONE'
            await event.reply(f"✅ **Key Verified!** (⏳ `{validity_str}`)\n\n📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")
        else:
            await event.reply("❌ **Invalid Key!** Sahi key enter karein ya Admin se contact karein.")

    elif state == 'SELECT_SOURCES':
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            await search_and_send_channels(event, client, "add_source", query=text)
        else:
            user_states[user_id] = {'state': 'WAITING_PHONE_FOR_SOURCE', 'pending_source': text}
            await event.reply("📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")

    elif state in ['SELECT_DEST', 'SELECT_DEST_CUSTOM']:
        client = user_data.get(user_id, {}).get('client')
        is_custom = user_data[user_id].get('source_list')
        action_prefix = "add_destcust" if is_custom else "add_dest"
        if client and client.is_connected():
            await search_and_send_channels(event, client, action_prefix, query=text)
        else:
            user_states[user_id] = {'state': 'WAITING_PHONE', 'pending_dest': text}
            await event.reply("📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")

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
            await event.reply(f"✅ Login Successful! (⏳ `{validity_str}`)\n\n🎯 Ab apna **Sniper Mode** select karein:", buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
            ])
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
            await event.reply(f"✅ Password Verified! (⏳ `{validity_str}`)\n\n🎯 Ab apna **Sniper Mode** select karein:", buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
            ])
        except Exception as e:
            await event.reply(f"❌ Password galat hai ya error aayi: {e}\n/start dabakar fir se try karein.")
            user_states[user_id] = None

print("👑 Master Bot Initialized Successfully!")
master_bot.start(bot_token=BOT_TOKEN)
master_bot.run_until_disconnected()
