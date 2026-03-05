from __future__ import annotations

import logging

from amex_ai_agent.chat import AgentChatApp
from amex_ai_agent.config import ConfigLoader


def setup_logging() -> None:
    logging.basicConfig(
        filename="agent.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main() -> None:
    setup_logging()
    config = ConfigLoader().load()
    app = AgentChatApp(config)
    app.start()


if __name__ == "__main__":
    main()
