import logging

from configuration import Configuration


def init_root_logger(level):
    # logging.basicConfig(
    #     level=level,
    #     format='%(asctime)s %(filename)s - %(module)s - %(funcName)s() - line:%(lineno)d - %(name)s - %(levelname)s - %(message)s',
    #     datefmt='%Y-%m-%d %H:%M:%S'
    # )
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(module)s.%(funcName)s, %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# Default level is the one specified in the config.json file.
# Level passed as parameter will override config file
def init_custom_logger(module_name):
    config = Configuration.get_config()
    config_level = logging_level_str_to_int(config['logging']['global_level'])

    logger = logging.getLogger(module_name)
    logger.setLevel(config_level)

    # Console Handler
    c_handler = logging.StreamHandler()
    c_format = logging.Formatter('[%(name)s] %(levelname)s:  %(message)s')
    c_handler.setFormatter(c_format)
    c_handler.setLevel(config_level)

    # File Handler
    f_handler = logging.FileHandler('log.txt', mode='w')
    f_format = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='[%Y-%m-%d.%H:%M:%S]')
    f_handler.setFormatter(f_format)
    f_handler.setLevel(config_level)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)
    return logger


def logging_level_str_to_int(level_str):
    level_str = level_str.lower()
    match level_str:
        case 'debug':
            return logging.DEBUG
        case 'info':
            return logging.INFO
        case 'warning':
            return logging.WARNING
        case 'error':
            return logging.ERROR
        case 'critical':
            return logging.CRITICAL
    msg = f"Invalid logging level [{level_str}]"
    logging.error(msg)
    raise Exception(msg)

# Examples
# # Test root logger
# init_root_logger()
# a = 5
# b = 0
# try:
#   c = a / b
# except Exception as e:
#   """
#       Using logging.exception() would show a log at the level of ERROR.
#       If you don’t want that, you can call any of the other logging methods
#       from debug() to critical() and pass the exc_info parameter as True.
#   """
#   # logging.error("Une erreur est survenue", exc_info=True)
#   logging.exception("Une erreur est survenue")
#
# # Test custom logger
# logger = init_custom_logger()
# logger.warning('This is a warning')
# logger.error('This is an error')
