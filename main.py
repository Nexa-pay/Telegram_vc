import uvloop
import asyncio
import json
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID
from utils.keyboard import admin_panel_keyboard, cancel_keyboard
from database import count_sessions, add_session
from services.account_manager import request_otp, submit_otp_and_save
from services.vc_manager import join_all_vc
from services.auto_watcher import register_auto_watcher
from services.engagement import blast_views, blast_reactions, blast_comments

# 1. Install uvloop for high performance asynchronous operations
uvloop.install()

# 2. Fix for Python 3.11+ / Pyrogram v2: Create and set the event loop manually
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

bot = Client(
    "EngagementBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# State manager for conversations (OTP handling & Engagement prompts)
user_states = {}

@bot.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start_cmd(client, message):
    user_states[message.from_user.id] = None # Reset state
    sessions = await count_sessions()
    await message.reply(
        "<b><emoji id=5310129635848103696>⚙️</emoji> Admin Dashboard</b>\n\nManage your accounts, engagement, and Voice Chats.",
        reply_markup=admin_panel_keyboard(sessions)
    )

@bot.on_callback_query(filters.user(OWNER_ID))
async def callback_handler(client, query):
    data = query.data
    user_id = query.from_user.id
    
    if data == "add_otp":
        user_states[user_id] = {"step": "ask_phone"}
        await query.message.reply(
            "Please send the phone number in international format (e.g., +1234567890)\n\n"
            "<i>Or, send a Pyrogram String Session directly as text, or upload a .txt/.json file containing it.</i>", 
            reply_markup=cancel_keyboard()
        )
    
    elif data == "join_vc":
        user_states[user_id] = {"step": "ask_vc_chat_id"}
        await query.message.reply("Send the Chat ID or Username where accounts should join the Voice Chat:", reply_markup=cancel_keyboard())
        
    elif data == "boost_views":
        user_states[user_id] = {"step": "ask_view_url"}
        await query.message.reply("Forward the message here OR send the Channel ID and Message ID (e.g., `-10012345678 152`):", reply_markup=cancel_keyboard())

    elif data == "boost_reacts":
        user_states[user_id] = {"step": "ask_react_url"}
        await query.message.reply("Send the Channel ID, Message ID, and Emoji separated by space\n(e.g., `-10012345678 152 🔥`):", reply_markup=cancel_keyboard())
        
    elif data == "boost_comments":
        user_states[user_id] = {"step": "ask_comment_url"}
        await query.message.reply("Send the Channel ID, Message ID, and Text separated by space\n(e.g., `-10012345678 152 Great post!`):", reply_markup=cancel_keyboard())

    elif data == "cancel_action":
        user_states[user_id] = None
        await query.message.reply("Action cancelled.")
        
    await query.answer()

# Handle Document Uploads for Session Strings (JSON or TXT)
@bot.on_message(filters.document & filters.user(OWNER_ID))
async def handle_document(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if state and state.get("step") == "ask_phone":
        file_path = await message.download()
        try:
            with open(file_path, "r") as f:
                content = f.read().strip()
                
            # If JSON, try to extract 'session' key
            if message.document.file_name.endswith(".json"):
                data = json.loads(content)
                session_string = data.get("session", content)
            else:
                session_string = content
                
            # Use a dummy phone number for manual session strings
            dummy_phone = f"manual_{message.id}" 
            await add_session(dummy_phone, session_string)
            sessions = await count_sessions()
            await message.reply(f"Session imported successfully!\n\nAccounts active: {sessions}")
            user_states[user_id] = None
        except Exception as e:
            await message.reply(f"Failed to parse file: {e}")

@bot.on_message(filters.text & filters.user(OWNER_ID))
async def state_handler(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if not state:
        return

    step = state.get("step")
    text = message.text
    
    # 1. Login Logic
    if step == "ask_phone":
        # Check if the user pasted a session string directly (they are long, usually > 100 chars)
        if len(text) > 100:
            dummy_phone = f"manual_{message.id}"
            await add_session(dummy_phone, text)
            sessions = await count_sessions()
            await message.reply(f"Session string imported successfully!\n\nAccounts active: {sessions}")
            user_states[user_id] = None
            return

        msg = await message.reply("Requesting OTP...")
        success, response = await request_otp(text)
        if success:
            user_states[user_id] = {"step": "ask_otp", "phone": text}
            await msg.edit(f"OTP sent to {text}. Please send the code here (format: `12345`):", reply_markup=cancel_keyboard())
        else:
            user_states[user_id] = None
            await msg.edit(f"Failed: {response}")
            
    elif step == "ask_otp":
        phone = state.get("phone")
        msg = await message.reply("Verifying OTP and generating session...")
        success, response = await submit_otp_and_save(phone, text)
        user_states[user_id] = None
        
        if success:
            sessions = await count_sessions()
            await msg.edit(f"{response}\n\nAccounts active: {sessions}")
        else:
            await msg.edit(f"Failed to login: {response}")
            
    # 2. Voice Chat Logic
    elif step == "ask_vc_chat_id":
        msg = await message.reply("Connecting accounts to VC...")
        user_states[user_id] = None
        try:
            chat_id = int(text) if text.replace("-", "").isdigit() else text
            success_count = await join_all_vc(chat_id)
            await msg.edit(f"Successfully joined VC with {success_count} accounts.")
        except Exception as e:
            await msg.edit(f"Error joining VC: {e}")

    # 3. Engagement Logic
    elif step == "ask_view_url":
        user_states[user_id] = None
        try:
            parts = text.split()
            chat_id = int(parts[0])
            message_id = int(parts[1])
            asyncio.create_task(blast_views(chat_id, message_id))
            await message.reply(f"🚀 Blasting views on message {message_id}...")
        except Exception:
            await message.reply("Invalid format. Use: `-10012345678 152`")

    elif step == "ask_react_url":
        user_states[user_id] = None
        try:
            parts = text.split(maxsplit=2)
            chat_id = int(parts[0])
            message_id = int(parts[1])
            emoji = parts[2] if len(parts) > 2 else "🔥"
            asyncio.create_task(blast_reactions(chat_id, message_id, emoji))
            await message.reply(f"🚀 Blasting {emoji} reactions on message {message_id}...")
        except Exception:
            await message.reply("Invalid format. Use: `-10012345678 152 🔥`")

    elif step == "ask_comment_url":
        user_states[user_id] = None
        try:
            parts = text.split(maxsplit=2)
            chat_id = int(parts[0])
            message_id = int(parts[1])
            comment_text = parts[2]
            asyncio.create_task(blast_comments(chat_id, message_id, comment_text))
            await message.reply(f"🚀 Blasting comments on message {message_id}...")
        except Exception:
            await message.reply("Invalid format. Use: `-10012345678 152 Awesome!`")


# Register the automatic channel watcher
register_auto_watcher(bot)

if __name__ == "__main__":
    print("Bot is starting...")
    # Create a dummy audio file if it doesn't exist (required for PyTgCalls)
    with open("dummy.mp3", "wb") as f:
        pass 
    bot.run()
