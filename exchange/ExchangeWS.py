"""
    Exchange class that implements operations done through the WebSocket API
    This class is hardcoded for the Bybit exchange
"""
import api_keys
import constants

"""
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
from pybit import WebSocket
import logger
from configuration import Configuration

logger = logger.init_custom_logger(__name__)


class ExchangeWS:
    name = None
    use_testnet = False

    # websockets
    public_ws = None
    private_ws = None

    endpoint_public = None
    endpoint_private = None

    def __init__(self, interval):
        self.interval = interval
        self.config = Configuration.get_config()
        self.name = str(self.config['exchange']['name']).capitalize()
        self.pair = self.config['exchange']['pair']
        self.validate_pair()

        # Testnet/Mainnet
        if self.config['exchange']['testnet']:
            self.use_testnet = True
            self.name = self.name + '-Testnet'
            self.endpoint_public = self.config['exchange']['websockets']['ws_linear_public_testnet']
            self.endpoint_private = self.config['exchange']['websockets']['ws_linear_private_testnet']
            self.api_key = api_keys.TESTNET_BYBIT_API_KEY
            self.api_secret = api_keys.TESTNET_BYBIT_API_SECRET
        else:
            self.use_testnet = False
            self.endpoint_public = self.config['exchange']['websockets']['ws_linear_public_mainnet']
            self.endpoint_private = self.config['exchange']['websockets']['ws_linear_private_mainnet']
            self.api_key = api_keys.BYBIT_API_KEY
            self.api_secret = api_keys.BYBIT_API_SECRET

        # Market type hardcoded for perpetual futures
        if self.config['exchange']['market_type'] != 'perpetual futures':
            msg = f"Unsupported market type [{self.config['exchange']['market_type']}]."
            logger.error(msg)
            raise Exception(msg)

        # Connect websockets and subscribe to topics
        self.public_topics = self.build_public_topics_list()
        self.private_topics = self.build_private_topics_list()
        self.subscribe_to_topics()

    def validate_pair(self):
        if 'USDT' not in self.pair:
            msg = f'Application only supports USDT perpetuals.'
            logger.error(msg)
            raise Exception(msg)

    def subscribe_to_topics(self):
        # public subscriptions
        self.public_ws = WebSocket(self.endpoint_public, subscriptions=self.public_topics)

        # private subscriptions, connect with authentication
        self.private_ws = WebSocket(
            self.endpoint_private,
            subscriptions=self.private_topics,
            api_key=self.api_key,
            api_secret=self.api_secret
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

    @staticmethod
    def get_candle_topic(pair, interval):
        interval = str(interval)
        assert(interval in constants.WS_VALID_CANDLE_INTERVALS)
        sub = 'candle.<interval>.<pair>'
        return sub.replace('<interval>', interval).replace('<pair>', pair)

    @staticmethod
    def get_liquidation_topic(pair):
        sub = "liquidation.<pair>"
        return sub.replace('<pair>', pair)

