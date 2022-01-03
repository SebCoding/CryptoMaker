"""
    Exchange class that implements operations done through the WebSocket API
    This class is hardcoded for the Bybit exchange
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

    def __init__(self):
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
        else:
            self.use_testnet = False
            self.endpoint_public = self.config['exchange']['websockets']['ws_linear_public_mainnet']
            self.endpoint_private = self.config['exchange']['websockets']['ws_linear_private_mainnet']

        # Market type hardcoded for perpetual futures
        if self.config['exchange']['market_type'] != 'perpetual futures':
            msg = f"Unsupported market type [{self.config['exchange']['market_type']}]."
            logger.error(msg)
            raise Exception(msg)

        # Connect websockets and subscribe to topics
        self.public_topics = self.get_public_topics_list()
        self.private_topics = self.get_private_topics_list()
        self.subscribe_to_topics()

    def validate_pair(self):
        if 'USDT' not in self.pair:
            msg = f'Application only supports USDT perpetuals.'
            logger.error(msg)
            raise Exception(msg)

    def subscribe_to_topics(self):
        # public subscriptions
        self.public_ws = WebSocket(self.endpoint_public, subscriptions=self.public_topics)
        # private subscriptions
        #self.private_ws = WebSocket(self.endpoint_private, subscriptions=self.private_topics)

    def get_public_topics_list(self):
        topic_list = []
        topic_list.append(self.get_orderbook25_topic(self.pair))
        return topic_list

    def get_private_topics_list(self):
        topic_list = []
        return topic_list

    @staticmethod
    def get_orderbook25_topic(pair):
        sub = "orderBookL2_25.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_orderbook200_topic(pair):
        sub = "orderBookL2_200.<pair>"
        return sub.replace('<pair>', pair)
