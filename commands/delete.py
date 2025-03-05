from logging import getLogger
from telegram import BotCommand, Update
from telegram.ext import CommandHandler, ContextTypes
from database import delete_user, get_user
from utils.functions import get_message_context, get_user_context

logger = getLogger(__name__)

# Команда удаления пользователя
async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = await get_message_context(update, context)

    logger.info(f'User {sender.id} started the bot')

    user = get_user(sender.id)

    if not user:
        return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    if user.role == 'admin' and context.args:
        try:
            user_id = int(context.args[0])

            result = delete_user(user_id)
            return await message.reply_text(result)

        except ValueError:
            return await message.reply_text('Ошибка: user_id должен быть числом.')

    return await message.reply_text('Для удаления пользователя используйте команду с аргументом: user_id.')

handler = CommandHandler('delete_user', delete_user_command)
command = (BotCommand('delete_user', 'Удалить пользователя'), handler)