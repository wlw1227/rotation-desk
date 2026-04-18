"""
Curated Telegram channels by signal tier.

TIER 1 — Early alpha (researchers, quant traders, protocol insiders)
TIER 2 — Mid signal (analysts, aggregators)
TIER 3 — Late/mainstream signal (when narratives appear here, they're maturing)

Add/remove channels based on what you find useful.
Use the @username format or channel invite links.
"""

TELEGRAM_CHANNELS = {

    # ── TIER 1: On-chain data, institutional research, macro intelligence ─────
    # Post infrequently — high signal per post. Collect 96h back.
    "tier1": [
        "defillama",           # DeFiLlama — protocol fees and TVL data
        "MessariCrypto",       # Messari — institutional research
        "glassnode",           # Glassnode — on-chain analytics
        "CryptoHayes",         # Arthur Hayes — macro + crypto positioning
        "Route2FI",            # Route 2 FI — DeFi rotation focus
        "thedefiedge",         # DeFi Edge — DeFi narrative early signal
        "CryptoQuant_Official", # CryptoQuant — on-chain metrics
        "WuBlockchain",        # Wu Blockchain — Asia/institutional flows
        "theblockresearch",    # The Block Research — institutional data
        "RaoulGMI",            # Raoul Pal — macro/institutional
        "Delphi_Digital",      # Delphi Digital — crypto research
        "NansenAI",            # Nansen — smart money on-chain
        "arkham_intel",        # Arkham — wallet intelligence
    ],

    # ── TIER 2: Analysts, aggregators, mid-tier commentary ────────────────────
    # Good for confirming narratives spreading from tier1. Collect 72h back.
    "tier2": [
        "coinbureau",          # Coin Bureau
        "Cointelegraph",       # Cointelegraph
        "CryptoSlate",         # CryptoSlate
        "TheBlock__",          # The Block news
        "DecryptMedia",        # Decrypt
        "ICODrops",            # ICO Drops — new token launches
        "WhaleAlert",          # Whale Alert — large on-chain moves
        "lookonchain",         # Look On Chain — whale tracking
        "rektfyi",             # Rekt News — protocol exploits/failures
        "DeFiMillionChannel",  # DeFi Million — DeFi narrative spread
        "CoinGecko",           # CoinGecko — market data
        "MilesDeUtscher",      # Miles Deutscher — narrative rotation analyst
    ],

    # ── TIER 3: Mainstream / late signal ──────────────────────────────────────
    # High volume here = narrative is crowded, time to exit. Collect 48h back.
    "tier3": [
        "CoinMarketCap",       # CoinMarketCap
        "binancenews",         # Binance
        "coinbase",            # Coinbase
        "CryptoCom",           # Crypto.com
        "decrypt_media",       # Decrypt
        "cointelegraph",       # Cointelegraph (volume check)
        "Bybit_Official",      # Bybit announcements
        "krakenfx",            # Kraken
        "OKX",                 # OKX exchange
    ],
}

# Sectors to track — maps to DefiLlama protocol categories
SECTORS = {
    "perp_dex": {
        "label": "Perp DEX",
        "keywords": ["perp", "perpetual", "dex", "hyperliquid", "drift", "gmx", "jupiter perp", "funding rate"],
        "defillama_category": "Derivatives",
        "color": "#00e676",
    },
    "payfi": {
        "label": "PayFi / Stablecoins",
        "keywords": ["payfi", "stablecoin", "payment", "settlement", "rails", "usdc", "usdt", "rlusd"],
        "defillama_category": "Stablecoins",
        "color": "#2979ff",
    },
    "defi_lending": {
        "label": "DeFi Lending",
        "keywords": ["lending", "borrow", "aave", "compound", "morpho", "euler", "collateral"],
        "defillama_category": "Lending",
        "color": "#888888",
    },
    "liquid_staking": {
        "label": "Liquid Staking",
        "keywords": ["lsd", "liquid staking", "lido", "eigenlayer", "restaking", "lst"],
        "defillama_category": "Liquid Staking",
        "color": "#7c4dff",
    },
    "ai_tokens": {
        "label": "AI Tokens",
        "keywords": ["ai agent", "artificial intelligence", "fetch", "render", "near ai", "bittensor"],
        "defillama_category": "AI",
        "color": "#ff3d5a",
    },
    "memecoins": {
        "label": "Memecoins",
        "keywords": ["meme", "memecoin", "dogwifhat", "pepe", "bonk", "shib", "pumpfun", "pump.fun"],
        "defillama_category": "Meme",
        "color": "#ffab00",
    },
    "rwa": {
        "label": "Real World Assets",
        "keywords": ["rwa", "real world asset", "tokenized", "treasury", "ondo", "maple", "centrifuge"],
        "defillama_category": "RWA",
        "color": "#00bcd4",
    },
}
