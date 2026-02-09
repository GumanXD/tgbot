import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Contact,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery  # 🔑 КРИТИЧЕСКИ ВАЖНЫЙ ИМПОРТ
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

# ============================================
# 🔧 КОНФИГУРАЦИЯ
# ============================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MANAGER_ID = int(os.getenv("MANAGER_ID", "0"))

if not BOT_TOKEN or MANAGER_ID == 0:
    raise ValueError("❌ Отсутствуют обязательные переменные окружения: BOT_TOKEN или MANAGER_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================
# 📋 ДАННЫЕ БОТА
# ============================================

PRICE_LIST = {
    "💧 Картриджи и фильтрующие элементы":[],
    "🌀 Картридж из нетканного полипропилена BB10 — 330 ₽": [
        "Глубинная очистка от механических примесей: песок, ржавчина, илистые частицы"
    ],
    "⚫ Картридж из прессованного активированного угля BB20 — 1 100 ₽": [
        "Удаление хлора, органики, неприятных запахов и привкусов",
    ],
    "🧂 Соль таблетированная для систем умягчения (мешок 25 кг) — от 875 ₽": [
        "Высокая степень очистки, не содержит примесей, идеальна для регенерации ионообменных смол"
    ],
    "🛠️ Сервисное обслуживание систем очистки воды, всего — от 4 000 р.": []
}

COMPANY_INFO = """💧 Аквафреска — ваш эксперт в сфере водоочистки в Санкт-Петербурге и Ленинградской области! 🌊
📍 Наше основное направление — профессиональная очистка воды из:
• 🕳️ Скважин
• 🪣 Колодцев
• 🌊 Открытых источников
• 🏠 Центрального водоснабжения
❤️ Мы понимаем, насколько важны безопасность и качество воды для здоровья вашей семьи 👨‍👩‍👧‍👦 и бесперебойной работы предприятия 🏢. Поэтому мы используем передовые технологии ⚙️ и инновационные системы фильтрации 🔬, которые гарантируют полное удаление всех видов загрязнений:
🚫 Эффективно удаляем:
• 💎 Жёсткость воды
• ⚫ Железо (двух- и трёхвалентное)
• 🟣 Растворённый марганец
• 🦠 Бактерии и микроорганизмы
• ⚠️ Другие вещества, превышающие нормативы СанПиН
🏭 Промышленная водоподготовка:
Мы специализируемся на решениях для предприятий пищевой промышленности 🥫, котельных 🔥 и промышленных производств ⚙️. Каждая система разрабатывается индивидуально 📐✨ под ваши технические требования и производственные задачи.
✅ Почему выбирают «Аквафреска»?
• 🏆 10+ лет опыта работы в водоочистке СПб и ЛО
• 🔬 Сертифицированное оборудование проверенных временем брендов
• 👷‍♂️ Собственная сервисная служб
• 💰 Честные цены без скрытых платежей
• 📜 Гарантия до 3 лет на оборудование и монтажные работы
📞 Свяжитесь с нами уже сегодня!
Наши инженеры-экологи бесплатно проконсультируют вас и подберут оптимальное решение 💧✨ для чистой, безопасной и приятной на вкус воды.
🌟 Вы заслуживаете чистую воду — «Аквафреска» сделает её такой! 💧💙"""

# ============================================
# 🧠 FSM И ХРАНИЛИЩЕ ДИАЛОГОВ
# ============================================

class DialogState(StatesGroup):
    in_dialog = State()  # Клиент находится в активном диалоге с менеджером

# Хранилище активных диалогов: {client_id: timestamp_последней_активности}
active_dialogs = {}

# ============================================
# 🎨 ФУНКЦИИ СОЗДАНИЯ КЛАВИАТУР
# ============================================

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [KeyboardButton(text="ℹ️ О компании"), KeyboardButton(text="💰 Прайс материалов")],
        [KeyboardButton(text="💬 Начать диалог с менеджером"), KeyboardButton(text="📞 Заказать звонок")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, input_field_placeholder="Выберите действие")

def get_dialog_menu() -> ReplyKeyboardMarkup:
    """Меню во время диалога с менеджером"""
    keyboard = [[KeyboardButton(text="⏹️ Завершить диалог")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, input_field_placeholder="Пишите сообщение менеджеру...")

def get_back_menu() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой «Назад»"""
    keyboard = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_contact_request_menu() -> ReplyKeyboardMarkup:
    """Клавиатура для отправки контакта"""
    keyboard = [
        [KeyboardButton(text="📱 Отправить контакт", request_contact=True)],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_manager_accept_keyboard(client_id: int) -> InlineKeyboardMarkup:
    """Inline-кнопки для менеджера: принять/отклонить диалог"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{client_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{client_id}")
        ]
    ])
    return keyboard

