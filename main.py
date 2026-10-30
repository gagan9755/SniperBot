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
    return "🤖 Master Sniper Bot is SECURE and RUNNING 24/7 (Local Storage Mode)!"
def run_server():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run_server).start()

# --- ⚙️ MASTER CONFIGURATION ---
API_ID = 21601452
API_HASH = 'cc8257993f2553fec9f43bcd6b8f79c4'
BOT_TOKEN = '8546884710:AAE8wswEhlG9vadlf22e-X41G1yw6M5iEfM' 

MASTER_ID = 8845438009  # Your Admin ID

master_bot = TelegramClient('master_bot_session', API_ID, API_HASH)

user_states = {}
user_data = {}  
active_snipers_dict = {}

# --- 📁 LOCAL JSON DATABASE SYSTEM (No MongoDB) ---
LICENSES_FILE = "licenses.json"
BOT_DATA_FILE = "bot_data.json"
SESSIONS_FILE = "sessions.json"

def load_json(filepath, default_data):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data

def save_json(filepath, data):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        pass

def load_licenses():
    default = {"keys": {}, "users": {}, "special_keys": {}, "special_users": {}, "settings": {"official_channel": ""}}
    return load_json(LICENSES_FILE, default)

def save_licenses(data):
    save_json(LICENSES_FILE, data)

license_db = load_licenses()

def load_bot_data():
    return load_json(BOT_DATA_FILE, {})

def save_bot_data():
    save_json(BOT_DATA_FILE, bot_db)

bot_db = load_bot_data()

