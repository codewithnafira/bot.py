import logging
import sqlite3
from datetime import datetime, timedelta
from random import choice, randint
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get the bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- Setup --- #
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Database initialization
def init_db():
    conn = sqlite3.connect('grade10_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        subject TEXT,
        description TEXT,
        due_date TEXT,
        added_by INTEGER,
        added_date TEXT
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        warnings INTEGER DEFAULT 0
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scores (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        score INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

init_db()

# Conversation states
HOMEWORK, REMINDER = range(2)

# Sample data
MEMES = ["https://i.imgur.com/xyz123.jpg", "https://i.imgur.com/abc456.jpg"]
COMPLIMENTS = ["You're acing 10th grade!", "Future valedictorian!"]
ROASTS = ["Did you forget to study... again?", "Your grades are like my WiFi - unstable!"]
TOPICS = ["If you could eliminate one subject, which would it be?", "Best/worst teacher?"]

# --- Trivia Questions --- #
TRIVIA_QUESTIONS = [
    {
        "question": "What is the capital of France?",
        "options": ["1. Berlin", "2. Madrid", "3. Paris", "4. Rome"],
        "answer": 3
    },
    {
        "question": "Which planet is known as the Red Planet?",
        "options": ["1. Earth", "2. Mars", "3. Jupiter", "4. Venus"],
        "answer": 2
    },
    {
        "question": "Who wrote 'Hamlet'?",
        "options": ["1. Charles Dickens", "2. William Shakespeare", "3. Mark Twain", "4. Jane Austen"],
        "answer": 2
    }
]

# --- Helper Functions --- #
def get_db():
    return sqlite3.connect('grade10_bot.db')

def add_homework(chat_id, subject, description, due_date, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO homework (chat_id, subject, description, due_date, added_by, added_date)
    VALUES (?, ?, ?, ?, ?, ?)''', 
    (chat_id, subject, description, due_date, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_homework(chat_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT subject, description, due_date FROM homework 
    WHERE chat_id = ? AND date(due_date) >= date('now')
    ORDER BY date(due_date)''', (chat_id,))
    results = cursor.fetchall()
    conn.close()
    return results

# --- Command Handlers --- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Welcome {user.first_name} \n\n"
        "📚 Homework tracking\n🎤 Voice chat features\n😂 Memes & games\n\n"
        "Type /help for commands"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Available commands:\n"
        "/homework - Add assignment\n"
        "/listhw - View homework\n"
        "/meme - Random meme\n"
        "/topic - Conversation starter\n"
        "/compliment - Get hyped\n"
        
    )

async def homework_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📝 Enter homework as:\nSubject: Description - DD/MM/YYYY\n"
        "Example:\nMath: Page 45 problems - 15/12/2023\n\n"
        "Type /cancel to quit"
    )
    return HOMEWORK

async def homework_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        text = update.message.text
        parts = text.split(" - ")
        desc_part = parts[0].strip()
        due_date = datetime.strptime(parts[1].strip(), "%d/%m/%Y").date()
        
        if ":" in desc_part:
            subject, description = desc_part.split(":", 1)
            subject, description = subject.strip(), description.strip()
        else:
            subject, description = "General", desc_part
            
        add_homework(
            update.message.chat_id,
            subject,
            description,
            due_date.isoformat(),
            update.effective_user.id
        )
        
        # Schedule reminder
        reminder_time = due_date - timedelta(days=1)
        context.job_queue.run_once(
            send_reminder,
            when=datetime.combine(reminder_time, datetime.min.time()),
            chat_id=update.message.chat_id,
            data=f"{subject}: {description}"
        )
        
        await update.message.reply_text(
            f"✅ Added!\n{subject}: {description}\nDue: {due_date.strftime('%A, %d %B %Y')}"
        )
        return ConversationHandler.END
        
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid format. Try again or /cancel")
        return HOMEWORK

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        job.chat_id,
        f"⏰ REMINDER!\n\n{job.data}\nDue tomorrow!"
    )

async def list_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    homework = get_homework(update.message.chat_id)
    if not homework:
        await update.message.reply_text("🎉 No pending homework!")
        return
    
    msg = "📚 Pending Homework...:\n\n"
    for subject, desc, due_date in homework:
        due = datetime.fromisoformat(due_date).strftime("%a, %d %b")
        msg += f"• {subject}: {desc} - Due: {due}\n"
    
    await update.message.reply_text(msg)

# --- Fun Commands --- #
async def send_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_photo(choice(MEMES), caption="😂 Here's your meme!")

async def send_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💖 {choice(COMPLIMENTS)}")

async def send_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔥 {choice(ROASTS)}")

async def topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 Discussion Topic:\n\n{choice(TOPICS)}")

async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = [
        "🎲 Roll a dice: /roll",
        "🧠 Trivia: /trivia",
        "✏️ Hangman: /hangman",
        "❌⭕ Tic Tac Toe: /tictactoe"
    ]
    await update.message.reply_text("🎮 Available Games:\n" + "\n".join(games))

