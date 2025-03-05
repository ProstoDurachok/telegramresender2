import asyncio
from datetime import datetime
from io import BytesIO
from logging import getLogger
from time import time
from typing import Any

from telegram import (
    InputMedia,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    MessageOriginChannel,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from database import get_channel, save_post

logger = getLogger(__name__)


async def get_user_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        raise Exception('User can not be fetched')

    return user


async def get_message_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message:
        raise Exception('Message can not be fetched')

    return message


async def get_callback_query_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_query = update.callback_query

    if not callback_query:
        raise Exception('Callback query can not be fetched')

    return callback_query


async def get_user_data_context(
    update: Update, context: ContextTypes.DEFAULT_TYPE, default: dict[Any, Any] | None = None
) -> dict[Any, Any]:
    if not context.user_data:
        if not default:
            return {}

        context.user_data = default

    return context.user_data


async def check_for_media(
    context: ContextTypes.DEFAULT_TYPE,
    message: Message,
    user_data: dict,
    media_group_id: str,
    user: User,
    will_send_at: datetime | None = None,
):
    media_group_ids = user_data.get('media_group_ids', {})
    media_group_data = media_group_ids.get(media_group_id, {})
    sent = {}

    logger.info('Checking for media')

    if not media_group_data:
        raise Exception('Media group data not found')

    while media_group_data.get('last_time_sended') + 3 > time():
        await asyncio.sleep(1)

    channels = media_group_data['channels']
    medias = media_group_data['media']
    caption = media_group_data['caption']

    if isinstance(will_send_at, datetime):
        delta = (will_send_at - datetime.now()).total_seconds()

        if delta > 0:
            await asyncio.sleep(delta)

    for channel_id in channels:
        assert isinstance(channel_id, int)

        final_media_group = []

        for media in medias:
            if str(media.media) not in [str(media.media) for media in final_media_group]:
                final_media_group.append(media)

        sent_messages = await context.bot.send_media_group(
            chat_id=channel_id,
            media=final_media_group,
        )

        channel = await context.bot.get_chat(channel_id)
        invite_link = channel.invite_link or ''
        link = f'https://t.me/{invite_link.split('/')[-1]}'
        footer = f'\n\nПодписывайтесь на канал - [{channel.title}]({link})'

        msg = await sent_messages[0].edit_caption(caption + footer, parse_mode=ParseMode.MARKDOWN)
        sent[channel_id] = {
            'channel_name': channel.full_name,
            'channel_link': channel.link,
            'message_link': msg.link,
        }

    del media_group_ids[media_group_id]

    await message.reply_text('Медиа успешно отправлено.')
    text = ''

    for k, v in sent.items():
        text += f'{v["channel_name"]} - {v["message_link"]}\n'
        save_post(k, v['channel_name'], message.message_id, caption, user.id)

    file_like_object = BytesIO(text.encode('utf-8'))
    file_like_object.name = 'posts.txt'
    await message.reply_document(document=file_like_object)


async def send_messages_to_channels(
    update: Update,
    selected_channels: list[int],
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    message: Message,
    will_send_at: datetime | None = None,
):
    user_data = await get_user_data_context(update, context)

    if not selected_channels:
        user_data['is_sending'] = False
        user_data['group_is_sending'] = False
        return await message.reply_text('Вы не выбрали каналы для отправки.')

    if will_send_at:
        user_data['will_send_at'] = will_send_at

    logger.info(f'User {user.id} is sending a message to {len(selected_channels)} channels.')
    is_group_media = False
    sent = {}

    for channel_id in selected_channels:
        channel = get_channel(channel_id)

        if not channel:
            raise Exception('Channel not found')

        chat_link = (
            channel.channel_link or (await context.bot.get_chat(channel.id)).invite_link or ''
        )
        link = f'https://t.me/{chat_link.split('/')[-1]}'

        header = f'📣 Переслано из канала - [{channel.channel_name}]({link})\n\n'
        footer = f'\n\nПодписывайтесь на канал - [{channel.channel_name}]({link})'

        try:
            if isinstance(message.forward_origin, MessageOriginChannel):
                chat = message.forward_origin.chat

                try:
                    if message.media_group_id:
                        is_group_media = True
                        media_group: list[InputMedia] = []

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

                        chat_link = (
                            chat.link or (await context.bot.get_chat(chat.id)).invite_link or ''
                        )
                        link = f'https://t.me/{chat_link.split('/')[-1]}'
                        header = f'📣 Переслано из канала - [{chat.title}]({link})\n\n'
                        caption = message.caption or ''

                        media_group_ids = user_data.get(
                            'media_group_ids',
                            {
                                message.media_group_id: {
                                    'channels': [],
                                    'media': [],
                                    'caption': header + caption,
                                    'last_time_sended': time(),
                                }
                            },
                        )

                        media_group_data = media_group_ids.get(
                            message.media_group_id,
                            {
                                'channels': [],
                                'media': [],
                                'caption': header + caption,
                                'last_time_sended': time(),
                            },
                        )

                        media_group_data['channels'].append(channel_id)
                        media_group_data['media'] += media_group
                        media_group_data['last_time_sended'] = time()

                        media_group_ids[message.media_group_id] = media_group_data
                        user_data['media_group_ids'] = media_group_ids

                        if len(media_group_data['channels']) == 1:
                            asyncio.create_task(
                                check_for_media(
                                    context, user_data, message.media_group_id, will_send_at, user
                                )
                            )

                        continue

                    else:
                        msg = await message.forward(channel_id)
                        logger.info(f'Message is forwarded to channel {channel_id}')
                        sent[channel_id] = {
                            'channel_name': channel.channel_name,
                            'channel_link': channel.channel_link,
                            'message_link': msg.link,
                            'message_text': message.caption or message.text,
                        }
                        continue

                except TelegramError:
                    pass

                header = f'📣 Переслано из канала - [{chat.title}]({chat.link})\n\n'
            else:
                header = ''

            if message.text:
                sent_message_id = (
                    await message.copy(chat_id=channel_id, parse_mode=ParseMode.MARKDOWN)
                ).message_id

                logger.info(f'Message with text is sending to channel {channel_id}')
                msg = await context.bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=sent_message_id,
                    text=header + message.text + footer,
                    parse_mode=ParseMode.MARKDOWN,
                )
                sent[channel_id] = {
                    'channel_name': channel.channel_name,
                    'channel_link': channel.channel_link,
                    'message_link': msg.link,
                }
                continue

            elif message.media_group_id:
                is_group_media = True
                logger.info(f'Message with media will be sended to channel {channel_id}')

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

                caption = message.caption or ''

                media_group_ids = user_data.get(
                    'media_group_ids',
                    {
                        message.media_group_id: {
                            'channels': [],
                            'media': [],
                            'caption': header + caption,
                            'last_time_sended': time(),
                        }
                    },
                )

                media_group_data = media_group_ids.get(
                    message.media_group_id,
                    {
                        'channels': [],
                        'media': [],
                        'caption': header + caption,
                        'last_time_sended': time(),
                    },
                )

                media_group_data['channels'].append(channel_id)
                media_group_data['media'] += media_group
                media_group_data['last_time_sended'] = time()

                media_group_ids[message.media_group_id] = media_group_data
                user_data['media_group_ids'] = media_group_ids

                if len(media_group_data['channels']) == 1:
                    asyncio.create_task(
                        check_for_media(
                            context, user_data, message.media_group_id, will_send_at, user
                        )
                    )

                continue

            elif message.photo:
                sent_message_id = (
                    await message.copy(chat_id=channel_id, parse_mode=ParseMode.MARKDOWN)
                ).message_id

                caption = message.caption or ''

                logger.info(f'Message with photo is sending to channel {channel_id}')
                msg = await context.bot.edit_message_caption(
                    chat_id=channel_id,
                    message_id=sent_message_id,
                    caption=header + caption + footer,
                    parse_mode=ParseMode.MARKDOWN,
                )
                sent[channel_id] = {
                    'channel_name': channel.channel_name,
                    'channel_link': channel.channel_link,
                    'message_link': msg.link,
                    'message_text': caption,
                }

            elif message.video or message.document or message.audio or message.voice:
                sent_message_id = (
                    await message.copy(chat_id=channel_id, parse_mode=ParseMode.MARKDOWN)
                ).message_id

                caption = message.caption or ''

                logger.info(f'Message with video is sending to channel {channel_id}')
                msg = await context.bot.edit_message_caption(
                    chat_id=channel_id,
                    message_id=sent_message_id,
                    caption=header + caption + footer,
                    parse_mode=ParseMode.MARKDOWN,
                )
                sent[channel_id] = {
                    'channel_name': channel.channel_name,
                    'channel_link': channel.channel_link,
                    'message_link': msg.link,
                    'message_text': caption,
                }

            elif message.caption:
                if not message.media_group_id:
                    sent_message_id = (
                        await message.copy(chat_id=channel_id, parse_mode=ParseMode.MARKDOWN)
                    ).message_id

                    logger.info(f'Message with caption is sending to channel {channel_id}')
                    msg = await context.bot.edit_message_caption(
                        chat_id=channel_id,
                        message_id=sent_message_id,
                        caption=header + message.caption + footer,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    sent[channel_id] = {
                        'channel_name': channel.channel_name,
                        'channel_link': channel.channel_link,
                        'message_link': msg.link,
                        'message_text': caption,
                    }
                    continue

        except Exception as e:
            logger.error(f'Failed to send message to channel {channel_id}: {e}')
            await message.reply_text(
                f'Не удалось отправить сообщение в канал {channel.channel_name}.'
            )

    user_data['is_sending'] = False
    user_data['group_is_sending'] = False

    logger.info(f'Message is sent to {len(selected_channels)} channels')
    await message.reply_text('Сообщение успешно отправлено в выбранные каналы.')

    user_data['selected_channels'] = []
    user_data['selected_group_channels'] = []

    if not is_group_media:
        text = ''

        for k, v in sent.items():
            text += f'{v["channel_name"]} - {v["message_link"]}\n'
            save_post(
                k, v['channel_name'], message.message_id, message.caption or message.text, user.id
            )

        file_like_object = BytesIO(text.encode('utf-8'))
        file_like_object.name = 'posts.txt'
        await message.reply_document(document=file_like_object)
