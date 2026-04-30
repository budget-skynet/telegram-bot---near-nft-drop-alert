import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"
PARAS_API = "https://api-v2-mainnet.paras.id"
MINTBASE_API = "https://graph.mintbase.xyz"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── Low-level RPC helper ──────────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """Send a JSON-RPC request to the NEAR mainnet RPC endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": "nearbot",
        "method": method,
        "params": params,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            NEAR_RPC,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if "error" in data:
                raise ValueError(f"RPC error: {data['error']}")
            return data.get("result", {})


# ── NEAR helper functions ─────────────────────────────────────────────────────

async def get_near_price() -> float:
    """Fetch the current NEAR price in USD from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "near", "vs_currencies": "usd"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["near"]["usd"]


async def get_paras_drops(limit: int = 5) -> list[dict]:
    """
    Fetch the latest NFT collections / drops listed on Paras marketplace.
    Returns a list of dicts with title, creator_id, floor_price, and url.
    """
    url = f"{PARAS_API}/token-series"
    params = {
        "sort_by": "createdAt",
        "order": "desc",
        "__limit": limit,
        "is_verified": "true",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            results = data.get("data", {}).get("results", [])
            drops = []
            for item in results:
                metadata = item.get("metadata", {})
                price_yocto = item.get("price")
                floor_near = (
                    round(int(price_yocto) / 1e24, 4)
                    if price_yocto
                    else None
                )
                drops.append(
                    {
                        "title": metadata.get("title", "Untitled"),
                        "creator_id": item.get("creator_id", "unknown"),
                        "floor_price": floor_near,
                        "collection": item.get("metadata", {}).get(
                            "collection", ""
                        ),
                        "url": (
                            f"https://paras.id/token/"
                            f"{item.get('contract_id', '')}::"
                            f"{item.get('token_series_id', '')}"
                        ),
                    }
                )
            return drops


async def get_mintbase_drops(limit: int = 5) -> list[dict]:
    """
    Query Mintbase GraphQL API for the most recently minted NFT stores/drops.
    Returns a list of dicts with name, owner, base_uri, and url.
    """
    query = """
    query LatestStores($limit: Int!) {
      nft_contracts(
        order_by: {created_at: desc}
        limit: $limit
        where: {is_mintbase: {_eq: false}}
      ) {
        id
        name
        owner_id
        base_uri
        created_at
      }
    }
    """
    payload = {"query": query, "variables": {"limit": limit}}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            MINTBASE_API,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            stores = (
                data.get("data", {}).get("nft_contracts", [])
            )
            drops = []
            for s in stores:
                drops.append(
                    {
                        "name": s.get("name") or s.get("id", "Unnamed"),
                        "owner_id": s.get("owner_id", "unknown"),
                        "base_uri": s.get("base_uri", ""),
                        "created_at": s.get("created_at", ""),
                        "url": f"https://www.mintbase.xyz/contract/{s.get('id','')}",
                    }
                )
            return drops


async def get_account_nfts(account_id: str, contract_id: str) -> list[dict]:
    """
    Fetch NFTs owned by an account on a given NEP-171 contract via view call.
    Returns a list of token metadata dicts.
    """
    import json, base64

    args = json.dumps({"account_id": account_id, "from_index": "0", "limit": 10})
    args_b64 = base64.b64encode(args.encode()).decode()

    result = await _rpc(
        "query",
        {
            "request_type": "call_function",
            "finality": "final",
            "account_id": contract_id,
            "method_name": "nft_tokens_for_owner",
            "args_base64": args_b64,
        },
    )
    raw = bytes(result.get("result", []))
    tokens = json.loads(raw.decode()) if raw else []
    return tokens


async def get_near_block_info() -> dict:
    """Return the latest NEAR block height and timestamp."""
    result = await _rpc("block", {"finality": "final"})
    header = result.get("header", {})
    ts_ns = header.get("timestamp", 0)
    ts_s = ts_ns / 1e9
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    return {
        "height": header.get("height"),
        "timestamp": dt,
        "hash": header.get("hash", ""),
    }


# ── /start and /help ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with command overview."""
    text = (
        "🟣 *NEAR NFT Drop Alert Bot*\n\n"
        "Stay ahead of every drop on the NEAR blockchain!\n\n"
        "📌 *Commands:*\n"
        "  /drops — Latest NFT drops on *Paras*\n"
        "  /mintbase — Latest stores on *Mintbase*\n"
        "  /price — Current *NEAR* price in USD\n"
        "  /chain — Live NEAR block info\n"
        "  /mynfts `<account>` `<contract>` — Your NFTs on any contract\n"
        "  /help — Show this message\n\n"
        "Built with ❤️ for the NEAR ecosystem 🌈"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Alias for /start — shows full help text."""
    await start(update, context)


# ── Command handlers ──────────────────────────────────────────────────────────

async def drops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /drops — Show the 5 most recent verified NFT drops on Paras marketplace.
    """
    await update.message.reply_text("🔍 Fetching latest Paras drops…")
    try:
        near_price = await get_near_price()
        items = await get_paras_drops(limit=5)
        if not items:
            await update.message.reply_text("😕 No drops found right now. Try again later.")
            return

        lines = ["🎨 *Latest NFT Drops on Paras*\n"]
        for i, drop in enumerate(items, 1):
            price_str = (
                f"{drop['floor_price']} NEAR"
                f" (≈ ${round(drop['floor_price'] * near_price, 2)} USD)"
                if drop["floor_price"] is not None
                else "Price TBD"
            )
            lines.append(
                f"*{i}. {drop['title']}*\n"
                f"   👤 Creator: `{drop['creator_id']}`\n"
                f"   💰 Floor: {price_str}\n"
                f"   🔗 [View on Paras]({drop['url']})\n"
            )
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.exception("drops error")
        await update.message.reply_text(f"❌ Error fetching drops: {exc}")


async def mintbase_drops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /mintbase — Show 5 newest NFT stores/contracts deployed on Mintbase.
    """
    await update.message.reply_text("🔍 Fetching latest Mintbase stores…")
    try:
        items = await get_mintbase_drops(limit=5)
        if not items:
            await update.message.reply_text("😕 No Mintbase drops found. Try again later.")
            return

        lines = ["🏪 *Latest Stores on Mintbase*\n"]
        for i, store in enumerate(items, 1):
            created = store["created_at"][:10] if store["created_at"] else "unknown"
            lines.append(
                f"*{i}. {store['name']}*\n"
                f"   👤 Owner: `{store['owner_id']}`\n"
                f"   📅 Created: {created}\n"
                f"   🔗 [View on Mintbase]({store['url']})\n"
            )
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.exception("mintbase error")
        await update.message.reply_text(f"❌ Error fetching Mintbase stores: {exc}")


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /price — Display the current NEAR token price in USD.
    """
    try:
        usd = await get_near_price()
        text = (
            f"💰 *NEAR Token Price*\n\n"
            f"  1 NEAR = *${usd:,.4f} USD*\n\n"
            f"_Data sourced from CoinGecko_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as exc:
        logger.exception("price error")
        await update.message.reply_text(f"❌ Could not fetch price: {exc}")


async def chain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /chain — Display live NEAR blockchain stats (block height & timestamp).
    """
    try:
        info = await get_near_block_info()
        text = (
            "⛓️ *NEAR Blockchain Status*\n\n"
            f"  📦 Block Height: `{info['height']:,}`\n"
            f"  🕐 Timestamp:    `{info['timestamp']}`\n"
            f"  🔑 Block Hash:\n  `{info['hash']}`\n\n"
            "_Fetched live from NEAR mainnet RPC_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as exc:
        logger.exception("chain error")
        await update.message.reply_text(f"❌ Could not fetch chain info: {exc}")


async def mynfts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /mynfts <account.near> <contract.near>
    Show the first 10 NFTs owned by the given account on a specific contract.

    Example:
        /mynfts alice.near x.paras.near
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Usage: `/mynfts <account.near> <contract.near>`\n\n"
            "Example:\n`/mynfts alice.near x.paras.near`",
            parse_mode="Markdown",
        )
        return

    account_id = context.args[0].strip()
    contract_id = context.args[1].strip()

    await update.message.reply_text(
        f"🔍 Looking up NFTs for `{account_id}` on `{contract_id}`…",
        parse_mode="Markdown",
    )
    try:
        tokens = await get_account_nfts(account_id, contract_id)
        if not tokens:
            await update.message.reply_text(
                f"😕 No NFTs found for `{account_id}` on `{contract_id}`.",
                parse_mode="Markdown",
            )
            return

        lines = [
            f"🖼️ *NFTs owned by* `{account_id}`\n"
            f"   _Contract: {contract_id}_\n"
        ]
        for i, tok in enumerate(tokens[:10], 1):
            meta = tok.get("metadata", {})
            token_id = tok.get("token_id", "?")
            title = meta.get("title") or f"Token #{token_id}"
            desc = (meta.get("description") or "")[:80]
            lines.append(
                f"*{i}. {title}*\n"
                f"   🆔 ID: `{token_id}`\n"
                + (f"   📝 {desc}\n" if desc else "")
            )
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.exception("mynfts error")
        await update.message.reply_text(
            f"❌ Error fetching NFTs: {exc}\n\n"
            "Make sure the contract supports `nft_tokens_for_owner` (NEP-171)."
        )

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("drops", drops))
    application.add_handler(CommandHandler("mintbase_drops", mintbase_drops))
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("chain", chain))
    application.add_handler(CommandHandler("mynfts", mynfts))
    application.run_polling()

if __name__ == "__main__":
    main()
