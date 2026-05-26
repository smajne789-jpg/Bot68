import asyncio
import random
import uuid
import time
import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB = "ferrari.db"

# ================= DATABASE =================

async def db_start():
    async with aiosqlite.connect(DB) as db:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0,
            wager REAL DEFAULT 0
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS checks (
            code TEXT PRIMARY KEY,
            amount REAL,
            activations INTEGER,
            used INTEGER DEFAULT 0,
            dep_required REAL DEFAULT 0,
            dep_check INTEGER DEFAULT 0
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS activated_checks (
            user_id INTEGER,
            code TEXT
        )
        ''')

        await db.commit()


async def add_user(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,)
        )
        user = await cursor.fetchone()

        if not user:
            await db.execute(
                "INSERT INTO users(user_id,balance,wager) VALUES(?,?,?)",
                (user_id, 0, 0)
            )
            await db.commit()


async def get_balance(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cursor.fetchone()

        return row[0] if row else 0


async def get_wager(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT wager FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cursor.fetchone()

        return row[0] if row else 0


async def update_balance(user_id, amount):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()


async def set_wager(user_id, wager):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET wager=? WHERE user_id=?",
            (wager, user_id)
        )
        await db.commit()

# ================= KEYBOARDS =================


def main_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
            ],
            [
                InlineKeyboardButton(text="🎲 Dice", callback_data="play")
            ],
            [
                InlineKeyboardButton(text="✖️ Multiply 18+", callback_data="multiply_game")
            ],
            [
                InlineKeyboardButton(text="🎯 Lucky", callback_data="lucky_game")
            ]
        ]
    )


def profile_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Пополнить", callback_data="deposit")
            ],
            [
                InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw")
            ]
        ]
    )


def admin_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎟 Создать обычный чек", callback_data="create_check")
            ],
            [
                InlineKeyboardButton(text="💰 Создать депозитный чек", callback_data="create_dep_check")
            ]
        ]
    )

# ================= STATES =================

class DepositState(StatesGroup):
    amount = State()


class WithdrawState(StatesGroup):
    amount = State()


class DiceState(StatesGroup):
    amount = State()


class MultiplyState(StatesGroup):
    amount = State()


class LuckyState(StatesGroup):
    amount = State()


class CheckState(StatesGroup):
    amount = State()
    activations = State()


class DepCheckState(StatesGroup):
    amount = State()
    activations = State()
    dep_amount = State()

# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):
    await add_user(message.from_user.id)

    args = message.text.split()

    if len(args) > 1:
        code = args[1]
        await activate_check(message, code)
        return

    text = f'''
🚗 <b>Добро пожаловать в Ferrari Dice</b>

🎲 Лучшая dice игра в Telegram
💸 Быстрые выплаты
⚡ Моментальные пополнения
    '''

    await message.answer(text, reply_markup=main_kb())

# ================= PROFILE =================

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    bal = await get_balance(call.from_user.id)

    text = f'''
👤 <b>Ваш профиль</b>

🆔 ID: <code>{call.from_user.id}</code>
💰 Баланс: <b>{bal}$</b>
    '''

    wager = await get_wager(call.from_user.id)

    if wager > 0:
        text += f"\n🎯 Осталось отыграть: <b>{wager}$</b>""

    await call.message.edit_text(text, reply_markup=profile_kb())

# ================= DEPOSIT =================

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery, state: FSMContext):
    await state.set_state(DepositState.amount)

    await call.message.answer(
        "💳 Введите сумму пополнения в $"
    )


@dp.message(DepositState.amount)
async def deposit_amount(message: Message, state: FSMContext):
    amount = float(message.text)

    url = "https://pay.crypt.bot/api/createInvoice"

    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
    }

    data = {
        "asset": "USDT",
        "amount": amount,
        "description": f"Deposit Ferrari Dice"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as resp:
            result = await resp.json()

    pay_url = result['result']['pay_url']

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить",
                    url=pay_url
                )
            ]
        ]
    )

    await message.answer(
        f"💳 Счет создан на <b>{amount}$</b>",
        reply_markup=kb
    )

    await state.clear()

# ================= WITHDRAW =================

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawState.amount)

    await call.message.answer(
        "💸 Введите сумму вывода"
    )


@dp.message(WithdrawState.amount)
async def withdraw_amount(message: Message, state: FSMContext):
    amount = float(message.text)

    if amount < 1.5:
        await message.answer("❌ Минимальный вывод 1.5$")
        return

    wager = await get_wager(message.from_user.id)

    if wager > 0:
        await message.answer(f"❌ Сначала отыграйте {wager}$")
        return

    bal = await get_balance(message.from_user.id)

    if amount > bal:
        await message.answer("❌ Недостаточно средств")
        return

    await update_balance(message.from_user.id, -amount)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"accept_{message.from_user.id}_{amount}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"decline_{message.from_user.id}_{amount}"
                )
            ]
        ]
    )

    await bot.send_message(
        ADMIN_ID,
        f'''
💸 Новая заявка на вывод

👤 Юзер: {message.from_user.id}
💰 Сумма: {amount}$
        ''',
        reply_markup=kb
    )

    await message.answer("⏳ Заявка отправлена")

    await state.clear()

# ================= ADMIN WITHDRAW =================

@dp.callback_query(F.data.startswith("accept_"))
async def accept_withdraw(call: CallbackQuery):
    data = call.data.split("_")

    user_id = int(data[1])
    amount = data[2]

    await bot.send_message(
        user_id,
        f"✅ Ваш вывод на сумму {amount}$ подтвержден"
    )

    await call.message.edit_text("✅ Вывод подтвержден")


@dp.callback_query(F.data.startswith("decline_"))
async def decline_withdraw(call: CallbackQuery):
    data = call.data.split("_")

    user_id = int(data[1])
    amount = float(data[2])

    await update_balance(user_id, amount)

    await bot.send_message(
        user_id,
        f"❌ Ваш вывод {amount}$ отклонен"
    )

    await call.message.edit_text("❌ Вывод отклонен")

# ================= DICE =================

@dp.callback_query(F.data == "play")
async def play(call: CallbackQuery, state: FSMContext):
    await state.set_state(DiceState.amount)

    await call.message.answer(
        "🎲 Введите сумму ставки"
    )


@dp.message(DiceState.amount)
async def dice_game(message: Message, state: FSMContext):
    amount = float(message.text)

    bal = await get_balance(message.from_user.id)

    if amount > bal:
        await message.answer("❌ Недостаточно средств")
        return

    await update_balance(message.from_user.id, -amount)

    dice = await bot.send_dice(
        message.chat.id,
        emoji="🎲"
    )

    value = dice.dice.value

    if value in [5, 6]:
        win = amount * 4

        await update_balance(message.from_user.id, win)

        await message.answer(
            f'''
🎉 Победа!

🎲 Выпало: {value}
💰 Вы выиграли: {win}$
            '''
        )
    else:
        await message.answer(
            f'''
❌ Проигрыш

🎲 Выпало: {value}
            '''
        )

    await state.clear()

# ================= MULTIPLY GAME =================

@dp.callback_query(F.data == "multiply_game")
async def multiply_game(call: CallbackQuery, state: FSMContext):
    await state.set_state(MultiplyState.amount)

    await call.message.answer(
        "✖️ Введите сумму ставки"
    )


@dp.message(MultiplyState.amount)
async def multiply_game_play(message: Message, state: FSMContext):
    amount = float(message.text)

    bal = await get_balance(message.from_user.id)

    if amount > bal:
        await message.answer("❌ Недостаточно средств")
        return

    await update_balance(message.from_user.id, -amount)

    first = random.randint(1, 6)
    second = random.randint(1, 6)

    result = first * second

    text = f'''
🎲 Первый кубик: {first}
🎲 Второй кубик: {second}

✖️ Произведение: {result}
    '''

    if result > 18:
        win = amount * 5

        await update_balance(message.from_user.id, win)

        text += f'''\n\n🎉 Победа!
💰 Выигрыш: {win}$'''
    else:
        text += "\n\n❌ Проигрыш"

    await message.answer(text)

    await state.clear()

# ================= LUCKY GAME =================

@dp.callback_query(F.data == "lucky_game")
async def lucky_game(call: CallbackQuery, state: FSMContext):
    await state.set_state(LuckyState.amount)

    await call.message.answer(
        "🎯 Введите сумму ставки"
    )


@dp.message(LuckyState.amount)
async def lucky_game_play(message: Message, state: FSMContext):
    amount = float(message.text)

    bal = await get_balance(message.from_user.id)

    if amount > bal:
        await message.answer("❌ Недостаточно средств")
        return

    await update_balance(message.from_user.id, -amount)

    chance = random.randint(1, 100)

    if chance <= 65:
        win = round(amount * 1.3, 2)

        await update_balance(message.from_user.id, win)

        await message.answer(
            f'''
🎯 Lucky выиграл

💰 Выплата: {win}$
📈 x1.3
            '''
        )
    else:
        await message.answer(
            "❌ Lucky проиграл"
        )

    wager_now = await get_wager(message.from_user.id)

    if wager_now > 0:
        new_wager = max(0, wager_now - amount)
        await set_wager(message.from_user.id, new_wager)

    await state.clear()

# ================= ADMIN PANEL =================

@dp.message(Command("admin"))
async def admin(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "⚙️ Админ панель",
        reply_markup=admin_kb()
    )

# ================= CREATE CHECK =================

@dp.callback_query(F.data == "create_check")
async def create_check(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        return

    await state.set_state(CheckState.amount)

    await call.message.answer(
        "💰 Введите сумму чека"
    )


@dp.message(CheckState.amount)
async def check_amount(message: Message, state: FSMContext):
    await state.update_data(amount=float(message.text))

    await state.set_state(CheckState.activations)

    await message.answer(
        "👥 Введите количество активаций"
    )


@dp.message(CheckState.activations)
async def check_activations(message: Message, state: FSMContext):
    data = await state.get_data()

    amount = data['amount']
    activations = int(message.text)

    code = str(uuid.uuid4())[:8]

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO checks VALUES(?,?,?,?,?,?)",
            (code, amount, activations, 0, 0, 0)
        )
        await db.commit()

    link = f"https://t.me/{BOT_USERNAME}?start={code}"

    await message.answer(
        f'''
✅ Чек создан

🔗 {link}
        '''
    )

    await state.clear()

# ================= DEPOSIT CHECK =================

@dp.callback_query(F.data == "create_dep_check")
async def create_dep_check(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        return

    await state.set_state(DepCheckState.amount)

    await call.message.answer(
        "💰 Введите сумму чека"
    )


@dp.message(DepCheckState.amount)
async def dep_check_amount(message: Message, state: FSMContext):
    await state.update_data(amount=float(message.text))

    await state.set_state(DepCheckState.activations)

    await message.answer(
        "👥 Введите количество активаций"
    )


@dp.message(DepCheckState.activations)
async def dep_check_activations(message: Message, state: FSMContext):
    await state.update_data(activations=int(message.text))

    await state.set_state(DepCheckState.dep_amount)

    await message.answer(
        "💳 Сколько нужно пополнить для активации?"
    )


@dp.message(DepCheckState.dep_amount)
async def dep_check_finish(message: Message, state: FSMContext):
    data = await state.get_data()

    amount = data['amount']
    activations = data['activations']
    dep_amount = float(message.text)

    code = str(uuid.uuid4())[:8]

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO checks VALUES(?,?,?,?,?,?)",
            (code, amount, activations, 0, dep_amount, 1)
        )
        await db.commit()

    link = f"https://t.me/{BOT_USERNAME}?start={code}"

    await message.answer(
        f'''
✅ Депозитный чек создан

🔗 {link}
        '''
    )

    await state.clear()

# ================= ACTIVATE CHECK =================

async def activate_check(message, code):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT * FROM checks WHERE code=?",
            (code,)
        )

        check = await cursor.fetchone()

        cursor2 = await db.execute(
            "SELECT * FROM activated_checks WHERE user_id=? AND code=?",
            (message.from_user.id, code)
        )

        already = await cursor2.fetchone()

        if already:
            await message.answer("❌ Вы уже активировали этот чек")
            return

        if not check:
            await message.answer("❌ Чек не найден")
            return

        code_db, amount, activations, used, dep_required, dep_check = check

        if used >= activations:
            await message.answer("❌ Чек закончился")
            return

        if dep_check == 1:
            await message.answer(
                f'''
💳 Для активации чека:

Пополните баланс минимум на {dep_required}$
                '''
            )
            return

        await update_balance(message.from_user.id, amount)

        wager = amount * 5

        async with aiosqlite.connect(DB) as db2:
            await db2.execute(
                "INSERT INTO activated_checks VALUES(?,?)",
                (message.from_user.id, code)
            )

            await db2.execute(
                "UPDATE users SET wager = wager + ? WHERE user_id=?",
                (wager, message.from_user.id)
            )

            await db2.commit()

        await db.execute(
            "UPDATE checks SET used = used + 1 WHERE code=?",
            (code,)
        )

        await db.commit()

        await message.answer(
            f'''
🎉 Чек активирован

💰 Начислено: {amount}$
🎯 Отыгрыш x5
💸 Осталось отыграть: {wager}$
            '''
        )

# ================= RUN =================

async def main():
    await db_start()
    print("BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
