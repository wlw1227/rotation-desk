"""
Community Scorer
----------------
Scores communities by comparing their sector mention timestamps
against DefiLlama breakout events. Computes:
  - Narrative lead time (days early vs breakout)
  - Hit rate (% of mentions that preceded a real move)
  - Narrative score (0-100 composite)
  - Current sector focus
  - Notable calls with outcomes
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from rich import print as rprint


BREAKOUT_THRESHOLD_PCT = 15.0  # WoW fee growth required to confirm breakout
LOOKFORWARD_DAYS = 14           # Window after mention to check for breakout
MIN_CALLS_FOR_RANKING = 3       # Minimum calls to appear on leaderboard


def score_communities(
    community_signals: dict,
    defillama_data: dict,
    historical_defillama: Optional[list] = None,
) -> list[dict]:
    """
    Main scoring function.
    Returns list of scored community dicts, sorted by narrative_score desc.
    """
    # Build sector breakout map from current DefiLlama data
    breakouts = _build_breakout_map(defillama_data)
    scored = []

    for slug, data in community_signals.items():
        score = _score_community(data, breakouts)
        if score:
            scored.append(score)

    # Sort by narrative score descending
    scored.sort(key=lambda x: x["narrative_score"], reverse=True)

    # Assign ranks
    for i, s in enumerate(scored):
        s["rank"] = i + 1

    return scored


def _build_breakout_map(defillama_data: dict) -> dict:
    """
    Identifies which sectors currently have breakout-level fee growth.
    Returns dict: sector_id -> {confirmed: bool, wow_pct: float, confirmed_at: str}
    """
    sector_fees = defillama_data.get("sector_fees", {})
    breakouts = {}

    # Map DefiLlama category names to our sector IDs
    category_to_sector = {
        "Derivatives":        "perp_dex",
        "Dexs":               "perp_dex",
        "Lending":            "defi_lending",
        "Liquid Staking":     "liquid_staking",
        "Stablecoin Issuer":  "payfi",
        "Chain":              "payfi",
        "Meme":               "memecoins",
        "RWA":                "rwa",
        "AI":                 "ai_tokens",
    }

    for category, data in sector_fees.items():
        sector_id = category_to_sector.get(category)
        if not sector_id:
            # Fuzzy match
            cat_lower = category.lower()
            if any(k in cat_lower for k in ["perp", "deriv", "dex"]):
                sector_id = "perp_dex"
            elif any(k in cat_lower for k in ["lend", "borrow"]):
                sector_id = "defi_lending"
            elif any(k in cat_lower for k in ["stake", "lsd", "liquid"]):
                sector_id = "liquid_staking"
            elif any(k in cat_lower for k in ["stable", "payfi", "payment"]):
                sector_id = "payfi"
            elif any(k in cat_lower for k in ["meme", "launch"]):
                sector_id = "memecoins"
            elif any(k in cat_lower for k in ["rwa", "real world"]):
                sector_id = "rwa"
            elif any(k in cat_lower for k in ["ai", "agent"]):
                sector_id = "ai_tokens"
            else:
                continue

        wow = data.get("wow_change_pct", 0) or 0
        confirmed = wow >= BREAKOUT_THRESHOLD_PCT

        if sector_id not in breakouts or breakouts[sector_id]["wow_pct"] < wow:
            breakouts[sector_id] = {
                "confirmed": confirmed,
                "wow_pct": wow,
                "confirmed_at": datetime.now(timezone.utc).isoformat() if confirmed else None,
                "category": category,
            }

    return breakouts


def _score_community(data: dict, breakouts: dict) -> Optional[dict]:
    """Score a single community against breakout data."""
    slug = data.get("slug")
    sector_mentions = data.get("sector_mentions", {})
    total_mentions = sum(len(v) for v in sector_mentions.values())

    if total_mentions < MIN_CALLS_FOR_RANKING:
        return None

    now = datetime.now(timezone.utc)
    hit_count = 0
    miss_count = 0
    lead_times = []
    notable_calls = []

    for sector_id, timestamps in sector_mentions.items():
        breakout = breakouts.get(sector_id, {})
        breakout_confirmed = breakout.get("confirmed", False)
        wow_pct = breakout.get("wow_pct", 0)

        if not timestamps:
            continue

        # First mention of this sector by this community
        first_mention_str = min(timestamps)
        try:
            first_mention = datetime.fromisoformat(first_mention_str.replace("Z", "+00:00"))
            if first_mention.tzinfo is None:
                first_mention = first_mention.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        days_ago = (now - first_mention).days

        if breakout_confirmed:
            # This sector broke out AND community was talking about it
            # Estimate lead time from first mention to breakout
            # Since we don't have historical breakout timestamps, use WoW as proxy:
            # high WoW = recent breakout = shorter lead time
            estimated_lead_days = max(1, min(14, round(14 * (1 - min(wow_pct, 50) / 50))))
            lead_times.append(estimated_lead_days)
            hit_count += 1

            notable_calls.append({
                "sector": sector_id,
                "sector_label": _sector_label(sector_id),
                "first_mention": first_mention_str,
                "mention_count": len(timestamps),
                "lead_days": estimated_lead_days,
                "outcome": "confirmed_move",
                "wow_pct": round(wow_pct, 1),
            })
        else:
            miss_count += 1
            notable_calls.append({
                "sector": sector_id,
                "sector_label": _sector_label(sector_id),
                "first_mention": first_mention_str,
                "mention_count": len(timestamps),
                "lead_days": None,
                "outcome": "no_move",
                "wow_pct": round(wow_pct, 1),
            })

    total_scored = hit_count + miss_count
    if total_scored == 0:
        return None

    hit_rate = round((hit_count / total_scored) * 100)
    avg_lead = round(sum(lead_times) / len(lead_times), 1) if lead_times else 0

    # Narrative score: weighted composite
    # 35% lead time (normalized to 14 day max)
    # 30% hit rate
    # 20% call frequency (normalized to 20 calls)
    # 15% sector diversity
    lead_score   = min(avg_lead / 14, 1.0) * 35
    hit_score    = (hit_rate / 100) * 30
    freq_score   = min(total_mentions / 20, 1.0) * 20
    div_score    = min(len(sector_mentions) / 4, 1.0) * 15
    narrative_score = round(lead_score + hit_score + freq_score + div_score)

    # Current focus = most mentioned sector in last 7 days
    recent_cutoff = now - timedelta(days=7)
    recent_counts = {}
    for sector_id, timestamps in sector_mentions.items():
        recent = [
            t for t in timestamps
            if _parse_ts(t) and _parse_ts(t) > recent_cutoff
        ]
        if recent:
            recent_counts[sector_id] = len(recent)

    current_focus = max(recent_counts, key=recent_counts.get) if recent_counts else (
        list(sector_mentions.keys())[0] if sector_mentions else None
    )

    # Timing label
    if avg_lead >= 7:
        timing = "early"
    elif avg_lead >= 3:
        timing = "ontime"
    else:
        timing = "late"

    return {
        "name": data["name"],
        "slug": slug,
        "platform": data["platform"],
        "paid": data["paid"],
        "price_usd": data["price_usd"],
        "members_est": data["members_est"],
        "sector_focus": data["sector_focus"],
        "narrative_score": narrative_score,
        "hit_rate": hit_rate,
        "avg_lead_days": avg_lead,
        "calls_tracked": total_mentions,
        "timing": timing,
        "current_focus": current_focus,
        "current_focus_label": _sector_label(current_focus) if current_focus else "—",
        "notable_calls": sorted(notable_calls, key=lambda x: x["lead_days"] or 0, reverse=True)[:5],
        "collection_error": data.get("collection_error"),
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_ts(ts_str: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _sector_label(sector_id: Optional[str]) -> str:
    labels = {
        "perp_dex":       "Perp DEX",
        "payfi":          "PayFi / Stables",
        "defi_lending":   "DeFi Lending",
        "liquid_staking": "Liquid Staking",
        "ai_tokens":      "AI Tokens",
        "memecoins":      "Memecoins",
        "rwa":            "RWA",
    }
    return labels.get(sector_id or "", sector_id or "—")
