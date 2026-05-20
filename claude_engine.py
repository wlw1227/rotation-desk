"""
Claude Synthesis Engine
-----------------------
This is the AI brain of the system. It takes raw data from all collectors
and produces structured, actionable rotation intelligence.

Three outputs:
  1. Weekly briefing  — plain English rotation read
  2. Sector scores    — ranked signals with confidence levels
  3. Position guidance — specific entry/exit/sizing suggestions

Cost per run: ~$0.05-0.15 using claude-sonnet-4-5
At daily runs: ~$2-5/month total.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from rich import print as rprint

load_dotenv()

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from config.channels import SECTORS


SYSTEM_PROMPT = """You are a crypto rotation analyst. Your job is to identify where liquidity is rotating BEFORE it becomes obvious.

You follow a specific framework based on how modern crypto markets actually work:
- The market moves in fast rotations, not one big altseason wave
- Token supply is massively diluted (5,300 new tokens/day), so attention concentrates in 1-2 sectors at a time
- Old strategy (hold and pray) is dead. New strategy: spot rotation early → ride it → exit before it's obvious → repeat
- 100x comes from stacking correct rotations, not finding one magic coin

The cycle always rhymes: Value/Revenue → Helicopter Money → Casino/Memes → Dump → Structured Extraction → repeat

Key signals you weight:
1. Fee/revenue trends (sustained multi-week growth = real, one week spike = noise)
2. Organic user return (without incentives = real conviction)
3. Narrative maturity (tier1 only = early, spreading to tier3 = late, run)  
4. TVL flows (capital moving in = conviction, moving out = distribution)
5. Sentiment in early channels (excited discovery tone = early, explaining-to-newcomers tone = late)

You output structured JSON only. No prose outside the JSON fields.
Be direct, specific, and actionable. Avoid vague language like "could potentially".
If signals conflict, say so explicitly rather than hedging.
"""

ANALYSIS_PROMPT = """Analyze the following data and produce a rotation intelligence briefing.

## ON-CHAIN DATA (DefiLlama)
{defillama_summary}

## NARRATIVE DATA (Telegram channels, tiered by influence)
{telegram_summary}

## REDDIT SIGNALS (late indicator)
{reddit_summary}

## TODAY'S DATE
{date}

Produce a JSON response with this exact structure:
{{
  "briefing_date": "YYYY-MM-DD",
  "market_phase": {{
    "current": "value_revenue | helicopter_money | casino | dump | extraction",
    "confidence": 0.0-1.0,
    "reasoning": "1-2 sentences on why you assessed this phase"
  }},
  "rotation_targets": [
    {{
      "sector": "sector name",
      "signal": "EARLY HOT | EARLY | MID | LATE | AVOID",
      "confidence": 0.0-1.0,
      "why_now": "specific reason this sector is a rotation target right now",
      "key_data_points": ["specific data point 1", "specific data point 2"],
      "layer_suggestions": {{
        "beta": "name of liquid market leader to play as beta position",
        "shovel": "pick-and-shovel infra play that wins either way",
        "flyer": "small cap that fits the narrative perfectly"
      }},
      "invalidation": "specific condition that would make this trade wrong",
      "time_horizon": "estimated weeks before this rotation matures/crowds"
    }}
  ],
  "sectors_to_avoid": [
    {{
      "sector": "sector name",
      "reason": "specific reason to avoid right now",
      "reconsider_when": "specific condition that would flip this"
    }}
  ],
  "weekly_actions": [
    "Specific action item 1",
    "Specific action item 2",
    "Specific action item 3"
  ],
  "narrative_alerts": [
    {{
      "alert": "description of narrative shift detected",
      "urgency": "high | medium | low",
      "source_tier": "tier1 | tier2 | tier3"
    }}
  ],
  "meta_read": "2-3 sentence plain English summary a trader can read in 30 seconds and act on",
  "data_quality": {{
    "defillama": "good | limited | unavailable",
    "telegram": "good | limited | unavailable",
    "reddit": "good | limited | unavailable",
    "overall_confidence": "high | medium | low",
    "caveats": "any data gaps or reliability issues to note"
  }}
}}

