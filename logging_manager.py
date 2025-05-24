import logging
import sys

from config import PROPOSED_BENCH_FILE_PATH, IS_DEBUG

logging_level = logging.DEBUG if IS_DEBUG else logging.INFO

logging.basicConfig(filename=PROPOSED_BENCH_FILE_PATH,
                    filemode='a',
                    format='%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging_level)
logger = logging.getLogger(__name__)
logger.setLevel(logging_level)

# Filtering redundant logs
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.addFilter(lambda rec: rec.levelno <= logging_level)
logger.addHandler(stdout_handler)

stderr_handler = logging.StreamHandler(stream=sys.stderr)
stderr_handler.addFilter(lambda rec: rec.levelno > logging_level)
logger.addHandler(stderr_handler)
