import logging
import sys

import constants
from Configuration import Configuration


class Logger:
    _config = Configuration.get_config()
    _logging_level = Configuration.get_config()['logging']['logging_level']
    _datefmt = constants.DATETIME_FMT

    # Shared global debug file handler for all modules
    # with level hardcoded to logging_.DEBUG
    _debug_file_handler = None

    @staticmethod
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
        msg = f"Invalid logging_ level [{level_str}]"
        logging.error(msg)
        raise Exception(msg)

    # Logging level defaults to config file, but can overwritten.
    # Each module can have their own console logger set to different custom levels
    @classmethod
    def get_console_handler(cls, level=logging_level_str_to_int(_logging_level)):
        c_handler = logging.StreamHandler(sys.stdout)
        c_format = logging.Formatter('[%(name)s] %(message)s')
        c_handler.setFormatter(c_format)
        c_handler.setLevel(level)
        return c_handler

    # Logging level defaults to config file, but can overwritten
    # We prefer to always log everything at debug level, in debug file
    # and limit output at the console level
    @classmethod
    def get_debug_file_handler(cls, filename=Configuration.get_config()['logging']['debug_file_path']):
        if not cls._debug_file_handler:
            f_handler = logging.FileHandler(filename, mode='w')
            f_format = logging.Formatter(fmt='%(asctime)s [%(name)s] - %(levelname)s - %(message)s', datefmt=cls._datefmt)
            f_handler.setFormatter(f_format)
            f_handler.setLevel(logging.DEBUG)
            cls._debug_file_handler = f_handler
        return cls._debug_file_handler

    @classmethod
    def init_root_logger(cls, level=logging_level_str_to_int(_logging_level)):
        # Always keep root level set to logging_.DEBUG, but limit the level in handlers as desired
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(levelname)s: %(module)s.%(funcName)s, %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[cls.get_console_handler(level), cls.get_debug_file_handler()]
        )

    # Default level is the one specified in the config.json file.
    # Level passed as parameter will override config file
    # This return a logger with a custom level console handler
    # and a debug level file handler to the debug_log file
    @classmethod
    def get_module_logger(cls, module_name, level=logging_level_str_to_int(_logging_level)):
        logger = logging.getLogger(module_name)

        # Always keep logger level set to logging_.DEBUG,
        # but limit the level in handlers as desired
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            logger.addHandler(cls.get_console_handler(level))
            logger.addHandler(cls.get_debug_file_handler())
        logger.propagate = False
        return logger
