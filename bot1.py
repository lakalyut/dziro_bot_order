
import asyncio
from time import time
import aiosqlite
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

DB_FILE = "templates.db"

TABLE, AROMA, STRENGTH, BOWL, DRAFT, SAVE_TEMPLATE_LABEL, MANUAL_BOWL = range(7)

STRENGTH_CHOICES = [
    ["Легкий", "Легкий+", "Легкий-Средний"],
    ["Безопасный Дарк", "Средний"],
    ["Средний+", "Выше среднего", "Крепкий"]
]
DRAFT_CHOICES = ["Union", "Yapona", "Wookah"]
BOWL_CHOICES = [
    [InlineKeyboardButton("Прямоток", callback_data="bowl_Прямоток"),
     InlineKeyboardButton("Фанел", callback_data="bowl_Фанел")],
    [InlineKeyboardButton("Фольга", callback_data="bowl_Фольга"),
     InlineKeyboardButton("Грейпфрут", callback_data="bowl_Грейпфрут")],
    [InlineKeyboardButton("Гранат", callback_data="bowl_Гранат")],
    [InlineKeyboardButton("Ввести вручную", callback_data="bowl_manual")]
]

TOPICS = {
    "1 Зона": 2,
    "2 Зона": 3,
    "2 Этаж": 5,
    "general": None
}

