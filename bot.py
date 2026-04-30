import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"
PARAS_API = "https://api-v2-mainnet.paras.id"
MINTBASE_API = "https://graph.mintbase.xyz"

# Known NFT marketplace / launchpad contract IDs on NEAR mainnet
NFT_LAUNCHPADS = [
    "mint.mintbase1.near",
    "paras-token-v2.testnet",
    "x.paras.near",
    "nftv2.enleap.near",
    "vaultfactory.mintbase1.near",
]

# ── Low-level NEAR RPC helper ──────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """
    Fire a JSON-RPC request at the NEAR mainnet endpoint and return
    the parsed JSON response.  Raises on HTTP or RPC-level errors.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": "nft-drop-bot",
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
                raise RuntimeError(f"RPC error: {data['error']}")
            return data.get("result", {})


# ── NEAR helper functions ──────────────────────────────────────────────────────

async def get_near_price() -> dict:
    """
    Fetch the current NEAR token price in USD via CoinGecko's free API.
    Returns a dict with 'usd', 'usd_24h_change', 'usd_market_cap'.
    """
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=near&vs_currencies=usd"
        "&include_market_cap=true&include_24hr_change=true"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("near", {})


async def get_nft_metadata(contract_id: str) -> dict:
    """
    Call nft_metadata on any NEP-171 contract and return its metadata dict.
    Useful to inspect a launchpad / collection contract quickly.
    """
    import base64, json

    result = await _rpc(
        "query",
        {
            "request_type": "call_function",
            "finality": "final",
            "account_id": contract_id,
            "method_name": "nft_metadata",
            "args_base64": base64.b64encode(b"{}").decode(),
        },
    )
    # result['result'] is a list of bytes
    raw = bytes(result["result"])
    return json.loads(raw.decode())


async def get_paras_drops(limit: int = 5) -> list[dict]:
    """
    Query the Paras marketplace API for the latest active NFT drops/series.
    Returns a list of drop dicts.
    """
    url = f"{PARAS_API}/series?status=active&__limit={limit}&__sort=created_at::-1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("data", {}).get("results", [])


async def get_account_nfts(account_id: str, contract_id: str) -> list[dict]:
    """
    Return all NFTs owned by *account_id* on *contract_id* (NEP-171).
    Uses nft_tokens_for_owner RPC view call.
    """
    import base64, json

    args = json.dumps(
        {"account_id": account_id, "from_index": "0", "limit": 20}
    ).encode()
    result = await _rpc(
        "query",
        {
            "request_type": "call_function",
            "finality": "final",
            "account_id": contract_id,
            "method_name": "nft_tokens_for_owner",
            "args_base64": base64.b64encode(args).decode(),
        },
    )
    raw = bytes(result["result"])
    return json.loads(raw.decode())


