
import os
import time
from dotenv import load_dotenv
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, filters
)

(
    TABLE, STRENGTH, AROMA, STOPS, BOWL, BOWL_MANUAL, DRAFT, TEA,
    WAITING_ADD_DISH, WAITING_REMOVE_DISH, CONFIRM, EDIT_FIELD
) = range(12)

STRENGTH_CHOICES = [
    ["Легкий", "Легкий-Средний"],
    ["Безопасный Дарк", "Средний"],
    ["Средний+", "Выше среднего", "Крепкий"]
]
DRAFT_CHOICES = [["Union", "Yapona", "Wookah"]]
BOWL_CHOICES = [
    [InlineKeyboardButton("Хайп Т", callback_data="bowl_Хайп Т"),
     InlineKeyboardButton("Япона Т", callback_data="bowl_Япона Т")],
    [InlineKeyboardButton("Концептик", callback_data="bowl_Концептик"),
     InlineKeyboardButton("Фанел", callback_data="bowl_Фанел")],
    [InlineKeyboardButton("Элиан", callback_data="bowl_Элиан"),
     InlineKeyboardButton("КС", callback_data="bowl_КС")],
    [InlineKeyboardButton("Ввести вручную", callback_data="bowl_manual")],
    [InlineKeyboardButton("⏭ Пропустить вопрос", callback_data="skip"),
     InlineKeyboardButton("⚡ Быстрый заказ", callback_data="fast_order")]
]

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN_TEST")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID_TEST", "0"))

if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен. Укажи его в .env")

TOPICS = {
    "1 Зона": 5,
    "2 Зона": 2,
    "2 Этаж": 6,
    "general": None
}

STOPLIST_FILE = "stoplist.txt"

MAIN_MENU_KEYBOARD = [
    [InlineKeyboardButton("📝 Сделать заказ", callback_data="main_start")],
    [InlineKeyboardButton("📋 Стоп-лист", callback_data="main_stoplist")]
]

def load_stop_dishes():
    if not os.path.exists(STOPLIST_FILE):
        return []
    with open(STOPLIST_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_stop_dishes(stop_dishes):
    with open(STOPLIST_FILE, "w", encoding="utf-8") as f:
        for dish in stop_dishes:
            f.write(dish + "\n")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD)
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "Главное меню:",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD)
        )

async def main_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "main_stoplist":
        await stoplist(update, context)

async def stoplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stop_dishes = load_stop_dishes()
    text = "Стоп-лист пуст." if not stop_dishes else \
        "Стоп-лист:\n" + "\n".join(f"- {dish}" for dish in stop_dishes)
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить блюдо", callback_data="add_dish"),
            InlineKeyboardButton("➖ Удалить блюдо", callback_data="remove_dish"),
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="to_menu")
        ]
    ]
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def stoplist_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add_dish":
        await query.message.reply_text("Введите название блюда для добавления в стоп-лист:")
        return WAITING_ADD_DISH
    elif query.data == "remove_dish":
        await query.message.reply_text("Введите название блюда для удаления из стоп-листа:")
        return WAITING_REMOVE_DISH
    elif query.data == "to_menu":
        await menu(update, context)
        return ConversationHandler.END

async def add_dish_wait(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dish = update.message.text.strip()
    stop_dishes = load_stop_dishes()
    user = update.effective_user
    username = (
        f"@{user.username}" if user.username else user.full_name or user.id
    )
    if dish.lower() in (d.lower() for d in stop_dishes):
        await update.message.reply_text(f"Позиция «{dish}» уже в стоп-листе.")
    else:
        stop_dishes.append(dish)
        save_stop_dishes(stop_dishes)
        await update.message.reply_text(
            f"Позиция «{dish}» добавлена в стоп-лист пользователем {username}."
        )
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"➕ Позиция «{dish}» добавлена в стоп-лист пользователем {username}."
        )
    await stoplist(update, context)
    return ConversationHandler.END

