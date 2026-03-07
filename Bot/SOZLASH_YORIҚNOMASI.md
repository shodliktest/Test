# 🚀 Streamlit Cloud — To'liq Sozlash Yo'riqnomasi

---

## 1-QADAM — Bot Token olish (@BotFather)

1. Telegramda **@BotFather** ni oching
2. `/newbot` yozing
3. Bot nomini kiriting: masalan `MyQuizBot`
4. Username kiriting: masalan `myquiz_test_bot`
5. BotFather sizga token beradi:
   ```
   1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```
   ✅ Bu — **BOT_TOKEN**

---

## 2-QADAM — Telegram DB guruhi yaratish

1. Telegramda yangi **Private Group** yarating
2. Guruh nomini qo'ying: masalan `QuizBot Database`
3. Botingizni guruhga **qo'shing**
4. Botga **Admin huquqi** bering (barcha huquqlar)
5. Guruh ID sini aniqlash:

   **Usul A — @userinfobot orqali:**
   - Guruhga `/start@userinfobot` yozing
   - Bot guruh ID sini ko'rsatadi: `-1009876543210`

   **Usul B — API orqali:**
   - Brauzerda oching:
     `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - `chat.id` qiymatini toping

   ✅ Bu — **DB_GROUP_ID** (manfiy son!)

---

## 3-QADAM — Shaxsiy Telegram ID olish

1. **@userinfobot** ga `/start` yozing
2. U sizga ID beradi: masalan `123456789`

   ✅ Bu — **ADMIN_IDS** ga kiradi

---

## 4-QADAM — Streamlit Cloud da Secrets sozlash

1. **share.streamlit.io** ga kiring
2. Ilovangizni toping → **⋮ Menu** → **Settings**
3. **Secrets** bo'limiga o'ting
4. Quyidagini **copy-paste** qiling va o'z qiymatlaringizni kiriting:

```toml
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
DB_GROUP_ID = "-1009876543210"
ADMIN_IDS = "123456789"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "parolingiz"
DEFAULT_QUESTION_TIMEOUT = "30"
MAX_QUESTIONS_PER_QUIZ = "50"
```

5. **Save** tugmasini bosing
6. Ilova avtomatik **restart** bo'ladi

---

## 5-QADAM — Sozlamalarni tekshirish

Admin panelga kiring:
- **URL:** `https://sizning-app.streamlit.app`
- **Login:** `admin` (yoki o'zingiz belgilagan)
- **Parol:** o'zingiz belgilagan parol

Agar kirish ishlasa — ✅ muvaffaqiyat!

---

## 6-QADAM — Botni ishga tushirish

Bot **alohida server** da ishlashi kerak (Streamlit bu uchun emas).

### Variant A — Railway.app (bepul)
```bash
# railway.app da yangi loyiha → Deploy from GitHub
# Environment variables:
# BOT_TOKEN=...
# DB_GROUP_ID=...
# ADMIN_IDS=...

# Start command:
python bot/bot.py
```

### Variant B — Render.com (bepul)
```
Build Command:  pip install -r requirements.txt
Start Command:  python bot/bot.py
```

### Variant C — Local (test uchun)
```bash
cd telegram_quiz_platform
pip install -r requirements.txt

# .env fayl yarating:
BOT_TOKEN=1234567890:ABCdef...
DB_GROUP_ID=-1009876543210
ADMIN_IDS=123456789

python bot/bot.py
```

---

## 7-QADAM — Guruhda test o'tkazish

1. Botingizni o'quv guruhga **qo'shing**
2. Botga **Admin huquqi** bering
3. Admin panelda quiz yarating
4. Guruhda yozing:
   ```
   /quiz_list
   ```
5. Quiz ID sini ko'rib:
   ```
   /quiz_start quiz_20240307_abc123
   ```
6. O'quvchilar tugmalarni bosib javob beradi! 🎉

---

## ❗ Tez-tez uchraydigan muammolar

| Muammo | Sabab | Yechim |
|--------|-------|--------|
| Bot javob bermaydi | Token noto'g'ri | BotFather dan yangi token oling |
| DB guruhga yoza olmaydi | Bot admin emas | Guruhda botga admin bering |
| `/quiz_start` ishlamaydi | Siz admin emassiz | Guruhda o'zingizga admin bering |
| Secrets saqlanmaydi | TOML format xato | Qo'shtirnoqlarni tekshiring |
| `DB_GROUP_ID` xato | Manfiy bo'lishi kerak | `-100...` formatda ekanini tekshiring |

---

## 📋 secrets.toml to'liq namuna

```toml
# Majburiy
BOT_TOKEN            = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
DB_GROUP_ID          = "-1009876543210"
ADMIN_IDS            = "123456789,987654321"

# Admin panel
ADMIN_USERNAME       = "admin"
ADMIN_PASSWORD       = "xavfsiz_parol_2024"

# Sozlamalar (ixtiyoriy)
DEFAULT_QUESTION_TIMEOUT = "30"
MAX_QUESTIONS_PER_QUIZ   = "50"
```

---

## ✅ Tekshiruv ro'yxati

- [ ] Bot token olindi (@BotFather)
- [ ] DB guruhi yaratildi (private)
- [ ] Bot DB guruhiga admin sifatida qo'shildi
- [ ] DB_GROUP_ID aniqlandi (manfiy son)
- [ ] Shaxsiy Telegram ID aniqlandi
- [ ] Streamlit Secrets to'ldirildi
- [ ] Admin panelga kirish ishladi
- [ ] Bot serverda ishga tushdi
- [ ] O'quv guruhga bot qo'shildi
- [ ] Test guruhda muvaffaqiyatli o'tkazildi 🎉
