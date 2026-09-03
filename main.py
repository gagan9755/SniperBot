import asyncio
import time
import re
from collections import deque
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types
from telethon.tl.types import MessageEntityCode, MessageEntityPre
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

# ✅ APNI TELEGRAM ID (Aapki Master ID set kar di gayi hai)
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

def generate_key(days):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    expiry_dt = datetime.now() + timedelta(days=days)
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

# --- 🧠 HAR USER KI ALAG MEMORY AUR RADAR ---
class UserSniper:
    def __init__(self, user_id, client, name):
        self.user_id = user_id
        self.client = client
        self.name = name
        self.destinations = {} 
        self.pinned_chats = set()
        self.is_running = True
        self.is_paused = False
        
        self.processed_ids_set = set()
        self.processed_ids_queue = deque(maxlen=50)
        self.seen_codes_set = set()
        self.seen_codes_queue = deque(maxlen=100)
        
    async def update_pinned_loop(self):
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

async def start_sniper_for_user(user_id, client, dest_chat, name):
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_running = False

    sniper = UserSniper(user_id, client, name)
    
    try:
        target_entity = await client.get_entity(dest_chat)
        sniper.destinations[dest_chat] = target_entity
    except Exception as e:
        await master_bot.send_message(user_id, f"❌ Error: ID galat hai ya aapne wo channel join nahi kiya hai.")
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
        if event.id in sniper.processed_ids_set or event.chat_id not in sniper.pinned_chats or not event.message.entities:
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

    await master_bot.send_message(user_id, f"✅ **SNIPER ACTIVE!** 🎯\n\n🟢 **Status:** ON\n🚀 **Targets:** `{len(sniper.destinations)}`")

# --- 💬 BOT CONVERSATION & LICENSE LOGIC ---
@master_bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    if user_id == MASTER_ID:
        await event.reply("👑 **MASTER ADMIN PANEL UNLOCKED!**\n\nKripya /help dekhein saare Admin commands ke liye.")
        return
        
    if is_user_authorized(user_id):
        if check_subscription(user_id):
            user_states[user_id] = 'WAITING_DEST'
            await event.reply("✅ **Welcome Back!**\n\n🎯 Apni **Destination Channel ki ID** bhejein:")
        else:
            await event.reply("⚠️ **Aapki Key Expire ho chuki hai!** Nayi key ke liye Admin se संपर्क karein.")
        return

    user_states[user_id] = 'WAITING_KEY'
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:")

@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip()
    
    if text.startswith('/'):
        return

    state = user_states.get(user_id)

    # 1. Key Verification State
    if state == 'WAITING_KEY':
        if text in license_db["keys"]:
            key_info = license_db["keys"][text]
            if key_info["used_by"] is not None and key_info["used_by"] != user_id:
                await event.reply("❌ Ye key pehle hi kisi aur dwara use ki ja chuki hai!")
                return
            
            # Authorize User
            license_db["keys"][text]["used_by"] = user_id
            license_db["users"][str(user_id)] = {
                "name": f"{event.sender.first_name or ''} {event.sender.last_name or ''}".strip(),
                "key": text,
                "expires": key_info["expires"]
            }
            save_licenses(license_db)
            
            user_states[user_id] = 'WAITING_DEST'
            await event.reply("✅ **Key Verified Successfully!** 🎉\n\nAb apni **Destination Channel ki ID** bhejein jahan codes forward karne hain:")
        else:
            await event.reply("❌ **Invalid Key!** Sahi key enter karein ya Admin se contact karein.")

    # 2. Destination Channel Input State
    elif state == 'WAITING_DEST':
        try:
            dest_chat = int(text) if text.startswith('-') or text.isdigit() else text
            user_states[user_id] = 'WAITING_PHONE'
            user_data[user_id] = {'dest': dest_chat}
            await event.reply("📱 Ab apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")
        except ValueError:
            await event.reply("⚠️ Galat ID format! Kripya sahi Channel ID bhejein.")

    # 3. Phone Number & Session Login State
    elif state == 'WAITING_PHONE':
        phone = text
        await event.reply("🔄 Connecting... Aapko Telegram par ek **OTP (Code)** aayega, kripya wo yahan bhejein:")
        user_states[user_id] = {'state': 'WAITING_OTP', 'phone': phone, 'dest': user_data[user_id]['dest']}
        
        try:
            client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(phone)
            user_data[user_id]['client'] = client
            user_data[user_id]['phone_code_hash'] = sent.phone_code_hash
        except Exception as e:
            await event.reply(f"❌ Error: {e}\n/start dabakar fir se koshish karein.")
            user_states[user_id] = None

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        otp = text
        phone = state['phone']
        dest_chat = state['dest']
        client = user_data[user_id]['client']
        hash_code = user_data[user_id]['phone_code_hash']
        
        try:
            await client.sign_in(phone=phone, code=otp, phone_code_hash=hash_code)
            user_states[user_id] = 'ACTIVE'
            name = f"{event.sender.first_name or ''}"
            await event.reply("✅ Login Successful! Sniper start ho raha hai...")
            await start_sniper_for_user(user_id, client, dest_chat, name)
        except Exception as e:
            await event.reply(f"❌ OTP Galat hai ya error aayi: {e}\n/start dabakar fir se try karein.")
            user_states[user_id] = None

