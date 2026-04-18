# Rotation Intel

Crypto rotation intelligence system. Monitors Telegram channels and on-chain fee data, synthesizes signals with Claude AI, surfaces the 1-2 rotation targets worth trading.

Based on the framework: spot rotation early → ride it → exit before obvious → repeat.

---

## How it works

```
Telegram channels (free)     DefiLlama API (free)
       ↓                            ↓
  Narrative signals          Fee/revenue trends
       ↓                            ↓
           Claude Synthesis Engine
                    ↓
         Rotation Intelligence
         - Market phase assessment
         - 1-2 sector targets (max)
         - 3-layer position suggestions (beta/shovel/flyer)
         - Invalidation conditions
         - Weekly action items
                    ↓
          Live Dashboard (WebSocket)
```

---

## Quick start

```bash
# 1. Clone / download this folder
# 2. Run setup
chmod +x run.sh
./run.sh

# 3. Edit .env with your credentials (script will prompt)
# 4. Run again
./run.sh
```

---

## Credentials needed

| Service | Required | Cost | Where to get |
|---------|----------|------|--------------|
| Anthropic API | Yes (for AI synthesis) | ~$2-5/month | console.anthropic.com |
| Telegram API | Recommended | Free | my.telegram.org/apps |
| Reddit API | Optional | Free | reddit.com/prefs/apps |

Without Anthropic key: system runs with mock synthesis output.  
Without Telegram: narrative signals use mock data, on-chain data still live.

---

## Customizing channels

Edit `config/channels.py` to add/remove Telegram channels.

**Tier 1** = early signal (researchers, quant traders)  
**Tier 2** = mid signal (analysts, larger accounts)  
**Tier 3** = late signal (mainstream, media)

Narrative maturity is scored by the ratio across tiers:
- High T1, low T3 = EARLY (entry signal)
- High T3, declining T1 = LATE (exit signal)

---

## Customizing sectors

Also in `config/channels.py` — add keywords and DefiLlama categories for sectors you want to track.

---

## Architecture

```
rotation-intel/
├── server.py              # FastAPI server + scheduler
├── run.sh                 # Setup + start script
├── requirements.txt
├── .env.example
│
├── collectors/
│   ├── defillama.py       # On-chain fee/revenue/TVL data
│   ├── telegram.py        # Narrative signal collection
│   └── reddit.py          # Late signal (optional)
│
├── synthesis/
│   └── claude_engine.py   # AI synthesis — feeds all data into Claude
│
├── config/
│   └── channels.py        # Telegram channels + sector definitions
│
└── dashboard/
    └── index.html         # Live dashboard (WebSocket connected)
```

---

## Pipeline schedule

Default: runs every 6 hours automatically.  
On-demand: click **▶ RUN NOW** in dashboard or hit `GET /api/run`.

Each run costs approximately $0.05-0.15 in Claude API fees.  
At 4x/day: ~$6-18/month total.

---

## API endpoints

```
GET  /              Dashboard UI
GET  /api/state     Full current state
GET  /api/synthesis Latest synthesis result
GET  /api/defillama Latest DefiLlama data
GET  /api/run       Trigger pipeline manually
WS   /ws            WebSocket (real-time updates)
```

---

## Telegram first run

First time with Telegram configured, you'll see:

```
Please enter your phone (or bot token): +1234567890
Please enter the code you received: 12345
```

After that, a `rotation_intel.session` file is saved and subsequent runs are automatic.

---

## Cost summary

| Component | Cost |
|-----------|------|
| DefiLlama API | Free |
| Telegram API | Free |
| Reddit API | Free |
| Claude API (4x/day) | ~$6-18/month |
| Hosting (VPS) | $5-10/month optional |
| **Total** | **~$6-28/month** |
