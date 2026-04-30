import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"
PARAS_API = "https://api-v2-mainnet.paras.id"
MINTBASE_API = "https://graph.mintbase.xyz"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── Low-level RPC helper ──────────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """
    Generic async helper that sends a JSON-RPC request to the NEAR mainnet RPC
    endpoint and returns the parsed response dict.
    Raises RuntimeError on transport or RPC-level errors.
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
            if resp.status != 200:
                raise RuntimeError(
                    f"NEAR RPC HTTP error: {resp.status}"
                )
            data = await resp.json()
            if "error" in data:
                raise RuntimeError(
                    f"NEAR RPC error: {data['error'].get('message', data['error'])}"
                )
            return data.get("result", {})


# ── NEAR helper functions ─────────────────────────────────────────────────────

async def get_nft_metadata(contract_id: str) -> dict:
    """
    Fetch NFT contract metadata (name, symbol, base_uri, icon …) via
    `nft_metadata` view call on the given contract.
    Returns a dict with keys: name, symbol, base_uri, icon, spec, reference.
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
    raw = bytes(result["result"])
    return json.loads(raw.decode())


async def get_nft_supply(contract_id: str) -> int:
    """
    Return the total minted supply for an NFT contract via `nft_total_supply`.
    Returns an integer.
    """
    import base64, json

    result = await _rpc(
        "query",
        {
            "request_type": "call_function",
            "finality": "final",
            "account_id": contract_id,
            "method_name": "nft_total_supply",
            "args_base64": base64.b64encode(b"{}").decode(),
        },
    )
    raw = bytes(result["result"])
    value = json.loads(raw.decode())
    # Some contracts return a string, others an int
    return int(value)


