# main.py
import logging
import json
from datetime import datetime
import aiosqlite
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ========== Настройки ==========
BOT_TOKEN = "8376106425:AAFj2QKo7qK5zqvbGbhE_whIbUngY8S9r10"            # <- вставь свой токен от BotFather
ADMIN_CHAT_ID = 123456789                   # <- сюда будут приходить уведомления о бронях (ваш id или группа)
DB_PATH = "restaurant_bot.db"
# Укажи сюда публичный URL где лежит твой webapp (index.html, script.js, style.css).
# Пример для GitHub Pages: "https://username.github.io/repo-name"
WEBAPP_BASE_URL = "https://N1kLeS.github.io/Bot_TG"  # <- обнови перед деплоем

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== Инициализация и миграции базы ==========
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                restaurant TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS restaurants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                restaurant TEXT,
                type TEXT,            -- 'book_dish' или 'booking_form'
                payload TEXT,         -- json payload
                created_at TEXT
            )
        """)
        await db.commit()

        # добавим пример ресторанов, если пусто
        async with db.execute("SELECT COUNT(*) FROM restaurants") as cur:
            row = await cur.fetchone()
            if row and row[0] == 0:
                sample = [
                    ("Lemon Place", "Итальянская и средиземноморская кухня"),
                    ("Sushi Bar", "Свежие роллы и сашими"),
                    ("Steak House", "Стейки и гриль")
                ]
                await db.executemany("INSERT INTO restaurants (name, description) VALUES (?,?)", sample)
                await db.commit()

# ========== Вспомогательные функции ==========
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username, full_name, phone, restaurant FROM users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

async def ensure_user_exists(user):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?,?,?)",
            (user.id, user.username, user.full_name)
        )
        await db.commit()

async def get_restaurants():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, description FROM restaurants") as cur:
            return await cur.fetchall()

# ========== Хендлеры ==========

# /start — регистрация + переход в главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    await ensure_user_exists(user)
    # Если пришёл обычный message
    if update.message:
        await show_main_menu(update)
    else:
        # возможно callback
        await show_main_menu(update)

# Главное меню
async def show_main_menu(update: Update, text: str = "Главное меню:"):
    keyboard = [
        [InlineKeyboardButton("📋 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🍴 Выбрать ресторан", callback_data="choose_restaurant")],
        [InlineKeyboardButton("📖 Меню ресторана", callback_data="open_menu")],
        [InlineKeyboardButton("🕰 Забронировать столик", callback_data="open_booking")],
        [InlineKeyboardButton("ℹ️ О ресторане", callback_data="about")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # edit_message_text если callback, иначе send message
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
            # если редактирование не получилось (например, старое сообщение), просто отправим новое
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

# Профиль
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    row = await get_user(user_id)
    if row:
        _, username, full_name, phone, restaurant = row
        text = f"👤 Профиль:\n\nИмя: {full_name or '-'}\nЮзер: @{username}\nТелефон: {phone or 'не указан'}\nВыбранный ресторан: {restaurant or 'не выбран'}"
    else:
        text = "Профиль не найден."
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

# Выбор ресторана (список)
async def choose_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows = await get_restaurants()
    keyboard = [[InlineKeyboardButton(name, callback_data=f"set_rest|{name}")] for (name, _) in rows]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    await query.edit_message_text("🏢 Выберите ресторан:", reply_markup=InlineKeyboardMarkup(keyboard))

# Сохранение выбора ресторана
async def set_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|", 1)
    if len(data) < 2:
        await query.edit_message_text("Ошибка выбора ресторана.")
        return
    rest_name = data[1]
    user_id = query.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET restaurant = ? WHERE user_id = ?", (rest_name, user_id))
        await db.commit()
    await show_main_menu(update, f"✅ Вы выбрали ресторан: {rest_name}")

# О ресторане (описание текущего выбранного)
async def about_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    row = await get_user(user_id)
    restaurant = row[4] if row else None
    if not restaurant:
        await query.edit_message_text("⚠️ Сначала выберите ресторан.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]))
        return
    # можно подтянуть описание из таблицы restaurants, но пока короткий текст
    text = f"ℹ️ Информация о ресторане *{restaurant}*.\nУютная атмосфера и вкусная еда."
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Открыть WebApp: меню
async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    row = await get_user(user_id)
    restaurant = row[4] if row else None
    if not restaurant:
        await query.edit_message_text("⚠️ Сначала выберите ресторан.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]))
        return
    # URL веб-приложения — index.html?restaurant=...
    url = f"{WEBAPP_BASE_URL}/index.html?restaurant={restaurant}"
    keyboard = [
        [InlineKeyboardButton("🍽 Открыть меню", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"Меню ресторана *{restaurant}*:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Открыть WebApp: бронирование
async def open_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    row = await get_user(user_id)
    restaurant = row[4] if row else None
    if not restaurant:
        await query.edit_message_text("⚠️ Сначала выберите ресторан.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]))
        return
    url = f"{WEBAPP_BASE_URL}/index.html?restaurant={restaurant}#booking"
    keyboard = [
        [InlineKeyboardButton("📅 Забронировать", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"Бронирование в *{restaurant}*:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Обработчик callback-кнопок
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "profile":
        await show_profile(update, context)
    elif data == "choose_restaurant":
        await choose_restaurant(update, context)
    elif data.startswith("set_rest|"):
        await set_restaurant(update, context)
    elif data == "open_menu":
        await open_menu(update, context)
    elif data == "open_booking":
        await open_booking(update, context)
    elif data == "about":
        await about_restaurant(update, context)
    elif data == "main_menu":
        await show_main_menu(update)
    else:
        await update.callback_query.answer("Неизвестная кнопка")

# Обработка данных от WebApp (tg.sendData)
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not getattr(msg, "web_app_data", None):
        return
    data_raw = msg.web_app_data.data  # JSON строка, присланная script.js
    try:
        payload = json.loads(data_raw)
    except Exception as e:
        logger.exception("Невозможно распарсить web_app_data")
        await msg.reply_text("Ошибка: неверный формат данных от WebApp.")
        return

    user = update.effective_user
    restaurant = payload.get("restaurant")
    action = payload.get("action")
    data = payload.get("data")

    # Сохраним бронь в БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bookings (user_id, restaurant, type, payload, created_at) VALUES (?,?,?,?,?)",
            (user.id, restaurant, action, json.dumps(data, ensure_ascii=False), datetime.utcnow().isoformat())
        )
        await db.commit()
        # найдём id последней вставки
        async with db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            booking_id = row[0] if row else None

    # Отправим админу уведомление
    admin_text = f"Новая WebApp бронь #{booking_id}\nПользователь: {user.full_name or user.username} ({user.id})\nРесторан: {restaurant}\nДействие: {action}\nДанные: {json.dumps(data, ensure_ascii=False)}"
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)
    except Exception as e:
        logger.warning("Не удалось отправить сообщение админу: %s", e)

    # Ответим пользователю
    await msg.reply_text("✅ Ваш запрос получен. Спасибо! Мы свяжемся с вами для подтверждения.")

# Команда /cancel (на случай разговоров)
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Отменено.")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Отменено.")

# ========== Запуск приложения ==========
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(CommandHandler("cancel", cancel))

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