Be specific with token names where appropriate. Prioritize actionability over completeness.
Only include rotation_targets where signal is EARLY HOT or EARLY.
Limit rotation_targets to maximum 2 (the PDF framework says max 2 rotations at once).
"""


def _format_defillama_for_prompt(data: dict) -> str:
    """Condense DefiLlama data into prompt-friendly text."""
    if not data:
        return "No DefiLlama data available."

    lines = []

    # Top revenue protocols
    if data.get("top_revenue_protocols"):
        lines.append("TOP REVENUE PROTOCOLS (7d):")
        for p in data["top_revenue_protocols"][:15]:
            lines.append(
                f"  {p['name']} ({p.get('category','?')}): "
                f"${p['revenue_7d']:,.0f} revenue, "
                f"${p['fees_7d']:,.0f} fees"
            )

    # Sector fee trends
    if data.get("sector_fees"):
        lines.append("\nSECTOR FEE TRENDS (7d):")
        sectors_sorted = sorted(
            data["sector_fees"].items(),
            key=lambda x: x[1].get("total_7d", 0),
            reverse=True
        )
        for cat, sdata in sectors_sorted[:10]:
            wow = sdata.get("wow_change_pct", 0)
            direction = "↑" if wow > 0 else "↓"
            lines.append(
                f"  {cat}: ${sdata['total_7d']:,.0f} 7d fees | "
                f"{direction}{abs(wow):.1f}% WoW | "
                f"{sdata['protocol_count']} protocols"
            )

    # TVL flows
    if data.get("tvl_flows"):
        lines.append("\nTVL FLOWS (7d change):")
        flows_sorted = sorted(
            data["tvl_flows"].items(),
            key=lambda x: x[1].get("avg_change_7d", 0),
            reverse=True
        )
        for cat, fdata in flows_sorted[:8]:
            if fdata.get("total_tvl", 0) > 10_000_000:  # Only >$10M TVL
                lines.append(
                    f"  {cat}: ${fdata['total_tvl']/1e9:.1f}B TVL | "
                    f"{fdata['avg_change_7d']:+.1f}% 7d"
                )

    return "\n".join(lines)


def _format_telegram_for_prompt(data: dict) -> str:
    """Condense Telegram data into prompt-friendly text."""
    if not data or not data.get("sectors"):
        return "No Telegram data available."

    lines = [f"Hours analyzed: {data.get('hours_analyzed', 48)}"]
    if data.get("mock"):
        lines.append("⚠️ MOCK DATA — configure Telegram credentials for real data")

    lines.append("\nSECTOR NARRATIVE SIGNALS:")

    sectors_sorted = sorted(
        data["sectors"].items(),
        key=lambda x: x[1].get("total_mentions", 0),
        reverse=True
    )

    for sector_id, sdata in sectors_sorted:
        sector_label = SECTORS.get(sector_id, {}).get("label", sector_id)
        t1 = sdata.get("tier1_mentions", 0)
        t2 = sdata.get("tier2_mentions", 0)
        t3 = sdata.get("tier3_mentions", 0)
        total = sdata.get("total_mentions", t1 + t2 + t3)
        maturity = sdata.get("maturity", "unknown")
        signal = sdata.get("signal", "?")
        bull = sdata.get("bullish_count", 0)
        bear = sdata.get("bearish_count", 0)

        lines.append(
            f"\n  {sector_label} | {signal} | maturity: {maturity}"
            f"\n    Tier1(alpha): {t1} | Tier2(analysts): {t2} | Tier3(mainstream): {t3}"
            f"\n    Sentiment: {bull} bullish / {bear} bearish"
        )

        # Include sample messages from tier1 (most valuable)
        samples = sdata.get("sample_messages", [])
        if samples:
            lines.append(f"    Sample tier1 message: \"{samples[0]['text'][:200]}\"")

    return "\n".join(lines)


def _format_reddit_for_prompt(data: dict) -> str:
    """Condense Reddit data into prompt-friendly text."""
    if not data:
        return "No Reddit data available (optional — configure REDDIT_CLIENT_ID to enable)."

    lines = ["REDDIT SIGNALS (late indicator — high here = narrative maturing):"]
    for sector_id, sdata in data.items():
        sector_label = SECTORS.get(sector_id, {}).get("label", sector_id)
        early = sdata.get("early_mentions", 0)
        late = sdata.get("late_mentions", 0)
        if early + late > 0:
            lines.append(f"  {sector_label}: {early} early-sub mentions | {late} mainstream-sub mentions")

    return "\n".join(lines) if len(lines) > 1 else "Reddit: no significant signals."


async def synthesize(
    defillama_data: dict,
    telegram_data: dict,
    reddit_data: dict = None,
) -> dict:
    """
    Main synthesis function. Feeds all collector data into Claude
    and returns structured rotation intelligence.
    """
    if not ANTHROPIC_AVAILABLE:
        rprint("[yellow]Anthropic SDK not installed: pip install anthropic[/yellow]")
        return _mock_synthesis()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        rprint("[yellow]ANTHROPIC_API_KEY not set — using mock synthesis[/yellow]")
        return _mock_synthesis()

    # Format data for prompt
    defillama_summary = _format_defillama_for_prompt(defillama_data)
    telegram_summary = _format_telegram_for_prompt(telegram_data)
    reddit_summary = _format_reddit_for_prompt(reddit_data or {})

    prompt = ANALYSIS_PROMPT.format(
        defillama_summary=defillama_summary,
        telegram_summary=telegram_summary,
        reddit_summary=reddit_summary,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
    )

    rprint("[cyan]Running Claude synthesis...[/cyan]")

    client = anthropic.Anthropic(api_key=api_key)

    # Run synchronously in thread pool to not block async loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    )

    raw_text = response.content[0].text.strip()

    # Parse JSON response
    try:
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        rprint(f"[red]JSON parse error: {e}[/red]")
        rprint(f"[dim]Raw response: {raw_text[:500]}[/dim]")
        result = {"error": str(e), "raw": raw_text}

    # Add metadata
    result["synthesized_at"] = datetime.utcnow().isoformat()
    result["input_tokens"] = response.usage.input_tokens
    result["output_tokens"] = response.usage.output_tokens
    result["estimated_cost_usd"] = round(
        (response.usage.input_tokens * 0.000003) +
        (response.usage.output_tokens * 0.000015), 4
    )

    rprint(f"[green]Synthesis complete — ${result['estimated_cost_usd']} | "
           f"{result['input_tokens']}in / {result['output_tokens']}out tokens[/green]")

    return result


def _mock_synthesis() -> dict:
    """Realistic mock synthesis output for development."""
    return {
        "briefing_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "mock": True,
        "market_phase": {
            "current": "value_revenue",
            "confidence": 0.78,
            "reasoning": "Perp DEX fees hitting 6-week highs with organic user return. Market rewarding real revenue after casino dump. Helicopter money signal not yet visible."
        },
        "rotation_targets": [
            {
                "sector": "Perp DEX",
                "signal": "EARLY HOT",
                "confidence": 0.82,
                "why_now": "6 consecutive weeks of fee growth, organic DAU up 22% without incentives, narrative still sub-top-20 in CT. Classic early rotation profile.",
                "key_data_points": [
                    "Perp DEX sector fees +34% WoW, 6 weeks sustained",
                    "Tier1 mentions: 47 vs Tier3: 3 — narrative very early",
                    "Hyperliquid doing $800M daily volume with real buybacks"
                ],
                "layer_suggestions": {
                    "beta": "HYPE (Hyperliquid) — liquid market leader with proven fee buyback model",
                    "shovel": "JUP (Jupiter) — aggregator that benefits from all Solana perp volume",
                    "flyer": "DRIFT — smaller perp DEX with similar model, lower MC, more upside"
                },
                "invalidation": "Weekly fees decline 2 consecutive weeks OR narrative hits top-10 CT mentions OR major unlock event",
                "time_horizon": "4-8 weeks before this becomes crowded based on typical rotation speed"
            },
            {
                "sector": "PayFi / Stablecoins",
                "signal": "EARLY",
                "confidence": 0.61,
                "why_now": "Tier1 researchers starting to discuss payment rails narrative. DefiLlama showing stablecoin TVL inflows. Too early for confirmation but worth watching.",
                "key_data_points": [
                    "23 tier1 mentions vs 2 tier3 — very early",
                    "Stablecoin TVL +8% 7d across chains",
                    "Multiple payment protocol announcements in last 2 weeks"
                ],
                "layer_suggestions": {
                    "beta": "ONDO — tokenized RWA leader with institutional backing",
                    "shovel": "USDC-adjacent infra plays (Circle ecosystem)",
                    "flyer": "Smaller PayFi protocols with <$50M MC when narrative confirms"
                },
                "invalidation": "Fee growth doesn't materialize in 3 weeks OR narrative stays dormant in tier2",
                "time_horizon": "6-12 weeks — earlier stage, less certain"
            }
        ],
        "sectors_to_avoid": [
            {
                "sector": "AI Tokens",
                "reason": "88 total mentions but tier3 dominant (44 vs 8 tier1). Bearish sentiment increasing in smart money channels. Classic late distribution profile.",
                "reconsider_when": "Tier1 mentions recover to 3x tier3 levels with fresh catalyst"
            },
            {
                "sector": "Alt L1/L2",
                "reason": "No fee growth, TVL outflows, narrative dead in all tiers. High FDV tokens with unlocks incoming.",
                "reconsider_when": "New chain achieves genuine fee milestone with organic users"
            }
        ],
        "weekly_actions": [
            "Monitor Perp DEX weekly fees — if growth continues week 7, increase position sizing",
            "Watch for PayFi narrative to appear in tier2 channels — that's your confirmation signal to size in",
            "Set price alerts on HYPE at -15% from entry as invalidation trigger",
        ],
        "narrative_alerts": [
            {
                "alert": "PayFi narrative appearing in tier1 channels for first time this cycle",
                "urgency": "medium",
                "source_tier": "tier1"
            },
            {
                "alert": "AI token sentiment turning bearish in tier1 while tier3 remains bullish — classic distribution warning",
                "urgency": "high",
                "source_tier": "tier1"
            }
        ],
        "meta_read": "Market is in value/revenue phase. Perp DEX is the confirmed rotation — early, organic, real fees. PayFi is the one to watch building behind it. Everything else is either late or dead. Max 2 positions: HYPE stack + small PayFi watch.",
        "data_quality": {
            "defillama": "good",
            "telegram": "limited",
            "reddit": "unavailable",
            "overall_confidence": "medium",
            "caveats": "Telegram using mock data — connect real credentials for live narrative signals"
        },
        "synthesized_at": datetime.utcnow().isoformat(),
        "estimated_cost_usd": 0.0,
    }


if __name__ == "__main__":
    # Test with mock data
    result = asyncio.run(synthesize({}, {}))
    print(json.dumps(result, indent=2, default=str))
