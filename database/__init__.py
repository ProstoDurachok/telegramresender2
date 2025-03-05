from datetime import datetime
from logging import getLogger
from typing import Literal

from psycopg import connect
from psycopg.errors import OperationalError, ProgrammingError
from pydantic import PositiveInt

from config.environment import settings
from database.schemas import ChannelModel, GroupModel, PostModel, UserModel

conninfo: dict[str, str | int] = {
    'dbname': settings.DB_NAME,
    'user': settings.DB_USER_NAME,
    'password': settings.DB_USER_PASSWORD,
    'host': settings.DB_HOST,
    'port': settings.DB_PORT,
}

logger = getLogger(__name__)


def execute(query: str, fetch: Literal['one', 'all'] = 'all', retries: int = 3):
    connection = connect(
        ' '.join([f'{key}={value}' for key, value in conninfo.items()]), autocommit=True
    )

    try:
        with connection.cursor() as cur:
            cur.execute(query)  # type: ignore

            try:
                if fetch == 'one':
                    return cur.fetchone()
                elif fetch == 'all':
                    return cur.fetchall()
            except ProgrammingError:
                return None

    except OperationalError:
        if retries == 0:
            raise

        return execute(query, fetch, retries - 1)


def get_user(user_id: PositiveInt):
    user = execute(
        f'SELECT * FROM users WHERE user_id = {user_id}',
        fetch='one',
    )

    if not user:
        return False

    return UserModel.model_validate({'id': user[0], 'user_id': user[1], 'role': user[2]})


def add_user(user_id: int, role: str):
    """Добавляет нового пользователя в базу данных."""
    try:
        # Псевдокод для синхронного запроса
        existing_user = execute(  # Используем обычный вызов
            f'SELECT * FROM users WHERE user_id = {user_id}',
            fetch='one',
        )

        if existing_user:
            return f"Пользователь с ID {user_id} уже существует."

        # Если пользователя нет, добавляем нового
        execute(  # Синхронный запрос для добавления пользователя
            f"""INSERT INTO users (user_id, role) VALUES ({user_id}, '{role}')"""
        )

        return f"Пользователь с ID {user_id} добавлен с ролью {role}."

    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя в базу данных: {str(e)}")
        return f"Ошибка при добавлении пользователя: {str(e)}"




def get_total_channels():
    count = execute('SELECT COUNT(*) FROM user_chanels', fetch='one')

    if not isinstance(count, tuple):
        raise Exception('Count can not be fetched')

    return int(count[0])


def get_channel(channel_id: int):
    channel = execute(
        f'SELECT * FROM user_chanels WHERE channel_id = {channel_id}',
        fetch='one',
    )

    if not channel:
        return False

    return ChannelModel.model_validate(
        {
            'id': channel[0],
            'user_id': channel[1],
            'channel_id': channel[2],
            'channel_name': channel[3],
            'channel_link': channel[4],
        }
    )


def save_channel(user_id: int, channel_id: int, channel_name: str, channel_link: str):
    execute(
        f"""INSERT INTO user_chanels (user_id, channel_id, channel_name, channel_link) VALUES ({user_id}, {channel_id}, '{channel_name}', '{channel_link}')"""
    )


def delete_channel(channel_id: int):
    execute(f'DELETE FROM user_chanels WHERE channel_id = {channel_id}')


def get_channels(limit: int, offset: int = 0):
    if limit == -1:
        limit = get_total_channels()

    channels = execute(
        f'SELECT * FROM user_chanels c ORDER BY c.channel_name ASC LIMIT {limit} OFFSET {offset}',
        fetch='all',
    )

    if not isinstance(channels, list):
        raise Exception('Channels can not be fetched')

    return [
        ChannelModel.model_validate(
            {
                'id': channel[0],
                'user_id': channel[1],
                'channel_id': channel[2],
                'channel_name': channel[3],
                'channel_link': channel[4],
            }
        )
        for channel in channels
    ]


