from logging import getLogger
from telegram import BotCommand, Update
from telegram.ext import CommandHandler, ContextTypes
from database import get_all_users, get_user
from utils.functions import get_message_context, get_user_context

logger = getLogger(__name__)

# Команда просмотра пользователя
async def view_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = await get_message_context(update, context)

    logger.info(f'User {sender.id} started the bot')

    user = get_user(sender.id)

    if not user:
        return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    if user.role == 'admin':  # Проверка на роль admin
        # Получаем всех пользователей
        all_users = get_all_users()
        
        if not all_users:
            return await message.reply_text('Нет пользователей для отображения.')

        # Формируем строку с пользователями
        user_list = "\n".join([f"ID: {u.id}, UserID: {u.user_id}, Role: {u.role}" for u in all_users])
        return await message.reply_text(f"Список пользователей:\n{user_list}")

    return await message.reply_text('У вас нет прав для просмотра всех пользователей.')

# Обработчик команды
handler = CommandHandler('view_user', view_user_command)
command = (BotCommand('view_user', 'Просмотр всех пользователей (только для админов)'), handler)
