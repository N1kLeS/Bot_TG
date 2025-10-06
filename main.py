import logging
import sqlite3
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8376106425:AAFj2QKo7qK5zqvbGbhE_whIbUngY8S9r10"
ADMIN_CHAT_ID = 123456789  # id вашего аккаунта или группы
DB_PATH = "restaurant_bot.db"

# ========== ЛОГИ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== СОСТОЯНИЯ ==========
(
    REG_NAME,
    REG_PHONE,
    CHOOSE_RESTAURANT,
) = range(3)

# ========== ИНИЦИАЛИЗАЦИЯ БД ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # пользователи
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        phone TEXT,
        restaurant_id INTEGER
    )
    """)
    # рестораны
    cur.execute("""
    CREATE TABLE IF NOT EXISTS restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT
    )
    """)
    conn.commit()

    # если нет ресторанов — добавим тестовые
    cur.execute("SELECT COUNT(*) FROM restaurants")
    if cur.fetchone()[0] == 0:
        restaurants = [
            ("La Tavola", "Итальянский ресторан с домашней пастой и вином"),
            ("Sakura", "Японская кухня, суши, роллы и тепаньяки"),
            ("Grill House", "Стейки и бургеры на открытом огне")
        ]
        cur.executemany("INSERT INTO restaurants (name, description) VALUES (?,?)", restaurants)
        conn.commit()

    conn.close()

# ========== ХЕНДЛЕРЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT full_name, phone, restaurant_id FROM users WHERE user_id=?", (user_id,))
    user = cur.fetchone()
    conn.close()

    if user is None:
        await update.message.reply_text("👋 Привет! Давайте зарегистрируемся.\nВведите ваше имя:")
        return REG_NAME
    elif user[2] is None:
        await show_restaurant_choice(update, context)
        return CHOOSE_RESTAURANT
    else:
        await show_main_menu(update, context)
        return ConversationHandler.END


# === Регистрация ===
async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text("📱 Отлично! Теперь введите ваш телефон (в формате +7XXXXXXXXXX):")
    return REG_PHONE

async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user_id = update.effective_user.id
    name = context.user_data["name"]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (user_id, full_name, phone) VALUES (?,?,?)",
                (user_id, name, phone))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Регистрация завершена!")
    await show_restaurant_choice(update, context)
    return CHOOSE_RESTAURANT


# === Выбор ресторана ===
async def show_restaurant_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM restaurants")
    items = cur.fetchall()
    conn.close()

    buttons = [[InlineKeyboardButton(name, callback_data=f"rest|{rid}")] for rid, name in items]
    await update.message.reply_text("🏢 Выберите ресторан:", reply_markup=InlineKeyboardMarkup(buttons))

async def restaurant_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    rest_id = int(data[1])
    user_id = query.from_user.id

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET restaurant_id=? WHERE user_id=?", (rest_id, user_id))
    conn.commit()
    # получим название ресторана
    cur.execute("SELECT name FROM restaurants WHERE id=?", (rest_id,))
    rest_name = cur.fetchone()[0]
    conn.close()

    await query.message.reply_text(f"🍷 Отлично! Вы выбрали ресторан *{rest_name}*.", parse_mode="Markdown")
    await show_main_menu(update, context)
    return ConversationHandler.END


# === Главное меню ===
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍽 Меню", callback_data="menu")],
        [InlineKeyboardButton("📅 Бронь", callback_data="booking")],
        [InlineKeyboardButton("ℹ️ О ресторане", callback_data="about")],
        [InlineKeyboardButton("⭐ Мой профиль", callback_data="profile")]
    ]
    if update.message:
        await update.message.reply_text("Главное меню:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.message.reply_text("Главное меню:", reply_markup=InlineKeyboardMarkup(keyboard))


# === Обработчики кнопок главного меню (пока заглушки) ===
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("🍝 Здесь будет меню ресторана (в следующей версии).")

async def booking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("📅 Здесь будет бронь столика (в следующей версии).")

async def about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.name, r.description 
        FROM users u
        JOIN restaurants r ON u.restaurant_id = r.id
        WHERE u.user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        name, desc = row
        await query.message.reply_text(f"ℹ️ *{name}*\n{desc}", parse_mode="Markdown")
    else:
        await query.message.reply_text("Ресторан не выбран.")

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = update.callback_query.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT full_name, phone, r.name 
        FROM users u
        LEFT JOIN restaurants r ON u.restaurant_id = r.id
        WHERE u.user_id=?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        name, phone, rest = row
        await update.callback_query.message.reply_text(
            f"👤 *{name}*\n📱 {phone}\n🏢 Ресторан: {rest or 'не выбран'}",
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.message.reply_text("Профиль не найден.")


# === Отмена ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ========== MAIN ==========
def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone)],
            CHOOSE_RESTAURANT: [CallbackQueryHandler(restaurant_chosen, pattern="^rest\\|")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)

    # кнопки главного меню
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(booking_callback, pattern="^booking$"))
    app.add_handler(CallbackQueryHandler(about_callback, pattern="^about$"))
    app.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile$"))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
