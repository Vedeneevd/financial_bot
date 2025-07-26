import os
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Настройка Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'model-hexagon-466415-b1-cae1b431f892.json'
SPREADSHEET_ID = '12BDetUqLfdHTbEd29eZ4jj6-CQqxYBABRtNTCObkWns'

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Эмодзи для красоты
EMOJI = {
    "money": "💰",
    "chart": "📊",
    "house": "🏠",
    "car": "🚗",
    "gem": "💎",
    "calendar": "📅",
    "price": "🏷️",
    "camera": "📸",
    "done": "✅",
    "error": "❌",
    "warning": "⚠️",
    "back": "🔙",
    "contact": "📞",
    "user": "👤",
    "email": "📧",
    "phone": "📱",
    "add": "➕",
    "list": "📋",
    "bank": "🏦",
    "stock": "📈",
    "real_estate": "🏠",
    "alternative": "🎨",
    "transport": "🚗"
}

# Валюта
CURRENCIES = ["USD (Доллар)", "EUR (Евро)", "CNY (Юань)", "RUB (Рубль)", "CHF (Франк)"]

# Примеры для разных типов активов
ASSET_EXAMPLES = {
    "Акции": "Акции Сбербанка, Акции Газпрома, Акции Apple",
    "Облигации": "ОФЗ-26242, Облигации РЖД, Еврооблигации РФ-2028",
    "Недвижимость (жилая)": "Квартира в Москве, Дом в Подмосковье, Апартаменты в Сочи",
    "Земельные участки": "Участок 10 соток в Ленобласти, Земля под ИЖС в Новосибирске",
    "Автомобили, яхты, личные суда": "Toyota Camry, Яхта Princess 45, Катер Mercury",
    "Цифровые активы, криптовалюты": "Bitcoin, Ethereum, Solana"
}


# Стили текста
def bold(text):
    return f"<b>{text}</b>"


def italic(text):
    return f"<i>{text}</i>"


# Валидация email
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# Валидация телефона
def is_valid_phone(phone):
    pattern = r'^(\+7|7|8)?[\s\-]?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    return re.match(pattern, phone) is not None


# Валидация даты
def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, '%d.%m.%Y')
        return True
    except ValueError:
        return False


# Класс для хранения состояний (измененный порядок)
class Form(StatesGroup):
    choose_asset_group = State()
    choose_asset_subgroup = State()
    asset_name = State()
    asset_amount = State()
    currency = State()  # Валюта теперь перед датой
    entry_price = State()  # Цена теперь перед датой
    entry_date = State()  # Дата после цены
    exit_date = State()
    exit_price = State()
    image_url = State()
    add_another_asset = State()
    contact_name = State()
    contact_email = State()
    contact_phone = State()


# Данные для кнопок с точными названиями
asset_groups = {
    f"{EMOJI['stock']} Финансовые активы": [
        f"{EMOJI['chart']} Акции",
        f"{EMOJI['money']} Облигации",
        f"{EMOJI['list']} Индексные фонды (ETF, БПИФ)",
        f"{EMOJI['bank']} Паевые инвестиционные фонды",
        f"{EMOJI['gem']} Цифровые активы, криптовалюты",
        f"{EMOJI['house']} REIT"
    ],
    f"{EMOJI['real_estate']} Реальные активы": [
        f"{EMOJI['house']} Недвижимость (жилая)",
        f"{EMOJI['gem']} Земельные участки",
        f"{EMOJI['gem']} Драгоценные металлы",
        f"{EMOJI['money']} Сырьевые товары (коммодити)"
    ],
    f"{EMOJI['bank']} Денежные активы и эквиваленты": [
        f"{EMOJI['money']} Наличные и счета",
        f"{EMOJI['bank']} Депозиты/вклады"
    ],
    f"{EMOJI['alternative']} Альтернативные активы": [
        f"{EMOJI['money']} Частные инвестиции, венчурный капитал",
        f"{EMOJI['gem']} Коллекционные предметы",
        f"{EMOJI['user']} Интеллектуальная собственность",
        f"{EMOJI['chart']} Лизинговые инвестиции"
    ],
    f"{EMOJI['transport']} Транспортные средства и предметы роскоши": [
        f"{EMOJI['car']} Автомобили, яхты, личные суда",
        f"{EMOJI['money']} Аренда и чартер"
    ]
}


