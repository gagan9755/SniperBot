import asyncio
import time
import re
from collections import deque
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, Button
from telethon.tl.types import MessageEntityCode, MessageEntityPre
from telethon.errors import SessionPasswordNeededError
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

# --- 🧠 USER SNIPER CLASS ---
class UserSniper:
    def __init__(self, user_id, client, name, source_chat_id=None):
        self.user_id = user_id
        self.client = client
        self.name = name
        self.destinations = {} 
        self.source_chat_id = source_chat_id 
        self.pinned_chats = set()
        self.is_running = True
        self.is_paused = False
        
        self.processed_ids_set = set()
        self.processed_ids_queue = deque(maxlen=50)
        self.seen_codes_set = set()
        self.seen_codes_queue = deque(maxlen=100)
        
    async def update_pinned_loop(self):
        if self.source_chat_id:
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

async def start_sniper_for_user(user_id, client, dest_chat, name, source_chat_id=None):
    if user_id in active_snipers_dict:
        active_snipers_dict[user_id].is_running = False

    sniper = UserSniper(user_id, client, name, source_chat_id)
    
    try:
        target_entity = await client.get_entity(dest_chat)
        sniper.destinations[dest_chat] = target_entity
    except Exception as e:
        await master_bot.send_message(user_id, f"❌ Error: Destination ID galat hai ya aapne wo channel join nahi kiya hai.")
        return

    if source_chat_id:
        try:
            source_entity = await client.get_entity(source_chat_id)
            sniper.source_chat_id = source_entity.id
        except Exception as e:
            await master_bot.send_message(user_id, f"❌ Error: Source Channel ID galat hai!")
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
            
        if sniper.source_chat_id:
            if event.chat_id != sniper.source_chat_id:
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

    # Calculate days left for expiry display
    time_left = get_time_left(user_id)
    days_left = time_left.days if time_left else 0

    control_buttons = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline(f"⏳ Expiry: {days_left} Days Left", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")]
    ]
    mode_text = f"Specific Source (`{sniper.source_chat_id}`)" if source_chat_id else "Auto Pinned Chats"
    await master_bot.send_message(
        user_id, 
        f"✅ **SNIPER ACTIVE!** 🎯\n\n🟢 **Mode:** {mode_text}\n🚀 **Targets:** `{len(sniper.destinations)}`\n⏳ **Validity:** `{days_left} Days Remaining`", 
        buttons=control_buttons
    )

# Helper to search and send channels with query
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
            
        await event.respond(f"🔍 **Matching Channels (Total found: {len(buttons)})**\nNiche tap karke select karein:", buttons=buttons)
    except Exception as e:
        await event.respond(f"❌ Channels search karne me error aayi: {e}")

