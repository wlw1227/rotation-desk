"""
Telegram Collector
------------------
Connects to Telegram via Telethon (uses your personal account, not a bot).
Reads recent messages from curated channels and extracts narrative signals.

Setup:
  1. Go to https://my.telegram.org/apps
  2. Create an app, get API_ID and API_HASH
  3. Add to .env file
  4. First run will ask for your phone + verification code
  5. Session is saved locally — subsequent runs are automatic

Cost: FREE. Telegram API has no charges and generous limits.
"""

import os
import asyncio
import re
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional
from dotenv import load_dotenv
from rich import print as rprint

load_dotenv()

# Try importing telethon — guide user if not installed
try:
    from telethon import TelegramClient
    from telethon.errors import (
        FloodWaitError, ChannelPrivateError,
        UsernameNotOccupiedError, UsernameInvalidError,
    )
    from telethon.tl.types import Message
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

from config.channels import TELEGRAM_CHANNELS, SECTORS


def _build_keyword_patterns() -> dict[str, re.Pattern]:
    """Pre-compile regex patterns for each sector's keywords."""
    patterns = {}
    for sector_id, sector in SECTORS.items():
        keywords = sector["keywords"]
        pattern = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b',
            re.IGNORECASE
        )
        patterns[sector_id] = pattern
    return patterns


KEYWORD_PATTERNS = _build_keyword_patterns()


def score_message(text: str) -> dict[str, int]:
    """
    Count keyword hits per sector in a message.
    Returns {sector_id: hit_count}
    """
    scores = {}
    for sector_id, pattern in KEYWORD_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            scores[sector_id] = len(matches)
    return scores


def classify_sentiment(text: str) -> str:
    """
    Rough sentiment: bullish / bearish / neutral.
    Used to distinguish 'early excited' from 'warning/exit' signals.
    """
    bullish_terms = [
        'bullish', 'moon', 'pump', 'ape', 'buy', 'accumulate', 'undervalued',
        'early', 'gem', 'alpha', 'breakout', 'ripping', 'up only', 'send it',
        'rotation', 'narrative', 'next big', 'loading', 'positioned'
    ]
    bearish_terms = [
        'bearish', 'dump', 'sell', 'exit', 'caution', 'warning', 'rug',
        'overvalued', 'late', 'crowded', 'overbought', 'distribution', 'avoid',
        'scam', 'dead', 'rekt', 'wrecked', 'over', 'done', 'peaked'
    ]

    text_lower = text.lower()
    bull_count = sum(1 for t in bullish_terms if t in text_lower)
    bear_count = sum(1 for t in bearish_terms if t in text_lower)

    if bull_count > bear_count:
        return "bullish"
    elif bear_count > bull_count:
        return "bearish"
    return "neutral"


# Hours to look back per tier — research channels post infrequently so need wider window
TIER_HOURS = {"tier1": 96, "tier2": 72, "tier3": 48}