# Функция для создания клавиатуры с группировкой кнопок
def create_keyboard(items, row_width=2, back_button=True):
    buttons = []
    for i in range(0, len(items), row_width):
        row = items[i:i + row_width]
        buttons.append([KeyboardButton(text=item) for item in row])

    if back_button:
        buttons.append([KeyboardButton(text=f"{EMOJI['back']} Назад")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выберите вариант..."
    )


# Главное меню
async def show_start_menu(message: types.Message):
    welcome_text = f"""
{bold(f'{EMOJI["chart"]} Финансовый трекер')}

Привет, {message.from_user.first_name}! 
Я помогу тебе вести учет твоих активов и инвестиций.

{italic('Выбери действие:')}
"""

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{EMOJI['add']} Добавить актив")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started the bot")
    await state.clear()
    await show_start_menu(message)


# Обработчик кнопки "Добавить актив"
@dp.message(F.text == f"{EMOJI['add']} Добавить актив")
async def add_asset(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started adding an asset")
    await state.set_state(Form.choose_asset_group)

    keyboard = create_keyboard(
        items=list(asset_groups.keys()),
        row_width=2,
        back_button=True
    )

    await message.answer(
        f"{EMOJI['chart']} {bold('Выберите категорию актива:')}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Обработчик кнопки "Назад" (обновлен под новый порядок)
@dp.message(F.text == f"{EMOJI['back']} Назад")
async def back_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()

    state_mapping = {
        Form.choose_asset_subgroup.state: (
        Form.choose_asset_group, None, "Выберите категорию актива:", list(asset_groups.keys())),
        Form.asset_name.state: (Form.choose_asset_subgroup, data.get('asset_group'), "Выберите подкатегорию:",
                                asset_groups.get(data.get('asset_group', ''), [])),
        Form.asset_amount.state: (Form.asset_name, None,
                                  f"Введите название актива:\nПример: {ASSET_EXAMPLES.get(data.get('asset_subgroup', 'Актив')[2:], 'Актив')}",
                                  None),
        Form.currency.state: (
        Form.asset_amount, None, "Введите количество:\nЦелое число или дробное через точку", None),
        Form.entry_price.state: (Form.currency, None, "Выберите валюту:", CURRENCIES),
        Form.entry_date.state: (
        Form.entry_price, None, "Введите цену входа/покупки:\nСумма в выбранной валюте (например: 15000 или 1250.50)",
        None),
        Form.exit_date.state: (
        Form.entry_date, None, "Введите дату входа/покупки:\nФормат: ДД.ММ.ГГГГ (например: 15.05.2023)", None),
        Form.exit_price.state: (
        Form.exit_date, None, "Введите дату выхода/продажи:\nФормат: ДД.ММ.ГГГГ или '-' если актив не продан", None),
        Form.image_url.state: (
        Form.exit_price, None, "Введите цену выхода/продажи:\nСумма в выбранной валюте или '-' если актив не продан",
        None),
        Form.add_another_asset.state: (
        Form.image_url, None, "Пришлите ссылку на изображение:\nИли отправьте '-' если изображения нет", None),
        Form.contact_name.state: (Form.add_another_asset, None, "Хотите добавить еще один актив?", ["Да", "Нет"]),
        Form.contact_email.state: (Form.contact_name, None, "Введите ваше имя:", None),
        Form.contact_phone.state: (Form.contact_email, None, "Введите ваш email:\nПример: example@mail.com", None),
    }

    if current_state in state_mapping:
        prev_state, extra_data, message_text, items = state_mapping[current_state]
        await state.set_state(prev_state)

        if items is not None:
            keyboard = create_keyboard(
                items=items,
                row_width=2,
                back_button=True
            )
            await message.answer(
                f"{EMOJI['chart']} {bold(message_text)}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"{EMOJI['chart']} {bold(message_text)}",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
                    resize_keyboard=True
                ),
                parse_mode="HTML"
            )
    else:
        await state.clear()
        await show_start_menu(message)


# Обработчик выбора группы активов
@dp.message(Form.choose_asset_group)
async def process_asset_group(message: types.Message, state: FSMContext):
    if message.text not in asset_groups:
        logger.warning(f"User {message.from_user.id} selected invalid asset group: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Пожалуйста, выберите вариант из меню')}",
            parse_mode="HTML"
        )
        return

    await state.update_data(asset_group=message.text)
    logger.info(f"User {message.from_user.id} selected asset group: {message.text}")

    keyboard = create_keyboard(
        items=asset_groups[message.text],
        row_width=2,
        back_button=True
    )

    await state.set_state(Form.choose_asset_subgroup)
    await message.answer(
        f"{EMOJI['chart']} {bold('Выберите подкатегорию:')}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Обработчик выбора подгруппы
@dp.message(Form.choose_asset_subgroup)
async def process_asset_subgroup(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_group = data.get('asset_group')

    if message.text not in asset_groups[current_group]:
        logger.warning(f"User {message.from_user.id} selected invalid asset subgroup: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Пожалуйста, выберите вариант из меню')}",
            parse_mode="HTML"
        )
        return

    await state.update_data(asset_subgroup=message.text)
    logger.info(f"User {message.from_user.id} selected asset subgroup: {message.text}")
    await state.set_state(Form.asset_name)

    example = ASSET_EXAMPLES.get(message.text[2:], "Актив")
    await message.answer(
        f"{EMOJI['price']} {bold('Введите название актива:')}\n"
        f"{italic(f'Пример: {example}')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода названия актива
@dp.message(Form.asset_name)
async def process_asset_name(message: types.Message, state: FSMContext):
    if len(message.text) > 100:
        await message.answer(
            f"{EMOJI['error']} {bold('Название слишком длинное! Максимум 100 символов.')}",
            parse_mode="HTML"
        )
        return

    await state.update_data(asset_name=message.text)
    logger.info(f"User {message.from_user.id} entered asset name: {message.text}")
    await state.set_state(Form.asset_amount)
    await message.answer(
        f"{EMOJI['chart']} {bold('Введите количество:')}\n"
        f"{italic('Целое число или дробное через точку')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода количества
@dp.message(Form.asset_amount)
async def process_asset_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        await state.update_data(asset_amount=amount)
        logger.info(f"User {message.from_user.id} entered asset amount: {amount}")
        await state.set_state(Form.currency)

        keyboard = create_keyboard(
            items=CURRENCIES,
            row_width=2,
            back_button=True
        )
        await message.answer(
            f"{EMOJI['money']} {bold('Выберите валюту:')}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except ValueError:
        logger.warning(f"User {message.from_user.id} entered invalid amount: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректное число!')}\n"
            f"Пожалуйста, введите положительное число (например: 10 или 5.5)",
            parse_mode="HTML"
        )


# Обработчик выбора валюты
@dp.message(Form.currency)
async def process_currency(message: types.Message, state: FSMContext):
    if message.text not in CURRENCIES:
        logger.warning(f"User {message.from_user.id} selected invalid currency: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Пожалуйста, выберите вариант из меню')}",
            parse_mode="HTML"
        )
        return

    await state.update_data(currency=message.text)
    logger.info(f"User {message.from_user.id} selected currency: {message.text}")
    await state.set_state(Form.entry_price)
    await message.answer(
        f"{EMOJI['money']} {bold('Введите цену входа/покупки:')}\n"
        f"{italic('Сумма в выбранной валюте (например: 15000 или 1250.50)')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода цены покупки
@dp.message(Form.entry_price)
async def process_entry_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(entry_price=price)
        logger.info(f"User {message.from_user.id} entered entry price: {price}")
        await state.set_state(Form.entry_date)
        await message.answer(
            f"{EMOJI['calendar']} {bold('Введите дату входа/покупки:')}\n"
            f"{italic('Формат: ДД.ММ.ГГГГ (например: 15.05.2023)')}",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
    except ValueError:
        logger.warning(f"User {message.from_user.id} entered invalid entry price: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректная сумма!')}\n"
            f"Пожалуйста, введите положительное число (например: 15000 или 1250.50)",
            parse_mode="HTML"
        )


# Обработчик ввода даты покупки
@dp.message(Form.entry_date)
async def process_entry_date(message: types.Message, state: FSMContext):
    if message.text != '-' and not is_valid_date(message.text):
        logger.warning(f"User {message.from_user.id} entered invalid date: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректная дата!')}\n"
            f"Пожалуйста, введите дату в формате ДД.ММ.ГГГГ или '-'",
            parse_mode="HTML"
        )
        return

    await state.update_data(entry_date=message.text)
    logger.info(f"User {message.from_user.id} entered entry date: {message.text}")
    await state.set_state(Form.exit_date)
    await message.answer(
        f"{EMOJI['calendar']} {bold('Введите дату выхода/продажи:')}\n"
        f"{italic('Формат: ДД.ММ.ГГГГ или "-" если актив не продан')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода даты продажи
@dp.message(Form.exit_date)
async def process_exit_date(message: types.Message, state: FSMContext):
    if message.text != '-' and not is_valid_date(message.text):
        logger.warning(f"User {message.from_user.id} entered invalid exit date: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректная дата!')}\n"
            f"Пожалуйста, введите дату в формате ДД.ММ.ГГГГ или '-'",
            parse_mode="HTML"
        )
        return

    await state.update_data(exit_date=message.text)
    logger.info(f"User {message.from_user.id} entered exit date: {message.text}")
    await state.set_state(Form.exit_price)
    await message.answer(
        f"{EMOJI['money']} {bold('Введите цену выхода/продажи:')}\n"
        f"{italic('Сумма в выбранной валюте или "-" если актив не продан')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода цены продажи
@dp.message(Form.exit_price)
async def process_exit_price(message: types.Message, state: FSMContext):
    if message.text != '-':
        try:
            price = float(message.text)
            if price <= 0:
                raise ValueError
            await state.update_data(exit_price=price)
            logger.info(f"User {message.from_user.id} entered exit price: {price}")
        except ValueError:
            logger.warning(f"User {message.from_user.id} entered invalid exit price: {message.text}")
            await message.answer(
                f"{EMOJI['error']} {bold('Некорректная сумма!')}\n"
                f"Пожалуйста, введите положительное число или '-'",
                parse_mode="HTML"
            )
            return
    else:
        await state.update_data(exit_price=message.text)
        logger.info(f"User {message.from_user.id} has no exit price")

    await state.set_state(Form.image_url)
    await message.answer(
        f"{EMOJI['camera']} {bold('Пришлите ссылку на изображение:')}\n"
        f"{italic('Или отправьте "-" если изображения нет')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода ссылки на изображение
@dp.message(Form.image_url)
async def process_image_url(message: types.Message, state: FSMContext):
    if message.text != '-' and not message.text.startswith(('http://', 'https://')):
        logger.warning(f"User {message.from_user.id} entered invalid image URL: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректная ссылка!')}\n"
            f"Пожалуйста, введите корректную URL-ссылку или '-'",
            parse_mode="HTML"
        )
        return

    await state.update_data(image_url=message.text)
    logger.info(f"User {message.from_user.id} entered image URL: {message.text}")
    await state.set_state(Form.add_another_asset)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
            [KeyboardButton(text=f"{EMOJI['back']} Назад")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"{EMOJI['chart']} {bold('Хотите добавить еще один актив?')}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Обработчик выбора "Добавить еще актив"
@dp.message(Form.add_another_asset)
async def process_add_another_asset(message: types.Message, state: FSMContext):
    if message.text.lower() not in ["да", "нет"]:
        await message.answer(
            f"{EMOJI['error']} {bold('Пожалуйста, выберите "Да" или "Нет"')}",
            parse_mode="HTML"
        )
        return

    if message.text.lower() == "да":
        # Сохраняем текущий актив и начинаем новый
        await save_current_asset(message, state)
        await add_asset(message, state)
    else:
        # Переходим к вводу контактных данных
        await save_current_asset(message, state)
        await state.set_state(Form.contact_name)
        await message.answer(
            f"{EMOJI['user']} {bold('Введите ваше имя:')}\n"
            f"{italic('Как к вам можно обращаться?')}",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )


async def save_current_asset(message: types.Message, state: FSMContext):
    # Здесь можно добавить логику сохранения текущего актива
    pass


# Обработчик ввода имени
@dp.message(Form.contact_name)
async def process_contact_name(message: types.Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer(
            f"{EMOJI['error']} {bold('Имя слишком длинное! Максимум 50 символов.')}",
            parse_mode="HTML"
        )
        return

    await state.update_data(contact_name=message.text)
    logger.info(f"User {message.from_user.id} entered name: {message.text}")
    await state.set_state(Form.contact_email)
    await message.answer(
        f"{EMOJI['email']} {bold('Введите ваш email:')}\n"
        f"{italic('Пример: example@mail.com')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода email
@dp.message(Form.contact_email)
async def process_contact_email(message: types.Message, state: FSMContext):
    if not is_valid_email(message.text):
        logger.warning(f"User {message.from_user.id} entered invalid email: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректный email!')}\n"
            f"Пожалуйста, введите действительный email (например: example@mail.com)",
            parse_mode="HTML"
        )
        return

    await state.update_data(contact_email=message.text)
    logger.info(f"User {message.from_user.id} entered email: {message.text}")
    await state.set_state(Form.contact_phone)
    await message.answer(
        f"{EMOJI['phone']} {bold('Введите ваш номер телефона:')}\n"
        f"{italic('Формат: +79991234567 или 89991234567')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=f"{EMOJI['back']} Назад")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )


# Обработчик ввода телефона
@dp.message(Form.contact_phone)
async def process_contact_phone(message: types.Message, state: FSMContext):
    if not is_valid_phone(message.text):
        logger.warning(f"User {message.from_user.id} entered invalid phone: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректный номер телефона!')}\n"
            f"Пожалуйста, введите действительный номер (например: +79991234567 или 89991234567)",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    username = message.from_user.username or f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()

    # Форматируем итоговые данные для проверки
    summary_text = f"""
{bold(f'{EMOJI["done"]} Данные сохранены в таблицу:')}

{EMOJI['price']} {bold('Категория:')} {data.get('asset_group', '-')[2:]}
{EMOJI['price']} {bold('Подкатегория:')} {data.get('asset_subgroup', '-')[2:]}
{EMOJI['price']} {bold('Название актива:')} {data.get('asset_name', '-')}
{EMOJI['chart']} {bold('Количество:')} {data.get('asset_amount', '-')}
{EMOJI['money']} {bold('Валюта:')} {data.get('currency', '-')}
{EMOJI['calendar']} {bold('Дата входа:')} {data.get('entry_date', '-')}
{EMOJI['money']} {bold('Цена входа:')} {data.get('entry_price', '-')} {data.get('currency', '').split()[0] if data.get('entry_price') != '-' else ''}
{EMOJI['calendar']} {bold('Дата выхода:')} {data.get('exit_date', '-')}
{EMOJI['money']} {bold('Цена выхода:')} {data.get('exit_price', '-')} {data.get('currency', '').split()[0] if data.get('exit_price') != '-' else ''}
{EMOJI['camera']} {bold('Изображение:')} {'Есть' if data.get('image_url', '-') != '-' else 'Нет'}
{EMOJI['user']} {bold('Имя:')} {data.get('contact_name', '-')}
{EMOJI['email']} {bold('Email:')} {data.get('contact_email', '-')}
{EMOJI['phone']} {bold('Телефон:')} {message.text}
"""

    # Подготовка данных для Google Sheets
    row_data = [
        data.get('asset_group', '')[2:],  # Убираем эмодзи
        data.get('asset_subgroup', '')[2:],  # Убираем эмодзи
        data.get('asset_name', ''),
        data.get('asset_amount', ''),
        data.get('currency', ''),
        data.get('entry_date', ''),
        data.get('entry_price', ''),
        data.get('exit_date', ''),
        data.get('exit_price', ''),
        data.get('image_url', ''),
        data.get('contact_name', ''),
        data.get('contact_email', ''),
        message.text,  # phone
        username
    ]

    try:
        all_values = sheet.get_all_values()
        if not all_values:
            sheet.append_row([
                "Категория актива", "Подкатегория актива", "Название актива",
                "Количество", "Валюта", "Дата входа/покупки", "Цена входа/покупки",
                "Дата выхода/продажи", "Цена выхода/продажи",
                "Ссылка на изображение", "Имя", "Email", "Телефон", "Пользователь"
            ])
        sheet.append_row(row_data)
        logger.info(f"User {message.from_user.id} successfully saved data to Google Sheets")

        await message.answer(summary_text, parse_mode="HTML")

        # Финальное сообщение с благодарностью
        final_message = f"""
{bold(f'{EMOJI["done"]} Благодарим вас за предоставленные данные!')}

Вы получите индивидуальные рекомендации и результаты анализа на указанные контакты:
📧 Email: {bold(data.get('contact_email'))}

Спасибо за доверие!
"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"{EMOJI['chart']} В главное меню")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            final_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error saving data for user {message.from_user.id}: {str(e)}")
        await message.answer(
            f"{EMOJI['error']} {bold('Ошибка сохранения:')}\n{str(e)}",
            parse_mode="HTML"
        )

    await state.clear()


# Обработчик кнопки "В главное меню"
@dp.message(F.text == f"{EMOJI['chart']} В главное меню")
async def back_to_main_menu(message: types.Message):
    logger.info(f"User {message.from_user.id} returned to main menu")
    await show_start_menu(message)


# Запуск бота
async def main():
    # Подключение к Google Sheets
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        global sheet
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        logger.info(f"{EMOJI['done']} Успешное подключение к Google Sheets")

        # Проверяем и создаем заголовки если нужно
        if not sheet.get_all_values():
            sheet.append_row([
                "Категория актива", "Подкатегория актива", "Название актива",
                "Количество", "Валюта", "Дата входа/покупки", "Цена входа/покупки",
                "Дата выхода/продажи", "Цена выхода/продажи",
                "Ссылка на изображение", "Имя", "Email", "Телефон", "Пользователь"
            ])
            logger.info("Created headers in Google Sheets")

    except Exception as e:
        logger.error(f"{EMOJI['error']} Ошибка подключения: {e}")
        exit()

    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())