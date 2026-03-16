"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "PRICE_"}

    # Database
    database_url: str = "postgresql://pricebot:pricebot@localhost:5432/pricebot"

    # Anthropic
    anthropic_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: int = 0

    # Scheduler
    scrape_interval_hours: int = 6
    report_hour: int = 8


settings = Settings()