def init_user_db(user_id):
    uid = str(user_id)
    if uid not in bot_db:
        bot_db[uid] = {
            'dest_dict': {}, 'source_dict': {}, 
            'sniper_mode': 'rush', 'lines_count': 4,
            'is_running': False, 'is_paused': False, 
            'edit_catcher': False, 'link_catcher': False,
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

def load_user_session(user_id):
    sessions = load_json(SESSIONS_FILE, {})
    return sessions.get(str(user_id))

def save_user_session(user_id, string_session):
    sessions = load_json(SESSIONS_FILE, {})
    sessions[str(user_id)] = string_session
    save_json(SESSIONS_FILE, sessions)

def delete_user_session(user_id):
    sessions = load_json(SESSIONS_FILE, {})
    if str(user_id) in sessions:
        del sessions[str(user_id)]
        save_json(SESSIONS_FILE, sessions)

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
    if link: 
        return [[Button.url("📢 Join Official Channel", url=link)]]
    return None

def get_official_btn_single():
    link = license_db.get("settings", {}).get("official_channel", "")
    if link: 
        return [Button.url("📢 Join Official Channel", url=link)]
    return []

def get_mode_buttons(user_id):
    btns = [
        [Button.inline("📌 Auto Pinned Chats Mode", b"mode_pinned")],
        [Button.inline("🎯 Specific Source Channel", b"mode_source")],
        [Button.inline("⚡ GOD MODE V2 (Ultimate Clone Engine)", b"mode_god_start")],
        [Button.inline("🔐 Special Code Mode (Secret)", b"mode_special_start")],
        [Button.inline("📂 Saved Presets / Setups", b"list_presets")],
        [Button.inline("📱 Change Phone Number", b"change_phone_prompt")]
    ]
    off_btn = get_official_btn_single()
    if off_btn: btns.append(off_btn)
    return btns

def get_control_buttons(validity_str, uid):
    edit_status = "🟢 ON" if bot_db[str(uid)].get('edit_catcher') else "🔴 OFF"
    link_status = "🟢 ON" if bot_db[str(uid)].get('link_catcher') else "🔴 OFF"
    
    btns = [
        [Button.inline("🔴 Pause Bot", b"ctl_pause"), Button.inline("🟢 Resume Bot", b"ctl_run")],
        [Button.inline(f"👁️ Smart Edit Catcher: {edit_status}", b"toggle_edit_catcher")],
        [Button.inline(f"🔗 Deep Link Catcher: {link_status}", b"toggle_link_catcher")],
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
        [Button.inline("🔐 Gen Special Key (30D)", b"adm_gen_sp_30"), Button.inline("⚙️ Custom Special Key", b"adm_custom_sp_key")],
        [Button.inline("👥 View Special Users", b"adm_special_users"), Button.inline("⚙️ Custom Key (Days/Hours)", b"adm_custom_key")],
        [Button.inline("👥 View Active Users", b"adm_users"), Button.inline("🔗 Set Official Channel", b"adm_set_channel")],
        [Button.inline("🚫 Ban User", b"adm_ban_prompt"), Button.inline("✅ Unban User", b"adm_unban_prompt")],
        [Button.inline("📢 Broadcast Message", b"adm_broadcast")]
    ]

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
                if len(buttons) >= 50: break
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

# --- 🔄 MENU ROUTING HELPERS ---
async def send_format_menu(event, uid):
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

async def send_god_mode_menu(event, uid):
    link = bot_db[uid].get('replacer_link')
    uname = bot_db[uid].get('replacer_username')
    
    msg = "⚡ **GOD MODE V2 Replacer Setup:**\n\n"
    msg += "Kya aap chahte hain ki original message ke @usernames ya links ko aapke custom links se replace kiya jaye?\n"
    msg += "*(Note: Replace karne par Premium Emojis HTML mein convert ho jate hain)*\n\n"
    msg += f"🔗 **Current Link:** `{link}`\n" if link else "🔗 **Current Link:** ❌ Not Set\n"
    msg += f"👤 **Current @User:** `{uname}`\n" if uname else "👤 **Current @User:** ❌ Not Set\n\n"
    
    btns = [
        [Button.inline("🔗 Set Link", b"ask_replacer_link"), Button.inline("🗑️ Remove Link", b"rem_replacer_link")],
        [Button.inline("👤 Set @Username", b"ask_replacer_username"), Button.inline("🗑️ Remove User", b"rem_replacer_username")],
        [Button.inline("🚀 Start GOD MODE V2", b"run_god_0")],
        [Button.inline("🔙 Cancel Setup", b"mode_god_start")]
    ]
    await event.respond(msg, buttons=btns)

# --- ⚡ ULTRA-FAST RUSH MODE EXECUTOR (NO JSON WAIT) ---
async def fast_send_rush(client, target, text):
    try:
        await client.send_message(target, text, parse_mode='md', link_preview=False)
    except Exception:
        pass

# --- 🎯 CORE ENGINE CLASS ---
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
        self.seen_codes_set = set()
        self.seen_codes_queue = deque(maxlen=200)
        self.special_triggered = False 
        
        self.god_msg_map = {}
        self.god_msg_keys = deque(maxlen=2000)
        
        # --- NEW RAM-ONLY STORAGE FOR RUSH MODE ---
        self.rush_processed_ids = deque(maxlen=300)
        self.rush_seen_codes = deque(maxlen=300)
        
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
    
    # 🎯 TARGET CACHING IN RAM FOR ALL MODES
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

    def remove_all_handlers():
        try: client.remove_event_handler(handler)
        except: pass
        try: client.remove_event_handler(edit_handler)
        except: pass
        try: client.remove_event_handler(delete_handler)
        except: pass

    # --- ⚡ NEW ULTRA-FAST RUSH MODE ENGINE ---
    async def process_rush_mode(event):
        if event.id in sniper.rush_processed_ids: return
        
        extracted_codes = []
        for ent, text in event.message.get_entities_text():
            if isinstance(ent, (MessageEntityCode, MessageEntityPre)):
                # Ignore private invite links mistakenly tagged as code
                if re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/(?:joinchat/|\+|c/)', text, re.IGNORECASE): 
                    continue
                if text not in sniper.rush_seen_codes:
                    extracted_codes.append(text)
                    sniper.rush_seen_codes.append(text)
                    
        if not extracted_codes: return
        
        # Add to processed
        sniper.rush_processed_ids.append(event.id)
        
        num = len(extracted_codes)
        lines = [f"{num} Code"]
        if num == 1:
            lines.extend([f"`{extracted_codes[0]}`"] * 3)
        elif num == 2:
            for c in extracted_codes: lines.extend([f"`{c}`", f"`{c}`"])
        else:
            for c in extracted_codes: lines.append(f"`{c}`")
            
        final_msg = "\n".join(lines)
        
        # 🚀 ASYNC TASK DIRECT FIRE (ZERO WAIT, ZERO JSON SAVING)
        for target in sniper.destinations.values():
            asyncio.create_task(fast_send_rush(client, target, final_msg))

    async def process_fast_event(event, is_edit=False):
        if is_edit and event.id in sniper.processed_ids_set: 
            return 
            
        if sniper.sniper_mode == "special":
            if not is_special_authorized(user_id):
                sniper.is_running = False
                bot_db[uid]['is_running'] = False
                save_bot_data()
                if user_id in active_snipers_dict: del active_snipers_dict[user_id]
                try: await master_bot.send_message(user_id, "⚠️ **Aapki Special Key expire ho chuki hai ya authorized nahi hai!**\nSpecial Code mode stop ho gaya hai.")
                except: pass
                return
            if sniper.special_triggered: return

        text_content = event.message.message or ""
        extracted_items = []

        def get_codes_from_msg(msg):
            codes = []
            if sniper.sniper_mode == "link":
                txt = msg.message or ""
                found = re.findall(r'(?:\b|https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?(?:#[^\s]*)?', txt)
                for ent, t in msg.get_entities_text():
                    if isinstance(ent, (types.MessageEntityUrl, types.MessageEntityTextUrl)) and t not in found:
                        found.append(t)
                codes = found
            else:
                for ent, ent_text in msg.get_entities_text():
                    if isinstance(ent, (MessageEntityCode, MessageEntityPre)):
                        if re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/(?:joinchat/|\+|c/)', ent_text, re.IGNORECASE): 
                            continue
                        if ent_text not in codes: codes.append(ent_text)
            return codes

        extracted_items.extend(get_codes_from_msg(event.message))

        if bot_db[uid].get('link_catcher'):
            link_pattern = r'(?:https?://)?(?:t\.me|telegram\.me)/(?:c/(\d+)/(\d+)|([a-zA-Z0-9_]+)/(\d+))'
            for match in re.finditer(link_pattern, text_content):
                try:
                    c_id = int("-100" + match.group(1)) if match.group(1) else match.group(3)
                    m_id = int(match.group(2) if match.group(1) else match.group(4))
                    f_msg = await client.get_messages(c_id, ids=m_id)
                    if f_msg: extracted_items.extend(get_codes_from_msg(f_msg))
                except: pass

        final_codes = []
        for c in extracted_items:
            if c not in sniper.seen_codes_set:
                final_codes.append(c)

        if not final_codes: return
        
        sniper.processed_ids_set.add(event.id)
        for c in final_codes:
            sniper.seen_codes_queue.append(c)
            sniper.seen_codes_set.add(c)

        messages_to_send = []
        
        if sniper.sniper_mode == "special":
            c = final_codes[0]
            body_text = "\n".join([f"`{c}`"] * sniper.lines_count)
            messages_to_send.append({'text': body_text, 'is_special': True})
            sniper.special_triggered = True
            
        else:
            for c in final_codes: 
                body_text = "\n".join([f"`{c}`"] * sniper.lines_count)
                final_text = ""
                if bot_db[uid].get('custom_header'): final_text += bot_db[uid]['custom_header'] + "\n\n"
                final_text += body_text
                if bot_db[uid].get('custom_footer'): final_text += "\n\n" + bot_db[uid]['custom_footer']
                messages_to_send.append({'text': final_text})

        async def send_dest(target):
            for item in messages_to_send:
                try:
                    sent_msg = await client.send_message(target, item['text'], parse_mode='md', link_preview=False)
                    timer_sec = bot_db[uid].get('over_timer', 0)
                    if timer_sec > 0 and not item.get('is_special'):
                        custom_over = bot_db[uid].get('over_text', "❌️❌️ OVER ❌️❌️")
                        asyncio.create_task(auto_over_message(client, target, sent_msg.id, timer_sec, custom_over))
                except: pass

        tasks = [send_dest(target) for target in sniper.destinations.values()]
        await asyncio.gather(*tasks)
        
        bot_db[uid]['stats']['forwarded'] += 1
        save_bot_data()

        if sniper.sniper_mode == "special" and sniper.special_triggered:
            sniper.is_running = False
            bot_db[uid]['is_running'] = False
            save_bot_data()
            if user_id in active_snipers_dict: del active_snipers_dict[user_id]
            try: await master_bot.send_message(user_id, "🎯 **1st Special Code successfully forwarded!**\n\nBot automatically stop ho gaya hai.")
            except: pass

    async def process_god_mode(event):
        if event.id in sniper.processed_ids_set: return
        sniper.processed_ids_set.add(event.id)
        
        text_content = event.message.message or ""
        if not text_content and not event.message.media: return
            
        replacer_link = bot_db[uid].get('replacer_link')
        replacer_uname = bot_db[uid].get('replacer_username')
        reply_to_id = event.message.reply_to_msg_id
        
        sent_msgs_this_event = {}
        
        async def send_god_dest(d_id, target):
            try:
                reply_obj = None
                if reply_to_id and reply_to_id in sniper.god_msg_map:
                    dest_reply_id = sniper.god_msg_map[reply_to_id].get(d_id)
                    if dest_reply_id: reply_obj = dest_reply_id
                
                kwargs = {'link_preview': True}
                if reply_obj: kwargs['reply_to'] = reply_obj
                if event.message.media: kwargs['file'] = event.message.media

                if not replacer_link and not replacer_uname:
                    kwargs['formatting_entities'] = event.message.entities
                    sent_msg = await client.send_message(target, text_content, **kwargs)
                else:
                    try: msg_html = html.unparse(text_content, event.message.entities)
                    except: msg_html = text_content
                    if replacer_link: 
                        msg_html = re.sub(r'(https?://)?t\.me/\+[a-zA-Z0-9_-]+', replacer_link, msg_html)
                        msg_html = re.sub(r'(https?://)?t\.me/joinchat/[a-zA-Z0-9_-]+', replacer_link, msg_html)
                    if replacer_uname: 
                        msg_html = safe_replace_username(msg_html, replacer_uname)
                    kwargs['parse_mode'] = 'html'
                    sent_msg = await client.send_message(target, msg_html, **kwargs)
                
                if sent_msg: return d_id, sent_msg.id
            except: pass
            return None

        tasks = [send_god_dest(d_id, target) for d_id, target in sniper.destinations.items()]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res: sent_msgs_this_event[res[0]] = res[1]

        if sent_msgs_this_event:
            if len(sniper.god_msg_keys) >= 2000:
                old_id = sniper.god_msg_keys.popleft()
                sniper.god_msg_map.pop(old_id, None)
            sniper.god_msg_keys.append(event.id)
            sniper.god_msg_map[event.id] = sent_msgs_this_event
            bot_db[uid]['stats']['forwarded'] += 1
            save_bot_data()

    @client.on(events.NewMessage())
    async def handler(event):
        if not sniper.is_running: return
        if not check_subscription(user_id):
            sniper.is_running = False
            remove_all_handlers()
            return
        if sniper.is_paused or not sniper.destinations: return
        
        if sniper.source_chat_ids:
            if event.chat_id not in sniper.source_chat_ids: return
        else:
            if event.chat_id not in sniper.pinned_chats: return

        # ⚡ ROUTING TO RUSH OR OTHER MODES
        if sniper.sniper_mode == 'rush':
            await process_rush_mode(event)
        elif sniper.sniper_mode == 'god':
            await process_god_mode(event)
        else:
            await process_fast_event(event, is_edit=False)

    @client.on(events.MessageEdited())
    async def edit_handler(event):
        if not sniper.is_running or sniper.is_paused: return
        if sniper.sniper_mode == 'rush': return # Rush mode me edit catch karne ka load hata diya
        
        if sniper.source_chat_ids:
            if event.chat_id not in sniper.source_chat_ids: return
        else:
            if event.chat_id not in sniper.pinned_chats: return

        if sniper.sniper_mode == 'god':
            if event.id not in sniper.god_msg_map: return
            text_content = event.message.message or ""
            replacer_link = bot_db[uid].get('replacer_link')
            replacer_uname = bot_db[uid].get('replacer_username')
            
            try:
                if not replacer_link and not replacer_uname:
                    for d_id, dest_msg_id in sniper.god_msg_map[event.id].items():
                        target = sniper.destinations.get(int(d_id))
                        if target:
                            await client.edit_message(target, dest_msg_id, text=text_content, file=event.message.media, formatting_entities=event.message.entities)
                else:
                    try: msg_html = html.unparse(text_content, event.message.entities)
                    except: msg_html = text_content
                    if replacer_link: 
                        msg_html = re.sub(r'(https?://)?t\.me/\+[a-zA-Z0-9_-]+', replacer_link, msg_html)
                        msg_html = re.sub(r'(https?://)?t\.me/joinchat/[a-zA-Z0-9_-]+', replacer_link, msg_html)
                    if replacer_uname: 
                        msg_html = safe_replace_username(msg_html, replacer_uname)
                    
                    for d_id, dest_msg_id in sniper.god_msg_map[event.id].items():
                        target = sniper.destinations.get(int(d_id))
                        if target: await client.edit_message(target, dest_msg_id, text=msg_html, parse_mode='html', file=event.message.media)
            except: pass
            
        elif bot_db[uid].get('edit_catcher'):
            await process_fast_event(event, is_edit=True)

    @client.on(events.MessageDeleted())
    async def delete_handler(event):
        if sniper.sniper_mode != 'god': return 
        if not sniper.is_running or sniper.is_paused: return
        
        for deleted_id in event.deleted_ids:
            if deleted_id in sniper.god_msg_map:
                for d_id, dest_msg_id in sniper.god_msg_map[deleted_id].items():
                    target = sniper.destinations.get(int(d_id))
                    if target:
                        try: await client.delete_messages(target, dest_msg_id)
                        except: pass

    try:
        time_left = get_time_left(user_id)
        validity_str = format_time_left(time_left)
        mode_text = f"Multiple Sources ({len(source_chat_ids)})" if source_chat_ids else "Auto Pinned Chats"
        lines_info = f" ({sniper.lines_count} Lines)" if sniper.sniper_mode not in ["rush", "god", "special"] else ""
        mode_name = "🔐 SPECIAL" if sniper.sniper_mode == "special" else "⚡ GOD V2" if sniper.sniper_mode == "god" else sniper.sniper_mode.capitalize()
        await master_bot.send_message(
            user_id, 
            f"✅ **SNIPER ACTIVE!** 🎯\n\n🟢 **Target Mode:** {mode_text}\n🛠 **Forwarding:** `{mode_name} Mode{lines_info}`\n🚀 **Destinations:** `{len(sniper.destinations)}`\n⏳ **Validity:** `{validity_str}`", 
            buttons=get_control_buttons(validity_str, user_id)
        )
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
            session_str = load_user_session(user_id)
            client = TelegramClient(StringSession(session_str) if session_str else f'session_{user_id}', API_ID, API_HASH)
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
                await event.reply(f"{status_txt}\n\n⏳ **Validity:** `{validity_str}`\nApna bot control karne ke liye niche buttons use karein:", buttons=get_control_buttons(validity_str, user_id))
                return

            session_str = load_user_session(user_id)
            client = user_data.get(user_id, {}).get('client')
            if not client:
                client = TelegramClient(StringSession(session_str) if session_str else f'session_{user_id}', API_ID, API_HASH)
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
            btn_row = get_official_btn_row()
            await event.reply(
                "⚠️ **Aapki purani Key Expire ho chuki hai!**\n\nKripya apni **Nayi License Key (PIN)** yahan bhejein:", 
                buttons=btn_row if btn_row else None
            )
            return

    user_states[user_id] = 'WAITING_KEY'
    btn_row = get_official_btn_row()
    await event.reply(
        "🔒 **Ye bot sirf authorized users ke liye hai.**\n\nKripya apni **License Key (PIN)** yahan bhejein:", 
        buttons=btn_row if btn_row else None
    )

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
    uid = str(user_id)
    init_user_db(user_id)

    try: await event.delete()
    except: pass

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
            await event.respond(f"🔐 **1 New Special Key (30 Days) Generated:**\n\n`{skey}`", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            return
        elif data == "adm_custom_sp_key":
            user_states[user_id] = 'WAITING_CUSTOM_SP_KEY'
            await event.respond("⚙️ **Custom Special Key:**\nFormat: `<count> <time>`", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
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
            await event.respond("⚙️ **Custom Key:**\nFormat: `<count> <time>`", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
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

    if data == "ctl_pause":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = True
        bot_db[uid]['is_paused'] = True
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.respond(f"🟡 **BOT IS PAUSED (OFF)**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str, user_id))
    
    elif data == "ctl_run":
        if user_id in active_snipers_dict: active_snipers_dict[user_id].is_paused = False
        bot_db[uid]['is_paused'] = False
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.respond(f"🟢 **BOT IS ON**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str, user_id))

    elif data == "toggle_edit_catcher":
        bot_db[uid]['edit_catcher'] = not bot_db[uid].get('edit_catcher', False)
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.respond(f"✅ **Smart Edit Catcher Toggled!**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str, user_id))

    elif data == "toggle_link_catcher":
        bot_db[uid]['link_catcher'] = not bot_db[uid].get('link_catcher', False)
        save_bot_data()
        validity_str = format_time_left(get_time_left(user_id))
        await event.respond(f"✅ **Deep Link Catcher Toggled!**\n\n⏳ **Validity:** `{validity_str}`", buttons=get_control_buttons(validity_str, user_id))

    elif data == "save_current_preset":
        prompt_msg = await event.respond("💾 **Save Preset:**\n\nApne is setup ke liye ek pyara sa **Name** type karke bhejein:", buttons=[[Button.inline("🔙 Back", b"back_to_mode")]])
        user_states[user_id] = {'state': 'WAITING_PRESET_NAME', 'prompt_id': prompt_msg.id}
        return

    elif data == "list_presets":
        presets = bot_db[uid].get('presets', {})
        if not presets:
            await event.respond("📂 **Aapke paas koi saved preset nahi hai!**", buttons=[[Button.inline("🔙 Back", b"back_to_mode")]])
            return
        btns = []
        for pname in presets.keys():
            btns.append([Button.inline(f"📂 Load: {pname}", f"load_preset:{pname}".encode()), Button.inline(f"❌ Delete", f"del_preset:{pname}".encode())])
        btns.append([Button.inline("🔙 Back", b"back_to_mode")])
        await event.respond("📂 **Aapke Saved Presets:**", buttons=btns)
        return

    elif data.startswith("load_preset:"):
        pname = data.split(":")[1]
        presets = bot_db[uid].get('presets', {})
        if pname in presets:
            pdata = presets[pname]
            bot_db[uid]['dest_dict'] = dict(pdata.get('dest_dict', {}))
            bot_db[uid]['source_dict'] = dict(pdata.get('source_dict', {}))
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
                await event.respond("❌ Is preset ke liye Special Key required hai!")
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
            if not presets:
                await event.respond("📂 **Aapke paas koi saved preset nahi hai!**", buttons=[[Button.inline("🔙 Back", b"back_to_mode")]])
            else:
                btns = []
                for pn in presets.keys():
                    btns.append([Button.inline(f"📂 Load: {pn}", f"load_preset:{pn}".encode()), Button.inline(f"❌ Delete", f"del_preset:{pn}".encode())])
                btns.append([Button.inline("🔙 Back", b"back_to_mode")])
                await event.respond("📂 **Aapke Saved Presets:**", buttons=btns)
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
        await event.respond(f"🔄 **Setup Restarted!**\n\n🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))

    elif data == "change_phone_prompt":
        await event.respond(
            "⚠️ **Dhyan Dein:**\nKya aap sach mein apna phone number change karna chahte hain? Isse aapka current session delete ho jayega.",
            buttons=[
                [Button.inline("✅ Yes, Change Number", b"confirm_change_phone")],
                [Button.inline("❌ No, Cancel", b"back_to_mode")]
            ]
        )

    elif data == "confirm_change_phone":
        client = user_data.get(user_id, {}).get('client')
        if client:
            try: await client.log_out()
            except: pass
        delete_user_session(user_id)
        user_states[user_id] = 'WAITING_PHONE'
        await event.respond("✅ **Session Deleted!**\n\n📱 Kripya apna naya **Telegram Phone Number** bhejein:")

    elif data == "back_to_mode":
        user_states[user_id] = 'CHOOSE_MODE'
        await event.respond(f"🎯 Target Mode select karein:", buttons=get_mode_buttons(user_id))

    elif data == "mode_special_start":
        if not is_special_authorized(user_id):
            prompt_msg = await event.respond(
                "🔐 **Special Code Mode:**\n\nKripya apni Special Key yahan bhejein:",
                buttons=[[Button.inline("🔙 Back", b"back_to_mode")]]
            )
            user_states[user_id] = {'state': 'WAITING_SPECIAL_KEY', 'prompt_id': prompt_msg.id}
            return

        await event.respond(
            "🔐 **Special Code Mode Setup:**",
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
                await event.respond("🎯 **Special Code Mode:**\n📥 Apna Source Channel select karein\n*(Ya channel ka naam type karein / message forward karein):*", buttons=buttons)
        else:
            user_states[user_id] = {'state': 'SELECT_DEST_SP'}
            client = user_data.get(user_id, {}).get('client')
            if client and client.is_connected():
                buttons = await get_channel_buttons(client, "add_dest_sp", require_admin=True)
                buttons.append([Button.inline("🔙 Back", b"mode_special_start")])
                await event.respond("🎯 **Special Code Mode:**\n📌 Apna Destination Channel select karein\n*(Ya channel ka naam type karein):*", buttons=buttons)

    elif data == "mode_god_start":
        await event.respond(
            "⚡ **GOD MODE V2 Setup:**",
            buttons=[
                [Button.inline("📌 Auto Pinned Chats Mode", b"god_mode_pinned")],
                [Button.inline("🎯 Specific Source Channel", b"god_mode_source")],
                [Button.inline("🔙 Back", b"back_to_mode")]
            ]
        )

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
            title_prefix = "⚡ GOD MODE V2: " if is_god else ""
            await event.respond(f"{title_prefix}📌 **Pinned Mode:**\n🎯 Apna Destination select karein\n*(Ya channel ka naam type karein):*", buttons=buttons)
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
            title_prefix = "⚡ GOD MODE V2: " if is_god else ""
            await event.respond(f"{title_prefix}🎯 **Specific Source Mode:**\n📥 Apna Source select karein\n*(Ya channel ka naam type karein / message forward karein):*", buttons=buttons)
        else: await event.respond("📱 Pehle apna Telegram Phone Number bhejein:")

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
        await event.respond("🎯 Agla **PINNED Source Channel** select karein\n*(Ya naam type karein / message forward karein):*", buttons=buttons)

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
            "📏 **Special Code Mode - Line Settings:**",
            buttons=[
                [Button.inline("1 Line", b"run_special_1"), Button.inline("2 Lines", b"run_special_2")],
                [Button.inline("3 Lines", b"run_special_3"), Button.inline("4 Lines", b"run_special_4")],
                [Button.inline("🔙 Back", b"mode_special_start")]
            ]
        )

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
        src_buttons.append([Button.inline("🔙 Back", b"god_mode_source" if is_god else b"mode_source")])
        await event.respond(src_msg, buttons=src_buttons)

    elif data == "more_source":
        user_states[user_id] = {'state': 'SELECT_SOURCES'}
        client = user_data.get(user_id, {}).get('client')
        is_god = (bot_db[uid].get('setup_type') == 'god')
        buttons = await get_channel_buttons(client, "add_source", pinned_only=True)
        buttons.append([Button.inline("🔙 Back", b"god_mode_source" if is_god else b"mode_source")])
        await event.respond("🎯 Agla **PINNED Source Channel** select karein\n*(Ya naam type karein / message forward karein):*", buttons=buttons)

    elif data == "done_sources":
        user_states[user_id] = {'state': 'SELECT_DEST_CUSTOM'}
        client = user_data.get(user_id, {}).get('client')
        is_god = (bot_db[uid].get('setup_type') == 'god')
        buttons = await get_channel_buttons(client, "add_destcust", require_admin=True)
        buttons.append([Button.inline("🔙 Back", b"god_mode_source" if is_god else b"mode_source")])
        await event.respond("🎯 **Sources Saved!**\n\nAb **Destination Channel** select karein:", buttons=buttons)

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
                dest_buttons.append([Button.inline("🚀 Next: GOD MODE V2 Settings", b"setup_god_mode")])
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

    elif data == "select_fwd_mode":
        await event.respond(
            "🛠 **Sniper Forwarding Mode:**",
            buttons=[
                [Button.inline("🚀 Start Rush Mode (Ultra Fast)", b"run_rush_0")], 
                [Button.inline("🟢 Normal Mode", b"ask_lines_normal")],
                [Button.inline("🔗 Link Forwarder", b"ask_lines_link")],
                [Button.inline("🔙 Back", b"back_to_mode")]
            ]
        )

    elif data.startswith("ask_lines_"):
        mode = data.split("_")[2]
        await event.respond(
            f"📏 **{mode.capitalize()} Mode - Line Settings:**",
            buttons=[
                [Button.inline("1 Line", f"format_{mode}_1".encode()), Button.inline("2 Lines", f"format_{mode}_2".encode())],
                [Button.inline("3 Lines", f"format_{mode}_3".encode()), Button.inline("4 Lines", f"format_{mode}_4".encode())],
                [Button.inline("🔙 Back", b"select_fwd_mode")]
            ]
        )

    elif data.startswith("format_"):
        parts = data.split("_")
        mode_cache = parts[1]
        lines_cache = int(parts[2])
        bot_db[uid]['setup_mode_cache'] = mode_cache
        bot_db[uid]['setup_lines_cache'] = lines_cache
        save_bot_data()
        
        await event.respond(
            "⏱️ **Auto-Over Timer Setup:**\n*(Note: Timer is bypassed for Rush Mode)*",
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
        await send_format_menu(event, uid)

    elif data == "show_format_menu":
        await send_format_menu(event, uid)

    elif data == "rem_header":
        bot_db[uid]['custom_header'] = None
        save_bot_data()
        await event.answer("Header Removed!", alert=True)
        await send_format_menu(event, uid)
        
    elif data == "rem_footer":
        bot_db[uid]['custom_footer'] = None
        save_bot_data()
        await event.answer("Footer Removed!", alert=True)
        await send_format_menu(event, uid)

    elif data == "ask_header":
        prompt_msg = await event.respond("🔝 **Send Custom Header:**", buttons=[[Button.inline("🔙 Cancel", b"show_format_menu")]])
        user_states[user_id] = {'state': 'WAITING_HEADER', 'prompt_id': prompt_msg.id}
        
    elif data == "ask_footer":
        prompt_msg = await event.respond("🔚 **Send Custom Footer:**", buttons=[[Button.inline("🔙 Cancel", b"show_format_menu")]])
        user_states[user_id] = {'state': 'WAITING_FOOTER', 'prompt_id': prompt_msg.id}

    elif data == "ask_over_text":
        prompt_msg = await event.respond("✏️ **Send Custom Over Text:**", buttons=[[Button.inline("🔙 Cancel", b"show_format_menu")]])
        user_states[user_id] = {'state': 'WAITING_OVER_TEXT', 'prompt_id': prompt_msg.id}

    elif data == "setup_god_mode":
        await send_god_mode_menu(event, uid)

    elif data == "rem_replacer_link":
        bot_db[uid]['replacer_link'] = None
        save_bot_data()
        await event.answer("Link Removed!", alert=True)
        await send_god_mode_menu(event, uid)

    elif data == "rem_replacer_username":
        bot_db[uid]['replacer_username'] = None
        save_bot_data()
        await event.answer("Username Removed!", alert=True)
        await send_god_mode_menu(event, uid)

    elif data == "ask_replacer_link":
        prompt_msg = await event.respond("🔗 **Send Custom Link:**", buttons=[[Button.inline("🔙 Cancel", b"setup_god_mode")]])
        user_states[user_id] = {'state': 'WAITING_CLONE_LINK', 'prompt_id': prompt_msg.id}

    elif data == "ask_replacer_username":
        prompt_msg = await event.respond("👤 **Send Custom @Username:**", buttons=[[Button.inline("🔙 Cancel", b"setup_god_mode")]])
        user_states[user_id] = {'state': 'WAITING_CLONE_USERNAME', 'prompt_id': prompt_msg.id}

    elif data.startswith("run_"):
        parts = data.split("_")
        sniper_mode, lines_count = parts[1], int(parts[2])
        client = user_data.get(user_id, {}).get('client')
        dest_list = list(bot_db[uid]['dest_dict'].keys())
        src_keys = list(bot_db[uid]['source_dict'].keys())
        source_list = [int(s) for s in src_keys] if src_keys else None
        mode_disp = "🔐 Special Code" if sniper_mode == "special" else "⚡ GOD V2" if sniper_mode == "god" else sniper_mode.capitalize()
        await event.respond(f"🚀 **Sniper Bot Start ho raha hai [{mode_disp} Mode]...**")
        await start_sniper_for_user(user_id, client, dest_list, "User", source_list, sniper_mode, lines_count)

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
            for u_id in license_db["users"].keys():
                try:
                    await master_bot.send_message(int(u_id), f"📢 **Admin Message:**\n\n{text}")
                    msg_count += 1
                except: pass
            user_states[user_id] = None
            await event.reply(f"✅ **Broadcast Successful!** Sent to {msg_count} users.", buttons=[[Button.inline("🔙 Back", b"adm_back")]])
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
            except: await event.reply("⚠️ Format Error!", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return
        elif state == 'WAITING_CUSTOM_SP_KEY':
            try:
                parts = text.lower().split()
                count, time_str = int(parts[0]), parts[1]
                hours = int(time_str[:-1]) if time_str.endswith('h') else 0
                days = int(time_str[:-1]) if time_str.endswith('d') else int(time_str) if not hours else 0
                generated = [f"`{generate_special_key(days=days, hours=hours)}`" for _ in range(count)]
                user_states[user_id] = None
                await event.reply(f"🔐 **{count} New Special Keys Generated:**\n\n" + "\n".join(generated), buttons=[[Button.inline("🔙 Back", b"adm_back")]])
            except: await event.reply("⚠️ Format Error!", buttons=[[Button.inline("🔙 Cancel", b"adm_back")]])
            return

    is_waiting_special = False
    if isinstance(state, dict) and state.get('state') == 'WAITING_SPECIAL_KEY':
        is_waiting_special = True

    if is_waiting_special:
        clean_text = text.strip()
        if clean_text in license_db["special_keys"]:
            sk_info = license_db["special_keys"][clean_text]
            if sk_info["used_by"] and str(sk_info["used_by"]) != str(user_id):
                await event.reply("❌ Ye Special Key pehle hi use ho chuki hai!")
                return
            license_db["special_keys"][clean_text]["used_by"] = user_id
            license_db["special_users"][uid] = {"key": clean_text, "expires": sk_info["expires"]}
            save_licenses(license_db)
            user_states[user_id] = None
            try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
            except: pass
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
        await event.respond(f"✅ **Preset '{pname}' Saved!**", buttons=[[Button.inline("📂 View Presets", b"list_presets"), Button.inline("🔙 Back", b"back_to_mode")]])
        return

    if isinstance(state, dict) and state.get('state') in ['SELECT_SOURCES', 'SELECT_SOURCES_SP']:
        client = user_data.get(user_id, {}).get('client')
        if not client: return
        
        st = state.get('state')
        action_prefix = "add_source_sp" if st == 'SELECT_SOURCES_SP' else "add_source"
        
        forwarded_chat_id = None
        forwarded_chat_title = None
        
        fwd = getattr(event.message, 'forward', None)
        if fwd:
            if getattr(fwd, 'chat', None):
                forwarded_chat_id = fwd.chat.id
                forwarded_chat_title = getattr(fwd.chat, 'title', None) or getattr(fwd.chat, 'username', 'Source Channel')
            elif getattr(fwd, 'from_id', None):
                from_id = fwd.from_id
                if isinstance(from_id, PeerChannel):
                    forwarded_chat_id = from_id.channel_id
                elif isinstance(from_id, PeerChat):
                    forwarded_chat_id = -from_id.chat_id

        if not forwarded_chat_id and fwd:
            try:
                if hasattr(fwd, 'saved_from_peer') and fwd.saved_from_peer:
                    resolved = await client.get_entity(fwd.saved_from_peer)
                    forwarded_chat_id = resolved.id
                    forwarded_chat_title = getattr(resolved, 'title', 'Source Channel')
            except Exception: pass

        if not forwarded_chat_id and hasattr(event.message, 'fwd_from') and event.message.fwd_from:
            try:
                fwd_from = event.message.fwd_from
                if hasattr(fwd_from, 'from_id') and fwd_from.from_id:
                    resolved = await client.get_entity(fwd_from.from_id)
                    forwarded_chat_id = resolved.id
                    forwarded_chat_title = getattr(resolved, 'title', 'Source Channel')
            except Exception: pass

        if forwarded_chat_id:
            if not str(forwarded_chat_id).startswith("-100") and abs(forwarded_chat_id) < 1000000000000:
                full_dest_id = int(f"-100{abs(forwarded_chat_id)}")
            else:
                full_dest_id = forwarded_chat_id

            if not forwarded_chat_title:
                try:
                    ent = await client.get_entity(full_dest_id)
                    forwarded_chat_title = getattr(ent, 'title', 'Source Channel')
                except:
                    forwarded_chat_title = "Source Channel"

            bot_db[uid]['source_dict'][str(full_dest_id)] = forwarded_chat_title[:15]
            save_bot_data()
            
            src_msg = "✅ **Selected Source Channels:**\n"
            src_buttons = []
            for sid, sname in bot_db[uid]['source_dict'].items():
                src_msg += f"• `{sname}`\n"
                src_buttons.append([Button.inline(f"❌ Remove {sname}", f"{action_prefix.replace('add', 'rem')}:{sid}".encode())])
                
            src_buttons.append([Button.inline("➕ Add More Source", b"more_source_sp" if 'SP' in st else b"more_source")])
            src_buttons.append([Button.inline("🎯 Done, Select Destination", b"done_sources_sp" if 'SP' in st else b"done_sources")])
            src_buttons.append([Button.inline("🔙 Back", b"mode_special_start" if 'SP' in st else b"back_to_mode")])
            
            await event.reply(f"✅ **Source Channel Auto-Added:** `{forwarded_chat_title}`\n\n{src_msg}", buttons=src_buttons)
            return

        raw_query = text.lower()
        query = re.sub(r'[^\w\s]', '', raw_query).strip()
        if not query: query = raw_query

        try:
            dialogs = await client.get_dialogs(limit=1000)
            buttons = []
            for d in dialogs:
                if d.is_channel or d.is_group:
                    name = d.name if d.name else "Unnamed"
                    uname = getattr(d.entity, 'username', '') or ''
                    clean_name = re.sub(r'[^\w\s]', '', name.lower()).strip()
                    
                    if query in clean_name or query in name.lower() or query in uname.lower() or any(word in clean_name for word in query.split()):
                        buttons.append([Button.inline(name[:20], data=f"{action_prefix}:{d.id}:{name[:15]}")])
                        if len(buttons) >= 15: break
            
            if buttons:
                back_rt = b"mode_special_start" if 'SP' in st else b"back_to_mode"
                buttons.append([Button.inline("🔙 Back", back_rt)])
                await event.respond(f"🔍 **Search Results for '{text}':**\nSelect your channel below:", buttons=buttons)
            else:
                await event.respond(f"❌ Koi channel nahi mila '{text}' ke naam se. Aap chahe toh us channel ka koi message yahan **forward** bhi kar sakte hain!")
        except Exception:
            pass
        return

    if isinstance(state, dict) and state.get('state') in ['SELECT_DEST', 'SELECT_DEST_CUSTOM', 'SELECT_DEST_SP']:
        client = user_data.get(user_id, {}).get('client')
        if not client: return
        
        raw_query = text.lower()
        query = re.sub(r'[^\w\s]', '', raw_query).strip()
        if not query: query = raw_query

        st = state.get('state')
        if st == 'SELECT_DEST_SP': action_prefix = "add_dest_sp"
        elif st == 'SELECT_DEST_CUSTOM': action_prefix = "add_destcust"
        else: action_prefix = "add_dest"
        
        try:
            dialogs = await client.get_dialogs(limit=1000)
            buttons = []
            for d in dialogs:
                if d.is_channel or d.is_group:
                    if not (getattr(d.entity, 'creator', False) or getattr(d.entity, 'admin_rights', None)): continue
                    name = d.name if d.name else "Unnamed"
                    uname = getattr(d.entity, 'username', '') or ''
                    clean_name = re.sub(r'[^\w\s]', '', name.lower()).strip()
                    
                    if query in clean_name or query in name.lower() or query in uname.lower():
                        buttons.append([Button.inline(name[:20], data=f"{action_prefix}:{d.id}:{name[:15]}")])
                        if len(buttons) >= 15: break
            
            if buttons:
                back_rt = b"mode_special_start" if 'SP' in st else b"back_to_mode"
                buttons.append([Button.inline("🔙 Back", back_rt)])
                await event.respond(f"🔍 **Search Results for '{text}':**\nSelect your channel below:", buttons=buttons)
            else:
                await event.respond(f"❌ Koi destination channel nahi mila '{text}' ke naam se.")
        except Exception: pass
        return

    if isinstance(state, dict) and state.get('state') in ['WAITING_HEADER', 'WAITING_FOOTER', 'WAITING_OVER_TEXT']:
        st = state.get('state')
        if st == 'WAITING_HEADER': bot_db[uid]['custom_header'] = text
        elif st == 'WAITING_FOOTER': bot_db[uid]['custom_footer'] = text
        else: bot_db[uid]['over_text'] = text
        save_bot_data()
        
        try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
        except: pass
        user_states[user_id] = None
        
        await send_format_menu(event, uid)
        return

    if isinstance(state, dict) and state.get('state') in ['WAITING_CLONE_LINK', 'WAITING_CLONE_USERNAME']:
        is_link = state.get('state') == 'WAITING_CLONE_LINK'
        if is_link: bot_db[uid]['replacer_link'] = text
        else:
            if not text.startswith('@'): text = '@' + text
            bot_db[uid]['replacer_username'] = text
        save_bot_data()
        try: await master_bot.delete_messages(user_id, [state.get('prompt_id'), event.id])
        except: pass
        user_states[user_id] = None
        await send_god_mode_menu(event, uid)
        return

    if state == 'WAITING_KEY':
        if text in license_db["keys"]:
            k_info = license_db["keys"][text]
            if k_info["used_by"] and k_info["used_by"] != user_id:
                await event.reply("❌ Ye key use ho chuki hai!")
                return
            license_db["keys"][text]["used_by"] = user_id
            license_db["users"][str(user_id)] = {"name": event.sender.first_name, "key": text, "expires": k_info["expires"]}
            save_licenses(license_db)
            
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id]['client'] = client
            user_states[user_id] = 'WAITING_PHONE'
            await event.reply("✅ **Key Verified!**\n\n📱 Apna **Telegram Phone Number** bhejein (jaise +91...):")
        else: await event.reply("❌ **Invalid Key!**")

    elif state == 'WAITING_PHONE':
        user_states[user_id] = {'state': 'WAITING_OTP', 'phone': text}
        await event.reply("🔄 OTP bhej rahe hain...")
        try:
            client = TelegramClient(
                StringSession(), 
                API_ID, 
                API_HASH,
                device_model="iPhone 14 Pro Max",
                system_version="iOS 16.5",
                app_version="10.1.1"
            )
            await client.connect()
            sent = await client.send_code_request(text)
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id].update({'client': client, 'phone_code_hash': sent.phone_code_hash})
            await event.reply("✅ OTP aapke Telegram app par bhej diya gaya hai!\n\nKripya apna OTP yahan type karein:")
        except Exception as e:
            await event.reply(f"❌ Error: {e}\n\nKripya apna number sahi format mein bhejein (jaise +91...).")
            user_states[user_id] = 'WAITING_PHONE'

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        try:
            client = user_data[user_id]['client']
            await client.sign_in(phone=state['phone'], code=text, phone_code_hash=user_data[user_id]['phone_code_hash'])
            
            session_string = client.session.save()
            save_user_session(user_id, session_string)
            
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply("✅ Login Successful! (Session Saved Locally 💾)", buttons=get_mode_buttons(user_id))
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'WAITING_PASSWORD'}
            await event.reply("🔒 2-Step Verification Password bhejein:")
        except Exception as e:
            await event.reply(f"❌ OTP Error: {e}\nSahi OTP dobara type karein:")

    elif isinstance(state, dict) and state.get('state') == 'WAITING_PASSWORD':
        try:
            client = user_data[user_id]['client']
            await client.sign_in(password=text)
            
            session_string = client.session.save()
            save_user_session(user_id, session_string)
            
            user_states[user_id] = 'CHOOSE_MODE'
            await event.reply("✅ Password Verified! (Session Saved Locally 💾)", buttons=get_mode_buttons(user_id))
        except Exception as e:
            await event.reply(f"❌ Password Error: {e}")

print("👑 Ultimate Master Bot V2 Initialized Successfully (Local Storage Mode)!")
master_bot.start(bot_token=BOT_TOKEN)
master_bot.loop.create_task(auto_resume_snipers())
master_bot.run_until_disconnected()