# ============================================
# 🤖 ОСНОВНЫЕ ОБРАБОТЧИКИ
# ============================================

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Стартовая команда"""
    await state.clear()
    client_id = message.from_user.id
    
    # Если клиент в активном диалоге — продолжаем диалог
    if client_id in active_dialogs:
        await state.set_state(DialogState.in_dialog)
        await message.answer(
            "💬 Вы возобновили диалог с менеджером.\n"
            "Все ваши сообщения будут пересылаться менеджеру.\n"
            "Нажмите «⏹️ Завершить диалог», чтобы выйти.",
            reply_markup=get_dialog_menu()
        )
        return
    
    greeting = (
        "👋 Добро пожаловать в *«Аквафреска»*!\n\n"
        "Ваш эксперт в сфере водоочистки в Санкт-Петербурге и Ленинградской области! 🌊\n"
        "Выберите действие ниже 👇"
    )
    await message.answer(greeting, reply_markup=get_main_menu(), parse_mode="Markdown")

@router.message(F.text == "⬅️ Назад")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    """Возврат в главное меню"""
    client_id = message.from_user.id
    
    # Если клиент в диалоге — завершаем диалог при нажатии «Назад»
    if client_id in active_dialogs:
        del active_dialogs[client_id]
        await state.clear()
        await message.answer(
            "ℹ️ Диалог с менеджером завершён.\n"
            "Вы вернулись в главное меню.",
            reply_markup=get_main_menu()
        )
        # Уведомляем менеджера
        try:
            await message.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"ℹ️ Клиент {client_id} завершил диалог."
            )
        except:
            pass
        return
    
    await state.clear()
    await message.answer("↩️ Вы вернулись в главное меню", reply_markup=get_main_menu())

@router.message(F.text == "ℹ️ О компании")
async def about_company(message: Message, state: FSMContext) -> None:
    """Показать информацию о компании"""
    client_id = message.from_user.id
    if client_id in active_dialogs:
        await message.answer("⚠️ Сначала завершите диалог с менеджером.", reply_markup=get_dialog_menu())
        return
    
    await message.answer(COMPANY_INFO, reply_markup=get_back_menu(), parse_mode="Markdown")

@router.message(F.text == "💰 Прайс материалов")
async def show_price_list(message: Message, state: FSMContext) -> None:
    """Показать прайс-лист"""
    client_id = message.from_user.id
    if client_id in active_dialogs:
        await message.answer("⚠️ Сначала завершите диалог с менеджером.", reply_markup=get_dialog_menu())
        return
    
    price_text = "📊 *Прайс-лист на расходные материалы для водоочистки*\n\n"
    
    for category, items in PRICE_LIST.items():
        price_text += f"*{category}*\n"
        for item in items:
            price_text += f"{item}\n"
        price_text += "\n"
    
    await message.answer(price_text, reply_markup=get_back_menu(), parse_mode="Markdown")

@router.message(F.text == "📞 Заказать звонок")
async def request_contact(message: Message, state: FSMContext) -> None:
    """Запросить контакт для звонка"""
    client_id = message.from_user.id
    if client_id in active_dialogs:
        await message.answer("⚠️ Сначала завершите диалог с менеджером.", reply_markup=get_dialog_menu())
        return
    
    await message.answer(
        "📱 Нажмите кнопку ниже, чтобы отправить свой номер телефона.\n"
        "Менеджер перезвонит вам в течение 30 минут.",
        reply_markup=get_contact_request_menu()
    )

@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext) -> None:
    """Обработка полученного контакта"""
    contact: Contact = message.contact
    phone = contact.phone_number
    user_name = contact.first_name or "Пользователь"
    client_id = message.from_user.id
    
    # Формируем сообщение для менеджера
    manager_msg = (
        f"🔔 *Новая заявка на звонок!*\n"
        f"👤 Имя: {user_name}\n"
        f"📱 Телефон: +{phone}\n"
        f"🆔 ID пользователя: {client_id}"
    )
    
    try:
        await message.bot.send_message(
            chat_id=MANAGER_ID,
            text=manager_msg,
            parse_mode="Markdown"
        )
        logger.info(f"Заявка на звонок от {client_id} отправлена менеджеру")
    except Exception as e:
        logger.error(f"Ошибка отправки заявки менеджеру: {e}")
        await message.answer("⚠️ Не удалось отправить заявку. Попробуйте позже.", reply_markup=get_main_menu())
        return
    
    await message.answer(
        "✅ Заявка на звонок принята!\n"
        "Менеджер перезвонит вам в течение 30 минут.",
        reply_markup=get_main_menu()
    )
    await state.clear()

# ============================================
# 💬 СИСТЕМА ДИАЛОГА С МЕНЕДЖЕРОМ
# ============================================

@router.message(F.text == "💬 Начать диалог с менеджером")
async def start_dialog_request(message: Message, state: FSMContext) -> None:
    """Запрос на начало диалога с менеджером"""
    client_id = message.from_user.id
    
    # Проверяем, не в диалоге ли уже клиент
    if client_id in active_dialogs:
        await message.answer(
            "💬 Вы уже находитесь в диалоге с менеджером.\n"
            "Все ваши сообщения пересылаются менеджеру.",
            reply_markup=get_dialog_menu()
        )
        await state.set_state(DialogState.in_dialog)
        return
    
    # Отправляем запрос менеджеру
    username = f"@{message.from_user.username}" if message.from_user.username else "не указан"
    request_msg = (
        f"💬 *Новый запрос на диалог!*\n"
        f"👤 Имя: {message.from_user.full_name}\n"
        f"🆔 ID: `{client_id}`\n"
        f"🔗 Username: {username}\n\n"
        f"Нажмите ✅ чтобы начать диалог"
    )
    
    try:
        await message.bot.send_message(
            chat_id=MANAGER_ID,
            text=request_msg,
            parse_mode="Markdown",
            reply_markup=get_manager_accept_keyboard(client_id)
        )
        logger.info(f"Запрос на диалог от {client_id} отправлен менеджеру")
    except Exception as e:
        logger.error(f"Ошибка отправки запроса менеджеру: {e}")
        await message.answer(
            "⚠️ Менеджер временно недоступен. Попробуйте позже или закажите звонок.",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        "⏳ Ожидайте подключения менеджера...\n"
        "Как только менеджер примет запрос, вы сможете общаться в реальном времени.",
        reply_markup=get_back_menu()
    )

@router.callback_query(F.data.startswith("accept_"))
async def accept_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    """Менеджер принял запрос на диалог"""
    client_id = int(callback.data.split("_")[1])
    
    # Проверяем, не завершил ли клиент диалог за это время
    if client_id not in active_dialogs:
        active_dialogs[client_id] = datetime.now()
    
    # Уведомляем менеджера
    await callback.message.edit_text(
        f"✅ Диалог с клиентом {client_id} начат.\n"
        f"Все ваши сообщения будут пересылаться клиенту.\n"
        f"Чтобы завершить диалог, напишите /стоп_{client_id}"
    )
    
    # Уведомляем клиента
    try:
        await callback.bot.send_message(
            chat_id=client_id,
            text="✅ Менеджер подключился к диалогу!\n"
                 "Теперь вы можете общаться в реальном времени.\n"
                 "Все сообщения будут доставлены мгновенно.",
            reply_markup=get_dialog_menu()
        )
        # Устанавливаем состояние диалога для клиента
        # Нужно получить состояние клиента через отдельный экземпляр FSMContext
        # Для простоты используем глобальное состояние через роутер
        # В реальном проекте лучше использовать отдельное хранилище состояний
    except Exception as e:
        logger.error(f"Не удалось уведомить клиента {client_id}: {e}")
        await callback.bot.send_message(
            chat_id=MANAGER_ID,
            text=f"⚠️ Клиент {client_id} заблокировал бота или недоступен."
        )
        if client_id in active_dialogs:
            del active_dialogs[client_id]
        return
    
    logger.info(f"Диалог между клиентом {client_id} и менеджером начат")
    await callback.answer()

@router.callback_query(F.data.startswith("reject_"))
async def reject_dialog(callback: CallbackQuery) -> None:
    """Менеджер отклонил запрос на диалог"""
    client_id = int(callback.data.split("_")[1])
    
    # Уведомляем клиента
    try:
        await callback.bot.send_message(
            chat_id=client_id,
            text="❌ Менеджер временно занят.\n"
                 "Попробуйте начать диалог позже или закажите обратный звонок.",
            reply_markup=get_main_menu()
        )
    except:
        pass  # Клиент может быть недоступен
    
    # Уведомляем менеджера
    await callback.message.edit_text(f"❌ Запрос от клиента {client_id} отклонён")
    await callback.answer()
    logger.info(f"Запрос на диалог от {client_id} отклонён менеджером")

@router.message(F.text == "⏹️ Завершить диалог")
async def end_dialog_by_client(message: Message, state: FSMContext) -> None:
    """Клиент завершил диалог"""
    client_id = message.from_user.id
    
    if client_id in active_dialogs:
        del active_dialogs[client_id]
        await state.clear()
        
        # Уведомляем менеджера
        try:
            await message.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"ℹ️ Клиент {client_id} завершил диалог."
            )
        except:
            pass
        
        await message.answer(
            "✅ Диалог с менеджером завершён.\n"
            "Спасибо за обращение! Возвращайтесь в главное меню.",
            reply_markup=get_main_menu()
        )
        logger.info(f"Клиент {client_id} завершил диалог")
    else:
        await message.answer("ℹ️ Диалог уже завершён.", reply_markup=get_main_menu())
        await state.clear()

@router.message(DialogState.in_dialog)
async def forward_client_message_to_manager(message: Message, state: FSMContext) -> None:
    """Пересылка сообщений клиента менеджеру во время диалога"""
    client_id = message.from_user.id
    
    # Проверяем, активен ли диалог
    if client_id not in active_dialogs:
        await state.clear()
        await message.answer("ℹ️ Диалог завершён. Начните новый диалог через главное меню.", reply_markup=get_main_menu())
        return
    
    # Обновляем время последней активности
    active_dialogs[client_id] = datetime.now()
    
    # Формируем префикс для сообщения
    prefix = f"👤 Клиент {client_id}"
    if message.from_user.username:
        prefix += f" (@{message.from_user.username})"
    prefix += ":\n\n"
    
    try:
        if message.text:
            await message.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"{prefix}{message.text}"
            )
        elif message.photo:
            await message.bot.send_photo(
                chat_id=MANAGER_ID,
                photo=message.photo[-1].file_id,
                caption=f"{prefix}{message.caption or ''}"
            )
        elif message.document:
            await message.bot.send_document(
                chat_id=MANAGER_ID,
                document=message.document.file_id,
                caption=f"{prefix}{message.caption or ''}"
            )
        else:
            await message.answer("⚠️ Поддерживаются только текст, фото и документы.")
            return
        
        logger.info(f"Сообщение от клиента {client_id} переслано менеджеру")
    except Exception as e:
        logger.error(f"Ошибка пересылки сообщения менеджеру: {e}")
        await message.answer(
            "⚠️ Менеджер временно недоступен. Попробуйте позже.",
            reply_markup=get_main_menu()
        )
        if client_id in active_dialogs:
            del active_dialogs[client_id]
        await state.clear()

@router.message(F.from_user.id == MANAGER_ID)
async def forward_manager_message_to_client(message: Message) -> None:
    """
    Обработка сообщений от менеджера:
    1. Если сообщение начинается с /стоп_{id} — завершаем диалог
    2. Если сообщение начинается с /чат_{id} — пересылаем клиенту
    3. Если менеджер отвечает через reply — пересылаем клиенту
    """
    bot = message.bot
    text = message.text or ""
    
    # Обработка команды /стоп_{id}
    if text.startswith("/стоп_"):
        try:
            client_id = int(text.split("_")[1])
            if client_id in active_dialogs:
                del active_dialogs[client_id]
                await bot.send_message(
                    chat_id=client_id,
                    text="ℹ️ Менеджер завершил диалог.\n"
                         "Спасибо за обращение! Возвращайтесь в главное меню.",
                    reply_markup=get_main_menu()
                )
                await message.answer(f"✅ Диалог с клиентом {client_id} завершён.")
                logger.info(f"Менеджер завершил диалог с клиентом {client_id}")
            else:
                await message.answer(f"⚠️ Клиент {client_id} не в активном диалоге.")
        except (IndexError, ValueError):
            await message.answer("⚠️ Неверный формат команды. Используйте: /стоп_123456789")
        return
    
    # Обработка команды /чат_{id} для явного указания клиента
    if text.startswith("/чат_"):
        try:
            parts = text.split(" ", 1)
            client_id = int(parts[0].split("_")[1])
            real_text = parts[1] if len(parts) > 1 else ""
            
            if client_id in active_dialogs:
                await bot.send_message(
                    chat_id=client_id,
                    text=f"👤 *Менеджер ответил:*\n\n{real_text}",
                    parse_mode="Markdown"
                )
                await message.answer(f"✅ Сообщение отправлено клиенту {client_id}.")
                logger.info(f"Менеджер отправил сообщение клиенту {client_id}")
            else:
                await message.answer(f"⚠️ Клиент {client_id} не в активном диалоге.")
        except (IndexError, ValueError):
            await message.answer("⚠️ Неверный формат команды. Используйте: /чат_123456789 текст сообщения")
        return
    
    # Если менеджер отвечает на сообщение клиента через reply
    if message.reply_to_message:
        # Извлекаем ID клиента из текста сообщения, на которое ответил менеджер
        reply_text = message.reply_to_message.text or ""
        # Ищем паттерн "Клиент 123456789"
        import re
        match = re.search(r"Клиент (\d+)", reply_text)
        if match:
            client_id = int(match.group(1))
            if client_id in active_dialogs:
                # Отправляем сообщение клиенту
                try:
                    if message.text:
                        await bot.send_message(
                            chat_id=client_id,
                            text=f"👤 *Менеджер ответил:*\n\n{message.text}",
                            parse_mode="Markdown"
                        )
                    elif message.photo:
                        await bot.send_photo(
                            chat_id=client_id,
                            photo=message.photo[-1].file_id,
                            caption=f"👤 *Менеджер ответил:*\n\n{message.caption or ''}",
                            parse_mode="Markdown"
                        )
                    elif message.document:
                        await bot.send_document(
                            chat_id=client_id,
                            document=message.document.file_id,
                            caption=f"👤 *Менеджер ответил:*\n\n{message.caption or ''}",
                            parse_mode="Markdown"
                        )
                    await message.answer(f"✅ Ответ отправлен клиенту {client_id}.")
                    logger.info(f"Менеджер ответил клиенту {client_id}")
                except Exception as e:
                    await message.answer(f"❌ Не удалось отправить сообщение клиенту {client_id}: {e}")
                return
    
    # Подсказка менеджеру
    active_clients = list(active_dialogs.keys())
    hint = "ℹ️ Чтобы ответить клиенту:\n"
    if active_clients:
        hint += f"• Нажмите «ответить» на его сообщение, ИЛИ\n"
        hint += f"• Напишите /чат_{active_clients[0]} ваше сообщение\n"
        hint += f"\nАктивные диалоги: {', '.join(map(str, active_clients))}"
    else:
        hint += "Нет активных диалогов."
    
    await message.answer(hint)

@router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    """Обработка неизвестных команд"""
    client_id = message.from_user.id
    
    # Если клиент в диалоге — пересылаем сообщение менеджеру
    if client_id in active_dialogs:
        await forward_client_message_to_manager(message, state)
        return
    
    await message.answer(
        "❓ Я понимаю только команды из меню.\n"
        "Выберите действие ниже 👇",
        reply_markup=get_main_menu()
    )

# ============================================
# 🧹 ФОНОВАЯ ЗАДАЧА: ОЧИСТКА НЕАКТИВНЫХ ДИАЛОГОВ
# ============================================

async def cleanup_inactive_dialogs(bot: Bot):
    """Удаляет диалоги без активности более 1 часа"""
    while True:
        await asyncio.sleep(300)  # Проверяем каждые 5 минут
        now = datetime.now()
        inactive_clients = [
            client_id for client_id, last_active in active_dialogs.items()
            if (now - last_active) > timedelta(hours=1)
        ]
        
        for client_id in inactive_clients:
            del active_dialogs[client_id]
            try:
                await bot.send_message(
                    chat_id=client_id,
                    text="ℹ️ Диалог автоматически завершён из-за неактивности.\n"
                         "Чтобы начать новый диалог, нажмите «💬 Начать диалог с менеджером».",
                    reply_markup=get_main_menu()
                )
            except:
                pass
            logger.info(f"Неактивный диалог с клиентом {client_id} завершён автоматически")

# ============================================
# 🚀 ЗАПУСК БОТА
# ============================================

async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username} (ID: {bot_info.id})")
    logger.info(f"ID менеджера: {MANAGER_ID}")
    logger.info("💡 Инструкция для менеджера:\n"
                "• Чтобы ответить клиенту — нажмите «ответить» на его сообщение\n"
                "• Чтобы завершить диалог — напишите /стоп_123456789\n"
                "• Чтобы написать клиенту напрямую — /чат_123456789 текст")
    
    # Запускаем фоновую задачу очистки неактивных диалогов
    asyncio.create_task(cleanup_inactive_dialogs(bot))
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise