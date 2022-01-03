import logging
import sys

import rapidjson
from jsonschema import validate
from jsonschema.exceptions import SchemaError

import constants


class Configuration:
    _config = None

    @classmethod
    def get_config(cls):
        if cls._config is None:
            cls.load_config_file()
        return cls._config

    @classmethod
    def load_config_file(cls):
        schema = constants.CONFIG_SCHEMA
        try:
            # Convert json to python object.
            with open(constants.CONFIG_FILE) as f:
                # data = json.load(f)
                data = rapidjson.load(f)

            # Validate will raise exception if given json is not
            # what is described in schema.

            validate(instance=data, schema=schema)
        except (SchemaError, rapidjson.JSONDecodeError) as e:
            logging.exception(f"Invalid config file [{constants.CONFIG_FILE}] content.")
            sys.exit(0)

        # print for debug
        # logging.debug(rapidjson.dumps(data, indent=2))
        cls._config = data



