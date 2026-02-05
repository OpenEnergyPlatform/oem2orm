import logging
import logging.config
import yaml


def setup_logging():
    try:
        with open("config/logging.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        logging.config.dictConfig(cfg)
    except Exception:
        logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info("Logging is set up.")

    return logger