async def remove_dish_wait(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dish = update.message.text.strip()
    stop_dishes = load_stop_dishes()
    user = update.effective_user
    username = (
        f"@{user.username}" if user.username else user.full_name or user.id
    )
    for d in stop_dishes:
        if d.lower() == dish.lower():
            stop_dishes.remove(d)
            save_stop_dishes(stop_dishes)
            await update.message.reply_text(
                f"Позиция «{dish}» удалена из стоп-листа пользователем {username}."
            )
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"➖ Позиция «{dish}» удалена из стоп-листа пользователем {username}."
            )
            break
    else:
        await update.message.reply_text(f"Позиция «{dish}» не найдена в стоп-листе.")
    await stoplist(update, context)
    return ConversationHandler.END

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
    return None, None

def order_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ Пропустить вопрос", callback_data="skip"),
            InlineKeyboardButton("⚡ Быстрый заказ", callback_data="fast_order")
        ]
    ])

def strength_keyboard():
    keyboard = [row for row in STRENGTH_CHOICES]
    keyboard.append(["⏭ Пропустить вопрос", "⚡ Быстрый заказ"])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def draft_keyboard():
    keyboard = [row for row in DRAFT_CHOICES]
    keyboard.append(["⏭ Пропустить вопрос", "⚡ Быстрый заказ"])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def bowl_keyboard():
    return InlineKeyboardMarkup(BOWL_CHOICES)

# --- Логика заказа с кнопками и редактированием ---

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_chat.send_message(
        "Вопрос 1: Номер стола?",
        reply_markup=order_keyboard()
    )
    return TABLE

async def table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        table_number = update.message.text
        context.user_data['table'] = table_number
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['table'] = ""
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    else:
        return TABLE

    zone, topic_id = get_zone_and_topic_id(context.user_data.get('table', ''))
    context.user_data['zone'] = zone
    context.user_data['topic_id'] = topic_id

    if update.message:
        await update.message.reply_text(
            "Вопрос 2: Крепость?",
            reply_markup=strength_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            "Вопрос 2: Крепость?",
            reply_markup=strength_keyboard()
        )
    return STRENGTH

async def strength(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['strength'] = update.message.text
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['strength'] = ""
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    else:
        return STRENGTH

    if update.message:
        await update.message.reply_text(
            "Вопрос 3: Ароматика?",
            reply_markup=order_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            "Вопрос 3: Ароматика?",
            reply_markup=order_keyboard()
        )
    return AROMA

async def aroma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_choice = update.message.text.strip().lower()
        stop_dishes = [dish.lower() for dish in load_stop_dishes()]
        for stop_word in stop_dishes:
            if stop_word and stop_word in user_choice:
                await update.message.reply_text(
                    f"Извините, позиция «{stop_word.capitalize()}» временно недоступна. Пожалуйста, выберите другую ароматику.",
                    reply_markup=order_keyboard()
                )
                return AROMA
        context.user_data['aroma'] = update.message.text
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['aroma'] = ""
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    else:
        return AROMA

    if update.message:
        await update.message.reply_text(
            "Вопрос 4: Стопы?",
            reply_markup=order_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            "Вопрос 4: Стопы?",
            reply_markup=order_keyboard()
        )
    return STOPS

async def stops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['stops'] = update.message.text
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['stops'] = ""
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    else:
        return STOPS

    if update.message:
        await update.message.reply_text(
            "Вопрос 5: Какая чаша?",
            reply_markup=bowl_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            "Вопрос 5: Какая чаша?",
            reply_markup=bowl_keyboard()
        )
    return BOWL

async def bowl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['bowl'] = update.message.text
        return await bowl_next(update, context)
    elif update.callback_query:
        data = update.callback_query.data
        if data == "skip":
            context.user_data['bowl'] = ""
            return await bowl_next(update, context)
        elif data == "fast_order":
            return await finish_order(update, context)
        elif data == "bowl_manual":
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Введите название чаши вручную:",
                reply_markup=order_keyboard()
            )
            return BOWL_MANUAL
        elif data.startswith("bowl_"):
            context.user_data['bowl'] = data[5:]
            return await bowl_next(update, context)
    return BOWL

async def bowl_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['bowl'] = update.message.text
        return await bowl_next(update, context)
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['bowl'] = ""
        return await bowl_next(update, context)
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    return BOWL_MANUAL

async def bowl_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Вопрос 6: Тяга?",
            reply_markup=draft_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "Вопрос 6: Тяга?",
            reply_markup=draft_keyboard()
        )
    return DRAFT

