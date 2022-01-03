import logging

import constants
import logger
from bot import Bot
from configuration import Configuration

logger.init_root_logger(logging.DEBUG)
logger = logger.init_custom_logger(constants.APPLICATION_NAME)


def main():
    my_bot = Bot()
    my_bot.run_forever()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        logger.info("Application Terminated by User.")
        # sys.exit(0)
