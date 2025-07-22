import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

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
    "warning": "⚠️"
}


# Стили текста
def bold(text):
    return f"<b>{text}</b>"


def italic(text):
    return f"<i>{text}</i>"


# Класс для хранения состояний
class Form(StatesGroup):
    choose_asset_group = State()
    choose_asset_subgroup = State()
    asset_name = State()
    asset_amount = State()
    entry_date = State()
    entry_price = State()
    exit_date = State()
    exit_price = State()
    image_url = State()


# Данные для кнопок с точными названиями
asset_groups = {
    "Финансовые активы": [
        "Акции",
        "Облигации",
        "Индексные фонды (ETF, БПИФ)",
        "Паевые инвестиционные фонды",
        "Цифровые активы, криптовалюты",
        "REIT"
    ],
    "Реальные активы": [
        "Недвижимость (жилая)",
        "Земельные участки",
        "Драгоценные металлы",
        "Сырьевые товары (коммодити)"
    ],
    "Денежные активы и эквиваленты": [
        "Наличные и счета",
        "Депозиты/вклады"
    ],
    "Альтернативные активы": [
        "Частные инвестиции, венчурный капитал",
        "Коллекционные предметы",
        "Интеллектуальная собственность",
        "Лизинговые инвестиции"
    ],
    "Транспортные средства и предметы роскоши": [
        "Автомобили, яхты, личные суда",
        "Аренда и чартер"
    ]
}


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
            [KeyboardButton(text="Добавить актив")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started the bot")
    await show_start_menu(message)


# Обработчик кнопки "Добавить актив"
@dp.message(F.text == "Добавить актив")
async def add_asset(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started adding an asset")
    await state.set_state(Form.choose_asset_group)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=group)] for group in asset_groups.keys()
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите категорию..."
    )
    await message.answer(
        f"{EMOJI['chart']} {bold('Выберите категорию актива:')}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


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

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=subgroup)] for subgroup in asset_groups[message.text]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите подкатегорию..."
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
    await message.answer(
        f"{EMOJI['price']} {bold('Введите название актива:')}\n"
        f"{italic('Пример: Акции Сбербанка, Квартира в Москве')}",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )


# Обработчик ввода названия актива
@dp.message(Form.asset_name)
async def process_asset_name(message: types.Message, state: FSMContext):
    await state.update_data(asset_name=message.text)
    logger.info(f"User {message.from_user.id} entered asset name: {message.text}")
    await state.set_state(Form.asset_amount)
    await message.answer(
        f"{EMOJI['chart']} {bold('Введите количество:')}\n"
        f"{italic('Целое число или дробное через точку')}",
        parse_mode="HTML"
    )


# Обработчик ввода количества
@dp.message(Form.asset_amount)
async def process_asset_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        await state.update_data(asset_amount=amount)
        logger.info(f"User {message.from_user.id} entered asset amount: {amount}")
        await state.set_state(Form.entry_date)
        await message.answer(
            f"{EMOJI['calendar']} {bold('Введите дату входа/покупки:')}\n"
            f"{italic('Формат: ДД.ММ.ГГГГ (например: 15.05.2023)')}",
            parse_mode="HTML"
        )
    except ValueError:
        logger.warning(f"User {message.from_user.id} entered invalid amount: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректное число!')}\n"
            f"Пожалуйста, введите число (например: 10 или 5.5)",
            parse_mode="HTML"
        )


# Обработчик ввода даты покупки
@dp.message(Form.entry_date)
async def process_entry_date(message: types.Message, state: FSMContext):
    await state.update_data(entry_date=message.text)
    logger.info(f"User {message.from_user.id} entered entry date: {message.text}")
    await state.set_state(Form.entry_price)
    await message.answer(
        f"{EMOJI['money']} {bold('Введите цену входа/покупки:')}\n"
        f"{italic('Сумма в рублях (например: 15000 или 1250.50)')}",
        parse_mode="HTML"
    )


# Обработчик ввода цены покупки
@dp.message(Form.entry_price)
async def process_entry_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(entry_price=price)
        logger.info(f"User {message.from_user.id} entered entry price: {price}")
        await state.set_state(Form.exit_date)
        await message.answer(
            f"{EMOJI['calendar']} {bold('Введите дату выхода/продажи:')}\n"
            f"{italic('Формат: ДД.ММ.ГГГГ или "-" если актив не продан')}",
            parse_mode="HTML"
        )
    except ValueError:
        logger.warning(f"User {message.from_user.id} entered invalid entry price: {message.text}")
        await message.answer(
            f"{EMOJI['error']} {bold('Некорректная сумма!')}\n"
            f"Пожалуйста, введите число (например: 15000 или 1250.50)",
            parse_mode="HTML"
        )


