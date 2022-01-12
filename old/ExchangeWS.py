"""
    Exchange class that implements operations done through the WebSocket API
    This class is hardcoded for the Bybit exchange
----------------------------------------------------------------------------
To see which endpoints and topics are available, check the Bybit API
documentation:
    https://bybit-exchange.github.io/docs/inverse/#t-websocket
    https://bybit-exchange.github.io/docs/linear/#t-websocket

Inverse Perpetual endpoints:
wss://stream-testnet.bybit.com/realtime
wss://stream.bybit.com/realtime

Perpetual endpoints:
wss://stream-testnet.bybit.com/realtime_public
wss://stream-testnet.bybit.com/realtime_private
wss://stream.bybit.com/realtime_public or wss://stream.bytick.com/realtime_public
wss://stream.bybit.com/realtime_private or wss://stream.bytick.com/realtime_private

Spot endpoints:
wss://stream-testnet.bybit.com/spot/quote/ws/v1
wss://stream-testnet.bybit.com/spot/quote/ws/v2
wss://stream-testnet.bybit.com/spot/ws
wss://stream.bybit.com/spot/quote/ws/v1
wss://stream.bybit.com/spot/quote/ws/v2
wss://stream.bybit.com/spot/ws

Futures Public Topics:
orderBookL2_25
orderBookL2-200
trade
insurance
instrument_info
klineV2

Futures Private Topics:
position
execution
order
stop_order
wallet

Spot Topics:
Subscribing to spot topics uses the JSON format to pass the topic name and
filters, as opposed to futures WS where the topic and filters are pass in a
single string. So, it's recommended to pass a JSON or python dict in your
subscriptions, which also be used to fetch the topic's updates. Examples can
be found in the code panel here: https://bybit-exchange.github.io/docs/spot/#t-publictopics

However, as private spot topics do not require a subscription, the following
strings can be used to fetch data:
outboundAccountInfo
executionReport
ticketInfo

"""
from websocket._exceptions import WebSocketTimeoutException
import api_keys
import constants
from pybit import WebSocket
from logging_.Logger import Logger
from Configuration import Configuration


class ExchangeWS:
    name = None
    use_testnet = False

    # websockets
    public_ws = None
    private_ws = None

    endpoint_public = None
    endpoint_private = None

    # Bybit WS only support: ['1', '3', '5', '15', '30', '60', '120', '240', '360', 'D', 'W', 'M']
    interval_map = {
        '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
        '1h': '60', '2h': '120', '4h': '240', '6h': '360',
        '1d': 'D', '1w': 'W', '1M': 'M'
    }

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.interval = self.interval_map[self._config['strategy']['interval']]
        self.name = str(self._config['exchange']['name']).capitalize()
        self.pair = self._config['exchange']['pair']
        self.validate_pair()

        # Testnet/Mainnet
        if self._config['exchange']['testnet']:
            self.use_testnet = True
            self.name = self.name + '-Testnet'
            self.endpoint_public = self._config['exchange']['websockets']['ws_linear_public_testnet']
            self.endpoint_private = self._config['exchange']['websockets']['ws_linear_private_testnet']
            self.api_key = api_keys.TESTNET_BYBIT_API_KEY
            self.api_secret = api_keys.TESTNET_BYBIT_API_SECRET
        else:
            self.use_testnet = False
            self.endpoint_public = self._config['exchange']['websockets']['ws_linear_public_mainnet']
            self.endpoint_private = self._config['exchange']['websockets']['ws_linear_private_mainnet']
            self.api_key = api_keys.BYBIT_API_KEY
            self.api_secret = api_keys.BYBIT_API_SECRET

        # Market type hardcoded for perpetual futures
        if self._config['exchange']['market_type'] != 'perpetual futures':
            msg = f"Unsupported market type [{self._config['exchange']['market_type']}]."
            self._logger.error(msg)
            raise Exception(msg)

        # Connect websockets and subscribe to topics
        self.public_topics = self.build_public_topics_list()
        self.private_topics = self.build_private_topics_list()

        # TODO use a trier decorator to retry with timeouts
        try:
            self.subscribe_to_topics()
        except WebSocketTimeoutException as e:
            self._logger.exception(f'Websocket Timeout')
            raise e

    def validate_pair(self):
        if 'USDT' not in self.pair:
            msg = f'Application only supports USDT perpetuals.'
            self._logger.error(msg)
            raise Exception(msg)

    def subscribe_to_topics(self):
        # public subscriptions
        self.public_ws = WebSocket(
            self.endpoint_public,
            subscriptions=self.public_topics,
            ping_interval=20,
            ping_timeout=15
        )

        # private subscriptions, connect with authentication
        self.private_ws = WebSocket(
            self.endpoint_private,
            subscriptions=self.private_topics,
            api_key=self.api_key,
            api_secret=self.api_secret,
            ping_interval=20,
            ping_timeout=15
        )

    def build_public_topics_list(self):
        topic_list = [
            self.get_candle_topic(self.pair, self.interval),
            self.get_orderbook25_topic(self.pair)
        ]
        return topic_list

    def build_private_topics_list(self):
        topic_list = ['position', 'execution', 'order', 'stop_order', 'wallet']
        return topic_list

    @staticmethod
    def get_orderbook25_topic(pair):
        sub = "orderBookL2_25.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_orderbook200_topic(pair):
        sub = "orderBook_200.100ms.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_trade_topic(pair):
        sub = "trade.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_instrument_info_topic(pair):
        sub = "instrument_info.100ms.<pair>"
        return sub.replace('<pair>', pair)

    # Expecting the interval in this list constants.WS_VALID_CANDLE_INTERVALS
    @classmethod
    def get_candle_topic(cls, pair, interval):
        assert (interval in constants.WS_VALID_CANDLE_INTERVALS)
        sub = 'candle.<interval>.<pair>'
        return sub.replace('<interval>', interval).replace('<pair>', pair)

    @staticmethod
    def get_liquidation_topic(pair):
        sub = "liquidation.<pair>"
        return sub.replace('<pair>', pair)
