import contextlib
from io import BytesIO
from logging import getLogger

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    MessageOriginChannel,
    Update,
)
from telegram.ext import CommandHandler, ContextTypes

from database import (
    delete_channel,
    get_channel,
    get_channels,
    get_total_channels,
    get_user,
    save_channel,
)
from utils.functions import (
    get_callback_query_context,
    get_message_context,
    get_user_context,
    get_user_data_context,
    send_messages_to_channels,
)

logger = getLogger(__name__)

CHANNELS_PER_PAGE = 20


async def channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = update.message
    query = update.callback_query
    user_data = await get_user_data_context(update, context)

    user = get_user(sender.id)
    selected_channels = user_data.get('selected_channels', [])

    if not user or not user.role or user.role == 'user':
        if message:
            return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')
        elif query:
            return await query.answer('У вас нет доступа к данному боту.', show_alert=True)

    page = user_data.get('channels_page', 0)
    if page < 0:
        page = 0

    logger.info(f'User {sender.id} requested channels [Page: {page+1}]')

    db_channels_count = get_total_channels()
    db_channels = get_channels(limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    keyboard = []
    navigation_buttons = []
    channels_buttons = []
    action_buttons = []

    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in selected_channels else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'channels_toggle_{channel.channel_id}',
        )
        link_button = InlineKeyboardButton('🔗 Перейти', url=f'{channel.channel_link}')
        keyboard.append([channel_button, link_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='channels_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < db_channels_count:
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='channels_next_page')
        )

    if user.role == 'admin':
        channels_buttons.append(
            InlineKeyboardButton('➕ Добавить канал', callback_data='channels_add')
        )
        channels_buttons.append(
            InlineKeyboardButton('🗑 Удалить канал', callback_data='channels_delete')
        )

    if len(selected_channels) != db_channels_count:
        action_buttons.append(
            InlineKeyboardButton('✅ Выбрать все каналы', callback_data='channels_all')
        )
    else:
        action_buttons.append(
            InlineKeyboardButton('❌ Отменить выбор', callback_data='channels_clear')
        )

    if len(selected_channels) > 0:
        action_buttons.append(InlineKeyboardButton('📨 Отправить', callback_data='channels_send'))
        action_buttons.append(
            InlineKeyboardButton('⬇️ Скачать список каналов', callback_data='channels_download')
        )

    keyboard.append(navigation_buttons)
    keyboard.append(channels_buttons)
    keyboard.append(action_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await message.reply_text(
            f'Выберите каналы для отправки: Всего каналов - {db_channels_count}',
            reply_markup=reply_markup,
        )

    elif query:
        await query.edit_message_text(
            f'Выберите каналы для отправки: Всего каналов - {db_channels_count}',
            reply_markup=reply_markup,
        )
        await query.answer()

    else:
        raise Exception('Either message or callback query can not be fetched')


async def channels_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = await get_user_data_context(update, context)
    query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    selected_channels = user_data.get('selected_channels', [])

    if not selected_channels:
        raise Exception('Selected channels can not be fetched')

    logger.info(
        f'User {user.id} getting ready to send message to {len(selected_channels)} channels'
    )

    context.user_data['is_sending'] = True

    await query.edit_message_text('Отправьте ваше сообщение')
    return await query.answer()


async def channels_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    selected_channels = context.user_data.get('selected_channels', [])

    if not selected_channels:
        raise Exception('Selected channels can not be fetched')

    logger.info(f'User {user.id} downloading {len(selected_channels)} channels')

    text = ''
    for idx, channel_id in enumerate(selected_channels, start=1):
        await query.edit_message_text(f'Обрабатываю каналы. [{idx}/{len(selected_channels)}]')

        channel = get_channel(channel_id)

        if not channel:
            raise Exception('Channel can not be fetched')

        link = (
            f'https://t.me/{channel.channel_link}'
            if not channel.channel_link.startswith('https://t.me/')
            else channel.channel_link
        )

        text += f'{channel.channel_name} - {link}\n'

    file_like_object = BytesIO(text.encode('utf-8'))
    file_like_object.name = 'document.txt'

    return await context.bot.send_document(chat_id=user.id, document=file_like_object)


async def channels_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = await get_callback_query_context(update, context)

    await query.edit_message_text('Перешлите сообщение из нужного канала')
    return await query.answer()


async def channels_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    channels_to_remove = context.user_data.get('selected_channels', [])

    for channel_id in channels_to_remove:
        delete_channel(channel_id)
        logger.info(f'User {user.id} deleted channel {channel_id}')

    with contextlib.suppress(Exception):
        del context.user_data['selected_channels']

    return await query.edit_message_text('Каналы успешно удалены')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = await get_user_data_context(update, context)

    if not user or not context.user_data:
        return

    try:
        message = await get_message_context(update, context)
    except Exception:
        return

    is_sending = user_data.get('is_sending', False)
    # is_waiting_for_date = user_data.get('is_waiting_for_date', None)
    is_adding_channel = user_data.get('is_adding_channel', False)
    media_group_ids = user_data.get('media_group_ids', {})

    if is_sending:
        # if is_waiting_for_date is None:
        #     await message.reply_text(
        #         'Отправьте время отправки в формате: ГГГГ-ММ-ДД ЧЧ:ММ. Если хотите отправить сейчас, напишите 0.'
        #     )
        #     context.user_data['is_waiting_for_date'] = True
        #     return

        # if message.text == '0':
        #     send_at = datetime.now()
        #     del context.user_data['is_waiting_for_date']

        # else:
        #     try:
        #         send_at = datetime.strptime(message.text, '%Y-%m-%d %H:%M')
        #     except Exception:
        #         return await message.reply_text(
        #             'Неверный формат даты. Пожалуйста, используйте формат ГГГГ-ММ-ДД ЧЧ:ММ'
        #         )
        #     else:
        #         del context.user_data['is_waiting_for_date']

        selected_channels = user_data.get('selected_channels', [])

        return await send_messages_to_channels(update, selected_channels, context, user, message)

    if is_adding_channel:
        origin = message.forward_origin

        if not isinstance(origin, MessageOriginChannel):
            return await message.reply_text('Перешлите сообщение из нужного канала')

        chat = origin.chat

        is_existing = get_channel(chat.id)

        if is_existing:
            context.user_data['is_adding_channel'] = False
            return await message.reply_text('Канал уже добавлен')

        try:
            member = await context.bot.get_chat_member(chat.id, context.bot.id)
        except Exception as e:
            logger.error(e)
            return await message.reply_text('Бот не является участником этого канала')

        if member.status != 'administrator' and member.status != 'creator':
            context.user_data['is_adding_channel'] = False
            return await message.reply_text('Бот не администратор или создатель канала')

        link = chat.link or (await context.bot.get_chat(chat.id)).invite_link

        if not chat.title or not link:
            raise Exception('Chat title or link can not be fetched')

        save_channel(user.id, chat.id, chat.title, link)

        context.user_data['is_adding_channel'] = False
        return await message.reply_text('Канал успешно добавлен')

    if message.media_group_id:
        media_group_id = message.media_group_id
        media_group_data = media_group_ids.get(media_group_id, {})

        if not media_group_data:
            return

        media_group = []

        if message.photo:
            media_group.append(InputMediaPhoto(media=message.photo[-1].file_id))

        if message.video:
            media_group.append(InputMediaVideo(media=message.video.file_id))

        if message.document:
            media_group.append(InputMediaDocument(media=message.document.file_id))

        if message.audio:
            media_group.append(InputMediaAudio(media=message.audio.file_id))

        if message.voice:
            media_group.append(InputMediaAudio(media=message.voice.file_id))

        media_group_data['media'] += media_group


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    query = await get_callback_query_context(update, context)

    if not isinstance(context.user_data, dict):
        raise Exception('User data can not be fetched')

    data = query.data

    if not data:
        raise Exception('Data can not be fetched')

    if data == 'channels_next_page':
        channels_page = context.user_data.get('channels_page', 0)
        context.user_data['channels_page'] = channels_page + 1
        return await channels(update, context)

    elif data == 'channels_prev_page':
        channels_page = context.user_data.get('channels_page', 0)
        context.user_data['channels_page'] = channels_page - 1
        return await channels(update, context)

    elif data == 'channels_all':
        logger.info(f'User {user.id} selected all channels')

        selected_channels = [channel.channel_id for channel in get_channels(-1)]
        context.user_data['selected_channels'] = selected_channels

        return await channels(update, context)

    elif data == 'channels_clear':
        logger.info(f'User {user.id} cleared selected channels')

        context.user_data['selected_channels'] = []

        return await channels(update, context)

    elif data == 'channels_add':
        logger.info(f'User {user.id} is adding a channel')
        context.user_data['is_adding_channel'] = True
        return await channels_add(update, context)

    elif data == 'channels_delete':
        logger.info(f'User {user.id} is deleting a channel')
        context.user_data['is_deleting_channel'] = True
        return await channels_delete(update, context)

    elif data == 'channels_send':
        return await channels_send(update, context)

    elif data == 'channels_download':
        return await channels_download(update, context)

    elif data.startswith('channels_toggle_'):
        channel_id = int(data.split('_')[2])
        selected_channels: list = context.user_data.get('selected_channels', [])

        is_checked = channel_id in selected_channels

        if not is_checked:
            logger.info(f'User {user.id} selected channel {channel_id}')
            selected_channels.append(channel_id)
        else:
            logger.info(f'User {user.id} unselected channel {channel_id}')
            selected_channels.remove(channel_id)

        context.user_data['selected_channels'] = selected_channels

        return await channels(update, context)


handler = CommandHandler('channels', channels)
command = (BotCommand('channels', 'Список каналов'), handler)

message_handlers = [
    handle_message,
]