def get_total_groups():
    count = execute('SELECT COUNT(*) FROM user_group', fetch='one')

    if not isinstance(count, tuple):
        raise Exception('Count can not be fetched')

    return int(count[0])


def get_groups(limit: int, offset: int = 0):
    if limit == -1:
        limit = get_total_groups()

    groups = execute(
        f'SELECT * FROM user_group c ORDER BY c.group_name ASC LIMIT {limit} OFFSET {offset}',
    )

    if not isinstance(groups, list):
        raise Exception('Groups can not be fetched')

    return [
        GroupModel.model_validate(
            {
                'id': group[0],
                'user_id': group[1],
                'group_name': group[2],
                'group_id': group[3],
            }
        )
        for group in groups
    ]


def get_channels_by_group(group_id: int, limit: int, offset: int = 0):
    if limit == -1:
        limit = get_total_channels_for_group(group_id)

    channels = execute(
        f"""
        SELECT u.id, u.user_id, u.channel_id, u.channel_name, u.channel_link
        FROM user_chanels u
        JOIN group_channel g ON u.channel_id = g.channel_id
        WHERE g.group_id = {group_id}
        ORDER BY u.channel_id ASC
        LIMIT {limit} OFFSET {offset}
        """,
    )

    if not isinstance(channels, list):
        raise Exception('Channels can not be fetched')

    return [
        ChannelModel.model_validate(
            {
                'id': channel[0],
                'user_id': channel[1],
                'channel_id': channel[2],
                'channel_name': channel[3],
                'channel_link': channel[4],
            }
        )
        for channel in channels
    ]


def get_total_channels_for_group(group_id: int):
    count = execute(f'SELECT COUNT(*) FROM group_channel WHERE group_id = {group_id}', fetch='one')

    if not isinstance(count, tuple):
        raise Exception('Count can not be fetched')

    return int(count[0])


def group_add_channels(group_id: int, channel_id: int):
    execute(
        f'INSERT INTO group_channel (group_id, channel_id) VALUES ({group_id}, {channel_id}) ON CONFLICT (group_id, channel_id) DO NOTHING'
    )


def group_delete_channels(group_id: int, channel_id: int):
    execute(f'DELETE FROM group_channel WHERE group_id = {group_id} AND channel_id = {channel_id}')


def new_group_channel_save(user_id: int, group_name: str, channel_ids: list[int]):
    group_id = execute(
        f"""INSERT INTO user_group (user_id, group_name) VALUES ({user_id}, '{group_name}') RETURNING id""",
        fetch='one',
    )

    if not isinstance(group_id, tuple):
        raise Exception('Group ID can not be fetched')

    group_id = group_id[0]

    for channel_id in channel_ids:
        group_add_channels(group_id, channel_id)


def group_delete(group_id: int):
    execute(f'DELETE FROM user_group WHERE id = {group_id}')
    execute(f'DELETE FROM group_channel WHERE group_id = {group_id}')


def new_group_name(group_id: int, group_name: str, user_id: int):
    execute(
        f"""UPDATE user_group SET group_name = '{group_name}' WHERE id = {group_id} AND user_id = {user_id}"""
    )


def save_post(
    channel_id: int, channel_name: str, post_id: int, post_text: str | None, user_id: int
):
    execute(
        f"""INSERT INTO posts (channel_id, channel_name, post_id, post_text, user_id, created_at) VALUES ({channel_id}, '{channel_name}', {post_id}, '{post_text}', {user_id}, '{datetime.now().date()}')"""
    )


def get_posts(channel_id: int):
    posts = execute(
        f"""SELECT (p.id, p.channel_id, p.channel_name, p.post_id, p.post_text, p.user_id, p.created_at) FROM posts p WHERE channel_id = '{channel_id}' ORDER BY created_at DESC""",
    )
    posts = [post[0] for post in posts]

    return [
        PostModel.model_validate(
            {
                'id': post[0],
                'channel_id': post[1],
                'channel_name': post[2],
                'post_id': post[3],
                'post_text': post[4],
                'created_at': post[6],
            }
        )
        for post in posts
    ]
