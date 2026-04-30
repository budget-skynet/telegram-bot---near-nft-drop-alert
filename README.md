# NEAR NFT Drop Alert Bot

A Telegram bot that delivers real-time NEAR Protocol NFT drop alerts directly to your chat. Stay ahead of upcoming mints, track live drops on Mintbase, monitor NEAR token price, and check chain stats — all without leaving Telegram.

---

## Prerequisites

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Installation

git clone https://github.com/your-username/near-nft-drop-bot.git
cd near-nft-drop-bot
pip install -r requirements.txt

---

## Configuration

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the token BotFather provides
4. Set it as an environment variable:

export BOT_TOKEN="your_telegram_bot_token_here"

Or create a `.env` file in the project root:

BOT_TOKEN=your_telegram_bot_token_here

---

## Running

python bot.py

---

## Available Commands

| Command | Description |
|---|---|
| `/start` | Start the bot and see the welcome message |
| `/help` | Display all available commands and usage info |
| `/drops` | Browse current and upcoming NEAR NFT drops |
| `/mintbase_drops` | View live drops listed on Mintbase |
| `/price` | Get the current NEAR token price |
| `/chain` | Check NEAR blockchain stats and network info |
| `/mynfts` | Look up NFTs held by your NEAR wallet |

---

## Deploy

**Railway (recommended):**

Add a `Procfile` to your project root:

worker: python bot.py

Then push to Railway:

railway up

**Heroku:**

heroku create your-app-name
heroku config:set BOT_TOKEN=your_token_here
git push heroku main

---

## Project Structure

near-nft-drop-bot/
├── bot.py
├── requirements.txt
├── Procfile
└── .env

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## License

[MIT](LICENSE)