async def get_mintbase_drops(limit: int = 5) -> list[dict]:
    """
    Query Mintbase GraphQL API for the most recently created stores/drops.
    Returns a list of store dicts.
    """
    query = """
    {
      stores(limit: %d, order_by: {created_at: desc}) {
        id
        name
        symbol
        owner
        created_at
      }
    }
    """ % limit

    async with aiohttp.ClientSession() as session:
        async with session.post(
            MINTBASE_API,
            json={"query": query},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("data", {}).get("stores", [])


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with feature overview."""
    text = (
        "🌐 *NEAR NFT Drop Alert Bot* 🚀\n\n"
        "Stay ahead of every NFT drop on the NEAR blockchain!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *Available Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 /drops — Latest active NFT drops on Paras\n"
        "🏪 /newstores — Newest Mintbase stores / collections\n"
        "🔍 /inspect `<contract>` — Inspect any NFT contract\n"
        "👜 /mynfts `<account> <contract>` — Your NFTs\n"
        "💰 /price — Current NEAR token price\n"
        "❓ /help — Full help & tips\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Built with ❤️ for the NEAR ecosystem."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /help ──────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed help message."""
    text = (
        "🆘 *NEAR NFT Drop Alert — Help*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "*🔥 /drops*\n"
        "Shows the 5 most recently active NFT series on Paras marketplace.\n"
        "Includes name, creator, floor price and mint progress.\n\n"
        "*🏪 /newstores*\n"
        "Lists the 5 most recently deployed NFT stores on Mintbase.\n"
        "Great for spotting brand-new collections before they blow up!\n\n"
        "*🔍 /inspect <contract_id>*\n"
        "Example: `/inspect x.paras.near`\n"
        "Fetches on-chain NFT contract metadata directly from NEAR RPC.\n\n"
        "*👜 /mynfts <account_id> <contract_id>*\n"
        "Example: `/mynfts alice.near x.paras.near`\n"
        "Lists up to 20 NFTs owned by an account on a specific contract.\n\n"
        "*💰 /price*\n"
        "Displays the live NEAR token price, market cap, and 24-hour change.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tips*\n"
        "• Set up Telegram alerts so you never miss a drop.\n"
        "• Use /inspect to vet a contract before minting.\n"
        "• Follow us to get community drop announcements!\n\n"
        "🌐 Powered by NEAR Protocol · Paras · Mintbase"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /price ─────────────────────────────────────────────────────────────────────
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the live NEAR token price."""
    await update.message.reply_text("⏳ Fetching NEAR price…")
    try:
        data = await get_near_price()
        usd = data.get("usd", "N/A")
        change = data.get("usd_24h_change", 0)
        mcap = data.get("usd_market_cap", 0)
        arrow = "📈" if change >= 0 else "📉"
        text = (
            "💰 *NEAR Token Price*\n\n"
            f"  Price  : `${usd:,.4f}`\n"
            f"  24h    : {arrow} `{change:+.2f}%`\n"
            f"  Mkt Cap: `${mcap:,.0f}`\n\n"
            "_Source: CoinGecko_"
        )
    except Exception as exc:
        logger.exception("price_command failed")
        text = f"❌ Could not fetch price: `{exc}`"
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /drops ─────────────────────────────────────────────────────────────────────
async def drops_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the latest active NFT drops on Paras."""
    await update.message.reply_text("⏳ Fetching latest Paras drops…")
    try:
        drops = await get_paras_drops(limit=5)
        if not drops:
            await update.message.reply_text("😔 No active drops found right now. Check back soon!")
            return

        lines = ["🔥 *Latest Active NFT Drops on Paras*\n"]
        for i, drop in enumerate(drops, 1):
            name = drop.get("metadata", {}).get("title") or drop.get("token_series_id", "Unnamed")
            creator = drop.get("creator_id", "unknown")
            price_raw = drop.get("price")
            if price_raw:
                price_near = int(price_raw) / 1e24
                price_str = f"{price_near:.2f} NEAR"
            else:
                price_str = "Free / TBD"
            total = drop.get("metadata", {}).get("copies", "∞")
            minted = drop.get("total_mint", 0)
            series_id = drop.get("token_series_id", "")
            url = f"https://paras.id/series/{creator}::{series_id}"

            lines.append(
                f"*{i}. {name}*\n"
                f"   👤 Creator  : `{creator}`\n"
                f"   💸 Price    : `{price_str}`\n"
                f"   🖼 Minted   : `{minted}` / `{total}`\n"
                f"   🔗 [View on Paras]({url})\n"
            )

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )
    except Exception as exc:
        logger.exception("drops_command failed")
        await update.message.reply_text(f"❌ Error fetching drops: `{exc}`", parse_mode="Markdown")


# ── /newstores ─────────────────────────────────────────────────────────────────
async def newstores_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the newest Mintbase stores."""
    await update.message.reply_text("⏳ Fetching newest Mintbase stores…")
    try:
        stores = await get_mintbase_drops(limit=5)
        if not stores:
            await update.message.reply_text("😔 No stores found.")
            return

        lines = ["🏪 *Newest NFT Stores on Mintbase*\n"]
        for i, store in enumerate(stores, 1):
            store_id = store.get("id", "unknown")
            name = store.get("name") or store_id
            symbol = store.get("symbol", "—")
            owner = store.get("owner", "unknown")
            created = (store.get("created_at") or "")[:10]
            url = f"https://www.mintbase.xyz/store/{store_id}"

            lines.append(
                f"*{i}. {name}* (`{symbol}`)\n"
                f"   👤 Owner   : `{owner}`\n"
                f"   📅 Created : `{created}`\n"
                f"   🔗 [View on Mintbase]({url})\n"
            )

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )
    except Exception as exc:
        logger.exception("newstores_command failed")
        await update.message.reply_text(
            f"❌ Error fetching stores: `{exc}`", parse_mode="Markdown"
        )


# ── /inspect ───────────────────────────────────────────────────────────────────
async def inspect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /inspect <contract_id>
    Fetches NFT contract metadata directly from NEAR RPC.
    """
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/inspect <contract_id>`\nExample: `/inspect x.paras.near`",
            parse_mode="Markdown",
        )
        return

    contract_id = context.args[0].strip()
    await update.message.reply_text(f"⏳ Inspecting `{contract_id}` on-chain…", parse_mode="Markdown")
    try:
        meta = await get_nft_metadata(contract_id)
        name = meta.get("name", "N/A")
        symbol = meta.get("symbol", "N/A")
        base_uri = meta.get("base_uri") or "N/A"
        icon = "✅" if meta.get("icon") else "❌"
        spec = meta.get("spec", "N/A")
        ref = meta.get("reference") or "N/A"

        text = (
            f"🔍 *NFT Contract Metadata*\n\n"
            f"  Contract : `{contract_id}`\n"
            f"  Name     : *{name}*\n"
            f"  Symbol   : `{symbol}`\n"
            f"  Spec     : `{spec}`\n"
            f"  Base URI : `{base_uri}`\n"
            f"  Icon     : {icon}\n"
            f"  Reference: `{ref}`\n\n"
            f"_Data pulled live from NEAR RPC_"
        )
    except Exception as exc:
        logger.exception("inspect_command failed")
        text = (
            f"❌ Could not fetch metadata for `{contract_id}`.\n\n"
            f"Reason: `{exc}`\n\n"
            "_Make sure the contract implements NEP-171._"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /mynfts ────────────────────────────────────────────────────────────────────
async def mynfts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /mynfts <account_id> <contract_id>
    Lists up to 20 NFTs owned by the given account on the given contract.
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Usage: `/mynfts <account_id> <contract_id>`\n"
            "Example: `/mynfts alice.near x.paras.near`",
            parse_mode="Markdown",
        )
        return

    account_id, contract_id = context.args[0].strip(), context.args[1].strip()
    await update.message.reply_text(
        f"⏳ Fetching NFTs for `{account_id}` on `{contract_id}`…",
        parse_mode="Markdown",
    )
    try:
        nfts = await get_account_nfts(account_id, contract_id)
        if not nfts:
            await update.message.reply_text(
                f"😔 No NFTs found for `{account_id}` on `{contract_id}`.",
                parse_mode="Markdown",
            )
            return

        lines = [f"👜 *NFTs owned by* `{account_id}`\n*Contract:* `{contract_id}`\n"]
        for i, token in enumerate(nfts[:20], 1):
            token_id = token.get("token_id", "?")
            title = (
                token.get("metadata", {}).get("title")
                or token.get("metadata", {}).get("description", "")[:40]
                or f"Token #{token_id}"
            )
            copies = token.get("metadata", {}).get("copies", "—")
            lines.append(f"  *{i}.* `{token_id}` — {title} (copies: {copies})")

        if len(nfts) == 20:
            lines.append("\n_Showing first 20 results._")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("mynfts_command failed")
        await update.message.reply_text(

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("drops", drops_command))
    application.add_handler(CommandHandler("newstores", newstores_command))
    application.add_handler(CommandHandler("inspect", inspect_command))
    application.add_handler(CommandHandler("mynfts", mynfts_command))
    application.run_polling()

if __name__ == "__main__":
    main()
