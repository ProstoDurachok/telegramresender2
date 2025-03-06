from io import BytesIO
from itertools import zip_longest
from logging import getLogger

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Update,
)
from telegram.ext import CommandHandler, ContextTypes

from database import (
    get_channel,
    get_channels,
    get_channels_by_group,
    get_groups,
    get_total_channels,
    get_total_channels_for_group,
    get_total_groups,
    get_user,
    group_add_channels,
    group_delete,
    group_delete_channels,
    new_group_channel_save,
    new_group_name,
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


def chunk_button(buttons, row_size):
    return [list(filter(None, row)) for row in zip_longest(*[iter(buttons)] * row_size)]


async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    message = await get_message_context(update, context)
    user_data = context.user_data

    if not user_data:
        user_data = {'groups_page': 0}

    user = get_user(sender.id)

    if not user or not user.role or user.role == 'user':
        return await message.reply_text('У вас нет доступа к данному боту. Для доступа обратитесь к @Prosto_Durachok')

    page = user_data.get('groups_page', 0)

    if page < 0:
        page = 0

    logger.info(f'User {sender.id} requested groups [Page: {page + 1}]')

    db_groups_count = get_total_groups()
    db_groups = get_groups(limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    keyboard = []
    navigation_buttons = []

    for group in db_groups:
        group_button = InlineKeyboardButton(
            f'{group.group_name}',
            callback_data=f'groups_select_{group.id}',
        )
        keyboard.append(
            [
                group_button,
            ]
        )

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='groups_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < db_groups_count:
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='groups_next_page')
        )

    keyboard.append(navigation_buttons)

    if user.role == 'admin':
        keyboard.append(
            [
                InlineKeyboardButton('➕ Создать Группу', callback_data='groups_add'),
            ]
        )

    await message.reply_text(
        f'Выберите группу. Всего групп: {db_groups_count}',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def group_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = context.user_data
    callback_data = await get_callback_query_context(update, context)
    user_role = get_user(user.id).role

    if not user_data:
        user_data = {
            'group_channels_page': 0,
            'selected_group_channels': [],
            'selected_group_channels_add': [],
        }

    group_id = user_data.get('selected_group_id', 0)
    selected_group_channels = user_data.get('selected_group_channels', [])
    page = int(user_data.get('group_channels_page', 0))

    if page < 0:
        page = 0

    logger.info(f'User {user.id} requested channels of group: {group_id} [Page: {page + 1}]')

    db_channels = get_channels_by_group(
        group_id, limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE
    )
    db_channels_length = len(db_channels)

    if not db_channels:
        return await callback_data.answer('Нет каналов в этой группе.')

    keyboard = []
    navigation_buttons = []

    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in selected_group_channels else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'group_channels_toggle_{channel.channel_id}',
        )
        link_button = InlineKeyboardButton('🔗 Перейти', url=f'{channel.channel_link}')
        keyboard.append([channel_button, link_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='group_channels_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < get_total_channels_for_group(group_id):
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='group_channels_next_page')
        )

    if len(selected_group_channels) != get_total_channels_for_group(group_id):
        navigation_buttons.append(
            InlineKeyboardButton('✅ Выбрать все каналы', callback_data='group_select_all')
        )

    else:
        navigation_buttons.append(
            InlineKeyboardButton('❌ Отменить выбор', callback_data='group_channels_clear')
        )

    if len(selected_group_channels) > 0:
        navigation_buttons.append(
            InlineKeyboardButton('📨 Отправить', callback_data='group_send_message')
        )
        navigation_buttons.append(
            InlineKeyboardButton(
                '⬇️ Скачать список каналов', callback_data='group_channels_download'
            )
        )

    keyboard.append(navigation_buttons)

    buttons = [
        InlineKeyboardButton('🏠 Главное меню', callback_data='group_menu_button'),
    ]

    if user_role == 'admin':
        buttons.append(
            InlineKeyboardButton('⚙️ Настройки группы', callback_data='group_settings'),
        )

    keyboard += chunk_button(buttons, 2)

    await callback_data.edit_message_text(
        text=f'Каналов в группе: {db_channels_length}',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def group_send_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = await get_user_data_context(update, context)
    query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    selected_group_channels = user_data.get('selected_group_channels', [])

    if not selected_group_channels:
        raise Exception('Selected channels can not be fetched')

    logger.info(
        f'User {user.id} getting ready to send message to {len(selected_group_channels)} channels'
    )

    context.user_data['group_is_sending'] = True

    await query.edit_message_text('Отправьте ваше сообщение')
    return await query.answer()


async def group_change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    context.user_data['group_change_name'] = True

    logger.info(f'User {user.id} requested to change group name')

    await query.edit_message_text('Введите новое название группы')
    return await query.answer()


async def group_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = context.user_data
    callback_data = await get_callback_query_context(update, context)

    if not user_data:
        user_data = {
            'group_channels_page': 0,
            'group_add_channels': [],
            'selected_group_channels_add': [],
        }

    group_add_channels = user_data.get('group_add_channels', [])
    page = int(user_data.get('group_channels_page', 0))

    if page < 0:
        page = 0

    logger.info(f'User {user.id} requested channels to add to group [Page: {page+1}]')

    db_channels = get_channels(limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    if not db_channels:
        return await callback_data.answer('Нет каналов.')

    keyboard = []
    navigation_buttons = []

    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in group_add_channels else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'group_add_toggle_{channel.channel_id}',
        )
        link_button = InlineKeyboardButton('🔗 Перейти', url=f'{channel.channel_link}')
        keyboard.append([channel_button, link_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='new_group_channels_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < len(get_channels(-1)):
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='new_group_channels_next_page')
        )

    if len(group_add_channels) != len(get_channels(-1)):
        navigation_buttons.append(
            InlineKeyboardButton('✅ Выбрать все каналы', callback_data='new_group_select_all')
        )

    else:
        navigation_buttons.append(
            InlineKeyboardButton('❌ Отменить выбор', callback_data='new_group_channels_clear')
        )

    keyboard.append(navigation_buttons)
    buttons = [
        InlineKeyboardButton('Создать группу', callback_data='new_group_save'),
        InlineKeyboardButton('🏠 Главное меню', callback_data='group_menu_button'),
    ]

    keyboard += chunk_button(buttons, 2)
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await callback_data.edit_message_text(
            'Выберите каналы для новой группы',
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f'Failed to edit message: {e}')
        return await callback_data.answer('Не удалось обновить сообщение.')


async def group_add_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = context.user_data
    callback_data = await get_callback_query_context(update, context)

    if not user_data:
        user_data = {
            'group_channels_page': 0,
            'group_add_channels': [],
        }

    group_id = user_data.get('selected_group_id', 0)
    group_add_channels = user_data.get('group_add_channels', [])
    page = int(user_data.get('group_channels_page', 0))

    if page < 0:
        page = 0

    logger.info(f'User {user.id} requested channels to add of group: {group_id} [Page: {page+1}]')

    db_channels = get_channels(limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    if not db_channels:
        return await callback_data.answer('Нет каналов.')

    keyboard = []
    navigation_buttons = []

    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in group_add_channels else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'group_add_toggle_{channel.channel_id}',
        )
        link_button = InlineKeyboardButton('🔗 Перейти', url=f'https://t.me/{channel.channel_link}')
        keyboard.append([channel_button, link_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='group_channels_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < get_total_channels_for_group(group_id):
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='group_channels_next_page')
        )

    keyboard.append(navigation_buttons)
    buttons = [
        InlineKeyboardButton('Создать группу', callback_data='new_group_save'),
        InlineKeyboardButton('🏠 Главное меню', callback_data='group_menu_button'),
    ]

    keyboard += chunk_button(buttons, 2)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await callback_data.edit_message_text(
        f'Выберите каналы для новой группы {group_id}:',
        reply_markup=reply_markup,
    )
    return await callback_data.answer()


async def new_group_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = context.user_data
    callback_query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    if not user_data:
        user_data = {
            'group_add_channels': [],
        }

    logger.info(f'User {user.id} requested to create new group')

    group_name = user_data.get('group_name')

    if not group_name:
        context.user_data['is_waiting_group_name'] = True
        return await user.send_message('Пожалуйста, введите название группы:')

    if not isinstance(group_name, str) or not group_name:
        return await callback_query.answer('Название группы не указано или некорректно.')


async def group_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    user_data = context.user_data
    callback_data = await get_callback_query_context(update, context)

    if not user_data:
        user_data = {'groups_page': 0}

    page = user_data.get('groups_page', 0)

    logger.info(f'User {sender.id} requested groups [Page: {page + 1}]')

    if page < 0:
        page = 0

    db_groups_count = get_total_groups()
    db_groups = get_groups(limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    keyboard = []
    navigation_buttons = []

    for group in db_groups:
        group_button = InlineKeyboardButton(
            f'{group.group_name}',
            callback_data=f'groups_select_{group.id}',
        )
        keyboard.append(
            [
                group_button,
            ]
        )

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton('⬅️ Предыдущая', callback_data='groups_prev_page')
        )

    if (page + 1) * CHANNELS_PER_PAGE < db_groups_count:
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='groups_next_page')
        )

    keyboard.append(navigation_buttons)
    keyboard.append(
        [
            InlineKeyboardButton('➕ Создать Группу', callback_data='groups_add'),
        ]
    )

    return await callback_data.edit_message_text(
        f'Выберите группу. Всего групп: {db_groups_count}',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def group_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    user_data = context.user_data
    callback_data = await get_callback_query_context(update, context)

    if not user_data:
        user_data = {'group_channels_page': 0, 'selected_group_channels': []}

    group_id = user_data.get('selected_group_id', 0)

    logger.info(f'User {user.id} requested settings of group: {group_id}')

    buttons = [
        InlineKeyboardButton('Добавить каналы', callback_data='group_channel_add'),
        InlineKeyboardButton('Удалить каналы', callback_data='group_channel_delete'),
        InlineKeyboardButton('Изменить название группы', callback_data='group_change_name'),
        InlineKeyboardButton('Удалить группу', callback_data='group_delete'),
        InlineKeyboardButton('Назад к каналам', callback_data='group_back_button'),
    ]

    keyboard = chunk_button(buttons, 2)

    return await callback_data.edit_message_text(
        text=f'Настройки группы {group_id}:',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def group_channels_add_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = await get_user_context(update, context)
    user_data = context.user_data
    callback_query = update.callback_query

    if not user_data:
        user_data = {'channels_page': 0, 'selected_group_channels_add': []}

    group_id = user_data.get('selected_group_id', 0)

    selected_group_channels_add = user_data.get('selected_group_channels_add', [])

    page = user_data.get('channels_page', 0)

    if page < 0:
        page = 0

    db_channels_count = get_total_channels()
    db_channels = get_channels(limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE)

    keyboard = []
    navigation_buttons = []

    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in selected_group_channels_add else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'group_channels_add_toggle_{channel.channel_id}',
        )
        keyboard.append([channel_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                '⬅️ Предыдущая', callback_data='group_channels_add_toggle_prev_page'
            )
        )

    if (page + 1) * CHANNELS_PER_PAGE < db_channels_count:
        navigation_buttons.append(
            InlineKeyboardButton('Следующая ➡️', callback_data='group_channels_add_toggle_next_page')
        )

    buttons = [InlineKeyboardButton('Добавить канал', callback_data='group_channels_add_toggle')]

    keyboard.append(navigation_buttons)
    keyboard += chunk_button(buttons, 2)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if callback_query:
        logger.info(f'User {sender.id} requested channels (page: {page + 1})')

        await callback_query.edit_message_text(
            f'Добавляем каналы в группу - {group_id}',
            reply_markup=reply_markup,
        )
        await callback_query.answer()


async def group_channels_delete_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    user_data = context.user_data
    callback_query = update.callback_query

    if not sender:
        raise Exception('User can not be fetched')

    if not user_data:
        user_data = {'channels_page': 0, 'selected_group_channels_add': []}

    group_id = user_data.get('selected_group_id', 0)

    selected_group_channels_add = user_data.get('selected_group_channels_add', [])

    page = user_data.get('channels_page', 0)

    db_channels_count = get_total_channels()
    db_channels = get_channels_by_group(
        group_id=group_id, limit=CHANNELS_PER_PAGE, offset=page * CHANNELS_PER_PAGE
    )

    keyboard = []
    navigation_buttons = []

    for channel in db_channels:
        checkmark = '✅' if channel.channel_id in selected_group_channels_add else '❌'
        channel_button = InlineKeyboardButton(
            f'{checkmark} {channel.channel_name}',
            callback_data=f'group_channels_delete_toggle_{channel.channel_id}',
        )
        keyboard.append([channel_button])

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                '⬅️ Предыдущая', callback_data='group_channels_delete_toggle_prev_page'
            )
        )

    if (page + 1) * CHANNELS_PER_PAGE < db_channels_count:
        navigation_buttons.append(
            InlineKeyboardButton(
                'Следующая ➡️', callback_data='group_channels_delete_toggle_next_page'
            )
        )

    buttons = [InlineKeyboardButton('Удалить канал', callback_data='group_channels_delete_toggle')]

    keyboard.append(navigation_buttons)
    keyboard += chunk_button(buttons, 2)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if callback_query:
        logger.info(f'User {sender.id} requested channels (page: {page + 1})')

        await callback_query.edit_message_text(
            f'Удаляем каналы из группы - {group_id}',
            reply_markup=reply_markup,
        )
        await callback_query.answer()