# --- ⚙️ USER COMMANDS ---
@master_bot.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    user_id = event.sender_id
    if not is_user_authorized(user_id) and user_id != MASTER_ID:
        await event.reply("🔴 **Access Denied!** /start dabakar apni key activate karein.")
        return
    if user_id == MASTER_ID:
        await event.reply("👑 Aap Master Admin hain. Commands ke liye /help dekhein.")
        return

    if user_id in active_snipers_dict and active_snipers_dict[user_id].is_running:
        sniper = active_snipers_dict[user_id]
        dest_list = "\n".join([f"🔸 `{d}`" for d in sniper.destinations.keys()])
        if sniper.is_paused:
            msg = f"🟡 **BOT IS PAUSED (OFF)**\n\n🎯 Target: {dest_list}\n\n▶️ Chalu karne ke liye 👉 /run"
        else:
            msg = f"🟢 **BOT IS ON**\n\n🎯 Target: {dest_list}\n\n🛑 Band karne ke liye 👉 /stop"
    else:
        msg = "🔴 **BOT IS OFF**\n\nChalu karne ke liye /start dabayein."
    await event.reply(msg)

@master_bot.on(events.NewMessage(pattern='/mykey'))
async def mykey_command(event):
    user_id = event.sender_id
    if not is_user_authorized(user_id):
        await event.reply("🔴 Aap authorized nahi hain.")
        return
    info = license_db["users"][str(user_id)]
    expires_dt = datetime.fromisoformat(info['expires'])
    time_left = get_time_left(user_id)
    await event.reply(f"🔑 **Aapki Key Details:**\n\n🏷 Key: `{info['key']}`\n📅 Expires On: {expires_dt.strftime('%Y-%m-%d %H:%M')}\n⏳ Time Left: {time_left.days} days")

@master_bot.on(events.NewMessage(pattern='/stop'))
async def stop_command(event):
    user_id = event.sender_id
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_paused = True
        await event.reply("🔴 **Bot Paused!** Wapas chalu karne ke liye 👉 /run")

@master_bot.on(events.NewMessage(pattern='/run'))
async def run_command(event):
    user_id = event.sender_id
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_paused = False
        await event.reply("🟢 **Bot Resumed!** Codes aana shuru.")

# --- 👑 MASTER ADMIN PANEL COMMANDS ---
@master_bot.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    if event.sender_id != MASTER_ID:
        await event.reply("🤖 Commands: /start, /status, /mykey, /stop, /run")
        return
    msg = ("👑 **MASTER ADMIN PANEL** 👑\n\n"
           "`/addkey <count> <days>` - Naye PINs banayein (Example: `/addkey 5 30`)\n"
           "`/users` - Active users aur unke names dekhein\n"
           "`/ban <user_id>` - User ka access khatam karein\n"
           "`/id` - Apni ID dekhein")
    await event.reply(msg)

@master_bot.on(events.NewMessage(pattern='/addkey'))
async def addkey_command(event):
    if event.sender_id != MASTER_ID: return
    try:
        args = event.message.text.split()
        count = int(args[1])
        days = int(args[2]) if len(args) > 2 else 30
        generated = [f"`{generate_key(days)}`" for _ in range(count)]
        await event.reply(f"✅ **{count} New Keys Generated ({days} Days Valid):**\n\n" + "\n".join(generated))
    except (ValueError, IndexError):
        await event.reply("⚠️ Sahi format use karein. Example: `/addkey 5 30`")

@master_bot.on(events.NewMessage(pattern='/users'))
async def users_command(event):
    if event.sender_id != MASTER_ID: return
    if not license_db["users"]:
        await event.reply("⚠️ Koi active user nahi hai.")
        return
    msg = "👥 **Active Authorized Users:**\n\n"
    for uid, info in license_db["users"].items():
        expires = datetime.fromisoformat(info['expires']).strftime('%Y-%m-%d')
        msg += f"👤 `{info['name']}` (ID: `{uid}`)\n   🔑 Key: `{info['key']}`\n   📅 Expiry: {expires}\n\n"
    await event.reply(msg)

@master_bot.on(events.NewMessage(pattern='/ban'))
async def ban_command(event):
    if event.sender_id != MASTER_ID: return
    try:
        target_id = event.message.text.split()[1]
        if target_id in license_db["users"]:
            del license_db["users"][target_id]
            save_licenses(license_db)
            if int(target_id) in active_snipers_dict:
                active_snipers_dict[int(target_id)].is_running = False
            await event.reply(f"✅ User `{target_id}` ko successfully ban kar diya gaya hai!")
        else:
            await event.reply("❌ Ye user list me nahi mila.")
    except IndexError:
        await event.reply("⚠️ Sahi format: `/ban <user_id>`")

print("👑 Master Bot Initialized Successfully!")
master_bot.run_until_disconnected()