async def draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['draft'] = update.message.text
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['draft'] = ""
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    else:
        return DRAFT

    if update.message:
        await update.message.reply_text(
            "Вопрос 7: Китайский чай и количество персон?",
            reply_markup=order_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            "Вопрос 7: Китайский чай и количество персон?",
            reply_markup=order_keyboard()
        )
    return TEA

async def tea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['tea'] = update.message.text
    elif update.callback_query and update.callback_query.data == "skip":
        context.user_data['tea'] = ""
    elif update.callback_query and update.callback_query.data == "fast_order":
        return await finish_order(update, context)
    else:
        return TEA

    return await show_confirm(update, context)

async def show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = (
        f"Проверьте заказ:\n"
        f"1️⃣ Номер стола: {context.user_data.get('table', '')}\n"
        f"2️⃣ Крепость: {context.user_data.get('strength', '')}\n"
        f"3️⃣ Ароматика: {context.user_data.get('aroma', '')}\n"
        f"4️⃣ Стопы: {context.user_data.get('stops', '')}\n"
        f"5️⃣ Чаша: {context.user_data.get('bowl', '')}\n"
        f"6️⃣ Тяга: {context.user_data.get('draft', '')}\n"
        f"7️⃣ Китайский чай и количество персон: {context.user_data.get('tea', '')}\n\n"
        "Если хотите изменить какой-либо пункт, нажмите на соответствующую кнопку.\n"
        "Если всё верно — подтвердите заказ."
    )
    keyboard = [
        [InlineKeyboardButton("1️⃣ Номер стола", callback_data="edit_table"),
         InlineKeyboardButton("2️⃣ Крепость", callback_data="edit_strength")],
        [InlineKeyboardButton("3️⃣ Ароматика", callback_data="edit_aroma"),
         InlineKeyboardButton("4️⃣ Стопы", callback_data="edit_stops")],
        [InlineKeyboardButton("5️⃣ Чаша", callback_data="edit_bowl"),
         InlineKeyboardButton("6️⃣ Тяга", callback_data="edit_draft")],
        [InlineKeyboardButton("7️⃣ Чай", callback_data="edit_tea")],
        [InlineKeyboardButton("✅ Всё верно, отправить заказ", callback_data="confirm_order")]
    ]
    if update.message:
        await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text(summary, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM

async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "confirm_order":
        return await finish_order(update, context)
    elif data.startswith("edit_"):
        field = data.replace("edit_", "")
        context.user_data["edit_field"] = field
        return await edit_field_start(update, context, field)
    return CONFIRM

async def edit_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE, field: str):
    prompts = {
        "table": "Введите новый номер стола:",
        "strength": "Выберите новую крепость:",
        "aroma": "Введите новую ароматику:",
        "stops": "Введите новые стопы:",
        "bowl": "Выберите новую чашу:",
        "draft": "Выберите новую тягу:",
        "tea": "Введите новый китайский чай и количество персон:"
    }
    if field == "strength":
        if update.callback_query:
            await update.callback_query.edit_message_text(prompts[field], reply_markup=strength_keyboard())
        else:
            await update.message.reply_text(prompts[field], reply_markup=strength_keyboard())
        return STRENGTH
    elif field == "draft":
        if update.callback_query:
            await update.callback_query.edit_message_text(prompts[field], reply_markup=draft_keyboard())
        else:
            await update.message.reply_text(prompts[field], reply_markup=draft_keyboard())
        return DRAFT
    elif field == "bowl":
        if update.callback_query:
            await update.callback_query.edit_message_text(prompts[field], reply_markup=bowl_keyboard())
        else:
            await update.message.reply_text(prompts[field], reply_markup=bowl_keyboard())
        return BOWL
    else:
        if update.callback_query:
            await update.callback_query.edit_message_text(prompts[field], reply_markup=order_keyboard())
        else:
            await update.message.reply_text(prompts[field], reply_markup=order_keyboard())
        return {
            "table": TABLE, "aroma": AROMA, "stops": STOPS, "tea": TEA
        }[field]