async def group_channels_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    callback_query = update.callback_query

    if not user:
        raise Exception('User can not be fetched')

    if not context.user_data or not user_data:
        raise Exception('User data can not be fetched')

    group_id = user_data.get('selected_group_id', 0)
    selected_group_channels_add = user_data.get('selected_group_channels_add', [])

    if not callback_query:
        raise Exception('Callback query can not be fetched')

    if not selected_group_channels_add:
        return await callback_query.answer('Не выбраны каналы для добавления.')

    for channel_id in selected_group_channels_add:
        try:
            group_add_channels(group_id, channel_id)
        except Exception as e:
            logger.error(f'Error while adding channel {channel_id} to group {group_id}: {e}')
            return await callback_query.answer(f'Ошибка при добавлении канала {channel_id}')

    del context.user_data['selected_group_channels_add']
    await callback_query.answer(f'Каналы успешно добавлены в группу {group_id}.')
    return await group_channels(update, context)


async def group_channels_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    callback_query = update.callback_query

    if not user:
        raise Exception('User can not be fetched')

    if not context.user_data or not user_data:
        raise Exception('User data can not be fetched')

    group_id = user_data.get('selected_group_id', 0)
    selected_group_channels_add = user_data.get('selected_group_channels_add', [])

    if not callback_query:
        raise Exception('Callback query can not be fetched')

    if not selected_group_channels_add:
        return await callback_query.answer('Не выбраны каналы для добавления.')

    for channel_id in selected_group_channels_add:
        try:
            group_delete_channels(group_id, channel_id)
        except Exception as e:
            logger.error(f'Error while adding channel {channel_id} to group {group_id}: {e}')
            return await callback_query.answer(f'Ошибка при удалении канала {channel_id}')

    del context.user_data['selected_group_channels_add']
    await callback_query.answer('Каналы успешно удалены.')
    return await group_channels(update, context)


