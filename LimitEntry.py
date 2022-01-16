import math
import time

import rapidjson
import arrow

import constants
from Configuration import Configuration
from Orderbook import Orderbook
from Orders import Order, Orders
from Position import Position
from TradeEntry import TradeEntry
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums.BybitEnums import OrderType, OrderSide, OrderStatus
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger

"""
    Sort a list of dictionaries by dict value
    newlist = sorted(list_to_be_sorted, key=lambda d: d['name']) 
"""


class LimitEntry(TradeEntry):
    # We do not place orders when the spread is greater than "spread_tolerance"
    SPREAD_TOLERANCE = 1.0

    # When we place an order the price = orderbook_top + "price_delta"
    # Price delta must be an even multiple of: exchange.pair_details_dict['price_filter']['min_price']
    # For example: BTCUSDT: 0.50, ETHUSDT: 0.05, ...
    PRICE_DELTA = 0.50

    def __init__(self, database, exchange, wallet, orders, position):
        super().__init__(database, exchange, wallet, orders, position)
        self._orderbook = Orderbook()

    def get_current_ob_price(self, side):
        if side == OrderSide.Buy:
            ob, spread = self._orderbook.get_top1()
            return float(ob[1]['price'])
        else:
            ob, spread = self._orderbook.get_top1()
            return float(ob[0]['price'])

    def get_entry_price(self, side):
        spread = 100000
        while spread > self.SPREAD_TOLERANCE:
            if side == OrderSide.Buy:
                ob, spread = self._orderbook.get_top1()
                price = float(ob[1]['price']) - self.PRICE_DELTA
                # print(f"Orderbook spread={spread} sellers top [{ob[1]['price']}]. Tentative Price: {price}")
            else:
                ob, spread = self._orderbook.get_top1()
                price = float(ob[0]['price']) - self.PRICE_DELTA
                # print(f"Orderbook spread={spread}, buyers top [{ob[0]['price']}]. Tentative Price: {price}")
        return float(price)

    def update_order(self, side, order_id):
        balance = self._wallet.free
        # tradable_balance = balance * self.tradable_ratio
        price = self.get_entry_price(side)
        stop_loss = self.get_stop_loss(side, price)

        # # Calculate trade size (qty) based on leverage
        # qty = tradable_balance / price
        # if side == OrderSide.Buy:
        #     lev = float(self._config['trading']['leverage_long'])
        # else:
        #     lev = float(self._config['trading']['leverage_short'])
        # qty = self.round_trade_qty(qty * lev)

        result = self._exchange.replace_active_order_pr_sl(order_id, price, stop_loss)
        self._logger.info(f"Updated Order[{order_id}: price={price}, stop_loss={stop_loss}]")

    def enter_trade(self, side):
        """
            Order Statuses: Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
        """
        qty, order_id = self.place_limit_entry(side)
        time.sleep(1)
        while True:
            # print(f'Orderbook {self.get_current_ob_price(side)}')
            # Wait for the order to appear on websocket or http session
            while True:
                order = self._exchange.get_order_by_id(self.pair, order_id)
                if order:
                    break
            match order['order_status']:
                case OrderStatus.Created | OrderStatus.New | OrderStatus.PartiallyFilled:
                    new_entry_price = self.get_entry_price(side)
                    if (side == OrderSide.Buy and new_entry_price > order['price']) \
                            or (side == OrderSide.Sell and new_entry_price < order['price']):
                        self._logger.info(
                            f"Order [{order['order_status']}] orderbook={self.get_current_ob_price(side)}, "
                            f"order_price={order['price']}")
                        self.update_order(side, order_id)
                    time.sleep(1)
                    continue
                case OrderStatus.Filled:
                    created_time = arrow.get(order['create_time']).to('local').datetime
                    created_time = created_time.strftime(constants.DATETIME_FMT)
                    self._logger.info(
                        f"Order [{order['order_status']}] Order has been filled. order_price={order['price']}")
                    return order['order_id']
                case _:
                    ob_price = self.get_current_ob_price(side)
                    self._logger.info(
                        f"Order [{order['order_status']}]: orderbook={ob_price} order_price={order['price']}. "
                        f"Retrying ...")
                    qty, order_id = self.place_limit_entry(side)
                    time.sleep(1)
                    continue

    def place_limit_entry(self, side):
        balance = self._wallet.free
        tradable_balance = balance * self.tradable_ratio

        price = self.get_entry_price(side)
        stop_loss = self.get_stop_loss(side, price)

        # Calculate trade size (qty) based on leverage
        qty = tradable_balance / price
        if side == OrderSide.Buy:
            lev = float(self._config['trading']['leverage_long'])
        else:
            lev = float(self._config['trading']['leverage_short'])
        qty = self.round_trade_qty(qty * lev)

        order = Order(
            side=side,
            symbol=self.pair,
            order_type=OrderType.Limit,
            qty=qty,
            price=price,
            stop_loss=stop_loss
        )
        order_id = self._orders.place_order(order, 'TradeEntry')['order_id']
        return qty, order_id


"""
    Testing Limit Order Trade Entries
"""
ex = ExchangeBybit()
db = Database(ex)
Wal = WalletUSDT(ex)
Ord = Orders(db, ex)
Pos = Position(db, ex)

limit_entry = LimitEntry(db, ex, Wal, Ord, Pos)
limit_entry.enter_trade(OrderSide.Buy)
