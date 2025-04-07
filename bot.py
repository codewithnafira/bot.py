#!/usr/bin/env python3
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    CallbackContext
)
from telegram.error import TelegramError
import redis

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN') or "YOUR_BOT_TOKEN_HERE"  # Better to use environment variables
REDIS_URL = os.getenv('REDIS_URL') or "redis://localhost:6379/0"
MAX_WARNINGS = 3
CAPTCHA_ENABLED = True  # Set to False if you don't want captcha verification

# Set up professional logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('group_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Redis with connection pool
redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_conn = redis.Redis(connection_pool=redis_pool)

class GroupManagerBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self._register_handlers()
        self._setup_commands()

    def _register_handlers(self):
        """Register all handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler("rules", self._show_rules))
        self.app.add_handler(CommandHandler("setrules", self._set_rules))
        self.app.add_handler(CommandHandler("warn", self._warn_user))
        self.app.add_handler(CommandHandler("ban", self._ban_user))
        self.app.add_handler(CommandHandler("mute", self._mute_user))
        self.app.add_handler(CommandHandler("unmute", self._unmute_user))
        self.app.add_handler(CommandHandler("kick", self._kick_user))
        self.app.add_handler(CommandHandler("report", self._report_user))
        self.app.add_handler(CommandHandler("warnings", self._check_warnings))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self._welcome_new_members))
        
        # Error handler
        self.app.add_error_handler(self._error_handler)

    def _setup_commands(self):
        """Set up bot commands menu"""
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help"),
            BotCommand("rules", "Show group rules"),
            BotCommand("report", "Report a user"),
            BotCommand("warnings", "Check your warnings")
        ]
        self.app.bot.set_my_commands(commands)

    async def _is_admin(self, update: Update, context: CallbackContext) -> bool:
        """Check if user is admin or owner"""
        try:
            if not update.effective_chat or not update.effective_user:
                return False
                
            member = await update.effective_chat.get_member(update.effective_user.id)
            return member.status in ['administrator', 'creator']
        except TelegramError as e:
            logger.error(f"Admin check failed: {e}")
            return False

    async def _start(self, update: Update, context: CallbackContext):
        """Send welcome message"""
        await update.message.reply_text(
            "👋 Welcome to Group Manager Bot!\n"
            "I help manage your Telegram groups with these features:\n\n"
            "• Automated moderation\n"
            "• Custom group rules\n"
            "• Warning system\n"
            "• User reporting\n\n"
            "Use /help for commands list"
        )

    async def _help(self, update: Update, context: CallbackContext):
        """Show help message"""
        help_text = (
            "🛠 <b>Admin Commands:</b>\n"
            "/setrules [text] - Set group rules\n"
            "/warn [reply] - Warn a user\n"
            "/mute [reply] [time] - Mute user (e.g. 1h)\n"
            "/unmute [reply] - Unmute user\n"
            "/ban [reply] - Ban user\n"
            "/kick [reply] - Kick user\n\n"
            "👤 <b>User Commands:</b>\n"
            "/rules - Show group rules\n"
            "/report [reply] - Report a user\n"
            "/warnings - Check your warnings"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")

    async def _warn_user(self, update: Update, context: CallbackContext):
        """Warn a user with proper validation"""
        if not await self._is_admin(update, context):
            await update.message.reply_text("❌ Admin privileges required.")
            return

        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ Please reply to the user's message.")
            return

        target_user = update.message.reply_to_message.from_user
        chat_id = update.effective_chat.id
        reason = " ".join(context.args) if context.args else "No reason provided"

        # Store warning with timestamp
        warn_data = {
            "by": update.effective_user.id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        redis_conn.rpush(f"warns:{chat_id}:{target_user.id}", str(warn_data))
        
        # Get current warning count
        warn_count = redis_conn.llen(f"warns:{chat_id}:{target_user.id}")

        # Prepare response
        response = (
            f"⚠️ Warning issued to {target_user.mention_html()}\n"
            f"Reason: {reason}\n"
            f"Total warnings: {warn_count}/{MAX_WARNINGS}"
        )
        await update.message.reply_text(response, parse_mode="HTML")

        # Auto-ban if max warnings reached
        if warn_count >= MAX_WARNINGS:
            await self._perform_ban(
                chat_id=chat_id,
                user_id=target_user.id,
                reason=f"Reached {MAX_WARNINGS} warnings",
                context=context
            )
            redis_conn.delete(f"warns:{chat_id}:{target_user.id}")

    async def _perform_ban(self, chat_id: int, user_id: int, reason: str, context: CallbackContext):
        """Professional ban handling with error management"""
        try:
            await context.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                revoke_messages=True
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 User banned. Reason: {reason}"
            )
        except TelegramError as e:
            logger.error(f"Ban failed: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Failed to ban user: {e}"
            )

    async def _welcome_new_members(self, update: Update, context: CallbackContext):
        """Enhanced welcome system with captcha"""
        if not CAPTCHA_ENABLED:
            return

        for new_member in update.message.new_chat_members:
            if new_member.is_bot:
                continue

            # Generate math captcha
            num1, num2 = random.randint(1, 10), random.randint(1, 10)
            answer = num1 + num2
            captcha_data = {
                "answer": answer,
                "attempts": 0,
                "timestamp": datetime.now().isoformat()
            }
            redis_conn.setex(
                f"captcha:{update.effective_chat.id}:{new_member.id}",
                timedelta(minutes=5),
                str(captcha_data)
            )

            # Restrict user
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=new_member.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                )
            )

            # Send captcha
            keyboard = [
                [InlineKeyboardButton("Verify Now", callback_data=f"verify_{new_member.id}")]
            ]
            await update.message.reply_text(
                f"👋 Welcome {new_member.mention_html()}!\n"
                f"Please solve: {num1} + {num2} = ?\n"
                "You have 5 minutes to verify.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

    async def _error_handler(self, update: object, context: CallbackContext):
        """Professional error handling"""
        logger.error(msg="Exception while handling update:", exc_info=context.error)
        
        if update and isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ An error occurred. Please try again later."
            )

def main():
    """Run the bot with professional setup"""
    try:
        bot = GroupManagerBot()
        
        # Set up signal handlers for clean shutdown
        if sys.platform != 'win32':
            import signal
            signal.signal(signal.SIGINT, lambda s, f: bot.app.stop())
            signal.signal(signal.SIGTERM, lambda s, f: bot.app.stop())
        
        logger.info("Starting bot...")
        bot.app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()