import time

import arrow

import constants
import utils
from Orderbook import Orderbook
from Orders import Order, Orders
from Position import Position
from trade_entry.TradeEntry import TradeEntry
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums.BybitEnums import OrderType, OrderSide, OrderStatus
from exchange.ExchangeBybit import ExchangeBybit


class LimitEntry(TradeEntry):

    # Wait time in seconds after creating/updating orders
    PAUSE_TIME = 0.1

    def __init__(self, database, exchange, wallet, orders, position):
        super().__init__(database, exchange, wallet, orders, position)
        self._orderbook = Orderbook()
        self.interval_secs = utils.convert_interval_to_sec(self._config['strategy']['interval'])

        # When we place an order the price = orderbook_top + "price_delta"
        # Price delta must be an even multiple of: exchange.pair_details_dict['price_filter']['min_price']
        # For example: BTCUSDT: 0.50, ETHUSDT: 0.05, ...
        self.price_delta = float(self._exchange.pair_details_dict['price_filter']['min_price'])

        # We do not place orders when the spread is greater than "spread_tolerance"
        self.spread_tolerance = float(self.price_delta * 2)

        # threshold in seconds that will cause the entry to abort
        # We use a % of the length of the trading interval.
        # For example: 0.25 * '5m' = 75s
        self.abort_seconds = self.interval_secs * float(self._config['limit_entry']['abort_time_ratio'])

        # The trade entry will abort after slippage becomes greater than this % of the current price
        self.abort_price_pct = float(self._config['limit_entry']['abort_price_pct'])

    def get_current_ob_price(self, side):
        if side == OrderSide.Buy:
            ob, spread = self._orderbook.get_top1()
            return float(ob[1]['price'])
        else:
            ob, spread = self._orderbook.get_top1()
            return float(ob[0]['price'])

    def get_entry_price(self, side):
        spread = 100000
        while spread > self.spread_tolerance:
            if side == OrderSide.Buy:
                ob, spread = self._orderbook.get_top1()
                price = float(ob[1]['price']) - self.price_delta
                # print(f"Orderbook spread={spread} sellers top [{ob[1]['price']}]. Tentative Price: {price}")
            else:
                ob, spread = self._orderbook.get_top1()
                price = float(ob[0]['price']) + self.price_delta
                # print(f"Orderbook spread={spread}, buyers top [{ob[0]['price']}]. Tentative Price: {price}")
        return float(price)

    def update_order(self, side, order_id):
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'
        price = self.get_entry_price(side)
        stop_loss = self.get_stop_loss(side, price)

        result = self._exchange.replace_active_order_pr_sl(order_id, price, stop_loss)
        self._logger.info(f"Updated {side_l_s} Limit Order[{order_id[-8:]}: price={self.f_dec(price)}, "
                          f"stop_loss={self.f_dec(stop_loss)}].")

    def cancel_order(self, side, order_id):
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'

        result = self._exchange.cancel_active_order(order_id)
        self._logger.info(f"Cancelled {side_l_s} Limit Order {order_id[-8:]}.")

    def enter_trade(self, side):
        """
            Order Statuses: Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
        """
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'
        start_time = time.time()
        start_price = self.get_current_ob_price(side)
        abort_price_diff = self.abort_price_pct * start_price
        qty, order_id = self.place_limit_entry(side)
        start_qty = qty
        time.sleep(self.PAUSE_TIME)
        while True:
            # Wait for the order to appear on websocket or http session
            while True:
                order = self._exchange.get_order_by_id(self.pair, order_id)
                if order:
                    break
            elapsed_time = time.time() - start_time
            current_price = self.get_current_ob_price(side)
            price_diff = abs(current_price - start_price)
            # Crossed time threshold, abort.
            if elapsed_time > self.abort_seconds:
                self._logger.info(f'{side_l_s} Limit Entry Aborting. '
                                  f'elapsed_time={self.f_dec(elapsed_time)}s > abort_threshold={self.abort_seconds}s')
                self.cancel_order(side, order_id)
                break
            # Crossed price threshold, abort.
            elif price_diff > abort_price_diff:
                if side == OrderSide.Buy:
                    abort_price = start_price + abort_price_diff
                    self._logger.info(f'{side_l_s} Limit Entry Aborting. current_price={self.f_dec(current_price)} > '
                                      f'abort_price_difference={self.f_dec(abort_price)}s')
                else:
                    abort_price = start_price - abort_price_diff
                    self._logger.info(f'{side_l_s} Limit Entry Aborting. current_price={self.f_dec(current_price)} < '
                                      f'abort_price_difference={self.f_dec(abort_price)}s')
                self.cancel_order(side, order_id)
                break
            else:
                match order['order_status']:
                    case OrderStatus.Created | OrderStatus.New | OrderStatus.PartiallyFilled:
                        new_entry_price = self.get_entry_price(side)
                        if (side == OrderSide.Buy and new_entry_price > order['price']) \
                                or (side == OrderSide.Sell and new_entry_price < order['price']):
                            filled = round(start_qty - order['leaves_qty'], 16)
                            self._logger.info(f"{order['order_status']} {side_l_s} Order {filled}/{start_qty} "
                                              f"price={self.f_dec(order['price'])}")
                            self.update_order(side, order_id)
                        time.sleep(self.PAUSE_TIME)
                        continue
                    case OrderStatus.Filled:
                        self._logger.info(
                            f"Filled {side_l_s} Limit Order. last_exec_price={self.f_dec(['price'])}.")
                        break
                    case _:
                        ob_price = self.get_current_ob_price(side)
                        self._logger.info(
                            f"{order['order_status']} {side_l_s} Order: orderbook={self.f_dec(ob_price)} "
                            f"order_price={self.f_dec(order['price'])}. Retrying ...")
                        qty, order_id = self.place_limit_entry(side)
                        time.sleep(self.PAUSE_TIME)
                        continue

        exec_time = time.time() - start_time

        # Get position summary
        position = self._position.get_position(side)
        qty = position['size'] if position else 0
        avg_price = position['entry_price'] if position else 0
        self._logger.info(f'{side_l_s} limit entry trade executed in {utils.format_execution_time(exec_time)},  '
                          f'qty={qty}/{start_qty}, avg_entry_price={self.f_dec(avg_price)}.')
        return qty, avg_price

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

# order_id = 'dfbe36f9-5717-47c6-89bc-9565c999c7be'
# result = ex.cancel_active_order(order_id)
