import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# log lower levels to stdout
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.addFilter(lambda rec: rec.levelno <= logging.INFO)
logger.addHandler(stdout_handler)

# log higher levels to stderr (red)
stderr_handler = logging.StreamHandler(stream=sys.stderr)
stderr_handler.addFilter(lambda rec: rec.levelno > logging.INFO)
logger.addHandler(stderr_handler)
