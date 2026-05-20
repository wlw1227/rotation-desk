"""
Community channels tracked for leaderboard scoring.

Two tiers:
  PUBLIC   — open Telegram channels anyone can read via API
  SPOILS   — paid communities running on Spoils (added as creators onboard)

To add a Spoils creator: set paid=True, spoils=True, and add their handle.
"""

COMMUNITIES = [

    # ── PUBLIC CHANNELS — DeFi / Rotation focus ──────────────────────────────

    {
        "name": "DeFi Million",
        "slug": "defi-million",
        "platform": "telegram",
        "handle": "DeFiMillionChannel",
        "sector_focus": ["defi_lending", "payfi", "liquid_staking"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 440000,
        "description": "Large DeFi-focused signal channel, sector rotation coverage",
    },
    {
        "name": "Miles Deutscher",
        "slug": "miles-deutscher",
        "platform": "telegram",
        "handle": "MilesDeUtscher",
        "sector_focus": ["memecoins", "ai_tokens", "perp_dex"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 85000,
        "description": "Narrative rotation analyst, known for early sector calls",
    },
    {
        "name": "Route 2 FI",
        "slug": "route2fi",
        "platform": "telegram",
        "handle": "Route2FI",
        "sector_focus": ["defi_lending", "liquid_staking", "payfi"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 45000,
        "description": "DeFi rotation focus, yield and sector analysis",
    },
    {
        "name": "DeFi Edge",
        "slug": "defi-edge",
        "platform": "telegram",
        "handle": "thedefiedge",
        "sector_focus": ["defi_lending", "liquid_staking", "rwa"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 38000,
        "description": "Early DeFi narrative signal, sector deep dives",
    },
    {
        "name": "Look On Chain",
        "slug": "lookonchain",
        "platform": "telegram",
        "handle": "lookonchain",
        "sector_focus": ["perp_dex", "defi_lending", "memecoins"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 320000,
        "description": "Whale tracking and on-chain flow analysis",
    },
    {
        "name": "Crypto Hayes",
        "slug": "crypto-hayes",
        "platform": "telegram",
        "handle": "CryptoHayes",
        "sector_focus": ["payfi", "perp_dex", "rwa"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 120000,
        "description": "Arthur Hayes macro + crypto positioning",
    },
    {
        "name": "ICO Drops",
        "slug": "ico-drops",
        "platform": "telegram",
        "handle": "ICODrops",
        "sector_focus": ["ai_tokens", "rwa", "defi_lending"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 290000,
        "description": "New token launches and early sector narrative tracking",
    },
    {
        "name": "Whale Alert",
        "slug": "whale-alert",
        "platform": "telegram",
        "handle": "WhaleAlert",
        "sector_focus": ["payfi", "defi_lending", "liquid_staking"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 760000,
        "description": "Large on-chain move tracking across sectors",
    },
    {
        "name": "Arkham Intel",
        "slug": "arkham-intel",
        "platform": "telegram",
        "handle": "arkham_intel",
        "sector_focus": ["perp_dex", "defi_lending", "ai_tokens"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 95000,
        "description": "Wallet intelligence and smart money flow tracking",
    },
    {
        "name": "CryptoQuant",
        "slug": "cryptoquant",
        "platform": "telegram",
        "handle": "CryptoQuant_Official",
        "sector_focus": ["payfi", "defi_lending", "liquid_staking"],
        "paid": False,
        "spoils": False,
        "price_usd": 0,
        "members_est": 180000,
        "description": "On-chain metrics and sector flow analysis",
    },

    # ── SPOILS CREATORS — add as they onboard ────────────────────────────────
    # Uncomment and fill in handle when a creator joins Spoils

    # {
    #     "name": "Your Community Name",
    #     "slug": "your-slug",
    #     "platform": "telegram",
    #     "handle": "YourTelegramHandle",
    #     "sector_focus": ["defi_lending"],
    #     "paid": True,
    #     "spoils": True,
    #     "price_usd": 29,
    #     "members_est": 0,
    #     "description": "Spoils creator community",
    # },
]
