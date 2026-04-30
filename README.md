# NEAR NFT Drop Alert Bot

A Telegram bot that delivers real-time NFT drop alerts and information from the NEAR ecosystem. Stay updated on the latest mints, collections, and supply data from Mintbase and other NEAR marketplaces. Never miss a drop again.

---

## Prerequisites

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Installation

git clone https://github.com/your-username/near-nft-drop-alert-bot.git
cd near-nft-drop-alert-bot
pip install -r requirements.txt

---

## Configuration

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the token BotFather provides
4. Set it as an environment variable:

# Linux / macOS
export BOT_TOKEN="your_token_here"

# Windows
set BOT_TOKEN=your_token_here

Alternatively, create a `.env` file in the project root:

BOT_TOKEN=your_token_here

---

## Running

python bot.py

---

## Available Commands

| Command | Description |
|---|---|
| `/start` | Start the bot and see the welcome message |
| `/help` | Show all available commands and usage info |
| `/drops` | View the latest NFT drops on NEAR |
| `/mintbase` | Browse trending Mintbase collections |
| `/nftinfo` | Get detailed info about a specific NFT or collection |
| `/supply` | Check current token supply stats |

---

## Deployment

**Railway (recommended):**

Push to GitHub and connect your repo at [railway.app](https://railway.app). Add `BOT_TOKEN` as an environment variable in the Railway dashboard.

**Heroku:**

echo "worker: python bot.py" > Procfile
git push heroku main
heroku config:set BOT_TOKEN=your_token_here

---

## Project Structure

near-nft-drop-alert-bot/
├── bot.py
├── requirements.txt
├── Procfile
└── .env.example

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## License

[MIT](LICENSE)