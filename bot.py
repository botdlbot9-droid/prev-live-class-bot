import os
import logging
import json
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONFIG ====================
# Cloudflare Worker API URL
API_BASE = os.environ.get('API_BASE', 'https://video-play-api.newstreamcp.workers.dev/api')

# Bot Token (from environment variable)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# ==================== API FUNCTIONS ====================

def check_user_exists(email):
    """Check if user exists in database"""
    try:
        response = requests.get(f"{API_BASE}/users", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                users = data.get('users', [])
                return any(user.get('email') == email for user in users)
        return False
    except Exception as e:
        logger.error(f"Error checking user: {e}")
        return False

def generate_key_for_bot(telegram_id, email):
    """Generate a new key for bot user via API"""
    try:
        response = requests.post(f"{API_BASE}/bot/generate-key", 
            json={"telegram_id": telegram_id, "email": email},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data
        return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.error(f"Error generating key: {e}")
        return {"success": False, "error": str(e)}

# ==================== BOT COMMANDS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /start is issued."""
    user = update.effective_user
    welcome_message = f"""
🤖 *Welcome to Video Portal Bot!*

Hi {user.first_name}! 👋

I can help you get access keys for the video portal.

📌 *How to use:*
1️⃣ Send your email address that is registered with the admin
2️⃣ If your email is found, you'll receive a unique 24-hour key
3️⃣ Use this key to login to the video portal

⚠️ *Rules:*
• Each key is valid for 24 hours only
• Each key can be used only ONCE
• You can generate only ONE key per day

🔗 *Video Portal:* https://your-website.com

Send your email to get started!
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user email input"""
    email = update.message.text.strip()
    telegram_id = str(update.effective_user.id)
    
    # Check if email is valid format
    if '@' not in email or '.' not in email:
        await update.message.reply_text("❌ Please send a valid email address.")
        return
    
    # Check if user exists in database
    if not check_user_exists(email):
        await update.message.reply_text(
            f"❌ Email '{email}' is not registered.\n\n"
            "Please contact the admin to get registered."
        )
        return
    
    # Generate key
    result = generate_key_for_bot(telegram_id, email)
    
    if result.get('success'):
        key = result.get('key')
        expires_at = result.get('expires_at')
        
        # Format expiry time
        try:
            expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            expiry_str = expiry_time.strftime("%d %B %Y, %I:%M %p")
        except:
            expiry_str = "24 hours from now"
        
        # Send key to user
        message = f"""
✅ *Key Generated Successfully!*

🔑 *Your Access Key:*
`{key}`

⏰ *Valid Until:* {expiry_str}

⚠️ *Important:*
• This key can be used only ONCE
• Use it to login at the video portal
• After use, this key will expire

📋 *Instructions:*
1️⃣ Copy the key above
2️⃣ Go to video portal
3️⃣ Enter your email and this key
4️⃣ Start watching videos!

🔐 *Security Tip:* Don't share this key with anyone!
        """
        
        # Inline buttons
        keyboard = [
            [InlineKeyboardButton("🎬 Open Video Portal", url="https://your-website.com")],
            [InlineKeyboardButton("📋 Copy Key", callback_data=f"copy_{key}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        error_msg = result.get('error', 'Unknown error')
        if 'already generated' in error_msg.lower() or 'today' in error_msg.lower():
            await update.message.reply_text(
                f"⚠️ {error_msg}\n\n"
                "You can generate only ONE key per day.\n"
                "Please try again tomorrow."
            )
        else:
            await update.message.reply_text(
                f"❌ Failed to generate key: {error_msg}\n\n"
                "Please contact the admin."
            )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('copy_'):
        key = query.data.replace('copy_', '')
        await query.edit_message_text(
            f"🔑 Your key is: `{key}`\n\n"
            "Use this key to login. Remember, it can be used only once!",
            parse_mode='Markdown'
        )

# ==================== MAIN ====================

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Please set it in environment variables.")
        return
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the Bot
    print("🤖 Bot is starting...")
    port = int(os.environ.get('PORT', 8080))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()
