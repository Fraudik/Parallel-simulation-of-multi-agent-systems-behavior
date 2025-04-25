import logging
import sys

# TODO path to global
logging.basicConfig(filename="benchs/data/experiment.txt",
                    filemode='a',
                    format='%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# log lower levels to stdout
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.addFilter(lambda rec: rec.levelno <= logging.INFO)
logger.addHandler(stdout_handler)

# log higher levels to stderr
stderr_handler = logging.StreamHandler(stream=sys.stderr)
stderr_handler.addFilter(lambda rec: rec.levelno > logging.INFO)
logger.addHandler(stderr_handler)
