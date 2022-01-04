import logging

APPLICATION_NAME = 'CryptoMaker'
SUPPORTED_EXCHANGES = ['Bybit']
MARKET_TYPES = ['perpetual futures']
LOGGING_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']

# Valid Intervals. Some intervals are not supported by some exchanges
REST_VALID_INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M']

# Valid intervals for websocket kline topic
WS_VALID_CANDLE_INTERVALS = ['1', '3', '5', '15', '30', '60', '120', '240', '360', 'D', 'W']

# Location of the config file
CONFIG_FILE = 'config.json'

# JSON configuration schema to validate the config.json file
CONFIG_SCHEMA = {
    '$schema': 'http://json-schema.org/schema#',
    'title': 'ConfigFileSchema',
    'description': 'json schema to validate config.json file',
    'type': 'object',
    'properties': {
        'exchange': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'enum': SUPPORTED_EXCHANGES},
                'testnet': {'type': 'boolean', 'default': True},
                'market_type': {'type': 'string', 'enum': MARKET_TYPES},
                'pair': {'type': 'string'},
                'rest': {
                    'type': 'object',
                    'properties': {
                        'linear_testnet': {'type': 'string', 'format': 'uri'},
                        'linear_mainnet': {'type': 'string', 'format': 'uri'},
                        'linear_mainnet2': {'type': 'string', 'format': 'uri'},
                        'timeout': {'type': 'integer', 'minimum': 0}
                    },
                    'required': ['timeout']
              },
                'websockets': {
                    'type': 'object',
                    'properties': {
                        'ws_linear_public_testnet': {'type': 'string', 'format': 'uri'},
                        'ws_linear_private_testnet': {'type': 'string', 'format': 'uri'},
                        'ws_linear_public_mainnet': {'type': 'string', 'format': 'uri'},
                        'ws_linear_public_mainnet2': {'type': 'string', 'format': 'uri'},
                        'ws_linear_private_mainnet': {'type': 'string', 'format': 'uri'},
                        'ws_linear_private_mainnet2': {'type': 'string', 'format': 'uri'}
                    }
                }
            },
            'required': ['name', 'testnet', 'market_type', 'rest', 'websockets']
        },
        'logging': {
            'type': 'object',
            'properties': {
                'global_level': {'type': 'string', 'enum': LOGGING_LEVELS},
                'log_file_path': {'type': 'string'}
            },
            'required': ['global_level', 'log_file_path']
        }
    },
    'required': ['exchange', 'logging']
}
