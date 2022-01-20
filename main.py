import constants
from Bot import Bot
from logging_.Logger import Logger

Logger.init_root_logger()
logger = Logger.get_module_logger(constants.APPLICATION_NAME)


def main():
    my_bot = Bot()
    my_bot.run_forever()


if __name__ == '__main__':
    main()
