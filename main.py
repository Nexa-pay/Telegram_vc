import uvloop
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID
from utils.keyboard import admin_panel_keyboard, cancel_keyboard
from database import count_sessions
from services.account_manager import request_otp, submit_otp_and_save
from services.vc_manager import join_all_vc
from services.auto_watcher import register_auto_watcher

# Install uvloop for high performance asynchronous operations
uvloop.install()

bot = Client(
    "EngagementBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# State manager for conversations (OTP handling)
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
        await query.message.reply("Please send the phone number in international format (e.g., +1234567890):", reply_markup=cancel_keyboard())
    
    elif data == "join_vc":
        user_states[user_id] = {"step": "ask_vc_chat_id"}
        await query.message.reply("Send the Chat ID or Username where accounts should join the Voice Chat:", reply_markup=cancel_keyboard())
        
    elif data == "cancel_action":
        user_states[user_id] = None
        await query.message.reply("Action cancelled.")
        
    await query.answer()

@bot.on_message(filters.text & filters.user(OWNER_ID))
async def state_handler(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if not state:
        return

    step = state.get("step")
    text = message.text
    
    if step == "ask_phone":
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
            
    elif step == "ask_vc_chat_id":
        msg = await message.reply("Connecting accounts to VC...")
        user_states[user_id] = None
        try:
            chat_id = int(text) if text.replace("-", "").isdigit() else text
            success_count = await join_all_vc(chat_id)
            await msg.edit(f"Successfully joined VC with {success_count} accounts.")
        except Exception as e:
            await msg.edit(f"Error joining VC: {e}")

# Register the automatic channel watcher
register_auto_watcher(bot)

if __name__ == "__main__":
    print("Bot is starting...")
    # Create a dummy audio file if it doesn't exist (required for PyTgCalls)
    with open("dummy.mp3", "wb") as f:
        pass 
    bot.run()
