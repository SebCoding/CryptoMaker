import time

import arrow
import rapidjson

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
    PAUSE_TIME = 0.2

    def __init__(self, database, exchange, wallet, orders, position):
        super().__init__(database, exchange, wallet, orders, position)
        self._logger.info(f'Limit Entry Settings:\n' + rapidjson.dumps(self._config['limit_entry'], indent=2))
        self._orderbook = Orderbook(exchange)
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
        self.abort_seconds = self.interval_secs * float(self._config['limit_entry']['abort_time_candle_ratio'])

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
        return round(price, 10)  # We need to round to avoid: 3323.05 - 0.05 = 3323.0499999999997

    def place_limit_order(self, side):
        balance = self._wallet.free
        tradable_balance = balance * self.tradable_ratio
        if tradable_balance < self.MIN_TRADE_AMOUNT:
            return 0, None

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

    def update_order(self, side, order_id, current_price):
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'
        new_entry_price = self.get_entry_price(side)
        stop_loss = self.get_stop_loss(side, new_entry_price)

        # Re-validate that the update is really required
        if (side == OrderSide.Buy and new_entry_price > current_price) \
                or (side == OrderSide.Sell and new_entry_price < current_price):
            result = self._exchange.replace_active_order_pr_sl(order_id, new_entry_price, stop_loss)
            self._logger.info(f"Updated {side_l_s} Limit Order[{order_id[-8:]}: price={new_entry_price}, "
                              f"stop_loss={stop_loss}].")

    def cancel_order(self, side, order_id):
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'

        result = self._exchange.cancel_active_order(order_id)
        self._logger.info(f"Cancelled {side_l_s} Limit Order {order_id[-8:]}.")

    def get_executions(self):
        """
        Returns a list of execution dictionaries
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
        data = self._exchange.ws_private.fetch(self._exchange.execution_topic_name)
        return data

    def enter_trade(self, side):
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'
        prev_line = ''
        last_filled = 0
        start_price = self.get_current_ob_price(side)
        abort_price_diff = self.abort_price_pct * start_price
        start_time = time.time()
        qty, order_id = self.place_limit_order(side)
        if qty == 0:
            return 0, 0
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
                                  f'elapsed_time={elapsed_time}s > abort_threshold={self.abort_seconds}s')
                self.cancel_order(side, order_id)
                break

            # Crossed price threshold, abort.
            if price_diff > abort_price_diff:
                if side == OrderSide.Buy:
                    abort_price = start_price + abort_price_diff
                    self._logger.info(f'{side_l_s} Limit Entry Aborting. current_price={current_price} > '
                                      f'abort_price_difference={abort_price}s')
                else:
                    abort_price = start_price - abort_price_diff
                    self._logger.info(f'{side_l_s} Limit Entry Aborting. current_price={current_price} < '
                                      f'abort_price_difference={abort_price}s')
                self.cancel_order(side, order_id)
                break

            order_status = order['order_status']
            filled = round(start_qty - order['leaves_qty'], 10)

            # Check order status and take action
            # Order Statuses: Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
            match order_status:
                case OrderStatus.Created | OrderStatus.New | OrderStatus.PartiallyFilled:
                    new_entry_price = self.get_entry_price(side)
                    line = f"{order_status} {side_l_s} Order {filled}/{start_qty} price={order['price']}"
                    if line != prev_line:
                        self._logger.info(line)
                        prev_line = line
                    if (side == OrderSide.Buy and new_entry_price > order['price']) \
                            or (side == OrderSide.Sell and new_entry_price < order['price']):
                        self.update_order(side, order_id, order['price'])
                    time.sleep(self.PAUSE_TIME)
                    continue
                case OrderStatus.Filled:
                    self._logger.info(
                        f"Filled {side_l_s} Limit Order. last_exec_price={order['price']}.")
                    break
                case _:
                    ob_price = self.get_current_ob_price(side)
                    self._logger.info(
                        f"{order_status} {side_l_s} Order: orderbook={ob_price} "
                        f"order_price={order['price']}. Retrying ...")
                    qty, order_id = self.place_limit_order(side)
                    time.sleep(self.PAUSE_TIME)
                    continue

        exec_time = time.time() - start_time

        # Get position summary
        position = self._position.get_position(side)
        qty = position['size'] if position else 0
        avg_price = position['entry_price'] if position else 0
        self._logger.info(f'{side_l_s} limit entry trade executed in {utils.format_execution_time(exec_time)},  '
                          f'qty={qty}/{start_qty}, avg_entry_price={avg_price}.')
        return qty, avg_price




"""
    Testing Limit Order Trade Entries
"""
# ex = ExchangeBybit()
# db = Database(ex)
# Wal = WalletUSDT(ex)
# Ord = Orders(db, ex)
# Pos = Position(db, ex)
#
# limit_entry = LimitEntry(db, ex, Wal, Ord, Pos)
# limit_entry.enter_trade(OrderSide.Buy)

# order_id = 'dfbe36f9-5717-47c6-89bc-9565c999c7be'
# result = ex.cancel_active_order(order_id)
