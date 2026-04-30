# NEAR NFT Drop Alert Bot

A Telegram bot that delivers real-time NFT drop alerts and NEAR ecosystem updates directly to your chat. Stay ahead of new mints, track prices, and explore your NEAR NFT portfolio without leaving Telegram.

---

## Prerequisites

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A NEAR-compatible wallet address (optional, for portfolio features)

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

export BOT_TOKEN=your_token_here

Or create a `.env` file in the project root:

BOT_TOKEN=your_token_here

---

## Running

python bot.py

The bot will start polling for updates. You should see a confirmation message in your terminal.

---

## Available Commands

| Command | Description |
|---|---|
| `/start` | Start the bot and see the welcome message |
| `/help` | Show all available commands and usage info |
| `/price` | Get the current NEAR token price |
| `/drops` | View upcoming and live NFT drops on NEAR |
| `/newstores` | Browse newly launched NFT stores and collections |
| `/inspect` | Inspect a specific NFT or collection by ID |
| `/mynfts` | View NFTs held in your connected NEAR wallet |

---

## Deployment

For production deployment, a `Procfile` is included. Deploy in one command using Railway or Heroku:

# Railway
railway up

# Heroku
heroku create && git push heroku main

Make sure to set `BOT_TOKEN` as an environment variable in your platform's dashboard before deploying.

---

## License

MIT