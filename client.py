from logging import getLogger

from telegram import BotCommand, Update
from telegram.ext import (
    AIORateLimiter,
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from commands import button_callbacks, commands, message_handlers
from config.environment import settings
from config.log import configure_logging

logger = getLogger(__name__)


async def set_commands(app):
    commands_list: list[BotCommand] = []

    for command_data, handler in commands:
        app.add_handler(handler)
        commands_list.append(command_data)

    await app.bot.set_my_commands(commands_list)


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for callback in button_callbacks:
        await callback(update, context)


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for handler in message_handlers:
        await handler(update, context)


def main():
    configure_logging()

    app = ApplicationBuilder().token(settings.TOKEN)
    app = app.rate_limiter(AIORateLimiter())
    app = app.build()

    commands_list: list[BotCommand] = []

    for command_data, handler in commands:
        app.add_handler(handler)
        commands_list.append(command_data)

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, messages),
    )

    app.post_init = set_commands

    app.run_polling()


if __name__ == '__main__':
    main()
