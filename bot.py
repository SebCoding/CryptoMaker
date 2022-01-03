import ccxt
from pybit import WebSocket

from exchange.ExchangeCCXT import ExchangeCCXT


class Bot:

    def __init__(self, exchange_name):
        self.exchange = ExchangeCCXT(exchange_name.lower())
