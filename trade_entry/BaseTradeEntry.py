import datetime as dt
import sys
import time
from abc import ABC, abstractmethod

import pandas as pd
import telegram

import api_keys
import constants
from Configuration import Configuration
from Orders import Order, Orders
from WalletUSDT import WalletUSDT
from enums.BybitEnums import OrderSide, OrderType, OrderStatus
from logging_.Logger import Logger


class BaseTradeEntry(ABC):
    # maximum ratio of the available balance of the wallet that is tradable
    MAX_TRADABLE_RATIO = 0.99

    MIN_TRADE_AMOUNT = 20

    # Wait time in seconds after creating/updating orders
    PAUSE_TIME = 0.3

    def __init__(self, db, exchange, position, signal):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.signal = signal
        self.pair = signal['Pair']
        self.tradable_ratio = float(self._config['trading']['tradable_balance_ratio'])
        if self.tradable_ratio > self.MAX_TRADABLE_RATIO:
            self._logger.error(f'Cannot trade with a tradable_ratio[{self.tradable_ratio}] > '
                               f'{self.MAX_TRADABLE_RATIO}. Exiting Application.')
            sys.exit(1)
        self._db = db
        self._exchange = exchange
        self._position = position
        self._wallet = WalletUSDT(self._exchange)
        self._orders = Orders(self._db, self._exchange)

        self.side_l_s = 'Long' if self.signal['Side'] == OrderSide.Buy else 'Short'
        self.tick_size = float(self._exchange.pair_details_dict['price_filter']['tick_size'])

        # tp order details for the current trade entry
        self.take_profit_order_id = None
        self.take_profit_cum_qty = 0

        # Values based on the signal that will remain constant throughout the trade entry
        # The take_profit will adjust dynamically, only if current price crosses initial tp
        self.sig_stop_loss_amount = self.get_stop_loss(signal['Side'], signal['EntryPrice'])
        self.sig_take_profit_amount = self.get_take_profit(signal['Side'], signal['EntryPrice'])

    @abstractmethod
    def enter_trade(self):
        pass

    @abstractmethod
    def get_current_ob_price(self, side):
        pass

    # @classmethod
    # def f_dec(cls, x):
    #     """
    #     Format decimal, global rounding and displaying setting for this class.
    #     :param x: Number to round
    #     :return: Number formatted as specified
    #     """
    #     return f'{x:.2f}'

    def adj_qty(self, qty):
        """
            Adjust the qty to an even number of qty steps,
            otherwise the remainder gets truncated by the exchange.

            Rounding at 10 decimals to remove the extra decimals that appear
            like this: 43 * 0.001 = 0.043000000000000003
        """
        min_trade_qty = float(self._exchange.pair_details_dict['lot_size_filter']['qty_step'])
        qty = int(qty / min_trade_qty) * min_trade_qty
        return round(qty, 10)

    def adj_price(self, price):
        """
            Adjust the price to an even number of minimum price increments,
            otherwise order get rejected by the exchange.

            Rounding at 10 decimals to remove the extra decimals that appear
            like this: 43 * 0.001 = 0.043000000000000003
        """
        price = int(price / self.tick_size) * self.tick_size
        return round(price, 10)

    def get_stop_loss(self, side, price):
        stop_loss_pct = self._config['trading']['stop_loss']
        stop_loss = price * stop_loss_pct
        if side == OrderSide.Buy:
            stop_loss = price - stop_loss
        if side == OrderSide.Sell:
            stop_loss = price + stop_loss
        return self.adj_price(stop_loss)

    def get_take_profit(self, side, price):
        take_profit_pct = self._config['trading']['take_profit']
        take_profit = price * take_profit_pct
        if side == OrderSide.Buy:
            take_profit = price + take_profit
        if side == OrderSide.Sell:
            take_profit = price - take_profit
        return self.adj_price(take_profit)

    def get_executions(self, side, order_id=None):
        """
            Returns a list of execution dictionaries for the specified side
            [
                {
                    "symbol": "BTCUSDT",
                    "side": "Sell",
                    "order_id": "7ee2d6e4-6857-42ea-b8c6-0054bca76480",
                    "exec_id": "f1309736-80e1-532b-b620-a348ae30386f",
                    "order_link_id": "",
                    "price": 42562,
                    "order_qty": 0.076,
                    "exec_type": "Trade",
                    "exec_qty": 0.076,
                    "exec_fee": 2.426034,
                    "leaves_qty": 0,
                    "is_maker": false,
                    "trade_time": "2022-01-17T12:23:53.035806Z"
                }
            ]
        """
        list_exec = None
        # Note: all executions of the opposite side are being lost here
        data = self._exchange.ws_private.fetch(self._exchange.execution_topic_name)
        if data:
            if order_id:
                # list_exec = list(filter(lambda person: data['side'] == side, data))
                list_exec = [e for e in data if e['side'] == side and e['order_id'] == order_id]
            else:
                # list_exec = list(filter(lambda person: data['side'] == side, data))
                list_exec = [e for e in data if e['side'] == side]
        return list_exec

    def place_tp_order(self, trade_side, qty, tp_price):
        # take_profit order side is opposite has trade entry
        tp_side = OrderSide.Buy if trade_side == OrderSide.Sell else OrderSide.Sell
        tp_order = Order(side=tp_side, symbol=self.pair, order_type=OrderType.Limit, qty=qty,
                         price=tp_price, reduce_only=True)
        result = self._orders.place_order(tp_order, 'TakeProfit')
        return result['order_id'] if result else None

    def set_tp_on_executions(self, main_order_id, validate_tp=False):
        """
            Strangely some executions are never received on the websocket. On the final call to set_tp_on_executions()
            prior to finalizing the trade entry, we must validate that take_profit = cum_exec_qty for the given order.
            When param validate_tp is set to true, the missing qty is added to fill the discrepancy.
        """
        fixed_tp = self._config['trading']['constant_take_profit']
        tp_side = OrderSide.Buy if self.signal['Side'] == OrderSide.Sell else OrderSide.Sell
        main_order = self._exchange.get_order_by_id_ws_only(self.pair, main_order_id)
        cum_exec_qty = main_order['cum_exec_qty'] if main_order else 0
        exec_list = self.get_executions(self.signal['Side'], main_order_id)

        qty = 0
        # All take profits during the current trade will have the same value
        if exec_list and fixed_tp:
            for e in exec_list:
                qty += float(e['exec_qty'])
                self._logger.info(
                    f"Execution: {self.signal['Side']} order[{e['order_id'][-8:]}: price={e['price']:.2f}, "
                    f"qty={e['exec_qty']}, cum_qty={round(self.take_profit_cum_qty + qty, 10)}]")

            missing_qty = round(cum_exec_qty - (self.take_profit_cum_qty + qty), 10)
            if validate_tp and missing_qty > 0:
                self._logger.info(f'Correcting discrepancy of {missing_qty} between executions and filled order size.')
                qty = round(cum_exec_qty - self.take_profit_cum_qty, 10)

            if self.take_profit_order_id:
                self.take_profit_cum_qty = round(self.take_profit_cum_qty + qty, 10)
                result = self._exchange.replace_active_order_qty(self.take_profit_order_id, self.take_profit_cum_qty)
                # The previous tp order still exists (not yet filled)
                if result and result['ret_code'] == 0:
                    self._logger.info(f"Updated {tp_side} TakeProfit Limit Order[{self.take_profit_order_id[-8:]}: "
                                      f"qty={self.take_profit_cum_qty}, tp_price={self.sig_take_profit_amount:.2f}]")
                # The previous tp order has been filled, we need to create a new one
                else:
                    self.take_profit_order_id = self.place_tp_order(self.signal['Side'], self.take_profit_cum_qty,
                                                                    self.sig_take_profit_amount)

            else:
                self.take_profit_cum_qty = round(qty, 10)
                self.take_profit_order_id = self.place_tp_order(self.signal['Side'], self.take_profit_cum_qty,
                                                                self.sig_take_profit_amount)

        # There are no more executions, the order has been filled, and the take_profit order needs to be adjusted
        elif not exec_list and fixed_tp and validate_tp:
            missing_qty = round(cum_exec_qty - self.take_profit_cum_qty, 10)
            if missing_qty > 0:
                self._logger.info(f'Correcting discrepancy of {missing_qty} between executions and filled order size..')
                qty = round(cum_exec_qty - self.take_profit_cum_qty, 10)

                if self.take_profit_order_id:
                    self.take_profit_cum_qty = round(self.take_profit_cum_qty + qty, 10)
                    result = self._exchange.replace_active_order_qty(self.take_profit_order_id,
                                                                     self.take_profit_cum_qty)
                    # The previous tp order still exists (not yet filled)
                    if result and result['ret_code'] == 0:
                        self._logger.info(f"Updated {tp_side} TakeProfit Limit Order[{self.take_profit_order_id[-8:]}: "
                                          f"qty={self.take_profit_cum_qty}, tp_price={self.sig_take_profit_amount:.2f}]")
                    # The previous tp order has been filled, we need to create a new one
                    else:
                        self.take_profit_order_id = self.place_tp_order(self.signal['Side'], self.take_profit_cum_qty,
                                                                        self.sig_take_profit_amount)

                else:
                    self.take_profit_cum_qty = round(qty, 10)
                    self.take_profit_order_id = self.place_tp_order(self.signal['Side'], self.take_profit_cum_qty,
                                                                    self.sig_take_profit_amount)

        # Each execution uses its own take profit order and price
        elif exec_list and not fixed_tp:
            # We are merging qty for executions that have the same price together
            # Group By: order_id, price => sum(exec_qty)
            df = pd.DataFrame(exec_list)
            df = df[['order_id', 'price', 'exec_qty']]
            df_sums = df.groupby(['order_id', 'price']).sum()
            df_sums.reset_index(inplace=True)
            grouped_list = df_sums.to_dict('records')

            # Print executions
            for e in exec_list:
                qty = round(float(e['exec_qty']), 10)
                self._logger.info(
                    f"Execution: {self.signal['Side']} order[{e['order_id'][-8:]}: price={e['price']:.2f}, "
                    f"qty={e['exec_qty']}, cum_qty={round(self.take_profit_cum_qty + qty, 10)}]")
            # Place merged tp orders
            for e in grouped_list:
                qty = round(float(e['exec_qty']), 10)
                take_profit = self.get_take_profit(self.signal['Side'], float(e['price']))
                self.place_tp_order(self.signal['Side'], qty, take_profit)
                self.take_profit_cum_qty = round(self.take_profit_cum_qty + qty, 10)
