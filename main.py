import time

import websocket

import sys
import os
import constants
from Bot import Bot
from logging_.Logger import Logger

Logger.init_root_logger()
logger = Logger.get_module_logger(constants.APPLICATION_NAME)


def restart(nb_seconds):
    # print("argv was", sys.argv)
    # print("sys.executable was", sys.executable)
    logger.error(f"restarting in {nb_seconds} seconds ...")
    time.sleep(nb_seconds)
    os.execv(sys.executable, ['python'] + sys.argv)


def main():
    try:
        my_bot = Bot()
        my_bot.run_forever()
    except websocket._exceptions.WebSocketTimeoutException as e:
        logger.exception(f'WebSocketTimeoutException: Last resort, restarting the whole application')
        restart(10)
    except KeyboardInterrupt as e:
        logger.info("Application Terminated by User.")


if __name__ == '__main__':
    main()