async def roll_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dice_roll = randint(1, 6)
    await update.message.reply_text(f"🎲 You rolled a {dice_roll}!")

async def trivia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = choice(TRIVIA_QUESTIONS)
    context.user_data["trivia_answer"] = question["answer"]
    await update.message.reply_text(
        f"🧠 Trivia Question:\n{question['question']}\n" + "\n".join(question['options'])
    )

async def trivia_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_answer = int(update.message.text.strip())
        correct_answer = context.user_data.get("trivia_answer")

        if user_answer == correct_answer:
            await update.message.reply_text("🎉 Correct! Well done!")
        else:
            await update.message.reply_text("❌ Wrong answer. Better luck next time!")
    except ValueError:
        await update.message.reply_text("❌ Please reply with the number of your answer.")

async def hangman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✏️ Hangman is under development. Stay tuned!")

async def tictactoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌⭕ Tic Tac Toe is under development. Stay tuned!")

# --- Voice Chat Features --- #
async def voice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Voice chat started!")

async def voice_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Voice chat ended!")

# --- Video Chat Feature --- #
async def request_video_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Initialize the counter if it doesn't exist
    if "video_chat_requests" not in context.chat_data:
        context.chat_data["video_chat_requests"] = set()

    user = update.effective_user
    if user.id in context.chat_data["video_chat_requests"]:
        await update.message.reply_text("❌ You have already requested a video chat.")
        return

    # Add the user to the set of requests
    context.chat_data["video_chat_requests"].add(user.id)
    request_count = len(context.chat_data["video_chat_requests"])

    await update.message.reply_text(
        f"📹 Video chat requested by {user.first_name}.\n"
        f"Current requests: {request_count}/5"
    )

    # Check if the threshold is reached
    if request_count >= 5:
        await start_video_chat(update, context)
        # Reset the counter after starting the video chat
        context.chat_data["video_chat_requests"] = set()

async def start_video_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎥 Starting video chat now!")
    # Add logic to start the video chat (e.g., send a notification or link)

# --- Admin Controls --- #
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user's message to warn them.")
        return

    warned_user = update.message.reply_to_message.from_user
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users SET warnings = warnings + 1 WHERE user_id = ?
    ''', (warned_user.id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"⚠️ {warned_user.first_name} has been warned!")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user's message to mute them.")
        return

    muted_user = update.message.reply_to_message.from_user
    await context.bot.restrict_chat_member(
        chat_id=update.message.chat_id,
        user_id=muted_user.id,
        permissions=ChatPermissions(can_send_messages=False)
    )
    await update.message.reply_text(f"🔇 {muted_user.first_name} has been muted!")

# --- Welcoming New Members --- #
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {new_member.first_name} to the group! 🎉\n"
            "Feel free to introduce yourself and check out the pinned messages for group rules."
        )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT username, score FROM scores
    ORDER BY score DESC LIMIT 10
    ''')
    results = cursor.fetchall()
    conn.close()

    if not results:
        await update.message.reply_text("📊 No scores yet!")
        return

    leaderboard_text = "🏆 Weekly Leaderboard:\n\n"
    for i, (username, score) in enumerate(results, start=1):
        leaderboard_text += f"{i}. {username}: {score} points\n"

    await update.message.reply_text(leaderboard_text)

# --- Main --- #
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for homework
    homework_conv = ConversationHandler(
        entry_points=[CommandHandler("homework", homework_start)],
        states={
            HOMEWORK: [MessageHandler(filters.TEXT & ~filters.COMMAND, homework_add)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(homework_conv)
    application.add_handler(CommandHandler("listhw", list_homework))
    application.add_handler(CommandHandler("meme", send_meme))
    application.add_handler(CommandHandler("compliment", send_compliment))
    application.add_handler(CommandHandler("roast", send_roast))
    application.add_handler(CommandHandler("topic", topic))
    application.add_handler(CommandHandler("game", game))
    application.add_handler(CommandHandler("roll", roll_dice))
    application.add_handler(CommandHandler("trivia", trivia))
    application.add_handler(CommandHandler("hangman", hangman))
    application.add_handler(CommandHandler("tictactoe", tictactoe))
    application.add_handler(MessageHandler(filters.StatusUpdate.VIDEO_CHAT_STARTED, voice_start))
    application.add_handler(MessageHandler(filters.StatusUpdate.VIDEO_CHAT_ENDED, voice_end))
    application.add_handler(CommandHandler("warn", warn_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))  # New handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trivia_answer))  # New handler
    application.add_handler(CommandHandler("leaderboard", leaderboard))  # New handler
    application.add_handler(CommandHandler("request_video_chat", request_video_chat))  # New handler
    application.add_handler(CommandHandler("videochat", request_video_chat))  # New handler

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()