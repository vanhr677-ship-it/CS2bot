# -*- coding: utf-8 -*-
"""
Telegram бот для CS2 турніру
Функції: реєстрація, розсилка, розіграші, посилання на групу
Покращена версія з редагуванням та видаленням команд
"""

import logging
import json
import os
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= НАЛАШТУВАННЯ =============
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]
GROUP_LINK = os.getenv("GROUP_LINK")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
# ===========================================

# Стани для реєстрації
(TEAM_NAME, TEAM_TAG, 
 CAP_NICK, CAP_NAME, CAP_AGE, CAP_STEAM, CAP_DISCORD, CAP_TG,
 P2_NICK, P2_NAME, P2_AGE, P2_STEAM,
 P3_NICK, P3_NAME, P3_AGE, P3_STEAM,
 P4_NICK, P4_NAME, P4_AGE, P4_STEAM,
 P5_NICK, P5_NAME, P5_AGE, P5_STEAM,
 COMMENTS, CONFIRM) = range(26)

# Стани для редагування
EDIT_SELECT_TEAM, EDIT_SELECT_FIELD, EDIT_INPUT_VALUE = range(3)

# Файли для зберігання даних
REGISTRATIONS_FILE = 'registrations.json'
SUBSCRIBERS_FILE = 'subscribers.json'

# ============= ФУНКЦІЇ ДЛЯ РОБОТИ З ДАНИМИ =============

def load_data(filename):
    """Завантажити дані з файлу"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return [] if filename == REGISTRATIONS_FILE else []

def save_data(filename, data):
    """Зберегти дані у файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_subscriber(user_id):
    """Додати підписника"""
    subscribers = load_data(SUBSCRIBERS_FILE)
    if user_id not in subscribers:
        subscribers.append(user_id)
        save_data(SUBSCRIBERS_FILE, subscribers)
        return True
    return False

def is_admin(user_id):
    """Перевірка чи користувач адмін"""
    return user_id in ADMIN_IDS

def validate_steam_id(steam_id):
    """Перевірка чи Steam ID містить тільки цифри"""
    return steam_id.isdigit() and len(steam_id) >= 8

def get_team_by_index(index):
    """Отримати команду за індексом"""
    registrations = load_data(REGISTRATIONS_FILE)
    if 0 <= index < len(registrations):
        return registrations[index]
    return None

def update_team(index, team_data):
    """Оновити дані команди"""
    registrations = load_data(REGISTRATIONS_FILE)
    if 0 <= index < len(registrations):
        registrations[index] = team_data
        save_data(REGISTRATIONS_FILE, registrations)
        return True
    return False

def delete_team(index):
    """Видалити команду"""
    registrations = load_data(REGISTRATIONS_FILE)
    if 0 <= index < len(registrations):
        deleted = registrations.pop(index)
        save_data(REGISTRATIONS_FILE, registrations)
        return deleted
    return None

# ============= ГОЛОВНЕ МЕНЮ =============

