from __future__ import annotations

import logging

from amex_ai_agent.chat import AgentChatApp
from amex_ai_agent.config import ConfigLoader
from amex_ai_agent.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


def run_app(config) -> None:
    log_path = configure_logging()
    LOGGER.info("Starting Sally agent. log_path=%s", log_path)
    app = AgentChatApp(config)
    app.start()


def main() -> None:
    config = ConfigLoader().load()
    run_app(config)


if __name__ == "__main__":
    main()
