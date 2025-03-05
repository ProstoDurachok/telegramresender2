# Telegram Resender

This is a Telegram bot that can forward messages from one channel to another.

## How to use

1. Clone this repository.
2. Install [uv](https://github.com/astral-sh/uv).
3. Install dependencies with `uv sync`.
4. Create a new Telegram bot by talking to the [BotFather](https://t.me/BotFather).
5. Create a new PostgreSQL database and add the connection details to the `.env` file.
6. Run the bot with `poe run`.
7. Add the bot to the channels you want to forward messages from and to.
8. Start the bot by sending the `/start` command.

## Features

* Forward messages from one channel to another
* Support for forwarding messages with media (photos, videos, audio, documents)
* Support for forwarding messages with captions
* Support for forwarding messages with inline keyboards
* Support for forwarding messages from channels with large amounts of messages
* Support for forwarding messages from channels with a large amount of members
