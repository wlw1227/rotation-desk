"""
Community Tracker
-----------------
Reads Telegram channels from COMMUNITIES config and extracts
timestamped sector mentions. Used to score narrative lead time
against DefiLlama breakout events.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from rich import print as rprint

from config.channels import SECTORS
from config.communities import COMMUNITIES


async def collect_community_signals(hours_back: int = 720) -> dict:
    """
    Collect last N hours of messages from community Telegram channels.
    Returns dict keyed by community slug with timestamped sector mentions.
    720 hours = 30 days rolling window.
    """
    try:
        from telethon import TelegramClient
        from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError
    except ImportError:
        rprint("[red]Telethon not available[/red]")
        return _mock_community_signals()

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        rprint("[yellow]Telegram credentials not set — using mock community data[/yellow]")
        return _mock_community_signals()

    session_file = str(Path(os.getcwd()) / "rotation_intel.session")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    results = {}

    try:
        client = TelegramClient(session_file, int(api_id), api_hash)
        await client.start()

        for community in COMMUNITIES:
            handle = community.get("handle")
            slug = community["slug"]
            results[slug] = {
                "name": community["name"],
                "slug": slug,
                "platform": community["platform"],
                "paid": community["paid"],
                "price_usd": community["price_usd"],
                "members_est": community["members_est"],
                "sector_focus": community["sector_focus"],
                "sector_mentions": {},  # sector_id -> list of timestamps
                "message_count": 0,
                "collection_error": None,
            }

            if not handle:
                results[slug]["collection_error"] = "discord_not_supported"
                continue

            try:
                rprint(f"[cyan]Community: {community['name']} (@{handle})[/cyan]")
                entity = await client.get_entity(handle)
                messages = []

                async for msg in client.iter_messages(entity, limit=500):
                    if not msg.date or msg.date < cutoff:
                        break
                    if msg.text:
                        messages.append({
                            "text": msg.text.lower(),
                            "timestamp": msg.date.isoformat(),
                            "ts": msg.date,
                        })

                results[slug]["message_count"] = len(messages)

                # Score each message against sector keywords
                for sector_id, sector_cfg in SECTORS.items():
                    keywords = sector_cfg.get("keywords", [])
                    mentions = []
                    for msg in messages:
                        if any(kw.lower() in msg["text"] for kw in keywords):
                            mentions.append(msg["timestamp"])
                    if mentions:
                        results[slug]["sector_mentions"][sector_id] = sorted(mentions)

                rprint(f"[green]  {len(messages)} messages, {len(results[slug]['sector_mentions'])} sectors mentioned[/green]")

            except (ChannelPrivateError, UsernameNotOccupiedError) as e:
                rprint(f"[yellow]  Skip {handle}: {e}[/yellow]")
                results[slug]["collection_error"] = str(e)
            except Exception as e:
                rprint(f"[red]  Error {handle}: {e}[/red]")
                results[slug]["collection_error"] = str(e)

        await client.disconnect()

    except Exception as e:
        rprint(f"[red]Community tracker error: {e}[/red]")
        return _mock_community_signals()

    # If every community errored with no messages, fall back to mock data
    all_errored = all(
        v.get("collection_error") and v.get("message_count", 0) == 0
        for v in results.values()
    ) if results else True
    if all_errored:
        rprint("[yellow]All community channels failed — using mock data[/yellow]")
        return _mock_community_signals()
    return results


def _mock_community_signals() -> dict:
    """Returns realistic mock data when Telegram is unavailable."""
    from datetime import timezone
    import random

    now = datetime.now(timezone.utc)
    results = {}

    mock_scores = {
        "base-alphas":      {"payfi": 8, "memecoins": 12, "perp_dex": 3},
        "agent-watch":      {"ai_tokens": 15, "rwa": 2},
        "defi-desk":        {"defi_lending": 18, "perp_dex": 9},
        "alpha-station":    {"payfi": 11, "defi_lending": 7, "ai_tokens": 5},
        "rotation-callers": {"perp_dex": 14, "memecoins": 8, "payfi": 6},
        "meme-desk":        {"memecoins": 22, "perp_dex": 4},
        "chain-signals":    {"rwa": 9, "defi_lending": 5},
    }

    for community in COMMUNITIES:
        slug = community["slug"]
        sector_mentions = {}
        for sector_id, count in mock_scores.get(slug, {}).items():
            # Spread mentions over last 30 days
            mentions = []
            for _ in range(count):
                days_ago = random.randint(0, 29)
                hours_ago = random.randint(0, 23)
                ts = now - timedelta(days=days_ago, hours=hours_ago)
                mentions.append(ts.isoformat())
            sector_mentions[sector_id] = sorted(mentions)

        results[slug] = {
            "name": community["name"],
            "slug": slug,
            "platform": community["platform"],
            "paid": community["paid"],
            "price_usd": community["price_usd"],
            "members_est": community["members_est"],
            "sector_focus": community["sector_focus"],
            "sector_mentions": sector_mentions,
            "message_count": sum(len(v) for v in sector_mentions.values()),
            "collection_error": "mock_data",
        }

    return results