# --- 💬 BOT CONVERSATION & LICENSE LOGIC ---
@master_bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    if user_id == MASTER_ID:
        await event.reply("👑 **MASTER ADMIN PANEL UNLOCKED!**\n\nCommands ke liye /help dekhein.")
        return
        
    if is_user_authorized(user_id):
        if check_subscription(user_id):
            time_left = get_time_left(user_id)
            days_left = time_left.days if time_left else 0

            if user_id in active_snipers_dict:
                sniper = active_snipers_dict[user_id]
                control_buttons = [
                    [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
                    [Button.inline(f"⏳ Expiry: {days_left} Days Left", b"ctl_mykey"), Button.inline("🔄 Restart Setup", b"ctl_restart")]
                ]
                status_txt = "🟢 **BOT IS ON**" if not sniper.is_paused else "🟡 **BOT IS PAUSED**"
                await event.reply(f"{status_txt}\n\n⏳ **Validity:** `{days_left} Days Remaining`\nApna bot control karne ke liye niche buttons use karein:", buttons=control_buttons)
                return

            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(
                f"✅ **Welcome Back!** (⏳ `{days_left} Days Left`)\n\n🎯 Apne kaam ke liye **Sniper Mode** select karein:",
                buttons=[
                    [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                    [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
                ]
            )
        else:
            await event.reply("⚠️ **Aapki Key Expire ho chuki hai!** Nayi key ke liye Admin se contact karein.")
        return

    user_states[user_id] = 'WAITING_KEY'
    await event.reply("🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:")

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
    
    if data == "ctl_pause":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_paused = True
            time_left = get_time_left(user_id)
            days_left = time_left.days if time_left else 0
            await event.answer("🔴 Bot Paused Successfully!", alert=True)
            await event.edit(f"🟡 **BOT IS PAUSED (OFF)**\n\n⏳ **Validity:** `{days_left} Days Remaining`\nDobara chalu karne ke liye button dabayein:", buttons=[
                [Button.inline("🟢 Resume Bot", b"ctl_run"), Button.inline(f"⏳ Expiry: {days_left} Days", b"ctl_mykey")],
                [Button.inline("🔄 Restart Setup", b"ctl_restart")]
            ])
    elif data == "ctl_run":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_paused = False
            time_left = get_time_left(user_id)
            days_left = time_left.days if time_left else 0
            await event.answer("🟢 Bot Resumed!", alert=True)
            await event.edit(f"🟢 **BOT IS ON**\n\n⏳ **Validity:** `{days_left} Days Remaining`\nCodes aana shuru ho gaye hain:", buttons=[
                [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline(f"⏳ Expiry: {days_left} Days", b"ctl_mykey")],
                [Button.inline("🔄 Restart Setup", b"ctl_restart")]
            ])
    elif data == "ctl_mykey":
        if is_user_authorized(user_id):
            info = license_db["users"][str(user_id)]
            time_left = get_time_left(user_id)
            await event.answer(f"🔑 Key: {info['key']} | ⏳ Days Left: {time_left.days}", alert=True)
    elif data == "ctl_restart":
        if user_id in active_snipers_dict:
            active_snipers_dict[user_id].is_running = False
            del active_snipers_dict[user_id]
        user_states[user_id] = 'CHOOSE_MODE'
        time_left = get_time_left(user_id)
        days_left = time_left.days if time_left else 0
        await event.edit(
            f"🔄 **Setup Restarted!** (⏳ `{days_left} Days Left`)\n\n🎯 Apne kaam ke liye **Sniper Mode** select karein:",
            buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
            ]
        )

    elif data == "mode_pinned":
        user_states[user_id] = {'state': 'SELECT_DEST', 'source_mode': 'pinned'}
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            await event.edit("📌 **Pinned Mode Selected.**\n\nAb apna **Destination Channel** search karne ke liye channel ka naam ya keyword type karke bhejein:")
        else:
            user_states[user_id] = {'state': 'WAITING_PHONE_FOR_PINNED', 'source_mode': 'pinned'}
            await event.edit("📌 **Pinned Mode Selected.**\n\n📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")

    elif data == "mode_source":
        user_states[user_id] = {'state': 'SELECT_SOURCE_SEARCH'}
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            await event.edit("🎯 **Specific Source Mode Selected.**\n\nAb apne **Source Channel** ka naam ya keyword type karke bhejein jisse bot use dhoondh sake:")
        else:
            user_states[user_id] = {'state': 'WAITING_PHONE_FOR_SOURCE'}
            await event.edit("🎯 **Specific Source Mode Selected.**\n\n📱 Pehle apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")

    elif data.startswith("source:"):
        source_chat = int(data.split(":")[1])
        user_data[user_id]['source_chat'] = source_chat
        user_states[user_id] = {'state': 'SELECT_DEST_SEARCH'}
        await event.edit("✅ Source Channel select ho gaya!\n\nAb apne **Destination Channel** ka naam ya keyword type karke bhejein:")

    elif data.startswith("dest:") or data.startswith("destcust:"):
        dest_chat = int(data.split(":")[1])
        user_data[user_id]['dest'] = dest_chat
        
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            await event.edit("✅ Setup Complete! Sniper start ho raha hai...")
            await start_sniper_for_user(user_id, client, dest_chat, "User", user_data[user_id].get('source_chat'))
        else:
            user_states[user_id] = {'state': 'WAITING_PHONE'}
            await event.edit("✅ Destination select ho gayi!\n\n📱 Ab apna **Telegram Phone Number** bhejein (Country code ke sath, jaise `+919876543210`):")

@master_bot.on(events.NewMessage())
async def handle_text(event):
    user_id = event.sender_id
    text = event.message.text.strip()
    
    if text.startswith('/'):
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
            days_left = time_left.days if time_left else 0
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(
                f"✅ **Key Verified Successfully!** 🎉 (⏳ `{days_left} Days Left`)\n\n🎯 Apne kaam ke liye **Sniper Mode** select karein:",
                buttons=[
                    [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                    [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
                ]
            )
        else:
            await event.reply("❌ **Invalid Key!** Sahi key enter karein ya Admin se contact karein.")

    elif state == 'SELECT_SOURCE_SEARCH':
        client = user_data.get(user_id, {}).get('client')
        if client and client.is_connected():
            await search_and_send_channels(event, client, "source", query=text)

    elif state in ['SELECT_DEST', 'SELECT_DEST_SEARCH']:
        client = user_data.get(user_id, {}).get('client')
        action_prefix = "destcust" if state == 'SELECT_DEST_SEARCH' else "dest"
        if client and client.is_connected():
            await search_and_send_channels(event, client, action_prefix, query=text)

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
            days_left = time_left.days if time_left else 0
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Login Successful! (⏳ `{days_left} Days Left`)\n\nAb apna **Sniper Mode** select karein:", buttons=[
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
            days_left = time_left.days if time_left else 0
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply(f"✅ Password Verified! (⏳ `{days_left} Days Left`)\n\nAb apna **Sniper Mode** select karein:", buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
                [Button.inline("🎯 Specific Source Channel (No Pin)", b"mode_source")]
            ])
        except Exception as e:
            await event.reply(f"❌ Password galat hai ya error aayi: {e}\n/start dabakar fir se try karein.")
            user_states[user_id] = None

@master_bot.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    if event.sender_id != MASTER_ID:
        await event.reply("🤖 Bot fully buttonized hai! /start dabakar control panel use karein.")
        return
    msg = ("👑 **MASTER ADMIN PANEL** 👑\n\n"
           "`/addkey <count> <days>` - Naye PINs banayein (Example: `/addkey 5 30`)\n"
           "`/users` - Active users aur unke names dekhein\n"
           "`/ban <user_id>` - User ka access khatam karein")
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
master_bot.start(bot_token=BOT_TOKEN)
master_bot.run_until_disconnected()
