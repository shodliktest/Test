import asyncio
import logging
import json
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.methods import DeleteWebhook
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

# ==========================================
# 1. KONFIGURATSIYA (SIZNING MA'LUMOTLARINGIZ)
# ==========================================
# Agar Streamlit Secrets ishlatsangiz: st.secrets["BOT_TOKEN"] deb yozing
BOT_TOKEN = "7735778627:AAHwSeGHgt-o4V87kiE276TQxicicy0JBk0"
DB_GROUP_ID = "-1002110664592"

logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher sozlamalari
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode='HTML')
)
dp = Dispatcher()

# Vaqtinchalik xotira (RAM)
active_polls = {} # poll_id : correct_option_id
user_scores = {}  # user_id : {"name": ism, "score": ball}

# ==========================================
# 2. YORDAMCHI FUNKSIYALAR
# ==========================================
def load_questions(filename="savollar.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError:
        return []
    
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
# 3. BOT HANDLERLARI
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>QuizMarker Botiga xush kelibsiz!</b>\n\n"
        "🚀 <b>Buyruqlar:</b>\n"
        "➕ /yaratish - Savollarni bazaga yuklash\n"
        "🗂 /mytests - Mening testlarim (Ro'yxat)\n\n"
        "<i>Eslatma: Savollar <code>savollar.txt</code> faylidan olinadi.</i>"
    )

# TEST YARATISH VA BAZAGA (GURUHGA) YOZISH
@dp.message(Command("yaratish"))
async def cmd_create_test(message: types.Message):
    quizzes = load_questions("savollar.txt")
    if not quizzes:
        return await message.answer("❌ <code>savollar.txt</code> fayli topilmadi yoki xato to'ldirilgan!")

    # Ma'lumotni JSON qilib bazaga yuboramiz
    test_json = json.dumps(quizzes, ensure_ascii=False)
    db_msg = await bot.send_message(
        chat_id=DB_GROUP_ID, 
        text=f"🗂 #YANGI_TEST\n📦 Savollar: {len(quizzes)} ta\n\n<code>{test_json}</code>"
    )
    
    test_id = db_msg.message_id # Baza xabar ID si = Test ID si

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="📤 Guruhga ulashish", 
        switch_inline_query=f"quiz_{test_id}"
    ))

    await message.answer(
        f"✅ <b>Test muvaffaqiyatli bazaga saqlandi!</b>\n🆔 Test ID: <code>{test_id}</code>\n\n"
        f"Uni guruhlarga yuborish uchun tugmani bosing:",
        reply_markup=builder.as_markup()
    )

# INLINE REJIMDA ULASHISH
@dp.inline_query(F.query.startswith("quiz_"))
async def inline_share_handler(inline_query: types.InlineQuery):
    test_id = inline_query.query.split("_")[1]

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="▶️ Boshlash", 
        callback_data=f"startquiz_{test_id}"
    ))

    result = InlineQueryResultArticle(
        id=test_id,
        title="📚 Testni guruhga yuborish",
        description=f"ID: {test_id} - Viktorinani boshlash",
        input_message_content=InputTextMessageContent(
            message_text=f"🎯 <b>Yangi Viktorina!</b>\n\nUshbu testni boshlash uchun pastdagi tugmani bosing.",
            parse_mode="HTML"
        ),
        reply_markup=builder.as_markup()
    )
    await inline_query.answer([result], cache_time=1)

# GURUHDA TESTNI ISHGA TUSHIRISH (GAME LOOP)
@dp.callback_query(F.data.startswith("startquiz_"))
async def run_quiz_in_group(callback: types.CallbackQuery):
    if callback.message.chat.type == "private":
        return await callback.answer("⚠️ Faqat guruhlarda ishlaydi!", show_alert=True)
    
    # Savollarni vaqtincha fayldan olamiz (yoki bazadan tortish logikasi)
    quizzes = load_questions("savollar.txt")
    
    await callback.message.delete()
    await callback.message.answer("📢 <b>Tayyorlaning! Viktorina 3 soniyadan so'ng boshlanadi...</b>")
    await asyncio.sleep(3)

    global active_polls, user_scores
    active_polls.clear()
    user_scores.clear()

    for index, q in enumerate(quizzes):
        poll_msg = await bot.send_poll(
            chat_id=callback.message.chat.id,
            question=f"{index + 1}) {q['q']}",
            options=q['opts'],
            type="quiz",
            correct_option_id=q['ans'],
            is_anonymous=False
        )
        active_polls[poll_msg.poll.id] = q['ans']
        
        await asyncio.sleep(15) # 15 soniya kutish
        await bot.stop_poll(chat_id=callback.message.chat.id, message_id=poll_msg.message_id)
        await asyncio.sleep(2)

    # REYTINGNI CHIQARISH
    if not user_scores:
        await callback.message.answer("🏁 <b>Test tugadi.</b>\nHech kim qatnashmadi.")
        return

    sorted_res = sorted(user_scores.values(), key=lambda x: x["score"], reverse=True)
    leaderboard = "🏆 <b>NATIJALAR:</b>\n\n"
    for i, u in enumerate(sorted_res):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "🎗"
        leaderboard += f"{medal} <b>{u['name']}</b> — {u['score']} ta\n"
    
    await callback.message.answer(leaderboard)

# OVOZLARNI HISOBLASH
@dp.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    if poll_answer.poll_id in active_polls:
        u_id = poll_answer.user.id
        if u_id not in user_scores:
            user_scores[u_id] = {"name": poll_answer.user.full_name, "score": 0}
        
        if poll_answer.option_ids[0] == active_polls[poll_answer.poll_id]:
            user_scores[u_id]["score"] += 1

# ==========================================
# 4. BOTNI ISHGA TUSHIRISH (STREAMLIT FIX)
# ==========================================
async def main():
    # Webhookni tozalash
    await bot.delete_webhook(drop_pending_updates=True)
    
    # handle_signals=False -> Streamlit Cloud uchun majburiy!
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    st.info("🤖 Bot orqa fonda ishga tushirildi...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
    