async def finish_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    table = context.user_data.get('table', '')
    zone = context.user_data.get('zone', '❓')
    topic_id = context.user_data.get('topic_id')
    order_time = int(time.time())
    user_id = update.effective_user.id

    # Сохраняем всю информацию о заказе для дальнейшего использования
    context.bot_data.setdefault("orders", {})[order_time] = {
        "user_id": user_id,
        "table": table
    }

    summary = (
        f"Новый заказ от пользователя @{update.effective_user.username or update.effective_user.id}:\n"
        f"Зона: {zone}\n"
        f"Номер стола: {context.user_data.get('table', '')}\n"
        f"Крепость: {context.user_data.get('strength', '')}\n"
        f"Ароматика: {context.user_data.get('aroma', '')}\n"
        f"Стопы: {context.user_data.get('stops', '')}\n"
        f"Чаша: {context.user_data.get('bowl', '')}\n"
        f"Тяга: {context.user_data.get('draft', '')}\n"
        f"Китайский чай и количество персон: {context.user_data.get('tea', '')}"
    )

    if update.message:
        await update.message.reply_text("Спасибо! Ваш заказ принят.", reply_markup=ReplyKeyboardRemove())
    elif update.callback_query:
        await update.callback_query.edit_message_text("Спасибо! Ваш заказ принят.")

    ready_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ КАЛЬЯН ГОТОВ", callback_data=f"order_ready|{order_time}")]
    ])

    if topic_id:
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

    if zone in ["1 Зона", "2 Зона"]:
        general_topic_id = TOPICS["general"]
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=summary,
            message_thread_id=general_topic_id,
            reply_markup=ready_keyboard
        )

    await menu(update, context)
    return ConversationHandler.END

async def order_ready_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("order_ready|"):
        order_time_str = data.split("|")[1]
        try:
            order_time = int(order_time_str)
        except Exception:
            await query.edit_message_text("Ошибка: не удалось определить время заказа.")
            return

        now = int(time.time())
        elapsed = now - order_time
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins} мин {secs} сек" if mins else f"{secs} сек"
        text = query.message.text + f"\n\n✅ КАЛЬЯН ГОТОВ!\n⏱ Время ожидания: {time_str}"

        await query.edit_message_text(text)

        # Получаем user_id и номер стола из bot_data
        order_info = context.bot_data.get("orders", {}).get(order_time)
        if order_info:
            user_id = order_info.get("user_id")
            table = order_info.get("table", "неизвестен")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"КАЛЬЯН ГОТОВ! ПОРА ОТДАВАТЬ ЗА СТОЛ №{table}."
                )
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler(['menu', 'start'], menu))
    app.add_handler(CallbackQueryHandler(main_menu_button, pattern=r"^main_stoplist$"))
    app.add_handler(CallbackQueryHandler(order_ready_callback, pattern=r"^order_ready\|"))

    stoplist_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(stoplist_button, pattern=r"^(add_dish|remove_dish|to_menu)$")
        ],
        states={
            WAITING_ADD_DISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_dish_wait)],
            WAITING_REMOVE_DISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_dish_wait)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(stoplist_conv)

    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order, pattern=r"^main_start$")],
        states={
            TABLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, table),
                CallbackQueryHandler(table, pattern=r"^(skip|fast_order)$")
            ],
            STRENGTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, strength),
                CallbackQueryHandler(strength, pattern=r"^(skip|fast_order)$")
            ],
            AROMA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, aroma),
                CallbackQueryHandler(aroma, pattern=r"^(skip|fast_order)$")
            ],
            STOPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, stops),
                CallbackQueryHandler(stops, pattern=r"^(skip|fast_order)$")
            ],
            BOWL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bowl),
                CallbackQueryHandler(bowl)  # <-- pattern убран!
            ],
            BOWL_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bowl_manual),
                CallbackQueryHandler(bowl_manual, pattern=r"^(skip|fast_order)$")
            ],
            DRAFT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, draft),
                CallbackQueryHandler(draft, pattern=r"^(skip|fast_order)$")
            ],
            TEA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tea),
                CallbackQueryHandler(tea, pattern=r"^(skip|fast_order)$")
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_callback)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(order_conv)

    app.run_polling()

if __name__ == '__main__':
    main()
