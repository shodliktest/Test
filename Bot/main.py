import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.methods import DeleteWebhook
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties # Importni tekshiring

# 1. SOZLAMALAR
BOT_TOKEN = "7735778627:AAHwSeGHgt-o4V87kiE276TQxicicy0JBk0"
DB_GROUP_ID = "-1002110664592"

logging.basicConfig(level=logging.INFO)

# Bot obyektini to'g'ri yaratish
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode='HTML')
)
dp = Dispatcher()

# ... qolgan barcha handlerlar o'zgarishsiz qoladi ...

# 2. SAVOLLARNI O'QISH FUNKSIYASI
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

# 3. HANDLERLAR (Start, Yaratish, Inline va h.k.)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Salom! Bot tayyor. /yaratish buyrug'ini bering.")

@dp.message(Command("yaratish"))
async def cmd_create_test(message: types.Message):
    quizzes = load_questions("savollar.txt")
    if not quizzes:
        return await message.answer("❌ savollar.txt fayli topilmadi!")
    
    test_data_str = json.dumps(quizzes, ensure_ascii=False)
    db_msg = await bot.send_message(chat_id=DB_GROUP_ID, text=f"🗂 #YANGI_TEST\n\n<code>{test_data_str}</code>")
    test_id = db_msg.message_id 

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📤 Guruhga ulashish", switch_inline_query=f"quiz_{test_id}"))
    await message.answer(f"✅ Saqlandi! ID: {test_id}", reply_markup=builder.as_markup())

@dp.inline_query(F.query.startswith("quiz_"))
async def inline_share(inline_query: types.InlineQuery):
    test_id = inline_query.query.split("_")[1]
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="▶️ Boshlash", callback_data=f"startquiz_{test_id}"))
    
    result = types.InlineQueryResultArticle(
        id=test_id,
        title="Viktorinani yuborish",
        input_message_content=types.InputTextMessageContent(message_text="🎯 Testni boshlash uchun pastdagi tugmani bosing."),
        reply_markup=builder.as_markup()
    )
    await inline_query.answer([result], cache_time=1)

@dp.callback_query(F.data.startswith("startquiz_"))
async def start_quiz(callback: types.CallbackQuery):
    # Bu yerda savollarni yuborish logikasi bo'ladi...
    await callback.answer("Test boshlanmoqda...")
    # Yuqoridagi oldingi kodda berilgan game-loopni shu yerga qo'shish mumkin

async def main():
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
