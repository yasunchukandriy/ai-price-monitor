# AI Price Monitor

AI-powered competitor price monitoring for auto parts. Tracks competitor prices, detects changes, and generates daily AI-powered reports via Claude API. Sends alerts through a Telegram bot.

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
│  (daily)     │◀────│  (summary)   │────▶│ (aiogram)     │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Tech Stack

- **Python 3.12** — async throughout (asyncio, asyncpg, aiogram)
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
├── scraper.py     # BaseScraper protocol + DemoScraper
├── analyzer.py    # Claude API daily report generation
├── bot.py         # Telegram bot (aiogram 3.x)
└── main.py        # Entry point: scheduler + bot
```

## License

MIT
