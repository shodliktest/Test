import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.methods import DeleteWebhook
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==========================================
# 1. SOZLAMALAR VA XOTIRA
# ==========================================
BOT_TOKEN = "SIZNING_TOKENINGIZNI_SHU_YERGA_YOZING"
DB_GROUP_ID = "-1001234567890" # Yopiq baza guruhingiz ID raqami

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
dp = Dispatcher()

# Vaqtinchalik xotira
active_polls = {}
user_scores = {}
loaded_test_cache = []

# Savollarni TXT fayldan o'qish funksiyasi
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
# 2. BOT BUYRUQLARI (HANDLERS)
# ==========================================

# Start buyrug'i
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Salom! Men Quiz botman.</b>\n\n"
        "Yangi test bazaga yuklash va guruhlarga yuborish uchun /yaratish buyrug'ini bering."
    )

# Test yaratish va Bazaga saqlash
@dp.message(Command("yaratish"))
async def cmd_create_test(message: types.Message):
    quizzes = load_questions("savollar.txt")
    if not quizzes:
        return await message.answer("❌ <code>savollar.txt</code> fayli bo'sh yoki topilmadi!")

    # 1. Bazaga (Yopiq guruhga) saqlash
    test_data_str = json.dumps(quizzes, ensure_ascii=False)
    db_msg = await bot.send_message(
        chat_id=DB_GROUP_ID, 
        text=f"🗂 #YANGI_TEST\n\nSavollar: {len(quizzes)} ta\n\n<code>{test_data_str}</code>"
    )
    
    # 2. Xabar ID sini test kodi qilib olamiz
    test_id = db_msg.message_id 

    # 3. Ulashish tugmasini yasaymiz (Standart emojilar bilan)
    builder = InlineKeyboardBuilder()
    button = types.InlineKeyboardButton(
        text="📤 Guruhga ulashish", 
        switch_inline_query=f"quiz_{test_id}"
    )
    builder.row(button)

    await message.answer(
        f"✅ <b>Test Bazaga muvaffaqiyatli saqlandi!</b>\n"
        f"🆔 Kodi: <code>{test_id}</code>\n\n"
        f"Pastdagi tugma orqali testni istalgan guruhga yuboring:",
        reply_markup=builder.as_markup()
    )

# Inline rejim (Guruhga ulashish bosilganda ishlaydi)
@dp.inline_query(F.query.startswith("quiz_"))
async def inline_share(inline_query: types.InlineQuery):
    test_id = inline_query.query.split("_")[1]

    # Guruhga tushadigan Boshlash tugmasi (Standart emoji bilan)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="▶️ Guruhda Boshlash", 
        callback_data=f"startquiz_{test_id}"
    ))

    result = types.InlineQueryResultArticle(
        id=test_id,
        title="📚 Testni guruhga yuborish",
        description="Shu yerni bosing va guruhga testni tashlang",
        input_message_content=types.InputTextMessageContent(
            message_text="🎯 <b>Yangi test keldi!</b>\nBarcha tayyor bo'lsa, pastdagi tugmani bosing va musobaqani boshlaymiz.",
            parse_mode="HTML"
        ),
        reply_markup=builder.as_markup()
    )
    await inline_query.answer([result], cache_time=1)

# Guruhda "Boshlash" bosilganda testni aylantirish (Game Loop)
@dp.callback_query(F.data.startswith("startquiz_"))
async def start_quiz_loop(callback: types.CallbackQuery):
    if callback.message.chat.type == "private":
        return await callback.answer("⚠️ Bu tugma faqat guruhlarda ishlaydi!", show_alert=True)
        
    global loaded_test_cache, active_polls, user_scores
    # Vaqtinchalik testni o'qib olamiz
    loaded_test_cache = load_questions("savollar.txt") 
    
    await callback.message.delete()
    await callback.message.answer(
        "📢 <b>Diqqat! Viktorina boshlanmoqda!</b>\n\n"
        "⏱ Har bir savolga <b>15 soniya</b> vaqt beriladi."
    )
    await asyncio.sleep(3) # Tayyorgarlik uchun pauza

    active_polls.clear()
    user_scores.clear()

    # Taymerli savol jo'natish tizimi
    for index, q in enumerate(loaded_test_cache):
        poll_msg = await bot.send_poll(
            chat_id=callback.message.chat.id,
            question=f"{index + 1}) {q['q']}",
            options=q['opts'],
            type="quiz",
            correct_option_id=q['ans'],
            is_anonymous=False
        )
        active_polls[poll_msg.poll.id] = q['ans']
        
        await asyncio.sleep(15) # 15 soniya kutamiz
        await bot.stop_poll(chat_id=callback.message.chat.id, message_id=poll_msg.message_id)
        await asyncio.sleep(2) # Keyingi savolga o'tishdan oldin tanaffus

    # Natijalarni hisoblash (Leaderboard)
    if not user_scores:
        return await callback.message.answer("🏁 <b>Viktorina tugadi!</b>\nHech kim to'g'ri javob topa olmadi 😔")

    sorted_scores = sorted(user_scores.values(), key=lambda x: x["score"], reverse=True)
    text = "🏆 <b>VIKTORINA NATIJALARI:</b>\n\n"
    for i, user in enumerate(sorted_scores):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "🎗"
        text += f"{medal} <b>{user['name']}</b> — {user['score']} ta\n"
        
    await callback.message.answer(text)

# Javoblarni ushlab ball berish (Orqa fonda ishlaydi)
@dp.poll_answer()
async def catch_answers(poll_answer: types.PollAnswer):
    if poll_answer.poll_id in active_polls:
        if poll_answer.user.id not in user_scores:
            user_scores[poll_answer.user.id] = {"name": poll_answer.user.full_name, "score": 0}
        
        # To'g'ri topgan bo'lsa ball beramiz
        if poll_answer.option_ids[0] == active_polls[poll_answer.poll_id]:
            user_scores[poll_answer.user.id]["score"] += 1

# ==========================================
# 3. BOTNI ISHGA TUSHIRISH
# ==========================================
async def main():
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
