import asyncio
import logging
import json
import io
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
# 2. SAVOLLARNI MATNDAN O'QISH (FUNKSIYA)
# ==========================================
def parse_questions_from_text(content):
    blocks = content.split("\n\n")
    quiz_data = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 3: continue 
        correct_id = 0
        options = []
        for i, line in enumerate(lines[1:]):
            if line.startswith("*"):
                correct_id = i
                options.append(line[1:].strip())
            else:
                options.append(line)
        quiz_data.append({"q": lines[0], "opts": options, "ans": correct_id})
    return quiz_data

# ==========================================
# 3. HANDLERLAR
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Siz yuborgan rasmdagi kabi maxsus so'rov tugmalari
    builder = ReplyKeyboardBuilder()
    
    # Rangli va maxsus turdagi tugmalar (User, Bot, Group, Channel)
    builder.button(text="👤 User", request_users=types.KeyboardButtonRequestUsers(request_id=1, user_is_bot=False))
    builder.button(text="🤖 Bot", request_users=types.KeyboardButtonRequestUsers(request_id=2, user_is_bot=True))
    builder.button(text="👥 Group", request_chat=types.KeyboardButtonRequestChat(request_id=3, chat_is_channel=False))
    builder.button(text="📢 Channel", request_chat=types.KeyboardButtonRequestChat(request_id=4, chat_is_channel=True))
    
    builder.adjust(2) # Tugmalarni 2 qatordan chiqarish

    await message.answer(
        "👋 <b>QuizMarker Botiga xush kelibsiz!</b>\n\n"
        "➕ /yaratish - Buyrug'ini bering va faylni yuboring.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# 1-QADAM: Buyruq berilganda yo'riqnoma ko'rsatish
@dp.message(Command("yaratish"))
async def ask_for_file(message: types.Message):
    await message.answer("📁 Iltimos, savollar yozilgan <b>.txt</b> faylni yuboring.")

# 2-QADAM: Fayl yuborilganda uni tutib olish
@dp.message(F.document)
async def handle_upload(message: types.Message):
    if not message.document.file_name.endswith('.txt'):
        return await message.answer("❌ Faqat <b>.txt</b> formatidagi fayllarni yuboring!")

    # Faylni yuklab olish
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    # Fayl mazmunini o'qish
    downloaded_file = await bot.download_file(file_path)
    content = downloaded_file.read().decode('utf-8')
    
    quizzes = parse_questions_from_text(content)
    
    if not quizzes:
        return await message.answer("❌ Fayl formati xato yoki savollar topilmadi!")

    # Bazaga (Guruhga) saqlash
    test_json = json.dumps(quizzes, ensure_ascii=False)
    db_msg = await bot.send_message(
        chat_id=DB_GROUP_ID, 
        text=f"🗂 #YANGI_TEST\n📦 Savollar: {len(quizzes)} ta\n\n<code>{test_json}</code>"
    )
    
    test_id = db_msg.message_id

    # Inline ulashish tugmasi
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📤 Guruhga ulashish", switch_inline_query=f"quiz_{test_id}"))

    await message.answer(
        f"✅ <b>Fayl qabul qilindi!</b>\n"
        f"📦 Test ID: <code>{test_id}</code>\n"
        f"Savollar soni: {len(quizzes)} ta\n\n"
        f"Endi testni guruhga yuborishingiz mumkin:",
        reply_markup=builder.as_markup()
    )

# ==========================================
# 4. ISHGA TUSHIRISH
# ==========================================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    import streamlit as st
    st.title("🤖 Quiz Bot")
    st.info("Bot ishlamoqda...")
    asyncio.run(main())
        
