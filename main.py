import logging

import constants
from Logger import Logger
from Bot import Bot
from Configuration import Configuration

Logger.init_root_logger()
logger = Logger.get_module_logger(constants.APPLICATION_NAME)


def main():
    my_bot = Bot()
    my_bot.run_forever()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        logger.info("Application Terminated by User.")
        # sys.exit(0)
