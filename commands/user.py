from logging import getLogger
from telegram import BotCommand, Update
from telegram.ext import CommandHandler, ContextTypes
from database import get_user, add_user
from utils.functions import get_message_context, get_user_context

logger = getLogger(__name__)

# Команда добавления пользователя (только для админов)
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = await get_message_context(update, context)

    logger.info(f'User {sender.id} is trying to add a new user')

    user = get_user(sender.id)
    if not user:
        return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    # Проверка на права администратора
    if user.role != 'admin':
        return await message.reply_text('Ошибка: у вас недостаточно прав для выполнения этой команды.')

    if not context.args or len(context.args) < 2:
        return await message.reply_text('Использование: /add_user user_id роль (admin/operator/user)')

    try:
        new_user_id = int(context.args[0])
        new_role = context.args[1]

        if new_role not in ['admin', 'operator', 'user']:
            return await message.reply_text('Ошибка: роль должна быть admin, operator или user.')

        if get_user(new_user_id):
            return await message.reply_text(f'Ошибка: пользователь с ID {new_user_id} уже существует.')

        # Добавление нового пользователя
        result = add_user(new_user_id, new_role)
        return await message.reply_text(result)

    except ValueError:
        return await message.reply_text('Ошибка: user_id должен быть числом.')

# Обработчик команды
handler = CommandHandler('add_user', add_user_command)
command = (BotCommand('add_user', 'Добавить нового пользователя (только для админов)'), handler)