# Обработчик ввода даты продажи
@dp.message(Form.exit_date)
async def process_exit_date(message: types.Message, state: FSMContext):
    await state.update_data(exit_date=message.text)
    logger.info(f"User {message.from_user.id} entered exit date: {message.text}")
    await state.set_state(Form.exit_price)
    await message.answer(
        f"{EMOJI['money']} {bold('Введите цену выхода/продажи:')}\n"
        f"{italic('Сумма в рублях или "-" если актив не продан')}",
        parse_mode="HTML"
    )


# Обработчик ввода цены продажи
@dp.message(Form.exit_price)
async def process_exit_price(message: types.Message, state: FSMContext):
    if message.text != '-':
        try:
            price = float(message.text)
            await state.update_data(exit_price=price)
            logger.info(f"User {message.from_user.id} entered exit price: {price}")
        except ValueError:
            logger.warning(f"User {message.from_user.id} entered invalid exit price: {message.text}")
            await message.answer(
                f"{EMOJI['error']} {bold('Некорректная сумма!')}\n"
                f"Пожалуйста, введите число или '-'",
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
        parse_mode="HTML"
    )


# Обработчик ввода ссылки на изображение
@dp.message(Form.image_url)
async def process_image_url(message: types.Message, state: FSMContext):
    data = await state.get_data()
    username = message.from_user.username or f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()

    # Форматируем итоговые данные для проверки
    summary_text = f"""
{bold(f'{EMOJI["done"]} Данные сохранены в таблицу:')}

{EMOJI['price']} {bold('Категория:')} {data.get('asset_group')}
{EMOJI['price']} {bold('Подкатегория:')} {data.get('asset_subgroup')}
{EMOJI['price']} {bold('Название актива:')} {data.get('asset_name')}
{EMOJI['chart']} {bold('Количество:')} {data.get('asset_amount')}
{EMOJI['calendar']} {bold('Дата входа:')} {data.get('entry_date')}
{EMOJI['money']} {bold('Цена входа:')} {data.get('entry_price')}
{EMOJI['calendar']} {bold('Дата выхода:')} {data.get('exit_date', '-')}
{EMOJI['money']} {bold('Цена выхода:')} {data.get('exit_price', '-')}
{EMOJI['camera']} {bold('Изображение:')} {'Есть' if message.text != '-' else 'Нет'}
"""

    # Подготовка данных для Google Sheets
    row_data = [
        data.get('asset_group', ''),
        data.get('asset_subgroup', ''),
        data.get('asset_name', ''),
        data.get('asset_amount', ''),
        data.get('entry_date', ''),
        data.get('entry_price', ''),
        data.get('exit_date', ''),
        data.get('exit_price', ''),
        message.text if message.text != '-' else '',
        username
    ]

    try:
        all_values = sheet.get_all_values()
        if not all_values:
            sheet.append_row([
                "Категория актива", "Подкатегория актива", "Название актива",
                "Количество", "Дата входа/покупки", "Цена входа/покупки",
                "Дата выхода/продажи", "Цена выхода/продажи",
                "Ссылка на изображение", "Пользователь"
            ])
        sheet.append_row(row_data)
        logger.info(f"User {message.from_user.id} successfully saved data to Google Sheets")

        await message.answer(summary_text, parse_mode="HTML")

        # Предлагаем добавить ещё одну запись
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Добавить ещё актив")],
                [KeyboardButton(text="В главное меню")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            f"{EMOJI['chart']} {bold('Что дальше?')}",
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


# Обработчик кнопки "Добавить ещё актив"
@dp.message(F.text == "Добавить ещё актив")
async def add_another_asset(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} wants to add another asset")
    await add_asset(message, state)


# Обработчик кнопки "В главное меню"
@dp.message(F.text == "В главное меню")
async def back_to_main_menu(message: types.Message):
    logger.info(f"User {message.from_user.id} returned to main menu")
    await show_start_menu(message)


# Обработчик кнопки "Мои активы" (заглушка)
@dp.message(F.text == "Мои активы")
async def show_assets(message: types.Message):
    logger.info(f"User {message.from_user.id} requested 'My Assets' (not implemented)")
    await message.answer(
        f"{EMOJI['warning']} {bold('Эта функция в разработке')}",
        parse_mode="HTML"
    )


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
                "Количество", "Дата входа/покупки", "Цена входа/покупки",
                "Дата выхода/продажи", "Цена выхода/продажи",
                "Ссылка на изображение", "Пользователь"
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