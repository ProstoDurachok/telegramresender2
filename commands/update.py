from logging import getLogger
from telegram import BotCommand, Update
from telegram.ext import CommandHandler, ContextTypes
from database import update_user_role, get_user
from utils.functions import get_message_context, get_user_context

logger = getLogger(__name__)

# Команда обновления роли пользователя
async def update_user_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = await get_message_context(update, context)

    logger.info(f'User {sender.id} started the bot')

    user = get_user(sender.id)

    if not user:
        return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    if user.role == 'admin' and context.args:
        if len(context.args) < 2:
            return await message.reply_text('Использование: /update_user_role user_id новая_роль')

        try:
            user_id = int(context.args[0])
            new_role = context.args[1]

            if new_role not in ['admin', 'operator', 'user']:
                return await message.reply_text('Ошибка: роль должна быть admin, operator или user.')

            result = update_user_role(user_id, new_role)
            return await message.reply_text(result)

        except ValueError:
            return await message.reply_text('Ошибка: user_id должен быть числом.')

    return await message.reply_text('Для обновления роли пользователя используйте команду с аргументами: user_id и новая_роль.')

handler = CommandHandler('update_user', update_user_role_command)
command = (BotCommand('update_user', 'Изменить пользователя'), handler)