async def collect_telegram_signals(
    hours_back: int = 48,  # fallback only; per-tier windows defined in TIER_HOURS
    session_name: str = "rotation_intel"
) -> dict:
    """
    Main collection function.
    Reads messages from all configured channels using per-tier lookback windows.
    Returns structured signal data per sector per tier.
    """
    if not TELETHON_AVAILABLE:
        rprint("[yellow]Telethon not installed. Run: pip install telethon[/yellow]")
        return _mock_telegram_data()

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not all([api_id, api_hash, phone]):
        rprint("[yellow]Telegram credentials not configured — using mock data[/yellow]")
        rprint("[dim]Add TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE to .env[/dim]")
        return _mock_telegram_data()

    now = datetime.now(timezone.utc)

    # Results structure
    results = {
        "collected_at": datetime.utcnow().isoformat(),
        "hours_analyzed": TIER_HOURS,
        "sectors": {sid: {
            "tier1_mentions": 0, "tier2_mentions": 0, "tier3_mentions": 0,
            "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
            "sample_messages": [],
            "channels_mentioning": [],
        } for sid in SECTORS},
        "channel_stats": {},
        "errors": [],
    }

    client = TelegramClient(session_name, int(api_id), api_hash)

    try:
        await client.start(phone=phone)
        rprint("[green]Telegram connected[/green]")

        # ── Pre-flight: resolve all channel entities before collection ─────────
        rprint("[dim]Pre-flight: resolving channels...[/dim]")
        resolved: dict[str, object] = {}  # username -> entity
        for tier, channels in TELEGRAM_CHANNELS.items():
            for username in channels:
                if username in resolved:
                    continue
                try:
                    entity = await client.get_entity(username)
                    resolved[username] = entity
                    rprint(f"  [green]✓[/green] [dim]{username}[/dim]")
                except (ChannelPrivateError, UsernameNotOccupiedError, UsernameInvalidError) as e:
                    rprint(f"  [red]✗[/red] [dim]{username}: {type(e).__name__}[/dim]")
                    results["errors"].append(f"{username}: {type(e).__name__}")
                except Exception as e:
                    rprint(f"  [red]✗[/red] [dim]{username}: {e}[/dim]")
                    results["errors"].append(f"{username}: {e}")
                await asyncio.sleep(0.3)

        # ── Main collection loop ───────────────────────────────────────────────
        for tier, channels in TELEGRAM_CHANNELS.items():
            tier_hours = TIER_HOURS.get(tier, hours_back)
            cutoff = now - timedelta(hours=tier_hours)
            rprint(f"[cyan]Reading {tier} channels ({len(channels)}, {tier_hours}h window)...[/cyan]")

            for channel_username in channels:
                entity = resolved.get(channel_username)
                if entity is None:
                    continue  # failed pre-flight, already logged

                try:
                    messages_processed = 0
                    channel_hits = defaultdict(int)

                    async for message in client.iter_messages(
                        entity,
                        offset_date=None,
                        limit=200,  # Max per channel
                        reverse=False,
                    ):
                        if not isinstance(message, Message):
                            continue
                        if not message.text:
                            continue
                        if message.date < cutoff:
                            break  # Messages are newest first

                        messages_processed += 1
                        text = message.text
                        sector_hits = score_message(text)
                        sentiment = classify_sentiment(text)

                        for sector_id, hit_count in sector_hits.items():
                            results["sectors"][sector_id][f"{tier}_mentions"] += hit_count
                            results["sectors"][sector_id][f"{sentiment}_count"] += 1
                            channel_hits[sector_id] += hit_count

                            # Save sample message (first 3 per sector per tier1)
                            samples = results["sectors"][sector_id]["sample_messages"]
                            if len(samples) < 3 and tier == "tier1":
                                samples.append({
                                    "channel": channel_username,
                                    "tier": tier,
                                    "text": text[:300],
                                    "date": message.date.isoformat(),
                                    "sentiment": sentiment,
                                })

                    # Track which channels mentioned which sectors
                    for sector_id, hits in channel_hits.items():
                        if hits > 0:
                            results["sectors"][sector_id]["channels_mentioning"].append({
                                "channel": channel_username,
                                "tier": tier,
                                "hits": hits,
                            })

                    results["channel_stats"][channel_username] = {
                        "tier": tier,
                        "messages_processed": messages_processed,
                    }

                    rprint(f"  [dim]{channel_username}: {messages_processed} msgs[/dim]")

                    # Polite rate limiting
                    await asyncio.sleep(0.5)

                except FloodWaitError as e:
                    rprint(f"  [yellow]Rate limited on {channel_username}, waiting {e.seconds}s[/yellow]")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    rprint(f"  [red]Skip {channel_username}: {e}[/red]")
                    results["errors"].append(f"{channel_username}: {e}")

    finally:
        await client.disconnect()

    # Calculate narrative maturity scores
    results["sectors"] = _score_maturity(results["sectors"])

    rprint(f"[green]Telegram collection complete[/green]")
    return results


def _score_maturity(sectors: dict) -> dict:
    """
    Narrative maturity scoring logic based on the PDF framework:

    - High tier1, low tier3 = EARLY (this is where you want to be)
    - High tier1 + tier2, moderate tier3 = MID (still ok, watch for exit)
    - High across all tiers = LATE (crowded, exit preparing)
    - Low everywhere = DORMANT (not a rotation target)

    Sentiment skew also matters:
    - Mostly bullish tier1 = organic early excitement
    - Bearish tier1 + bullish tier3 = classic distribution warning
    """
    for sector_id, data in sectors.items():
        t1 = data["tier1_mentions"]
        t2 = data["tier2_mentions"]
        t3 = data["tier3_mentions"]
        total = t1 + t2 + t3

        if total == 0:
            data["maturity"] = "dormant"
            data["maturity_score"] = 0
            data["signal"] = "SKIP"
            continue

        # Maturity score: 0 = early, 1 = late
        # Weighted toward tier3 dominance as the late indicator
        if total > 0:
            tier3_ratio = t3 / total
            tier1_ratio = t1 / total
        else:
            tier3_ratio = tier1_ratio = 0

        maturity_score = (tier3_ratio * 0.6) + ((1 - tier1_ratio) * 0.4)
        data["maturity_score"] = round(maturity_score, 2)

        # Classify
        if maturity_score < 0.2 and t1 > 0:
            data["maturity"] = "early"
            data["signal"] = "EARLY HOT" if data["bullish_count"] > data["bearish_count"] else "EARLY CAUTION"
        elif maturity_score < 0.5:
            data["maturity"] = "mid"
            data["signal"] = "MID — WATCH"
        elif maturity_score < 0.75:
            data["maturity"] = "late"
            data["signal"] = "LATE — REDUCE"
        else:
            data["maturity"] = "crowded"
            data["signal"] = "AVOID"

        data["total_mentions"] = total

    return sectors