async def get_account_nfts(contract_id: str, account_id: str) -> list:
    """
    Return the list of NFT tokens owned by *account_id* on *contract_id*
    (first 10 tokens via `nft_tokens_for_owner`).
    Each element is the raw token dict returned by the contract.
    """
    import base64, json

    args = json.dumps(
        {"account_id": account_id, "from_index": "0", "limit": 10}
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


async def get_paras_drops() -> list:
    """
    Fetch the latest NFT drops listed on Paras marketplace.
    Returns a list of dicts, each containing:
        title, collection_id, creator_id, price, supply, start_date.
    Falls back to an empty list on any network error so the bot stays alive.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{PARAS_API}/drops"
            params = {"__limit": 8, "__sort": "issued_at::-1"}
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                drops = data.get("data", {}).get("results", [])
                formatted = []
                for d in drops:
                    formatted.append(
                        {
                            "title": d.get("metadata", {}).get("title", "Untitled"),
                            "collection_id": d.get("collection_id", ""),
                            "creator_id": d.get("creator_id", ""),
                            "price": d.get("price", "N/A"),
                            "supply": d.get("supply", "?"),
                            "start_date": d.get("start_date", ""),
                            "end_date": d.get("end_date", ""),
                            "url": f"https://paras.id/drops/{d.get('id', '')}",
                        }
                    )
                return formatted
    except Exception as exc:
        logger.warning("Paras API error: %s", exc)
        return []


async def get_mintbase_recent_drops() -> list:
    """
    Fetch recently deployed NFT stores / drop contracts from Mintbase
    via its public GraphQL endpoint.
    Returns a list of dicts with keys: name, id, owner, created_at.
    Falls back to an empty list on any error.
    """
    query = """
    {
      nft_contracts(
        order_by: {created_at: desc}
        limit: 6
        where: {is_mintbase: {_eq: true}}
      ) {
        id
        name
        owner_id
        created_at
        tokens_aggregate {
          aggregate { count }
        }
      }
    }
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                MINTBASE_API,
                json={"query": query},
                headers={"mb-api-key": "anon", "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                contracts = (
                    data.get("data", {}).get("nft_contracts", [])
                )
                formatted = []
                for c in contracts:
                    minted = (
                        c.get("tokens_aggregate", {})
                        .get("aggregate", {})
                        .get("count", 0)
                    )
                    formatted.append(
                        {
                            "name": c.get("name") or c.get("id", "Unknown"),
                            "id": c.get("id", ""),
                            "owner": c.get("owner_id", ""),
                            "created_at": c.get("created_at", ""),
                            "minted": minted,
                            "url": f"https://mintbase.xyz/contract/{c.get('id', '')}",
                        }
                    )
                return formatted
    except Exception as exc:
        logger.warning("Mintbase API error: %s", exc)
        return []


# ── /start & /help ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Welcome the user and give a quick overview of available commands.
    """
    user = update.effective_user
    text = (
        f"👋 *Welcome, {user.first_name}!*\n\n"
        "🖼 *NEAR NFT Drop Alert Bot* keeps you ahead of every new drop "
        "on the NEAR blockchain.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 *Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "/drops — Latest NFT drops on Paras\n"
        "/mintbase — Recent Mintbase stores\n"
        "/nftinfo `<contract>` — NFT contract metadata\n"
        "/supply `<contract>` — Total minted supply\n"
        "/mynfts `<contract>` `<wallet>` — Your NFTs\n"
        "/help — Show this message again\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 _Example:_ `/nftinfo comic.paras.near`\n\n"
        "🌐 Powered by [NEAR Protocol](https://near.org)"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Re-send the full command reference.
    """
    text = (
        "📖 *NEAR NFT Drop Alert — Help*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 *Available Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🗓 */drops*\n"
        "  Shows the 8 newest NFT drops on Paras marketplace with price, "
        "supply and countdown.\n\n"
        "🏪 */mintbase*\n"
        "  Shows the 6 most recently created Mintbase NFT stores.\n\n"
        "🔍 */nftinfo* `<contract_id>`\n"
        "  Fetches on-chain metadata for any NEP-171 NFT contract.\n"
        "  _Example:_ `/nftinfo comic.paras.near`\n\n"
        "📊 */supply* `<contract_id>`\n"
        "  Returns the total number of tokens minted so far.\n"
        "  _Example:_ `/supply x.paras.near`\n\n"
        "🎒 */mynfts* `<contract_id>` `<wallet.near>`\n"
        "  Lists up to 10 NFTs you own in a specific collection.\n"
        "  _Example:_ `/mynfts x.paras.near alice.near`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 [NEAR Protocol](https://near.org) | "
        "[Paras](https://paras.id) | "
        "[Mintbase](https://mintbase.xyz)"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


# ── Command handlers ──────────────────────────────────────────────────────────

async def drops_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /drops — fetch and display the latest Paras NFT drops.
    """
    await update.message.reply_text("⏳ Fetching latest NEAR NFT drops from Paras…")

    drops = await get_paras_drops()

    if not drops:
        await update.message.reply_text(
            "😔 No drops found right now — please try again in a moment."
        )
        return

    lines = ["🔥 *Latest NEAR NFT Drops on Paras*\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, d in enumerate(drops, 1):
        price_near = (
            f"{int(d['price']) / 1e24:.2f} NEAR"
            if str(d["price"]).isdigit()
            else str(d["price"])
        )
        start = d["start_date"][:10] if d.get("start_date") else "TBA"
        end = d["end_date"][:10] if d.get("end_date") else "TBA"
        lines.append(
            f"*{i}. {d['title']}*\n"
            f"  👤 Creator: `{d['creator_id']}`\n"
            f"  💰 Price: {price_near}\n"
            f"  🖼 Supply: {d['supply']}\n"
            f"  📅 {start} → {end}\n"
            f"  🔗 [View Drop]({d['url']})\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🌐 [Browse all drops](https://paras.id/drops)")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def mintbase_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /mintbase — display recent Mintbase NFT store deployments.
    """
    await update.message.reply_text("⏳ Fetching recent Mintbase NFT stores…")

    stores = await get_mintbase_recent_drops()

    if not stores:
        await update.message.reply_text(
            "😔 Could not retrieve Mintbase stores right now — try again shortly."
        )
        return

    lines = ["🏪 *Recent Mintbase NFT Stores*\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, s in enumerate(stores, 1):
        created = s["created_at"][:10] if s.get("created_at") else "Unknown"
        lines.append(
            f"*{i}. {s['name']}*\n"
            f"  📋 Contract: `{s['id']}`\n"
            f"  👤 Owner: `{s['owner']}`\n"
            f"  🖼 Minted: {s['minted']} tokens\n"
            f"  📅 Created: {created}\n"
            f"  🔗 [Open Store]({s['url']})\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🌐 [Explore Mintbase](https://mintbase.xyz)")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def nftinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /nftinfo <contract_id>
    Fetch and display on-chain metadata for any NEP-171 NFT contract.
    """
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/nftinfo <contract_id>`\n"
            "_Example:_ `/nftinfo comic.paras.near`",
            parse_mode="Markdown",
        )
        return

    contract_id = context.args[0].strip()
    await update.message.reply_text(
        f"⏳ Looking up NFT contract `{contract_id}` on NEAR…",
        parse_mode="Markdown",
    )

    try:
        meta = await get_nft_metadata(contract_id)
    except Exception as exc:
        await update.message.reply_text(
            f"❌ Error fetching metadata:\n`{exc}`\n\n"
            "Make sure the contract ID is correct and implements NEP-171.",
            parse_mode="Markdown",
        )
        return

    name = meta.get("name", "N/A")
    symbol = meta.get("symbol", "N/A")
    spec = meta.get("spec", "N/A")
    base_uri = meta.get("base_uri") or "_not set_"
    reference = meta.get("reference") or "_not set_"
    icon = "✅ present" if meta.get("icon") else "❌ not set"

    text = (
        f"🖼 *NFT Contract Metadata*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Contract: `{contract_id}`\n"
        f"🏷 Name: *{name}*\n"
        f"🔤 Symbol: `{symbol}`\n"
        f"📐 Spec: `{spec}`\n"
        f"🌐 Base URI: {base_uri}\n"
        f"📄 Reference: {reference}\n"
        f"🖼 Icon: {icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [View on NEAR Explorer](https://explorer.near.org/accounts/{contract_id})"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def supply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /supply <contract_id>
    Fetch and display the total minted supply for an NFT contract.
    """
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/supply <contract_id>`\n"
            "_Example:_ `/supply x.paras.near`",
            parse_mode="Markdown",
        )
        return

    contract_id = context.args[0].strip()
    await update.message.reply_text(
        f"⏳ Fetching supply for `{contract_id}`…",
        parse_mode="Markdown",
    )

    try:
        supply = await get_nft_supply(contract_id)
        # Fetch name too for a nicer display
        try:
            meta = await get_nft_metadata(contract_id)

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("drops", drops_command))
    application.add_handler(CommandHandler("mintbase", mintbase_command))
    application.add_handler(CommandHandler("nftinfo", nftinfo_command))
    application.add_handler(CommandHandler("supply", supply_command))
    application.run_polling()

if __name__ == "__main__":
    main()
