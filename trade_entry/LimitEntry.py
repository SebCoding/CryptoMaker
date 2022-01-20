import sys
import time

import arrow
import rapidjson

import constants
import utils
from Orderbook import Orderbook
from Orders import Order, Orders
from Position import Position
from enums.TradeSignals import TradeSignals
from trade_entry.BaseTradeEntry import BaseTradeEntry
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums.BybitEnums import OrderType, OrderSide, OrderStatus
from exchange.ExchangeBybit import ExchangeBybit


class LimitEntry(BaseTradeEntry):
    # Wait time in seconds after creating/updating orders
    PAUSE_TIME = 0.3

    LOOP_TIMEOUT = 5*60  # 2 minutes

    def __init__(self, database, exchange, wallet, orders, position):
        super().__init__(database, exchange, wallet, orders, position)
        self._logger.info(f'Limit Entry Settings:\n' + rapidjson.dumps(self._config['limit_entry'], indent=2))
        self._orderbook = Orderbook(exchange)
        self.interval_secs = utils.convert_interval_to_sec(self._config['trading']['interval'])

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

    def place_limit_order(self, side, trade_start_price=0):
        """
            The first time we place a limit order for this trade entry, trade_start_price=0.
            All subsequents orders will have a value for trade_start_price that will be used
            to calculate a stop_loss equal to the first original order. All orders placed
            within a trade entry should have the same stop loss.
        """
        balance = self._wallet.free
        tradable_balance = balance * self.tradable_ratio
        if tradable_balance < self.MIN_TRADE_AMOUNT:
            return 0, None

        price = self.get_entry_price(side)
        if trade_start_price == 0:
            stop_loss = self.get_stop_loss(side, price)
        else:
            stop_loss = self.get_stop_loss(side, trade_start_price)

        # Calculate trade size (qty) based on leverage
        qty = tradable_balance / price
        if side == OrderSide.Buy:
            lev = float(self._config['trading']['leverage_long'])
        else:
            lev = float(self._config['trading']['leverage_short'])
        qty = self.adj_qty(qty * lev)

        order = Order(
            side=side,
            symbol=self.pair,
            order_type=OrderType.Limit,
            qty=qty,
            price=price,
            stop_loss=stop_loss
        )
        order.order_id = self._orders.place_order(order, 'TradeEntry')['order_id']
        time.sleep(self.PAUSE_TIME)
        return order

    def update_order_price(self, side, order_id, cur_order_price):
        new_entry_price = self.get_entry_price(side)
        # Re-validate that the update is really required
        if (side == OrderSide.Buy and new_entry_price > cur_order_price) \
                or (side == OrderSide.Sell and new_entry_price < cur_order_price):
            side_l_s = 'Long' if side == OrderSide.Buy else 'Short'

            # print(f'cur_order_price={cur_order_price}, new_entry_price={new_entry_price}')

            # Old version where we also update stop_loss
            # stop_loss = self.get_stop_loss(side, new_entry_price)
            # result = self._exchange.replace_active_order_pr_sl(order_id, new_entry_price, stop_loss)
            # self._logger.info(f"Updated {side_l_s} Limit Order[{order_id[-8:]}: price={new_entry_price:.2f}, "
            #                   f"stop_loss={stop_loss:.2f}].")

            result = self._exchange.replace_active_order_pr(order_id, new_entry_price)
            self._logger.info(f"Updated {side_l_s} Limit Order[{order_id[-8:]}: price={new_entry_price:.2f}]")

            # Wait until update appears on websocket
            timeout = time.time() + self.LOOP_TIMEOUT
            while True:
                order_dict = self._exchange.get_order_by_id_ws_only(self.pair, order_id)
                if (order_dict and order_dict['price'] == new_entry_price) or \
                        (order_dict and order_dict['order_status'] in
                         [OrderStatus.Filled, OrderStatus.Rejected, OrderStatus.PendingCancel, OrderStatus.Cancelled]):
                    break
                if time.time() > timeout:
                    self._logger.error(f'Possible infinite loop in update_order_price()')
                    sys.exit(1)

    def cancel_order(self, side, order_id):
        result = self._exchange.cancel_active_order(order_id)
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'
        self._logger.info(f"Cancelled {side_l_s} Limit Order {order_id[-8:]}.")

    def enter_trade(self, signal):
        side = OrderSide.Buy if signal['Signal'] == TradeSignals.EnterLong else OrderSide.Sell
        side_l_s = 'Long' if side == OrderSide.Buy else 'Short'
        self.take_profit_order_id = None
        self.take_profit_qty = 0
        self.filled_by_execution = 0
        prev_line = ''

        start_time = time.time()
        order_obj = self.place_limit_order(side)
        trade_start_qty = order_obj.qty
        trade_start_price = order_obj.price
        abort_price_diff = round(self.abort_price_pct * trade_start_price, 2)

        time.sleep(self.PAUSE_TIME)
        while True:

            # Wait for the order to appear on websocket
            timeout = time.time() + self.LOOP_TIMEOUT
            while True:
                order_dict = self._exchange.get_order_by_id_ws_only(self.pair, order_obj.order_id)
                if order_dict:
                    break
                if time.time() > timeout:
                    self._logger.error(f'Possible infinite loop: get_order_by_id_ws_only()')
                    sys.exit(1)

            order_id = order_dict['order_id']
            order_status = order_dict['order_status']
            order_qty = order_dict['qty']
            order_price = order_dict['price']
            leaves_qty = order_dict['leaves_qty']  # if 'leaves_qty' in order_dict.keys() else 0

            elapsed_time = time.time() - start_time
            current_price = self.get_current_ob_price(side)
            price_diff = abs(round(current_price - trade_start_price, 2))

            # Crossed time threshold, abort.
            if round(elapsed_time, 1) > self.abort_seconds:
                self._logger.info(f'{side_l_s} Limit Entry Aborting. '
                                  f'elapsed_time={round(elapsed_time, 1)}s > abort_threshold={self.abort_seconds}s')

                # Wait for tp orders to match possibly partially opened position
                timeout = time.time() + self.LOOP_TIMEOUT
                while self.take_profit_qty < round(order_qty - leaves_qty, 10):
                    self.create_tp_on_executions(side, trade_start_price, order_id)
                    if time.time() > timeout:
                        self._logger.error(f'Possible infinite loop: Crossed time threshold, abort')
                        sys.exit(1)

                self.cancel_order(side, order_id)
                break

            # Crossed price threshold, abort.
            if price_diff > abort_price_diff:
                if side == OrderSide.Buy:
                    abort_price = round(trade_start_price + abort_price_diff, 2)
                    self._logger.info(f'{side_l_s} Limit Entry Aborting. current_price={current_price} > '
                                      f'abort_price={abort_price}')
                else:
                    abort_price = trade_start_price - abort_price_diff
                    self._logger.info(f'{side_l_s} Limit Entry Aborting. current_price={current_price} < '
                                      f'abort_price={abort_price}')

                # Wait for tp orders to match possibly partially opened position
                timeout = time.time() + self.LOOP_TIMEOUT
                while self.take_profit_qty < round(order_qty - leaves_qty, 10):
                    self.create_tp_on_executions(side, trade_start_price, order_id)
                    if time.time() > timeout:
                        self._logger.error(f'Possible infinite loop: Crossed price threshold, abort')
                        sys.exit(1)

                self.cancel_order(side, order_id)
                break

            # Check order status and take action
            # Order Statuses: Created, New, PartiallyFilled, Filled, Rejected, PendingCancel, Cancelled
            match order_status:
                case OrderStatus.Created | OrderStatus.New:
                    filled = round(trade_start_qty - leaves_qty, 10)
                    line = f"{order_status} {side_l_s} Order[{order_id[-8:]}: {filled}/{trade_start_qty} price={order_price:.2f}]"
                    if line != prev_line:
                        self._logger.info(line)
                        prev_line = line
                    self.update_order_price(side, order_id, order_price)
                    self.create_tp_on_executions(side, trade_start_price, order_id)
                    continue
                case OrderStatus.PartiallyFilled:
                    filled = round(trade_start_qty - leaves_qty, 10)
                    line = f"{order_status} {side_l_s} Order[{order_id[-8:]}: {filled}/{trade_start_qty} price={order_price:.2f}]"
                    if line != prev_line:
                        self._logger.info(line)
                        prev_line = line
                    self.update_order_price(side, order_id, order_price)
                    self.create_tp_on_executions(side, trade_start_price, order_id)
                    continue
                case OrderStatus.Filled:
                    self._logger.info(
                        f"Filled {side_l_s} Limit Order[{order_id[-8:]}: qty={order_qty} last_exec_price={order_price:.2f}]")
                    timeout = time.time() + self.LOOP_TIMEOUT
                    while self.take_profit_qty < order_qty:
                        self.create_tp_on_executions(side, trade_start_price, order_id)
                        if time.time() > timeout:
                            self._logger.error(f'Possible infinite loop: case OrderStatus.Filled')
                            sys.exit(1)
                    break
                # Rejected, PendingCancel, Cancelled
                case _:
                    ob_price = self.get_current_ob_price(side)
                    self._logger.info(
                        f"{order_status} {side_l_s} Order[{order_id[-8:]}]: orderbook={ob_price:.2f} "
                        f"order_price={order_price:.2f}. Retrying ...")
                    order_obj = self.place_limit_order(side, trade_start_price)
                    self.take_profit_order_id = None
                    self.take_profit_qty = 0
                    self.create_tp_on_executions(side, order_obj.price, order_obj.order_id)
                    continue

        exec_time = time.time() - start_time

        # Get position summary
        position = self._position.get_position(side)
        # qty = position['size'] if position else 0
        avg_price = position['entry_price'] if position else 0
        self._logger.info(f'{side_l_s} limit entry trade executed in {utils.seconds_to_human_readable(exec_time)}, '
                          f'qty[{self.filled_by_execution}/{trade_start_qty}], '
                          f'avg_entry_price[{avg_price:.2f}], '
                          f'slippage[{(avg_price - trade_start_price if avg_price > 0 else 0):.2f}]')

        return self.filled_by_execution, avg_price


"""
    Testing Limit Order Trade Entries
"""
# ex = ExchangeBybit()
# db = Database(ex)
# Wal = WalletUSDT(ex)
# Ord = Orders(db, ex)
# Pos = Position(db, ex)
# limit_entry = LimitEntry(db, ex, Wal, Ord, Pos)
#
# limit_entry.enter_trade({'Signal': TradeSignals.EnterShort})
# print('sleeping'); time.sleep(10)
# limit_entry.enter_trade({'Signal': TradeSignals.EnterLong})
# print('sleeping'); time.sleep(10)
# ex.cancel_all_active_orders()
# limit_entry.enter_trade({'Signal': TradeSignals.EnterShort})
# print('sleeping'); time.sleep(10)
# ex.cancel_all_active_orders()
# limit_entry.enter_trade({'Signal': TradeSignals.EnterLong})
# print('sleeping'); time.sleep(10)
# ex.cancel_all_active_orders()
# limit_entry.enter_trade({'Signal': TradeSignals.EnterShort})