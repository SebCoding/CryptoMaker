import logging

import constants
import logger
from configuration import Configuration

logger.init_root_logger(logging.DEBUG)
logger = logger.init_custom_logger(constants.APPLICATION_NAME)


def main():
    print('CryptoMaker')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        logger.info("Application Terminated by User.")
        # sys.exit(0)