def _mock_telegram_data() -> dict:
    """
    Returns realistic mock data for development/testing
    when Telegram credentials aren't configured yet.
    """
    return {
        "collected_at": datetime.utcnow().isoformat(),
        "hours_analyzed": 48,
        "mock": True,
        "sectors": {
            "perp_dex": {
                "tier1_mentions": 47, "tier2_mentions": 12, "tier3_mentions": 3,
                "bullish_count": 38, "bearish_count": 5, "neutral_count": 19,
                "maturity": "early", "maturity_score": 0.15,
                "signal": "EARLY HOT", "total_mentions": 62,
                "sample_messages": [
                    {"channel": "DeFiEdge", "tier": "tier1", "sentiment": "bullish",
                     "text": "Perp DEX fees hitting new highs 6 weeks in a row. Hyperliquid doing $800M daily volume. This rotation is real and most people haven't noticed yet.",
                     "date": datetime.utcnow().isoformat()}
                ],
                "channels_mentioning": [
                    {"channel": "DeFiEdge", "tier": "tier1", "hits": 12},
                    {"channel": "gammichan", "tier": "tier1", "hits": 8},
                ]
            },
            "payfi": {
                "tier1_mentions": 23, "tier2_mentions": 8, "tier3_mentions": 2,
                "bullish_count": 18, "bearish_count": 3, "neutral_count": 12,
                "maturity": "early", "maturity_score": 0.19,
                "signal": "EARLY HOT", "total_mentions": 33,
                "sample_messages": [],
                "channels_mentioning": []
            },
            "ai_tokens": {
                "tier1_mentions": 8, "tier2_mentions": 31, "tier3_mentions": 44,
                "bullish_count": 12, "bearish_count": 28, "neutral_count": 43,
                "maturity": "crowded", "maturity_score": 0.88,
                "signal": "AVOID", "total_mentions": 83,
                "sample_messages": [],
                "channels_mentioning": []
            },
            "memecoins": {
                "tier1_mentions": 5, "tier2_mentions": 18, "tier3_mentions": 52,
                "bullish_count": 31, "bearish_count": 22, "neutral_count": 22,
                "maturity": "crowded", "maturity_score": 0.82,
                "signal": "AVOID", "total_mentions": 75,
                "sample_messages": [],
                "channels_mentioning": []
            },
            "defi_lending": {
                "tier1_mentions": 11, "tier2_mentions": 9, "tier3_mentions": 8,
                "bullish_count": 9, "bearish_count": 8, "neutral_count": 11,
                "maturity": "mid", "maturity_score": 0.48,
                "signal": "MID — WATCH", "total_mentions": 28,
                "sample_messages": [],
                "channels_mentioning": []
            },
            "rwa": {
                "tier1_mentions": 14, "tier2_mentions": 6, "tier3_mentions": 1,
                "bullish_count": 12, "bearish_count": 2, "neutral_count": 7,
                "maturity": "early", "maturity_score": 0.18,
                "signal": "EARLY HOT", "total_mentions": 21,
                "sample_messages": [],
                "channels_mentioning": []
            },
            "liquid_staking": {
                "tier1_mentions": 3, "tier2_mentions": 4, "tier3_mentions": 2,
                "bullish_count": 4, "bearish_count": 3, "neutral_count": 2,
                "maturity": "mid", "maturity_score": 0.45,
                "signal": "MID — WATCH", "total_mentions": 9,
                "sample_messages": [],
                "channels_mentioning": []
            },
        },
        "channel_stats": {"mock": True},
        "errors": [],
    }


if __name__ == "__main__":
    import json
    result = asyncio.run(collect_telegram_signals(hours_back=24))
    print(json.dumps(result, indent=2, default=str)[:3000])
