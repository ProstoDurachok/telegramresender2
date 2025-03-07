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


def execute(query: str, fetch: Literal['one', 'all'] = 'all', retries: int = 3, params = None):
    connection = connect(
        ' '.join([f'{key}={value}' for key, value in conninfo.items()]), autocommit=True
    )

    try:
        with connection.cursor() as cur:
            cur.execute(query, params)  # type: ignore

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

        return execute(query, params, fetch, retries - 1)


def get_user(user_id: PositiveInt):
    user = execute(
        f'SELECT * FROM users WHERE user_id = {user_id}',
        fetch='one',
    )

    if not user:
        return None  # Возвращаем None, чтобы соответствовать стандартному поведению

    return UserModel.model_validate({'id': user[0], 'user_id': user[1], 'role': user[2]})


def get_all_users():
    """Получить всех пользователей из базы данных."""
    try:
        users = execute('SELECT * FROM users', fetch='all')
        if not users:
            return []

        # Преобразуем результат в модели пользователей
        return [
            UserModel.model_validate({'id': user[0], 'user_id': user[1], 'role': user[2]})
            for user in users
        ]
    except Exception as e:
        logger.error(f"Ошибка при получении всех пользователей: {str(e)}")
        return []



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


def update_user_role(user_id: int, new_role: str):
    """Обновить роль пользователя."""
    try:
        if new_role not in ['admin', 'operator', 'user']:
            return "Ошибка: роль должна быть admin, operator или user."

        execute(f"UPDATE users SET role = '{new_role}' WHERE user_id = {user_id}")
        return f"Роль пользователя с ID {user_id} обновлена на {new_role}."
    except Exception as e:
        logger.error(f"Ошибка при обновлении роли: {str(e)}")
        return f"Ошибка при обновлении роли: {str(e)}"

def delete_user(user_id: int):
    """Удалить пользователя из базы данных."""
    try:
        execute(f"DELETE FROM users WHERE user_id = {user_id}")
        return f"Пользователь с ID {user_id} удален."
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {str(e)}")
        return f"Ошибка при удалении пользователя: {str(e)}"



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

def get_user_channels(user_id: int, limit: int = 20, offset: int = 0):
    query = """
        SELECT channel_id, channel_name, channel_link 
        FROM user_chanels 
        WHERE user_id = %s
        LIMIT %s OFFSET %s
    """
    channels = execute(query, fetch='all', params=(user_id, limit, offset))

    # Проверяем результат запроса
    if not channels:
        return []  # Возвращаем пустой список, если нет каналов

    # Добавляем проверку на наличие нужных данных в каждом канале
    return [
        ChannelModel.model_validate({
            'id': None,  # Нет id в запросе
            'user_id': user_id,
            'channel_id': ch[0],
            'channel_name': ch[1],
            'channel_link': ch[2],
        })
        for ch in channels if len(ch) == 3  # Проверяем, что в кортежах 3 элемента
    ]


def get_total_user_channels(user_id: int):
    query = "SELECT COUNT(*) FROM user_chanels WHERE user_id = %s"
    count = execute(query, fetch='one', params=(user_id,))  # Ensure the user_id is passed as a tuple
    
    if not count:
        raise Exception('Count cannot be fetched')

    return int(count[0])





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

def get_channels_by_user(user_id: int, limit: int = 10, offset: int = 0):
    """
    Получает список каналов, доступных пользователю.
    
    :param user_id: ID пользователя
    :param limit: Ограничение по количеству каналов
    :param offset: Смещение для пагинации
    :return: Список объектов каналов, доступных пользователю
    """
    # Если limit равен -1, устанавливаем его на общее количество каналов
    if limit == -1:
        limit = get_total_channels_by_user(user_id)

    # Запрос для получения всех доступных каналов пользователя с пагинацией
    query = """
        SELECT c.channel_id, c.channel_name, c.channel_link 
        FROM user_chanels c
        WHERE uc.user_id = %s
        ORDER BY c.channel_name ASC
        LIMIT %s OFFSET %s
    """
    
    # Выполняем запрос, чтобы получить каналы пользователя
    channels = execute(query, fetch='all', params=(user_id, limit, offset))

    # Если каналы найдены, возвращаем их как список объектов
    if channels:
        return [
            ChannelModel.model_validate({
                'id': None,  # ID может быть None, если не используется
                'user_id': user_id,
                'channel_id': ch[0],
                'channel_name': ch[1],
                'channel_link': ch[2],
            })
            for ch in channels
        ]
    else:
        return []  # Возвращаем пустой список, если каналы не найдены



def delete_group_if_no_channels(group_id: int):
    """Функция для удаления группы, если в ней нет каналов."""
    query = "DELETE FROM user_group WHERE id = %s"
    execute(query, params=(group_id,))
    logger.info(f'Группа с ID {group_id} удалена, так как не содержит каналов.')


def get_total_groups(user_id: int):
    count = execute(
        f'''
        SELECT COUNT(DISTINCT user_group.group_id)
        FROM user_group
        JOIN group_channel ON user_group.group_id = group_channel.group_id
        WHERE user_group.user_id = {user_id}
        ''', fetch='one'
    )

    if not isinstance(count, tuple):
        raise Exception('Count can not be fetched')

    return int(count[0])



def get_channels_by_group_id(group_id: int):
    # Выполняем запрос для получения всех каналов, которые принадлежат группе с заданным id
    channels = execute(
        f"SELECT * FROM group_channel WHERE group_id = {group_id}",
        fetch="all"
    )
    
    # Если каналы есть, возвращаем их. Если нет, возвращаем пустой список.
    return channels if channels else []


def get_group(user_id: int, limit: int, offset: int = 0):
    if limit == -1:
        limit = get_total_groups(user_id)

    groups = execute(
        f'SELECT * FROM user_group c WHERE c.user_id = {user_id} ORDER BY c.group_name ASC LIMIT {limit} OFFSET {offset}',
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



def get_groups(user_id: int, limit: int, offset: int = 0):
    if limit == -1:
        limit = get_total_groups(user_id)

    groups = execute(
        f'SELECT * FROM user_group c WHERE c.user_id = {user_id} ORDER BY c.group_name ASC LIMIT {limit} OFFSET {offset}',
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
