"""
DefiLlama Collector
-------------------
Pulls protocol fees, revenue, and TVL from DefiLlama's free API.
No API key required. Rate limit: be polite, don't hammer it.

Endpoints used:
  /overview/fees          — aggregate fees by protocol
  /overview/fees/{chain}  — chain-specific
  /protocols              — TVL + metadata for all protocols
  /protocol/{slug}        — historical data for specific protocol
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from rich import print as rprint

BASE_URL = "https://api.llama.fi"
FEES_URL = "https://api.llama.fi"


async def fetch_json(client: httpx.AsyncClient, url: str) -> Optional[dict | list]:
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        rprint(f"[red]DefiLlama fetch error {url}: {e}[/red]")
        return None


async def get_sector_fees() -> dict:
    """
    Returns fee data grouped by sector with 7d and 30d trends.
    This is the primary signal for identifying real revenue rotations.
    """
    async with httpx.AsyncClient() as client:
        data = await fetch_json(client, f"{FEES_URL}/overview/fees?excludeTotalDataChartBreakdown=true")

    if not data or "protocols" not in data:
        return {}

    # Group by category
    sectors: dict[str, dict] = {}

    for protocol in data["protocols"]:
        category = protocol.get("category", "Other")
        if not category:
            continue

        daily_fees = protocol.get("total24h") or 0
        weekly_fees = protocol.get("total7d") or 0
        monthly_fees = protocol.get("total30d") or 0

        if category not in sectors:
            sectors[category] = {
                "category": category,
                "protocols": [],
                "total_24h": 0,
                "total_7d": 0,
                "total_30d": 0,
                "protocol_count": 0,
            }

        sectors[category]["total_24h"] += daily_fees
        sectors[category]["total_7d"] += weekly_fees
        sectors[category]["total_30d"] += monthly_fees
        sectors[category]["protocol_count"] += 1
        sectors[category]["protocols"].append({
            "name": protocol.get("name"),
            "slug": protocol.get("module"),
            "24h": daily_fees,
            "7d": weekly_fees,
            "30d": monthly_fees,
            "chains": protocol.get("chains", []),
        })

    # Calculate week-over-week trend
    # 7d total vs prior 7d (approximated from 30d - 7d)
    for cat, data in sectors.items():
        prior_7d = data["total_30d"] - data["total_7d"]
        prior_7d_avg = prior_7d / 3  # rough 3 prior weeks
        current_7d = data["total_7d"]

        if prior_7d_avg > 0:
            wow_change = ((current_7d - prior_7d_avg) / prior_7d_avg) * 100
        else:
            wow_change = 0

        data["wow_change_pct"] = round(wow_change, 1)

        # Sort protocols by 7d fees descending
        data["protocols"] = sorted(data["protocols"], key=lambda x: x["7d"], reverse=True)[:10]

    return sectors


async def get_top_protocols_by_revenue(limit: int = 30) -> list[dict]:
    """
    Returns top protocols ranked by revenue (fees kept by protocol, not paid to LPs).
    Key for identifying 'real revenue' rotation candidates.
    """
    async with httpx.AsyncClient() as client:
        data = await fetch_json(
            client,
            f"{FEES_URL}/overview/fees?excludeTotalDataChartBreakdown=true"
        )

    if not data or "protocols" not in data:
        return []

    protocols = []
    for p in data["protocols"]:
        revenue_7d = p.get("revenue7d") or p.get("total7d") or 0
        if revenue_7d < 100_000:  # Skip tiny protocols
            continue

        protocols.append({
            "name": p.get("name"),
            "category": p.get("category"),
            "revenue_7d": revenue_7d,
            "fees_7d": p.get("total7d") or 0,
            "fees_24h": p.get("total24h") or 0,
            "chains": p.get("chains", []),
            # Revenue ratio = how much the protocol keeps (not LPs)
            # High ratio = protocol has pricing power
            "revenue_ratio": round(
                (revenue_7d / p["total7d"] * 100) if p.get("total7d") else 0, 1
            ),
        })

    return sorted(protocols, key=lambda x: x["revenue_7d"], reverse=True)[:limit]


async def get_protocol_trend(slug: str, days: int = 30) -> dict:
    """
    Gets historical fee data for a specific protocol to detect multi-week trends.
    This confirms whether fee growth is sustained (real signal) vs. a spike (noise).
    """
    async with httpx.AsyncClient() as client:
        data = await fetch_json(client, f"{FEES_URL}/summary/fees/{slug}")

    if not data:
        return {}

    total_data = data.get("totalDataChartBreakdown") or data.get("totalDataChart") or []

    if not total_data:
        return {}

    # Get last N days
    recent = total_data[-days:] if len(total_data) >= days else total_data

    # Calculate weekly buckets
    weekly_totals = []
    for i in range(0, len(recent), 7):
        week = recent[i:i+7]
        if isinstance(week[0], list):
            total = sum(w[1] for w in week if len(w) > 1)
        else:
            total = sum(week)
        weekly_totals.append(total)

    # Check if trend is consistently up
    if len(weekly_totals) >= 3:
        weeks_positive = sum(
            1 for i in range(1, len(weekly_totals))
            if weekly_totals[i] > weekly_totals[i-1]
        )
        trend_score = weeks_positive / (len(weekly_totals) - 1)  # 0-1, 1 = all weeks up
    else:
        trend_score = 0.5

    return {
        "slug": slug,
        "weekly_totals": weekly_totals,
        "trend_score": round(trend_score, 2),  # >0.7 = sustained uptrend
        "weeks_analyzed": len(weekly_totals),
        "latest_week": weekly_totals[-1] if weekly_totals else 0,
        "prior_week": weekly_totals[-2] if len(weekly_totals) >= 2 else 0,
    }


async def get_tvl_flows() -> dict:
    """
    TVL changes indicate where capital is rotating.
    Rising fees + rising TVL = strong conviction signal.
    Rising fees + falling TVL = protocol extracting from declining base (weaker).
    """
    async with httpx.AsyncClient() as client:
        data = await fetch_json(client, f"{BASE_URL}/protocols")

    if not data:
        return {}

    flows_by_category: dict[str, dict] = {}

    for protocol in data:
        category = protocol.get("category", "Other")
        if not category:
            continue

        tvl = protocol.get("tvl") or 0
        change_1d = protocol.get("change_1d") or 0
        change_7d = protocol.get("change_7d") or 0
        change_1m = protocol.get("change_1m") or 0

        if category not in flows_by_category:
            flows_by_category[category] = {
                "category": category,
                "total_tvl": 0,
                "weighted_change_7d": 0,
                "protocol_count": 0,
            }

        flows_by_category[category]["total_tvl"] += tvl
        flows_by_category[category]["protocol_count"] += 1
        # Weight by TVL size
        flows_by_category[category]["weighted_change_7d"] += change_7d * tvl

    # Normalize weighted changes
    for cat, data in flows_by_category.items():
        if data["total_tvl"] > 0:
            data["avg_change_7d"] = round(
                data["weighted_change_7d"] / data["total_tvl"], 2
            )
        else:
            data["avg_change_7d"] = 0
        del data["weighted_change_7d"]

    return flows_by_category


async def collect_all() -> dict:
    """Main collection function — runs all collectors in parallel."""
    rprint("[cyan]Collecting DefiLlama data...[/cyan]")

    sector_fees, top_protocols, tvl_flows = await asyncio.gather(
        get_sector_fees(),
        get_top_protocols_by_revenue(),
        get_tvl_flows(),
    )

    result = {
        "collected_at": datetime.utcnow().isoformat(),
        "sector_fees": sector_fees,
        "top_revenue_protocols": top_protocols,
        "tvl_flows": tvl_flows,
    }

    rprint(f"[green]DefiLlama: {len(sector_fees)} sectors, {len(top_protocols)} protocols[/green]")
    return result


if __name__ == "__main__":
    # Test run
    import json
    result = asyncio.run(collect_all())
    print(json.dumps(result, indent=2, default=str)[:3000])