def get_main_menu():
    """Головне меню бота"""
    keyboard = [
        [InlineKeyboardButton("🎮 Зареєструвати команду", callback_data='register')],
        [InlineKeyboardButton("📢 Наша група", url=GROUP_LINK)],
        [InlineKeyboardButton("ℹ️ Інформація про турнір", callback_data='info')],
        [InlineKeyboardButton("🏆 Призи", callback_data='prizes')],
        [InlineKeyboardButton("📋 Правила", callback_data='rules')],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu():
    """Меню для адміністраторів"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("📋 Всі команди (детально)", callback_data='admin_teams_full')],
        [InlineKeyboardButton("✏️ Редагувати команду", callback_data='admin_edit')],
        [InlineKeyboardButton("🗑 Видалити команду", callback_data='admin_delete')],
        [InlineKeyboardButton("📢 Розсилка", callback_data='admin_broadcast')],
        [InlineKeyboardButton("🎁 Розіграш", callback_data='admin_giveaway')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')],
    ]
    return InlineKeyboardMarkup(keyboard)

def format_team_full(team, index):
    """Форматування повної інформації про команду"""
    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 КОМАНДА #{index + 1}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Назва: {team['team_name']}\n"
        f"🔖 Тег: [{team['team_tag']}]\n"
        f"📅 Дата реєстрації: {team.get('timestamp', 'Н/Д')[:10]}\n"
        f"👤 ID користувача: {team.get('user_id', 'Н/Д')}\n\n"
        f"👑 КАПІТАН:\n"
        f"├ Нік: {team['cap_nick']}\n"
        f"├ Ім'я: {team['cap_name']}\n"
        f"├ Вік: {team['cap_age']} років\n"
        f"├ Steam ID: {team['cap_steam']}\n"
        f"├ Discord: {team['cap_discord']}\n"
        f"└ Telegram: {team['cap_tg']}\n\n"
        f"👥 ГРАВЕЦЬ 2:\n"
        f"├ Нік: {team['p2_nick']}\n"
        f"├ Ім'я: {team['p2_name']}\n"
        f"├ Вік: {team['p2_age']} років\n"
        f"└ Steam ID: {team['p2_steam']}\n\n"
        f"👥 ГРАВЕЦЬ 3:\n"
        f"├ Нік: {team['p3_nick']}\n"
        f"├ Ім'я: {team['p3_name']}\n"
        f"├ Вік: {team['p3_age']} років\n"
        f"└ Steam ID: {team['p3_steam']}\n\n"
        f"👥 ГРАВЕЦЬ 4:\n"
        f"├ Нік: {team['p4_nick']}\n"
        f"├ Ім'я: {team['p4_name']}\n"
        f"├ Вік: {team['p4_age']} років\n"
        f"└ Steam ID: {team['p4_steam']}\n\n"
        f"👥 ГРАВЕЦЬ 5:\n"
        f"├ Нік: {team['p5_nick']}\n"
        f"├ Ім'я: {team['p5_name']}\n"
        f"├ Вік: {team['p5_age']} років\n"
        f"└ Steam ID: {team['p5_steam']}\n\n"
        f"💬 Коментарі: {team.get('comments', 'Немає')}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    return text

# ============= ОСНОВНІ КОМАНДИ =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id

    add_subscriber(user_id)

    welcome_text = (
        f"🔥 Вітаю, {user.first_name}!\n\n"
        f"Це офіційний бот турніру CS2\n"
        f"💰 Призовий фонд: $200 + $50 MVP\n\n"
        f"📅 Дата: Листопад 2025\n"
        f"🎮 Формат: 5v5\n"
        f"🇺🇦 Регіон: Україна\n"
        f"🔞 Вік: 16+\n\n"
        f"Оберіть дію з меню:"
    )

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_main_menu())
    else:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=get_main_menu())

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin - панель адміністратора"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас немає доступу до адмін-панелі")
        return

    await update.message.reply_text(
        "🔧 АДМІН-ПАНЕЛЬ\n\n"
        "Оберіть дію:",
        reply_markup=get_admin_menu()
    )

# ============= CALLBACK ОБРОБНИКИ =============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка натискань кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == 'back_to_main':
        await start(update, context)

    elif data == 'register':
        await query.message.edit_text(
            "📝 РЕЄСТРАЦІЯ КОМАНДИ\n\n"
            "Щоб зареєструвати команду, використайте команду:\n"
            "/register\n\n"
            "Бот проведе вас через весь процес реєстрації крок за кроком.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')
            ]])
        )

    elif data == 'info':
        info_text = (
            "ℹ️ ІНФОРМАЦІЯ ПРО ТУРНІР\n\n"
            "📅 Дата: Листопад 2025\n"
            "🎮 Гра: Counter-Strike 2\n"
            "👥 Формат: 5 на 5\n"
            "🇺🇦 Регіон: Україна\n"
            "🔞 Вік: 16+\n\n"
            "📍 Платформа: Online\n"
            "🎯 Система: Single Elimination / Swiss\n"
            "⏰ Час матчів: За розкладом\n\n"
            "📢 Група турніру: " + GROUP_LINK
        )
        await query.message.edit_text(
            info_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')
            ]])
        )

    elif data == 'prizes':
        prizes_text = (
            "🏆 ПРИЗИ\n\n"
            "💰 1 місце: $200\n"
            "⭐ MVP турніру: $50\n\n"
            "Загальний призовий фонд: $250\n\n"
            "🎁 Додаткові призи:\n"
            "• Унікальні ролі в Discord\n"
            "• Фічер в соцмережах\n"
            "• Запрошення на майбутні турніри\n\n"
            "💳 Виплати через:\n"
            "• Monobank\n"
            "• PrivatBank\n"
            "• USDT (TRC20)"
        )
        await query.message.edit_text(
            prizes_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')
            ]])
        )

    elif data == 'rules':
        rules_text = (
            "📋 ПРАВИЛА ТУРНІРУ\n\n"
            "✅ Загальні правила:\n"
            "• Офіційні правила CS2 Competitive\n"
            "• Анті-чіт обов'язковий\n"
            "• Заборонено використання читів\n"
            "• Тайм-аути: 4 паузи по 30 сек\n\n"
            "🎮 Налаштування:\n"
            "• MR12 (12 раундів до зміни)\n"
            "• Best of 1 (плей-офф: BO3)\n\n"
            "⚠️ Штрафи:\n"
            "• Запізнення 15+ хв = поразка\n"
            "• Токсичність = дискваліфікація\n\n"
            "📢 Повні правила: " + GROUP_LINK
        )
        await query.message.edit_text(
            rules_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')
            ]])
        )

    # ============= АДМІН ФУНКЦІЇ =============

    elif data == 'admin_stats':
        if not is_admin(query.from_user.id):
            await query.message.edit_text("❌ Немає доступу")
            return

        registrations = load_data(REGISTRATIONS_FILE)
        subscribers = load_data(SUBSCRIBERS_FILE)

        stats_text = (
            f"📊 СТАТИСТИКА\n\n"
            f"👥 Підписників: {len(subscribers)}\n"
            f"🏆 Зареєстрованих команд: {len(registrations)}\n"
            f"👤 Гравців: {len(registrations) * 5}\n"
        )

        await query.message.edit_text(stats_text, reply_markup=get_admin_menu())

    elif data == 'admin_teams_full':
        if not is_admin(query.from_user.id):
            await query.message.edit_text("❌ Немає доступу")
            return

        registrations = load_data(REGISTRATIONS_FILE)

        if not registrations:
            await query.message.edit_text(
                "📋 Поки що немає зареєстрованих команд",
                reply_markup=get_admin_menu()
            )
            return

        # Відправляємо кожну команду окремим повідомленням
        await query.message.edit_text(
            f"📋 Всього команд: {len(registrations)}\n\n"
            f"Відправляю детальну інформацію...",
            reply_markup=get_admin_menu()
        )

        for i, team in enumerate(registrations):
            team_text = format_team_full(team, i)
            await query.message.reply_text(team_text)

    elif data == 'admin_edit':
        if not is_admin(query.from_user.id):
            await query.message.edit_text("❌ Немає доступу")
            return

        registrations = load_data(REGISTRATIONS_FILE)

        if not registrations:
            await query.message.edit_text(
                "📋 Немає команд для редагування",
                reply_markup=get_admin_menu()
            )
            return

        keyboard = []
        for i, team in enumerate(registrations):
            keyboard.append([InlineKeyboardButton(
                f"{i+1}. {team['team_name']} [{team['team_tag']}]",
                callback_data=f'edit_team_{i}'
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin')])

        await query.message.edit_text(
            "✏️ Оберіть команду для редагування:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith('edit_team_'):
        team_index = int(data.split('_')[2])
        context.user_data['editing_team_index'] = team_index
        team = get_team_by_index(team_index)

        if not team:
            await query.message.edit_text("❌ Команду не знайдено", reply_markup=get_admin_menu())
            return

        keyboard = [
            [InlineKeyboardButton("Назва команди", callback_data='edit_field_team_name')],
            [InlineKeyboardButton("Тег команди", callback_data='edit_field_team_tag')],
            [InlineKeyboardButton("Капітан - нік", callback_data='edit_field_cap_nick')],
            [InlineKeyboardButton("Капітан - ім'я", callback_data='edit_field_cap_name')],
            [InlineKeyboardButton("Капітан - вік", callback_data='edit_field_cap_age')],
            [InlineKeyboardButton("Капітан - Steam ID", callback_data='edit_field_cap_steam')],
            [InlineKeyboardButton("Капітан - Discord", callback_data='edit_field_cap_discord')],
            [InlineKeyboardButton("Капітан - Telegram", callback_data='edit_field_cap_tg')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_edit')],
        ]

        await query.message.edit_text(
            f"✏️ Редагування команди:\n{team['team_name']} [{team['team_tag']}]\n\n"
            f"Оберіть поле для зміни:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith('edit_field_'):
        field = data.replace('edit_field_', '')
        context.user_data['editing_field'] = field

        field_names = {
            'team_name': 'Назву команди',
            'team_tag': 'Тег команди',
            'cap_nick': 'Нікнейм капітана',
            'cap_name': "Ім'я капітана",
            'cap_age': 'Вік капітана',
            'cap_steam': 'Steam ID капітана',
            'cap_discord': 'Discord капітана',
            'cap_tg': 'Telegram капітана',
        }

        await query.message.edit_text(
            f"✏️ Введіть нове значення для поля:\n"
            f"📝 {field_names.get(field, field)}\n\n"
            f"Відправте нове значення текстовим повідомленням."
        )

    elif data == 'admin_delete':
        if not is_admin(query.from_user.id):
            await query.message.edit_text("❌ Немає доступу")
            return

        registrations = load_data(REGISTRATIONS_FILE)

        if not registrations:
            await query.message.edit_text(
                "📋 Немає команд для видалення",
                reply_markup=get_admin_menu()
            )
            return

        keyboard = []
        for i, team in enumerate(registrations):
            keyboard.append([InlineKeyboardButton(
                f"🗑 {i+1}. {team['team_name']} [{team['team_tag']}]",
                callback_data=f'delete_team_{i}'
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin')])

        await query.message.edit_text(
            "🗑 Оберіть команду для видалення:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith('delete_team_'):
        team_index = int(data.split('_')[2])
        deleted_team = delete_team(team_index)

        if deleted_team:
            await query.message.edit_text(
                f"✅ Команду видалено:\n"
                f"{deleted_team['team_name']} [{deleted_team['team_tag']}]",
                reply_markup=get_admin_menu()
            )
        else:
            await query.message.edit_text(
                "❌ Помилка видалення команди",
                reply_markup=get_admin_menu()
            )

    elif data == 'back_to_admin':
        await query.message.edit_text(
            "🔧 АДМІН-ПАНЕЛЬ\n\nОберіть дію:",
            reply_markup=get_admin_menu()
        )

    elif data == 'admin_broadcast':
        if not is_admin(query.from_user.id):
            await query.message.edit_text("❌ Немає доступу")
            return

        await query.message.edit_text(
            "📢 РОЗСИЛКА\n\n"
            "Використайте команду:\n"
            "/broadcast ваше повідомлення\n\n"
            "Повідомлення буде відправлено всім підписникам.",
            reply_markup=get_admin_menu()
        )

    elif data == 'admin_giveaway':
        if not is_admin(query.from_user.id):
            await query.message.edit_text("❌ Немає доступу")
            return

        await query.message.edit_text(
            "🎁 РОЗІГРАШ\n\n"
            "Використайте команду:\n"
            "/giveaway\n\n"
            "Буде обрано випадкового переможця.",
            reply_markup=get_admin_menu()
        )

# ============= ОБРОБНИК РЕДАГУВАННЯ =============

async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка введення нового значення при редагуванні"""
    if 'editing_team_index' not in context.user_data or 'editing_field' not in context.user_data:
        return

    if not is_admin(update.effective_user.id):
        return

    team_index = context.user_data['editing_team_index']
    field = context.user_data['editing_field']
    new_value = update.message.text

    # Валідація
    if field == 'cap_steam' and not validate_steam_id(new_value):
        await update.message.reply_text(
            "❌ Steam ID має містити тільки цифри (мінімум 8)\n"
            "Спробуйте ще раз:"
        )
        return

    if field == 'cap_age':
        try:
            age = int(new_value)
            if age < 16:
                await update.message.reply_text("❌ Вік має бути від 16 років. Спробуйте ще раз:")
                return
        except ValueError:
            await update.message.reply_text("❌ Введіть число. Спробуйте ще раз:")
            return

    # Оновлення
    team = get_team_by_index(team_index)
    if team:
        team[field] = new_value
        if update_team(team_index, team):
            await update.message.reply_text(
                f"✅ Поле оновлено!\n\n"
                f"Команда: {team['team_name']}\n"
                f"Поле: {field}\n"
                f"Нове значення: {new_value}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ До адмін-панелі", callback_data='back_to_admin')
                ]])
            )
        else:
            await update.message.reply_text("❌ Помилка оновлення")

    # Очищення
    context.user_data.pop('editing_team_index', None)
    context.user_data.pop('editing_field', None)