async def group_channels_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_context(update, context)
    query = await get_callback_query_context(update, context)

    if not context.user_data:
        raise Exception('User data can not be fetched')

    selected_channels = context.user_data.get('selected_group_channels', [])

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


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    query = update.callback_query

    if not user:
        raise Exception('User can not be fetched')

    if not user_data:
        user_data = {}

    if not query:
        raise Exception('Query can not be fetched')

    if not isinstance(context.user_data, dict):
        raise Exception('User data can not be fetched')

    data = query.data

    if not data:
        raise Exception('Data can not be fetched')

    if data.startswith('groups_select_'):
        selected_group_id = int(data.split('_')[2])
        context.user_data['selected_group_id'] = selected_group_id

        return await group_channels(update, context)

    elif data.startswith('group_settings'):
        return await group_settings(update, context)

    elif data.startswith('group_menu_button'):
        return await group_menu_button(update, context)

    elif data.startswith('group_back_button'):
        return await group_channels(update, context)

    elif data == ('group_channels_add_toggle'):
        return await group_channels_add(update, context)

    elif data == 'group_channels_delete_toggle':
        return await group_channels_delete(update, context)

    elif data.startswith('group_channel_add'):
        return await group_channels_add_toggle(update, context)

    elif data == 'group_channel_delete':
        return await group_channels_delete_toggle(update, context)

    elif data == 'group_channels_download':
        return await group_channels_download(update, context)

    elif data == 'group_channels_add_toggle_next_page':
        channels_page = context.user_data.get('channels_page', 0)
        context.user_data['channels_page'] = channels_page + 1

        return await group_channels_add_toggle(update, context)

    elif data == 'group_channels_add_toggle_prev_page':
        channels_page = context.user_data.get('channels_page', 0)
        context.user_data['channels_page'] = channels_page - 1

        return await group_channels_add_toggle(update, context)

    elif data == 'group_channels_delete_toggle_next_page':
        channels_page = context.user_data.get('channels_page', 0)
        context.user_data['channels_page'] = channels_page + 1

        return await group_channels_delete_toggle(update, context)

    elif data == 'group_channels_delete_toggle_prev_page':
        channels_page = context.user_data.get('channels_page', 0)
        context.user_data['channels_page'] = channels_page - 1

        return await group_channels_delete_toggle(update, context)

    elif data == 'group_channels_next_page':
        group_channels_page = context.user_data.get('group_channels_page', 0)
        context.user_data['group_channels_page'] = group_channels_page + 1
        return await group_channels(update, context)

    elif data == 'group_channels_prev_page':
        group_channels_page = context.user_data.get('group_channels_page', 0)
        context.user_data['group_channels_page'] = group_channels_page - 1

        return await group_channels(update, context)

    elif data == 'new_group_channels_next_page':
        group_channels_page = context.user_data.get('group_channels_page', 0)
        context.user_data['group_channels_page'] = group_channels_page + 1
        return await group_add(update, context)

    elif data == 'new_group_channels_prev_page':
        group_channels_page = context.user_data.get('group_channels_page', 0)
        context.user_data['group_channels_page'] = group_channels_page - 1
        return await group_add(update, context)

    elif data.startswith('groups_add'):
        return await group_add(update, context)

    elif data.startswith('group_add_toggle_'):
        channel_id = int(data.split('_')[3])
        group_add_channels: list = context.user_data.get('group_add_channels', [])

        is_checked = channel_id in group_add_channels

        if not is_checked:
            logger.info(f'User {user.id} selected channel {channel_id}')
            group_add_channels.append(channel_id)
        else:
            logger.info(f'User {user.id} unselected channel {channel_id}')
            group_add_channels.remove(channel_id)

        context.user_data['group_add_channels'] = group_add_channels

        return await group_add(update, context)

    elif data.startswith('new_group_save'):
        return await new_group_save(update, context)

    elif data == 'group_select_all':
        user = update.effective_user
        user_data = context.user_data

        if not user_data:
            user_data = {
                'group_channels_page': 0,
                'selected_group_channels': [],
            }

        group_id = user_data.get('selected_group_id', 0)
        selected_channels = []

        for channel in get_channels_by_group(group_id, -1):
            selected_channels.append(channel.channel_id)

        context.user_data['selected_group_channels'] = selected_channels

        return await group_channels(update, context)

    elif data == 'new_group_select_all':
        user = update.effective_user
        user_data = context.user_data

        if not user_data:
            user_data = {
                'group_add_channels': [],
            }

        group_id = user_data.get('selected_group_id', 0)
        selected_channels = []

        for channel in get_channels(-1):
            selected_channels.append(channel.channel_id)

        context.user_data['group_add_channels'] = selected_channels

        return await group_add(update, context)

    elif data == 'group_channels_clear':
        user = update.effective_user
        user_data = context.user_data

        if not user_data:
            user_data = {
                'selected_group_channels': [],
            }

        context.user_data['selected_group_channels'] = []

        return await group_channels(update, context)

    elif data == 'new_group_channels_clear':
        user = update.effective_user
        user_data = context.user_data

        if not user_data:
            user_data = {
                'group_add_channels': [],
            }

        context.user_data['group_add_channels'] = []

        return await group_add(update, context)

    elif data.startswith('group_channels_add_toggle_'):
        channel_id = int(data.split('_')[4])
        selected_group_channels_add: list = context.user_data.get('selected_group_channels_add', [])

        is_checked = channel_id in selected_group_channels_add

        if not is_checked:
            logger.info(f'User {user.id} selected channel {channel_id}')
            selected_group_channels_add.append(channel_id)
        else:
            logger.info(f'User {user.id} unselected channel {channel_id}')
            selected_group_channels_add.remove(channel_id)

        context.user_data['selected_group_channels_add'] = selected_group_channels_add

        return await group_channels_add_toggle(update, context)

    elif data.startswith('group_channels_delete_toggle_'):
        channel_id = int(data.split('_')[4])
        selected_group_channels_add: list = context.user_data.get('selected_group_channels_add', [])

        is_checked = channel_id in selected_group_channels_add

        if not is_checked:
            logger.info(f'User {user.id} selected channel {channel_id}')
            selected_group_channels_add.append(channel_id)
        else:
            logger.info(f'User {user.id} unselected channel {channel_id}')
            selected_group_channels_add.remove(channel_id)

        context.user_data['selected_group_channels_add'] = selected_group_channels_add

        return await group_channels_delete_toggle(update, context)

    elif data.startswith('group_channels_toggle_'):
        channel_id = int(data.split('_')[3])
        selected_group_channels: list = context.user_data.get('selected_group_channels', [])

        is_checked = channel_id in selected_group_channels

        if not is_checked:
            logger.info(f'User {user.id} selected channel {channel_id}')
            selected_group_channels.append(channel_id)
        else:
            logger.info(f'User {user.id} unselected channel {channel_id}')
            selected_group_channels.remove(channel_id)

        context.user_data['selected_group_channels'] = selected_group_channels

        return await group_channels(update, context)

    elif data == 'group_delete':
        user = update.effective_user
        user_data = context.user_data

        if not user or not context.user_data:
            return

        if not user_data:
            user_data = {
                'selected_group_id': 0,
            }

        group_id = user_data.get('selected_group_id', 0)

        try:
            group_delete(group_id)
        except Exception as e:
            logger.error(f'Error while deleting group: {e}')

        return await group_menu_button(update, context)

    elif data == 'group_send_message':
        return await group_send_message(update, context)

    elif data == 'group_change_name':
        return await group_change_name(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    message = update.message

    if not user or not message or not context.user_data:
        return

    if not user_data:
        raise Exception('User data can not be fetched')

    selected_group_id = user_data.get('selected_group_id', [])
    group_is_sending = user_data.get('group_is_sending', False)
    media_group_ids = user_data.get('media_group_ids', {})
    group_change_name = user_data.get('group_change_name', False)

    if group_change_name:
        if not message.text:
            raise Exception('Message text can not be fetched')

        if not selected_group_id:
            return

        group_name = message.text.strip()

        try:
            new_group_name(selected_group_id, group_name, user.id)  # type: ignore
        except Exception as e:
            logger.error(f'Error while saving group and channels: {e}')
            return await message.reply_text(f'Ошибка при изменении имени группы: {e}')

        del context.user_data['group_change_name']
        return await message.reply_text(f'Группа - "{group_name}" успешно сохранена.')

    if group_is_sending:
        selected_group_channels = user_data.get('selected_group_channels', [])

        return await send_messages_to_channels(
            update, selected_group_channels, context, user, message
        )

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

    if user_data.get('is_waiting_group_name', False):
        if not message.text:
            raise Exception('Message text can not be fetched')

        group_name = message.text.strip()
        group_add_channels = user_data.get('group_add_channels', [])

        try:
            new_group_channel_save(user.id, group_name, group_add_channels)
        except Exception as e:
            logger.error(f'Error while saving group and channels: {e}')
            return await message.reply_text(f'Ошибка при сохранении группы: {e}')

        del context.user_data['group_add_channels']

        await message.reply_text(f'Группа - "{group_name}" успешно сохранена.')
        return


handler = CommandHandler('groups', groups)
command = (BotCommand('groups', 'Список групп'), handler)

button_callbacks = [
    button_callback,
]
message_handlers = [
    handle_message,
]
