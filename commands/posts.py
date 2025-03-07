from io import BytesIO
from logging import getLogger

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes

from commands.channels import CHANNELS_PER_PAGE
from database import get_channels, get_posts, get_total_channels, get_user, get_user_channels, get_total_user_channels
from utils.functions import (
    get_callback_query_context,
    get_user_context,
    get_user_data_context,
)

logger = getLogger(__name__)


async def posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = update.message
    user_data = await get_user_data_context(update, context)
    query = update.callback_query

    user = get_user(sender.id)

    # Проверка роли пользователя
    if user and user.role == 'user':  # Предполагаем, что у пользователя есть атрибут role
        if message:
            return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    if not user and message:
        return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    page = user_data.get('posts_channels_page', 0)
    selected_channels = user_data.get('posts_selected_channels', [])

    if page < 0:
        page = 0

    logger.info(f'User {sender.id} requested channels to get posts [Page: {page+1}]')

    db_channels_count = get_total_user_channels(sender.id)
    db_channels = get_user_channels(sender.id, limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    keyboard: list[list[InlineKeyboardButton]] = []
    navigation_buttons: list[InlineKeyboardButton] = []
    action_buttons: list[InlineKeyboardButton] = []


    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in selected_channels else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'posts_channels_toggle_{channel.channel_id}',
        )
        link_button = InlineKeyboardButton('🔗 Перейти', url=f'{channel.channel_link}')
        keyboard.append([channel_button, link_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='posts_channels_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < db_channels_count:
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='posts_channels_next_page')
        )

    if len(selected_channels) != db_channels_count:
        action_buttons.append(
            InlineKeyboardButton('✅ Выбрать все каналы', callback_data='posts_channels_all')
        )

    else:
        action_buttons.append(
            InlineKeyboardButton('❌ Отменить выбор', callback_data='posts_channels_clear')
        )

    if len(selected_channels) > 0:
        action_buttons.append(
            InlineKeyboardButton('Скачать список постов', callback_data='posts_download')
        )

    keyboard.append(navigation_buttons)
    keyboard.append(action_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await message.reply_text(
            f'Выберите каналы для получения статистики: Всего каналов - {db_channels_count}',
            reply_markup=reply_markup,
        )

    elif query:
        await query.edit_message_text(
            f'Выберите каналы для получения статистики: Всего каналов - {db_channels_count}',
            reply_markup=reply_markup,
        )
        await query.answer()

    else:
        raise Exception('Either message or callback query can not be fetched')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    query = await get_callback_query_context(update, context)

    if not isinstance(context.user_data, dict):
        raise Exception('User data can not be fetched')

    data = query.data

    if not data:
        raise Exception('Data can not be fetched')

    if data == 'posts_channels_next_page':
        channels_page = context.user_data.get('posts_channels_page', 0)
        context.user_data['posts_channels_page'] = channels_page + 1
        return await posts(update, context)

    if data == 'posts_channels_prev_page':
        channels_page = context.user_data.get('posts_channels_page', 0)
        context.user_data['posts_channels_page'] = channels_page - 1
        return await posts(update, context)

    if data == 'posts_channels_all':
        logger.info(f'User {user.id} selected all channels')

        # Получаем только доступные пользователю каналы
        accessible_channels = [
            channel.channel_id for channel in get_user_channels(user.id)
        ]
        
        # Сохраняем только доступные каналы
        selected_channels = accessible_channels

        context.user_data['posts_selected_channels'] = selected_channels

        return await posts(update, context)


    if data == 'posts_channels_clear':
        logger.info(f'User {user.id} cleared selected channels')

        context.user_data['posts_selected_channels'] = []

        return await posts(update, context)

    if data.startswith('posts_channels_toggle_'):
        channel_id = int(data.split('_')[3])
        selected_channels: list[int] = context.user_data.get('posts_selected_channels', [])

        is_checked = channel_id in selected_channels

        if not is_checked:
            logger.info(f'User {user.id} selected channel {channel_id}')
            selected_channels.append(channel_id)
        else:
            logger.info(f'User {user.id} unselected channel {channel_id}')
            selected_channels.remove(channel_id)

        context.user_data['posts_selected_channels'] = selected_channels

        return await posts(update, context)

    if data == 'posts_download':
        logger.info(f'User {user.id} requested to download posts')

        selected_channels = context.user_data.get('posts_selected_channels', [])

        text = ''

        msg = await context.bot.send_message(
            chat_id=user.id, text=f'Скачиваю посты [0/{len(selected_channels)}]'
        )

        for idx, channel_id in enumerate(selected_channels, start=1):
            channel_posts = get_posts(channel_id)
            await msg.edit_text(f'Скачиваю посты [{idx}/{len(selected_channels)}]')

            for post in channel_posts:
                channel = await context.bot.get_chat(channel_id)
                invite_link = channel.invite_link or ''
                link = f'https://t.me/{invite_link.split('/')[-1]}'

                text += f'{post.channel_name} [{link}]\n- Отправлен: {post.created_at.date()}\n- Текст поста: {post.post_text}\n\n'

        file_like_object = BytesIO(text.encode('utf-8'))
        file_like_object.name = 'posts.txt'

        await msg.delete()
        return await context.bot.send_document(chat_id=user.id, document=file_like_object)


handler = CommandHandler('posts', posts)
command = (BotCommand('posts', 'Список отправленных постов'), handler)
