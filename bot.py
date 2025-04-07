#!/usr/bin/env python3
import logging
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import redis
from config import Config

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Redis Connection
redis_conn = redis.from_url(Config.REDIS_URL)

class GroupManager:
    def __init__(self):
        self.app = Application.builder().token(Config.TOKEN).build()
        self._register_handlers()
    
    def _register_handlers(self):
        """Register command and message handlers"""
        handlers = [
            CommandHandler("start", self._start),
            CommandHandler("help", self._help),
            CommandHandler("rules", self._show_rules),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self._welcome_new_members)
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message"""
        await update.message.reply_text(
            "👋 Welcome to Group Manager Bot!\n"
            "Use /help for available commands."
        )
    
    async def _warn_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Warn system with Redis persistence"""
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ Reply to a message to warn user")
            return
            
        user = update.message.reply_to_message.from_user
        chat_id = update.effective_chat.id
        
        # Store warning in Redis
        warn_key = f"warns:{chat_id}:{user.id}"
        warnings = redis_conn.incr(warn_key)
        
        await update.message.reply_text(
            f"⚠️ Warning issued to {user.mention_html()} "
            f"(Total: {warnings}/{Config.MAX_WARNINGS})",
            parse_mode="HTML"
        )
        
        if warnings >= Config.MAX_WARNINGS:
            await self._ban_user(update, context)
            redis_conn.delete(warn_key)

    # Add other methods (_ban_user, _mute_user, etc.)

def main():
    """Run the bot"""
    manager = GroupManager()
    manager.app.run_polling()

if __name__ == "__main__":
    main()