# ============= РЕЄСТРАЦІЯ КОМАНДИ =============

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок реєстрації"""
    await update.message.reply_text(
        "📝 РЕЄСТРАЦІЯ КОМАНДИ\n\n"
        "Я буду ставити запитання, а ви відповідайте.\n"
        "Для скасування: /cancel\n\n"
        "Введіть назву команди:"
    )
    return TEAM_NAME

async def team_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['team_name'] = update.message.text
    await update.message.reply_text(f"✅ Команда: {update.message.text}\n\nВведіть тег (2-5 символів):")
    return TEAM_TAG

async def team_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.upper()
    if len(tag) < 2 or len(tag) > 5:
        await update.message.reply_text("❌ Тег має бути 2-5 символів:")
        return TEAM_TAG

    context.user_data['team_tag'] = tag
    await update.message.reply_text(f"✅ Тег: [{tag}]\n\n👑 КАПІТАН\n\nНікнейм (Steam):")
    return CAP_NICK

async def captain_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cap_nick'] = update.message.text
    await update.message.reply_text("Справжнє ім'я:")
    return CAP_NAME

async def captain_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cap_name'] = update.message.text
    await update.message.reply_text("Вік:")
    return CAP_AGE

async def captain_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 16:
            await update.message.reply_text("❌ Вік від 16 років:")
            return CAP_AGE
        context.user_data['cap_age'] = age
        await update.message.reply_text("Steam ID (тільки цифри, мінімум 8):")
        return CAP_STEAM
    except ValueError:
        await update.message.reply_text("❌ Введіть число:")
        return CAP_AGE

async def captain_steam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    steam_id = update.message.text
    if not validate_steam_id(steam_id):
        await update.message.reply_text(
            "❌ Steam ID має містити тільки цифри (мінімум 8)\n"
            "Спробуйте ще раз:"
        )
        return CAP_STEAM

    context.user_data['cap_steam'] = steam_id
    await update.message.reply_text("Discord капітана (формат: username#0000):")
    return CAP_DISCORD

async def captain_discord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cap_discord'] = update.message.text
    await update.message.reply_text("Telegram капітана (@username):")
    return CAP_TG

async def captain_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cap_tg'] = update.message.text
    await update.message.reply_text("✅ Капітан готово!\n\n👤 ГРАВЕЦЬ 2\n\nНікнейм:")
    return P2_NICK

# Гравці 2-5 (тільки основна інформація, без Discord)
async def player2_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p2_nick'] = update.message.text
    await update.message.reply_text("Справжнє ім'я:")
    return P2_NAME

async def player2_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p2_name'] = update.message.text
    await update.message.reply_text("Вік:")
    return P2_AGE

async def player2_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 16:
            await update.message.reply_text("❌ Вік від 16:")
            return P2_AGE
        context.user_data['p2_age'] = age
        await update.message.reply_text("Steam ID (тільки цифри):")
        return P2_STEAM
    except ValueError:
        await update.message.reply_text("❌ Введіть число:")
        return P2_AGE

async def player2_steam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    steam_id = update.message.text
    if not validate_steam_id(steam_id):
        await update.message.reply_text("❌ Steam ID - тільки цифри (мінімум 8):")
        return P2_STEAM

    context.user_data['p2_steam'] = steam_id
    await update.message.reply_text("✅ Гравець 2 готово!\n\n👤 ГРАВЕЦЬ 3\n\nНікнейм:")
    return P3_NICK

async def player3_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p3_nick'] = update.message.text
    await update.message.reply_text("Справжнє ім'я:")
    return P3_NAME

async def player3_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p3_name'] = update.message.text
    await update.message.reply_text("Вік:")
    return P3_AGE

async def player3_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 16:
            await update.message.reply_text("❌ Вік від 16:")
            return P3_AGE
        context.user_data['p3_age'] = age
        await update.message.reply_text("Steam ID (тільки цифри):")
        return P3_STEAM
    except ValueError:
        await update.message.reply_text("❌ Введіть число:")
        return P3_AGE

async def player3_steam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    steam_id = update.message.text
    if not validate_steam_id(steam_id):
        await update.message.reply_text("❌ Steam ID - тільки цифри (мінімум 8):")
        return P3_STEAM

    context.user_data['p3_steam'] = steam_id
    await update.message.reply_text("✅ Гравець 3 готово!\n\n👤 ГРАВЕЦЬ 4\n\nНікнейм:")
    return P4_NICK

async def player4_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p4_nick'] = update.message.text
    await update.message.reply_text("Справжнє ім'я:")
    return P4_NAME

async def player4_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p4_name'] = update.message.text
    await update.message.reply_text("Вік:")
    return P4_AGE

async def player4_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 16:
            await update.message.reply_text("❌ Вік від 16:")
            return P4_AGE
        context.user_data['p4_age'] = age
        await update.message.reply_text("Steam ID (тільки цифри):")
        return P4_STEAM
    except ValueError:
        await update.message.reply_text("❌ Введіть число:")
        return P4_AGE

async def player4_steam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    steam_id = update.message.text
    if not validate_steam_id(steam_id):
        await update.message.reply_text("❌ Steam ID - тільки цифри (мінімум 8):")
        return P4_STEAM

    context.user_data['p4_steam'] = steam_id
    await update.message.reply_text("✅ Гравець 4 готово!\n\n👤 ГРАВЕЦЬ 5 (останній)\n\nНікнейм:")
    return P5_NICK

async def player5_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p5_nick'] = update.message.text
    await update.message.reply_text("Справжнє ім'я:")
    return P5_NAME

async def player5_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p5_name'] = update.message.text
    await update.message.reply_text("Вік:")
    return P5_AGE

async def player5_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 16:
            await update.message.reply_text("❌ Вік від 16:")
            return P5_AGE
        context.user_data['p5_age'] = age
        await update.message.reply_text("Steam ID (тільки цифри):")
        return P5_STEAM
    except ValueError:
        await update.message.reply_text("❌ Введіть число:")
        return P5_AGE

async def player5_steam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    steam_id = update.message.text
    if not validate_steam_id(steam_id):
        await update.message.reply_text("❌ Steam ID - тільки цифри (мінімум 8):")
        return P5_STEAM

    context.user_data['p5_steam'] = steam_id
    await update.message.reply_text(
        "✅ Всі гравці готові!\n\n"
        "Є коментарі? (якщо ні - напишіть '-')"
    )
    return COMMENTS

async def comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comments = update.message.text
    context.user_data['comments'] = comments if comments != '-' else "Без коментарів"

    data = context.user_data
    summary = (
        f"📋 ПІДСУМОК\n\n"
        f"🏆 {data['team_name']} [{data['team_tag']}]\n\n"
        f"👑 Капітан: {data['cap_nick']} ({data['cap_age']}р)\n"
        f"   Discord: {data['cap_discord']}\n"
        f"   Steam: {data['cap_steam']}\n\n"
        f"👥 Склад:\n"
        f"2. {data['p2_nick']} ({data['p2_age']}р) - {data['p2_steam']}\n"
        f"3. {data['p3_nick']} ({data['p3_age']}р) - {data['p3_steam']}\n"
        f"4. {data['p4_nick']} ({data['p4_age']}р) - {data['p4_steam']}\n"
        f"5. {data['p5_nick']} ({data['p5_age']}р) - {data['p5_steam']}\n\n"
        f"💬 {data['comments']}\n\n"
        f"Підтвердити?"
    )

    keyboard = [['✅ Підтвердити', '❌ Скасувати']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(summary, reply_markup=reply_markup)
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text

    if '✅' in choice:
        data = context.user_data
        data['timestamp'] = datetime.now().isoformat()
        data['user_id'] = update.effective_user.id

        registrations = load_data(REGISTRATIONS_FILE)
        registrations.append(data)
        save_data(REGISTRATIONS_FILE, registrations)

        # Повідомлення адмінам
        admin_msg = format_team_full(data, len(registrations) - 1)

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🆕 НОВА КОМАНДА!\n\n{admin_msg}"
                )
            except:
                pass

        await update.message.reply_text(
            "✅ Реєстрацію завершено!\n\n"
            "Очікуйте підтвердження від організаторів.\n\n"
            f"Приєднуйтесь: {GROUP_LINK}",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Скасовано. Для нової реєстрації: /register",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Скасовано.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# ============= АДМІН ФУНКЦІЇ =============

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Розсилка повідомлення"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Немає доступу")
        return

    if not context.args:
        await update.message.reply_text("Використання: /broadcast ваше повідомлення")
        return

    message = ' '.join(context.args)
    subscribers = load_data(SUBSCRIBERS_FILE)

    success = 0
    failed = 0

    for user_id in subscribers:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 {message}")
            success += 1
        except:
            failed += 1

    await update.message.reply_text(
        f"✅ Розсилка завершена\n\n"
        f"Успішно: {success}\n"
        f"Помилок: {failed}"
    )

async def giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Випадковий розіграш"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Немає доступу")
        return

    subscribers = load_data(SUBSCRIBERS_FILE)

    if not subscribers:
        await update.message.reply_text("❌ Немає підписників")
        return

    import random
    winner_id = random.choice(subscribers)

    try:
        winner = await context.bot.get_chat(winner_id)
        winner_name = winner.first_name
        winner_username = winner.username

        # Формування повідомлення
        winner_info = f"👤 {winner_name}"
        if winner_username:
            winner_info += f"\n📱 @{winner_username}"
        else:
            winner_info += f"\n🆔 ID: {winner_id}"

        await update.message.reply_text(
            f"🎁 Переможець розіграшу:\n\n"
            f"{winner_info}"
        )

        await context.bot.send_message(
            chat_id=winner_id,
            text="🎉 Вітаємо! Ви виграли розіграш! Організатори зв'яжуться з вами."
        )
    except:
        await update.message.reply_text(f"🎁 Переможець: ID {winner_id}")

# ============= ЗАПУСК БОТА =============

def main():
    """Головна функція"""

    application = Application.builder().token(BOT_TOKEN).build()

    # Обробник реєстрації
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register_command)],
        states={
            TEAM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, team_name)],
            TEAM_TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, team_tag)],
            CAP_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, captain_nickname)],
            CAP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, captain_name)],
            CAP_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, captain_age)],
            CAP_STEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, captain_steam)],
            CAP_DISCORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, captain_discord)],
            CAP_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, captain_telegram)],
            P2_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, player2_nick)],
            P2_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, player2_name)],
            P2_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, player2_age)],
            P2_STEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, player2_steam)],
            P3_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, player3_nick)],
            P3_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, player3_name)],
            P3_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, player3_age)],
            P3_STEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, player3_steam)],
            P4_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, player4_nick)],
            P4_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, player4_name)],
            P4_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, player4_age)],
            P4_STEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, player4_steam)],
            P5_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, player5_nick)],
            P5_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, player5_name)],
            P5_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, player5_age)],
            P5_STEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, player5_steam)],
            COMMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, comments)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Додаємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("giveaway", giveaway))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))

    # Обробник для редагування (працює поза ConversationHandler)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_edit_input
    ))

    # Запускаємо бота
    logger.info("🤖 Бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':

    main()




