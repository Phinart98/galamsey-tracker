"""Telegram bot for citizen galamsey reports. Implemented in Phase 5."""
import logging

from telegram.ext import Application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Bot stub — full implementation in Phase 5.")


if __name__ == "__main__":
    main()
