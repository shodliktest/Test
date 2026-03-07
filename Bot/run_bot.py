"""
Bot ishga tushirish — root papkadan:
  python run_bot.py
"""
import asyncio
import sys
import os

# .env faylni o'qish
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env fayl o'qildi")
except ImportError:
    print("⚠️  python-dotenv yo'q — pip install python-dotenv")

# Path sozlash
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.bot import main

if __name__ == "__main__":
    asyncio.run(main())
