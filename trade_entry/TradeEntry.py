import math
import sys
from abc import ABC, abstractmethod

import utils
from Configuration import Configuration
from Orderbook import Orderbook
from enums.BybitEnums import OrderSide
from logging_.Logger import Logger


class TradeEntry(ABC):

    # maximum ratio of the available balance of the wallet that is tradable
    MAX_TRADABLE_RATIO = 0.99

    def __init__(self, db, exchange, wallet, orders, position):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        self.tradable_ratio = float(self._config['trading']['tradable_balance_ratio'])
        if self.tradable_ratio > self.MAX_TRADABLE_RATIO:
            self._logger.error(f'Cannot trade with a tradable_ratio[{self.tradable_ratio}] > '
                               f'{self.MAX_TRADABLE_RATIO}. Exiting Application.')
            sys.exit(1)
        self._db = db
        self._exchange = exchange
        self._wallet = wallet
        self._orders = orders
        self._position = position


    @abstractmethod
    def enter_trade(self, side):
        pass

    @classmethod
    def f_dec(cls, x):
        """
        Format decimal, global rounding and displaying setting for this class.
        :param x: Number to round
        :return: Number formatted as specified
        """
        return f'{x:.2f}'

    def round_trade_qty(self, qty):
        """
            Adjust the qty to an even number of qty steps,
            otherwise the remainder gets truncated by the exchange.

            Rounding at 10 decimals to remove the extra decimals that appear
            like this: 43 * 0.001 = 0.043000000000000003
        """
        min_trade_qty = self._exchange.pair_details_dict['lot_size_filter']['qty_step']
        qty = int(qty / min_trade_qty) * min_trade_qty
        return round(qty, 10)

    def get_stop_loss(self, side, price):
        stop_loss_pct = self._config['trading']['stop_loss']
        stop_loss = price * stop_loss_pct
        if side == OrderSide.Buy:
            stop_loss = price - stop_loss
        if side == OrderSide.Sell:
            stop_loss = price + stop_loss
        return round(stop_loss, 0)


    def get_take_profit(self, side, price):
        take_profit_pct = self._config['trading']['take_profit']
        take_profit = price * take_profit_pct
        if side == OrderSide.Buy:
            take_profit = price + take_profit
        if side == OrderSide.Sell:
            take_profit = price - take_profit
        return round(take_profit, 0)
