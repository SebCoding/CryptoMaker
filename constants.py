APPLICATION_NAME = 'CryptoMaker'
SUPPORTED_EXCHANGES = ['Bybit']
MARKET_TYPES = ['perpetual futures']
LOGGING_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']

DATE_FMT = '%Y-%m-%d'
DATETIME_FMT = '%Y-%m-%d %H:%M:%S'
# Use some_date.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] to get only 3 digits for ms
DATETIME_FMT_MS = '%Y-%m-%d %H:%M:%S.%f'

TRADE_ENTRY_MODES = ['maker', 'taker']
IMPLEMENTED_STRATEGIES = ['ScalpEmaRsiAdx']

# Valid Intervals. Some intervals are not supported by Bybit Websockets
VALID_INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w']

# Valid intervals for websocket kline topic
WS_VALID_CANDLE_INTERVALS = ['1', '3', '5', '15', '30', '60', '120', '240', '360', 'D', 'W']

# API Retry count in case of errors, timeouts
API_RETRY_COUNT = 4

# Location of the config file
CONFIG_FILE = 'config.json'

# JSON configuration schema to validate the config.json file
CONFIG_SCHEMA = {
    '$schema': 'http://json-schema.org/schema#',
    'title': 'ConfigFileSchema',
    'description': 'json schema to validate config.json file',
    'type': 'object',
    'properties': {
        'bot': {
            'type': 'object',
            'properties': {
                'throttle_secs': {'type': 'integer', 'minimum': 0}
            },
            'required': ['throttle_secs']
        },
        'exchange': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'enum': SUPPORTED_EXCHANGES},
                'testnet': {'type': 'boolean', 'default': True},
                'market_type': {'type': 'string', 'enum': MARKET_TYPES},
                'pair': {'type': 'string'},
                'stake_currency': {'type': 'string'},
                'http': {
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
            'required': ['name', 'testnet', 'market_type', 'pair', 'stake_currency', 'http', 'websockets']
        },
        'strategy': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'enum': IMPLEMENTED_STRATEGIES},
                'interval': {'type': 'string', 'enum': VALID_INTERVALS},
                'minimum_candles_to_start': {'type': 'integer', 'minimum': 0}
            },
            'required': ['name', 'interval', 'minimum_candles_to_start']
        },
        'trading': {
            'type': 'object',
            'properties': {
                'leverage_long': {'type': 'number', 'minimum': 1, 'maximum': 50},
                'leverage_short': {'type': 'number', 'minimum': 1, 'maximum': 50},
                'take_profit': {'type': 'number'},
                'stop_loss': {'type': 'number'},
                'tradable_balance_ratio': {'type': 'number', 'minimum': 0.01, 'maximum': 1.0},
                'trade_on_closed_candles_only': {'type': 'boolean', 'default': False},
                'trade_entry_mode':  {'type': 'string', 'enum': TRADE_ENTRY_MODES},
            },
            'required': ['leverage_long', 'leverage_short', 'take_profit', 'stop_loss',
                         'tradable_balance_ratio', 'trade_on_closed_candles_only',
                         'trade_entry_mode']
        },
        'limit_entry': {
            'type': 'object',
            'properties': {
                'abort_price_pct': {'type': 'number', 'minimum': 0, 'maximum': 10},
                'abort_time_ratio': {'type': 'number', 'minimum': 0, 'maximum': 10}
            },
            'required': ['abort_price_pct', 'abort_time_ratio']
        },
        'database': {
            'type': 'object',
            'properties': {
                'db_name': {'type': 'string', 'default': 'CryptoMaker'},
                'address': {'type': 'string', 'default': 'localhost'},
                'port': {'type': 'integer', 'default': 5432},
                'username': {'type': 'string', 'default': 'postgres'},
                'password': {'type': 'string', 'default': 'postgres'}
            },
            'required': ['db_name', 'address', 'port', 'username', 'password']
        },
        'logging': {
            'type': 'object',
            'properties': {
                'logging_level': {'type': 'string', 'enum': LOGGING_LEVELS},
                'debug_file_path': {'type': 'string'},
                'output_file_path': {'type': 'string'}
            },
            'required': ['logging_level', 'debug_file_path', 'output_file_path']
        }
    },
    'required': ['bot', 'exchange', 'strategy', 'trading', 'database', 'logging']
}