# --- DATABASE FUNCTIONS ---

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                aroma TEXT,
                strength TEXT,
                bowl TEXT,
                draft TEXT
            )
        """)
        await db.commit()

async def save_template(label, aroma, strength, bowl, draft):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO templates (label, aroma, strength, bowl, draft) VALUES (?, ?, ?, ?, ?)",
            (label, aroma, strength, bowl, draft)
        )
        await db.commit()

async def get_templates():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id, label, aroma, strength, bowl, draft FROM templates") as cursor:
            rows = await cursor.fetchall()
            return rows

async def get_template_by_id(template_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT id, label, aroma, strength, bowl, draft FROM templates WHERE id = ?",
            (template_id,)
        ) as cursor:
            return await cursor.fetchone()

# --- BUSINESS LOGIC ---

def get_zone_and_topic_id(table_number: str):
    table_number = table_number.strip()
    try:
        num = int(table_number)
    except ValueError:
        num = None
    if (num is not None and 1 <= num <= 16) or table_number in ["101", "102", "103"]:
        return "1 Зона", TOPICS["1 Зона"]
    if (num is not None and 17 <= num <= 32) or table_number in ["104", "105"]:
        return "2 Зона", TOPICS["2 Зона"]
    if (num is not None and 33 <= num <= 47) or table_number in ["201", "777"]:
        return "2 Этаж", TOPICS["2 Этаж"]
    return "General", TOPICS["general"]

def get_order_keyboard(context):
    data = context.user_data
    def val(key): return data.get(key, "❌ Не выбрано")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Стол: {val('table')}", callback_data="edit_table")],
        [InlineKeyboardButton(f"Ароматика: {val('aroma')}", callback_data="edit_aroma")],
        [InlineKeyboardButton(f"Крепость: {val('strength')}", callback_data="edit_strength")],
        [InlineKeyboardButton(f"Чаша: {val('bowl')}", callback_data="edit_bowl")],
        [InlineKeyboardButton(f"Тяга: {val('draft')}", callback_data="edit_draft")],
        [InlineKeyboardButton("✅ Отправить заказ", callback_data="send_order")]
    ])

def get_table_input_keyboard(current_value: str):
    keyboard = [
        [InlineKeyboardButton("1", callback_data="table_digit_1"),
         InlineKeyboardButton("2", callback_data="table_digit_2"),
         InlineKeyboardButton("3", callback_data="table_digit_3")],
        [InlineKeyboardButton("4", callback_data="table_digit_4"),
         InlineKeyboardButton("5", callback_data="table_digit_5"),
         InlineKeyboardButton("6", callback_data="table_digit_6")],
        [InlineKeyboardButton("7", callback_data="table_digit_7"),
         InlineKeyboardButton("8", callback_data="table_digit_8"),
         InlineKeyboardButton("9", callback_data="table_digit_9")],
        [InlineKeyboardButton("0", callback_data="table_digit_0")],
        [
            InlineKeyboardButton("⬅️ Стереть", callback_data="table_digit_backspace"),
            InlineKeyboardButton("✅ Готово", callback_data="table_digit_done")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Сделать заказ", callback_data="main_order")],
        [InlineKeyboardButton("⚡ Быстрый заказ", callback_data="quick_order_menu")]
    ]
    if update.message:
        msg = await update.message.reply_text("Главное меню:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["order_msg_id"] = msg.message_id
    else:
        msg = await update.callback_query.edit_message_text("Главное меню:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["order_msg_id"] = msg.message_id

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_msg_id = context.user_data.get("order_msg_id")
    context.user_data.clear()
    if order_msg_id:
        context.user_data["order_msg_id"] = order_msg_id
    await update.callback_query.answer()
    msg = await update.callback_query.edit_message_text(
        "Меню заказа. Нажмите на пункт для ввода/изменения:",
        reply_markup=get_order_keyboard(context)
    )
    context.user_data["order_msg_id"] = msg.message_id

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edit_", "")
    context.user_data["edit_field"] = field
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = query.message.chat_id

    if field == "strength":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text, callback_data=f"strength_{text}") for text in row]
            for row in STRENGTH_CHOICES
        ])
        await context.bot.edit_message_text(
            "Выберите крепость:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=keyboard
        )
        return STRENGTH
    elif field == "bowl":
        await context.bot.edit_message_text(
            "Выберите чашу:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=InlineKeyboardMarkup(BOWL_CHOICES)
        )
        return BOWL
    elif field == "draft":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text, callback_data=f"draft_{text}")]
            for text in DRAFT_CHOICES
        ])
        await context.bot.edit_message_text(
            "Выберите тягу:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=keyboard
        )
        return DRAFT
    elif field == "table":
        context.user_data["table_input"] = ""
        await context.bot.edit_message_text(
            f"Введите номер стола:\n\n<b>{'' if '' else '—'}</b>",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=get_table_input_keyboard(""),
            parse_mode="HTML"
        )
        return TABLE
    else:
        prompts = {
            "aroma": "Введите ароматику:"
        }
        await context.bot.edit_message_text(
            prompts[field],
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=None
        )
        return AROMA

async def table_digit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = query.message.chat_id

    value = context.user_data.get("table_input", "")

    if data.startswith("table_digit_"):
        action = data.replace("table_digit_", "")
        if action.isdigit():
            value += action
        elif action == "backspace":
            value = value[:-1]
        elif action == "done":
            if value:
                context.user_data["table"] = value
                context.user_data["edit_field"] = None
                if context.user_data.get("from_quick"):
                    context.user_data.pop("from_quick")
                    await send_order(update, context, from_quick=True)
                    order_msg_id = context.user_data.get("order_msg_id")
                    context.user_data.clear()
                    if order_msg_id:
                        context.user_data["order_msg_id"] = order_msg_id
                    await menu(update, context)
                    return ConversationHandler.END
                else:
                    try:
                        await context.bot.edit_message_text(
                            "Сохранено!\n\nМеню заказа. Нажмите на пункт для ввода/изменения:",
                            chat_id=chat_id,
                            message_id=order_msg_id,
                            reply_markup=get_order_keyboard(context)
                        )
                    except Exception:
                        pass
                    return ConversationHandler.END
            else:
                try:
                    await context.bot.edit_message_text(
                        f"Введите номер стола:\n\n<b>{value if value else '—'}</b>\n\n❗ Введите хотя бы одну цифру.",
                        chat_id=chat_id,
                        message_id=order_msg_id,
                        reply_markup=get_table_input_keyboard(value),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                return TABLE

    context.user_data["table_input"] = value
    try:
        await context.bot.edit_message_text(
            f"Введите номер стола:\n\n<b>{value if value else '—'}</b>",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=get_table_input_keyboard(value),
            parse_mode="HTML"
        )
    except Exception:
        pass
    return TABLE

async def save_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("edit_field")
    if field not in ["aroma", "bowl"]:
        return
    context.user_data[field] = update.message.text
    context.user_data["edit_field"] = None

    # Удалить сообщение пользователя
    try:
        await update.message.delete()
    except Exception:
        pass

    order_msg_id = context.user_data.get('order_msg_id')
    chat_id = update.effective_chat.id

    if context.user_data.get("from_quick"):
        context.user_data.pop("from_quick")
        await send_order(update, context, from_quick=True)
        order_msg_id = context.user_data.get("order_msg_id")
        context.user_data.clear()
        if order_msg_id:
            context.user_data["order_msg_id"] = order_msg_id
        await menu(update, context)
        return ConversationHandler.END

    try:
        await context.bot.edit_message_text(
            "Сохранено!\n\nМеню заказа. Нажмите на пункт для ввода/изменения:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=get_order_keyboard(context)
        )
    except Exception:
        pass
    return ConversationHandler.END

async def save_strength_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = query.data.replace("strength_", "")
    context.user_data["strength"] = text
    context.user_data["edit_field"] = None
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = query.message.chat_id
    try:
        await context.bot.edit_message_text(
            "Сохранено!\n\nМеню заказа. Нажмите на пункт для ввода/изменения:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=get_order_keyboard(context)
        )
    except Exception:
        pass
    return ConversationHandler.END

async def save_draft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = query.data.replace("draft_", "")
    context.user_data["draft"] = text
    context.user_data["edit_field"] = None
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = query.message.chat_id
    try:
        await context.bot.edit_message_text(
            "Сохранено!\n\nМеню заказа. Нажмите на пункт для ввода/изменения:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=get_order_keyboard(context)
        )
    except Exception:
        pass
    return ConversationHandler.END

async def bowl_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = query.message.chat_id
    if data == "bowl_manual":
        context.user_data["edit_field"] = "bowl"
        try:
            await context.bot.edit_message_text(
                "Введите название чаши вручную:",
                chat_id=chat_id,
                message_id=order_msg_id,
                reply_markup=None
            )
        except Exception:
            pass
        return MANUAL_BOWL
    elif data.startswith("bowl_"):
        context.user_data["bowl"] = data[5:]
        context.user_data["edit_field"] = None
        try:
            await context.bot.edit_message_text(
                "Сохранено!\n\nМеню заказа. Нажмите на пункт для ввода/изменения:",
                chat_id=chat_id,
                message_id=order_msg_id,
                reply_markup=get_order_keyboard(context)
            )
        except Exception:
            pass
        return ConversationHandler.END

async def save_manual_bowl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bowl"] = update.message.text
    context.user_data["edit_field"] = None

    # Удалить сообщение пользователя
    try:
        await update.message.delete()
    except Exception:
        pass

    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = update.effective_chat.id
    try:
        await context.bot.edit_message_text(
            "Сохранено!\n\nМеню заказа. Нажмите на пункт для ввода/изменения:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=get_order_keyboard(context)
        )
    except Exception:
        pass
    return ConversationHandler.END

async def send_order(update: Update, context: ContextTypes.DEFAULT_TYPE, from_quick=False):
    data = context.user_data
    table = data.get('table', '')
    zone, topic_id = get_zone_and_topic_id(table)
    user_id = update.effective_user.id

    summary = (
        f"Новый заказ от пользователя @{update.effective_user.username or update.effective_user.id}:\n"
        f"Зона: {zone}\n"
        f"Стол: {table}\n"
        f"Ароматика: {data.get('aroma', '❌ Не выбрано')}\n"
        f"Крепость: {data.get('strength', '❌ Не выбрано')}\n"
        f"Чаша: {data.get('bowl', '❌ Не выбрано')}\n"
        f"Тяга: {data.get('draft', '❌ Не выбрано')}\n"
    )

    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not from_quick:
        try:
            if order_msg_id and chat_id:
                await context.bot.edit_message_text(
                    "Спасибо! Ваш заказ отправлен.",
                    chat_id=chat_id,
                    message_id=order_msg_id,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💾 Сохранить как шаблон", callback_data="save_as_template")],
                        [InlineKeyboardButton("📝 Сделать заказ", callback_data="main_order")],
                        [InlineKeyboardButton("⚡ Быстрый заказ", callback_data="quick_order_menu")]
                    ])
                )
            elif hasattr(update, "callback_query") and update.callback_query:
                await update.callback_query.edit_message_text(
                    "Спасибо! Ваш заказ отправлен.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💾 Сохранить как шаблон", callback_data="save_as_template")],
                        [InlineKeyboardButton("📝 Сделать заказ", callback_data="main_order")],
                        [InlineKeyboardButton("⚡ Быстрый заказ", callback_data="quick_order_menu")]
                    ])
                )
        except Exception:
            pass

    ready_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Кальян Отдан", callback_data=f"order_given|{int(time())}")]
    ])

    if topic_id is not None:
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=summary,
            message_thread_id=topic_id,
            reply_markup=ready_keyboard
        )
    else:
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"(Не определена тема для стола {table})\n" + summary,
            reply_markup=ready_keyboard
        )

async def order_given_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("order_given|"):
        order_time_str = data.split("|")[1]
        try:
            order_time = int(order_time_str)
        except Exception:
            await query.edit_message_text("Ошибка: не удалось определить время заказа.")
            return

        now = int(time())
        elapsed = now - order_time
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins} мин {secs} сек" if mins else f"{secs} сек"

        text = query.message.text + f"\n\n✅ Кальян отдан!\n⏱ Время ожидания: {time_str}"

        await query.edit_message_text(text)

async def send_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_order(update, context, from_quick=False)

async def to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_msg_id = context.user_data.get("order_msg_id")
    context.user_data.clear()
    if order_msg_id:
        context.user_data["order_msg_id"] = order_msg_id
    await menu(update, context)

# ----------- Быстрые заказы (шаблоны) -----------

async def quick_order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    templates = await get_templates()
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id

    if not templates:
        try:
            await context.bot.edit_message_text(
                "Нет сохранённых быстрых заказов.",
                chat_id=chat_id,
                message_id=order_msg_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 В меню", callback_data="to_menu")]
                ])
            )
        except Exception:
            pass
        return

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"quick_order_apply_{tpl_id}")]
        for tpl_id, label, *_ in templates
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="to_menu")])
    try:
        await context.bot.edit_message_text(
            "Выберите шаблон для быстрого заказа:",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        pass

async def quick_order_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tpl_id = int(update.callback_query.data.replace("quick_order_apply_", ""))
    tpl = await get_template_by_id(tpl_id)
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = update.callback_query.message.chat_id

    if not tpl:
        try:
            await context.bot.edit_message_text(
                "Шаблон не найден.",
                chat_id=chat_id,
                message_id=order_msg_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 В меню", callback_data="to_menu")]
                ])
            )
        except Exception:
            pass
        return ConversationHandler.END

    _, label, aroma, strength, bowl, draft = tpl
    context.user_data.clear()
    if order_msg_id:
        context.user_data["order_msg_id"] = order_msg_id

    context.user_data["aroma"] = aroma
    context.user_data["strength"] = strength
    context.user_data["bowl"] = bowl
    context.user_data["draft"] = draft

    if not context.user_data.get("table"):
        context.user_data["edit_field"] = "table"
        context.user_data["from_quick"] = True
        context.user_data["table_input"] = ""
        try:
            await context.bot.edit_message_text(
                f"Введите номер стола:\n\n<b>{context.user_data['table_input'] if context.user_data['table_input'] else '—'}</b>",
                chat_id=chat_id,
                message_id=order_msg_id,
                reply_markup=get_table_input_keyboard(context.user_data["table_input"]),
                parse_mode="HTML"
            )
        except Exception:
            pass
        return TABLE
    else:
        await send_order(update, context, from_quick=True)
        context.user_data.clear()
        if order_msg_id:
            context.user_data["order_msg_id"] = order_msg_id
        await menu(update, context)
        return ConversationHandler.END

async def save_as_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = update.callback_query.message.chat_id
    try:
        await context.bot.edit_message_text(
            "Введите подпись для шаблона (например, ФИО гостя):",
            chat_id=chat_id,
            message_id=order_msg_id,
            reply_markup=None
        )
    except Exception:
        pass
    return SAVE_TEMPLATE_LABEL

async def save_template_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    label = update.message.text
    aroma = context.user_data.get("aroma")
    strength = context.user_data.get("strength")
    bowl = context.user_data.get("bowl")
    draft = context.user_data.get("draft")
    await save_template(label, aroma, strength, bowl, draft)

    # Удалить сообщение пользователя
    try:
        await update.message.delete()
    except Exception:
        pass

    order_msg_id = context.user_data.get("order_msg_id")
    chat_id = update.effective_chat.id
    try:
        await context.bot.edit_message_text(
            f"Шаблон '{label}' сохранён!",
            chat_id=chat_id,
            message_id=order_msg_id
        )
    except Exception:
        pass
    order_msg_id = context.user_data.get("order_msg_id")
    context.user_data.clear()
    if order_msg_id:
        context.user_data["order_msg_id"] = order_msg_id
    await menu(update, context)
    return ConversationHandler.END

# --- ASYNC INIT FOR TELEGRAM PTB ---

async def post_init(application: Application):
    await init_db()

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler(['menu', 'start'], menu))
    app.add_handler(CallbackQueryHandler(start_order, pattern="^main_order$"))
    app.add_handler(CallbackQueryHandler(send_order_callback, pattern="^send_order$"))
    app.add_handler(CallbackQueryHandler(to_menu_callback, pattern="^to_menu$"))
    app.add_handler(CallbackQueryHandler(order_given_callback, pattern=r"^order_given\|"))

    # Быстрые заказы
    app.add_handler(CallbackQueryHandler(quick_order_menu, pattern="^quick_order_menu$"))

    order_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_field, pattern=r"^edit_"),
            CallbackQueryHandler(bowl_choice, pattern=r"^bowl_.*|bowl_manual$"),
            CallbackQueryHandler(save_as_template, pattern="^save_as_template$"),
            CallbackQueryHandler(quick_order_apply, pattern="^quick_order_apply_"),
            CallbackQueryHandler(save_strength_callback, pattern=r"^strength_"),
            CallbackQueryHandler(save_draft_callback, pattern=r"^draft_"),
            CallbackQueryHandler(table_digit_callback, pattern="^table_digit_"),
        ],
        states={
            TABLE: [CallbackQueryHandler(table_digit_callback, pattern="^table_digit_")],
            AROMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_field)],
            STRENGTH: [CallbackQueryHandler(save_strength_callback, pattern=r"^strength_")],
            BOWL: [
                CallbackQueryHandler(bowl_choice, pattern=r"^bowl_.*|bowl_manual$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_manual_bowl)
            ],
            DRAFT: [CallbackQueryHandler(save_draft_callback, pattern=r"^draft_")],
            MANUAL_BOWL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_manual_bowl)],
            SAVE_TEMPLATE_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_template_label)],
        },
        fallbacks=[CommandHandler('cancel', menu)],
        allow_reentry=True
    )
    app.add_handler(order_conv)

    app.run_polling()

if __name__ == "__main__":
    main()
    