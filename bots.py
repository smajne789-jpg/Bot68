import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# --- ENV VARIABLES ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN or not ADMIN_ID or not CHANNEL_ID:
    raise ValueError("Set BOT_TOKEN, ADMIN_ID, CHANNEL_ID environment variables")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

participants = []
message_id = None

def admin_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎁 Создать розыгрыш", callback_data="create"))
    return kb

def join_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎉 Участвовать", callback_data="join"))
    return kb

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Панель управления:", reply_markup=admin_keyboard())
    else:
        await message.answer("Этот бот для розыгрышей 🎁")

@dp.callback_query_handler(lambda c: c.data == "create")
async def create_giveaway(callback: types.CallbackQuery):
    global participants, message_id

    if callback.from_user.id != ADMIN_ID:
        return

    participants = []

    msg = await bot.send_message(
        CHANNEL_ID,
        "🎁ТОЛЬКО ПЕРВЫЕ 6 ЧЕЛОВЕК МОГУТ ПОУЧАСТВОВАТЬ!\n\nУчастники:\n(пусто)",
        reply_markup=join_keyboard()
    )

    message_id = msg.message_id
    await callback.answer("Розыгрыш создан!")

async def update_message():
    text = "🎁ТОЛЬКО ПЕРВЫЕ 6 ЧЕЛОВЕК МОГУТ ПОУЧАСТВОВАТЬ!\n\nУчастники:\n"

    if not participants:
        text += "(пусто)"
    else:
        for p in participants:
            name = p["username"] or p["name"]
            text += f"{p['number']}. @{name}\n"

    await bot.edit_message_text(
        text,
        chat_id=CHANNEL_ID,
        message_id=message_id,
        reply_markup=join_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "join")
async def join(callback: types.CallbackQuery):
    global participants

    user = callback.from_user

    if user.id in [p["id"] for p in participants]:
        await callback.answer("Ты уже участвуешь")
        return

    participants.append({
        "id": user.id,
        "username": user.username,
        "name": user.first_name,
        "number": len(participants) + 1
    })

    await callback.answer(f"Ты участник №{len(participants)}")
    await update_message()

    if len(participants) == 6:
        await bot.send_message(CHANNEL_ID, "🎲 Определяем победителя...")

        dice_msg = await bot.send_dice(CHANNEL_ID)
        await asyncio.sleep(3)

        dice_value = dice_msg.dice.value
        winner = participants[dice_value - 1]

        name = winner["username"] or winner["name"]

        await bot.send_message(
            CHANNEL_ID,
            f"🎁 Завершено!\n\n"
            f"🎲 Выпало число: {dice_value}\n\n"
            f"🏆 Победитель:\n@{name}"
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp)
