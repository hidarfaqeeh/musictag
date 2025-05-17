# ID3v2 Tag Editor Telegram Bot

A Telegram bot that allows users to view, edit, and save ID3v2 tags for audio files.

## Features

- View existing ID3v2 tags in audio files
- Edit tag values (artist, title, album, etc.)
- Save modified tags to the audio file
- Return the modified audio file to the user

## Supported Tags

This bot supports the following ID3v2 tags:

- Title
- Artist
- Album
- Year
- Genre
- Composer
- Comment
- Track number
- Length
- Lyrics

## Usage

1. Start a chat with the bot using the `/start` command
2. Send an audio file to the bot
3. View the current tags
4. Choose to edit tags or download without editing
5. If editing, enter tag values in the format `tag_name: value`
6. Send `/done` when finished editing
7. Receive your modified audio file

## Commands

- `/start` - Start the bot and show main menu
- `/help` - Show help information
- `/cancel` - Cancel the current operation

## Requirements

- Python 3.6+
- python-telegram-bot (v20.0+)
- mutagen

## Running the bot

1. Set your Telegram bot token as an environment variable:
   ```
   export TELEGRAM_TOKEN=your_bot_token_here
   