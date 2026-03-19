# AI Price Monitor

[![CI](https://github.com/yasunchukandriy/ai-price-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/yasunchukandriy/ai-price-monitor/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Coverage: 99%](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](https://github.com/yasunchukandriy/ai-price-monitor/actions)

AI-powered competitor price monitoring for auto parts. Scrapes competitor prices, stores history in PostgreSQL, detects changes, generates daily AI reports via Claude API, and sends alerts through a Telegram bot.

## Features

- **Price scraping** — Playwright-based headless browser scraper with CSS selector targeting and European price format parsing (`€ 1.234,56`)
- **Change detection** — automatic comparison between scraping cycles, alerts on price drops, increases, and out-of-stock events
- **AI daily reports** — Claude API generates actionable pricing analysis with competitive positioning and recommendations
- **Telegram bot** — 6 commands for on-demand prices, trends, reports, and alerts
- **Scheduler** — configurable scraping interval with automated daily report generation
- **135 tests, 99% coverage** — fully tested with ruff lint and strict mypy

## Demo

<details>
<summary><b>/prices</b> — competitor price comparison</summary>

```
Brake Pads Front (BMW 3 Series) (Our: 45.90 EUR)
  AutoDoc:      48.37 EUR (+2.47) [OK]
  KFZteile24:   39.44 EUR (-6.46) [OK]
  ATP Auto:     43.57 EUR (-2.33) [OUT]
  Mister Auto:  41.15 EUR (-4.75) [OK]

Oil Filter (Mercedes C-Class) (Our: 12.80 EUR)
  AutoDoc:      13.42 EUR (+0.62) [OK]
  KFZteile24:   11.98 EUR (-0.82) [OK]
  ATP Auto:     14.10 EUR (+1.30) [OK]
  Mister Auto:  12.55 EUR (-0.25) [OK]
```
</details>

<details>
<summary><b>/report</b> — AI-generated daily analysis</summary>

```markdown
## Summary
The auto parts market shows moderate price volatility across 4 competitors.
KFZteile24 consistently undercuts on brake components (-8-14%), while
AutoDoc maintains premium positioning (+3-7%).

## Price Alerts
- DOWN: Brake Pads Front @ KFZteile24: 42.10 → 39.44 EUR (-6.3%)
- UP:   Oil Filter @ ATP Auto: 13.20 → 14.10 EUR (+6.8%)
- OOS:  Brake Pads Front @ ATP Auto — out of stock

## Competitive Position
3 of 10 products priced above all competitors — review recommended.
Average competitor price is 4.2% below our catalog.

## Recommendations
1. Consider matching KFZteile24 on Brake Pads (-14% gap)
2. Oil Filter margin is safe — competitors within ±5%
3. Monitor ATP Auto stock recovery for Brake Pads
```
</details>

<details>
<summary><b>/trends</b> — 7-day price history</summary>

```
Brake Pads Front (BMW 3 Series) — 7-day price trends

  AutoDoc:      min 46.80 / avg 48.15 / max 49.90 EUR
  KFZteile24:   min 38.20 / avg 40.10 / max 42.10 EUR
  ATP Auto:     min 42.90 / avg 43.85 / max 45.20 EUR
  Mister Auto:  min 40.50 / avg 41.30 / max 42.80 EUR
```
</details>

<details>
<summary><b>/alerts</b> — real-time price change notifications</summary>

```
Price alerts (6):
  [DOWN] Brake Pads Front @ KFZteile24: 42.10 → 39.44 EUR
  [UP]   Oil Filter @ ATP Auto: 13.20 → 14.10 EUR
  [DOWN] Spark Plugs Set @ AutoDoc: 25.80 → 24.15 EUR
  [OOS]  Brake Pads Front @ ATP Auto
  [UP]   Timing Belt Kit @ Mister Auto: 85.40 → 89.90 EUR
  [DOWN] Wiper Blades @ KFZteile24: 16.20 → 14.80 EUR
```
</details>

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Scheduler  │────▶│   Scraper    │────▶│  PostgreSQL   │
│  (asyncio)   │     │ (Playwright) │     │  price_records│
└──────┬───────┘     └──────────────┘     └──────┬───────┘
       │                                         │
       ▼                                         ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Analyzer   │────▶│  Claude API  │     │ Telegram Bot  │
│  (daily)     │◀────│  (summary)   │────▶│ (aiogram 3.x) │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Tech Stack

- **Python 3.12** — async throughout (asyncio, asyncpg, aiogram)
- **Playwright** — headless Chromium scraper for competitor pages
- **PostgreSQL 16** — price history, alerts, reports
- **Claude API** — AI-powered daily pricing reports
- **Telegram Bot** — real-time commands and alerts (aiogram 3.x)
- **Docker Compose** — one-command deployment

## Quick Start

```bash
# 1. Start PostgreSQL with seed data
docker compose up -d postgres

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Run the application
python -m ai_price_monitor.main
```

Or run everything with Docker:

```bash
docker compose up -d
```

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and available commands |
| `/prices` | Latest prices for all products |
| `/prices <product>` | Prices for a specific product |
| `/report` | Generate AI analysis report |
| `/trends <product>` | 7-day price trends (min/avg/max) |
| `/alerts` | Recent price change alerts |
| `/status` | System health check |

## Configuration

All settings via environment variables with `PRICE_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `PRICE_DATABASE_URL` | `postgresql://pricebot:pricebot@localhost:5432/pricebot` | PostgreSQL connection string |
| `PRICE_ANTHROPIC_API_KEY` | — | Claude API key |
| `PRICE_TELEGRAM_BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `PRICE_TELEGRAM_CHAT_ID` | `0` | Chat ID for automated alerts |
| `PRICE_SCRAPE_INTERVAL_HOURS` | `6` | Hours between scraping cycles |
| `PRICE_REPORT_HOUR` | `8` | UTC hour for daily report generation |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v --cov=ai_price_monitor

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Project Structure

```
src/ai_price_monitor/
├── config.py      # pydantic-settings configuration
├── database.py    # asyncpg pool and CRUD operations
├── scraper.py     # PlaywrightScraper + DemoScraper with price parser
├── analyzer.py    # Claude API daily report generation
├── bot.py         # Telegram bot with 6 commands (aiogram 3.x)
└── main.py        # Entry point: scheduler + bot

tests/               # 135 tests, 99% coverage
seed/init.sql        # PostgreSQL schema + 10 products + 4 competitors
```

## License

MIT
