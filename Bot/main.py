import asyncio
import logging
import json
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.methods import DeleteWebhook
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# ==========================================
# 1. SOZLAMALAR
# ==========================================
BOT_TOKEN = "7735778627:AAHwSeGHgt-o4V87kiE276TQxicicy0JBk0"
DB_GROUP_ID = "-1002110664592"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# ==========================================
# 2. INTERFEYS VA QIDIRUV TUGMALARI
# ==========================================
def get_main_menu():
    builder = ReplyKeyboardBuilder()
    # Rasmdagi kabi ko'k (User/Bot) va yashil (Group/Channel) tugmalar
    builder.button(text="👤 User", request_users=types.KeyboardButtonRequestUsers(request_id=1, user_is_bot=False))
    builder.button(text="🌟 Premium", request_users=types.KeyboardButtonRequestUsers(request_id=2, user_is_premium=True))
    builder.button(text="🤖 Bot", request_users=types.KeyboardButtonRequestUsers(request_id=3, user_is_bot=True))
    builder.button(text="👥 Group", request_chat=types.KeyboardButtonRequestChat(request_id=4, chat_is_channel=False))
    builder.button(text="📢 Channel", request_chat=types.KeyboardButtonRequestChat(request_id=5, chat_is_channel=True))
    builder.button(text="🏛 Forum", request_chat=types.KeyboardButtonRequestChat(request_id=6, chat_has_forum=True))
    
    builder.adjust(3) # Har qatorda 3 tadan tugma
    return builder.as_markup(resize_keyboard=True)

# ==========================================
# 3. HANDLERLAR
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>QuizMarker Botiga xush kelibsiz!</b>\n\n"
        "🚀 <b>Buyruqlar:</b>\n"
        "➕ /yaratish - Yangi test fayli yuklash\n"
        "📂 /mytests - Bazadagi testlarni ko'rish",
        reply_markup=get_main_menu()
    )

# FAYL YUKLASH TARTIBI (Xatosiz variant)
@dp.message(Command("yaratish"))
async def start_creation(message: types.Message):
    await message.answer("📁 Iltimos, savollar yozilgan <b>.txt</b> faylni yuboring.\n\n"
                         "<i>Bot siz fayl yubormaguningizcha kutib turadi.</i>")

@dp.message(F.document)
async def handle_document(message: types.Message):
    if not message.document.file_name.endswith('.txt'):
        return await message.answer("❌ Faqat <b>.txt</b> fayl yuboring!")

    # Faylni xotiraga yuklash
    file = await bot.get_file(message.document.file_id)
    content = await bot.download_file(file.file_path)
    text_data = content.read().decode('utf-8')

    # Savollarni parslash (Sodda mantiq)
    blocks = text_data.strip().split("\n\n")
    if not blocks:
        return await message.answer("❌ Fayl ichida savollar topilmadi!")

    # Bazaga yozish (Guruhga JSON ko'rinishida)
    db_msg = await bot.send_message(
        chat_id=DB_GROUP_ID,
        text=f"🗂 #TEST_BAZA\n📦 Nomi: {message.document.file_name}\n\n<code>{text_data[:1000]}</code>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📤 Guruhga ulashish", switch_inline_query=f"quiz_{db_msg.message_id}"))

    await message.answer(f"✅ Test qabul qilindi! ID: <code>{db_msg.message_id}</code>", 
                         reply_markup=builder.as_markup())

# MENING TESTLARIM (SAHIFALANGAN RO'YXAT)
@dp.message(Command("mytests"))
async def list_tests(message: types.Message):
    # Bu yerda bazadan testlarni olish kerak, hozircha namuna:
    builder = InlineKeyboardBuilder()
    # Har bir test uchun alohida tugma
    builder.row(types.InlineKeyboardButton(text="1️⃣ English Test", callback_data="view_1"))
    builder.row(types.InlineKeyboardButton(text="2️⃣ Matematika", callback_data="view_2"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data="prev"),
                types.InlineKeyboardButton(text="Keyingi ➡️", callback_data="next"))
    
    await message.answer("📂 <b>Sizning testlaringiz:</b>", reply_markup=builder.as_markup())

# ==========================================
# 4. ISHGA TUSHIRISH (STREAMLIT FIX)
# ==========================================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    # handle_signals=False Streamlit Cloud uchun hayotiy muhim!
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    st.title("🤖 Quiz Bot")
    st.success("Bot tizimi ishga tushdi.")
    # Agar stop tugmasi ishlamasa, Manage App -> Reboot App qiling
    asyncio.run(main())
