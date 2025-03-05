from .channels import button_callback as channels_button_callback
from .channels import command as channels
from .channels import message_handlers as channels_message_handlers
from .groups import button_callback as groups_button_callback
from .groups import command as groups
from .groups import message_handlers as groups_message_handlers
from .posts import button_callback as posts_button_callback
from .posts import command as posts
from .start import command as start
from .user import command as add_user_command  # Импорт обработчика добавления пользователя

# Список команд в виде кортежей (BotCommand, CommandHandler)
commands = [
    start,
    channels,
    groups,
    posts,
    add_user_command,  # Команда добавления пользователя
]

# Обработчики кнопок
button_callbacks = [channels_button_callback, groups_button_callback, posts_button_callback]
message_handlers = channels_message_handlers + groups_message_handlers
