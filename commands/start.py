from logging import getLogger

from telegram import BotCommand, Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_user, add_user
from utils.functions import get_message_context, get_user_context

logger = getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = await get_message_context(update, context)

    logger.info(f'User {sender.id} started the bot')

    user = get_user(sender.id)

    if not user:
        # Добавляем пользователя в БД с ролью user
        add_user(sender.id, 'user')
        return await message.reply_text(
            'Вы были добавлены в базу данных с ролью "user". Для доступа обратитесь к @Prosto_Durachok'
        )

    match user.role:
        case 'admin':
            return await message.reply_text('Добро пожаловать! У вас есть полный доступ.')
        case 'operator':
            return await message.reply_text('Добро пожаловать! У вас есть ограниченный доступ.')
        case 'user':
            return await message.reply_text('Добро пожаловать! У вас нет доступа к данному боту.')
        case _:
            return await message.reply_text('Ваша роль не определена.')

handler = CommandHandler('start', start)
command = (BotCommand('start', 'Запустить бота'), handler)
