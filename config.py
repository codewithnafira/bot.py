import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Token from @BotFather
    TOKEN = os.getenv("7715194430:AAGme7w7uXVPD42E6bHvJL1FlILxrMvbM0Y")
    
    # Redis Configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Bot Settings
    MAX_WARNINGS = 3
    ADMIN_COMMANDS = ['warn', 'ban', 'mute', 'unmute', 'kick', 'setrules']