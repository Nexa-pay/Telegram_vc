from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_panel_keyboard(session_count):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟢 Active Accounts: {session_count}", callback_data="none")],
        [InlineKeyboardButton("➕ Add Account (OTP)", callback_data="add_otp")],
        [
            InlineKeyboardButton("<emoji id=5310129635848103696>📈</emoji> Boost Views", callback_data="boost_views"),
            InlineKeyboardButton("<emoji id=5310129635848103696>🔥</emoji> Reactions", callback_data="boost_reacts")
        ],
        [InlineKeyboardButton("💬 Blast Comments", callback_data="boost_comments")],
        [InlineKeyboardButton("🎙 Join VC", callback_data="join_vc")]
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
    ])
