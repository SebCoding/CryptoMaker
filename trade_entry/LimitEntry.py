import sys
import time

import rapidjson

import utils
from CandleHandler import CandleHandler
from Orderbook import Orderbook
from Orders import Order
from Position import Position
from database.Database import Database
from enums.BybitEnums import OrderType, OrderSide, OrderStatus
from enums.TradeSignals import TradeSignals
from exchange.ExchangeBybit import ExchangeBybit
from telegram_.TelegramBot import TelegramBot
from trade_entry.BaseTradeEntry import BaseTradeEntry


class LimitEntry(BaseTradeEntry):

    # Class/Static variable for counting total number of trades
    nb_trades = 0

    def __init__(self, database, exchange, position, signal):
        super().__init__(database, exchange, position, signal)
        self._orderbook = Orderbook(exchange)
        self.interval_secs = utils.convert_interval_to_sec(self._config['trading']['interval'])

        # When we place an order the price = orderbook_top + "price_delta"
        # Price delta must be an even multiple of:self.tick_size
        # For example: BTCUSDT: 0.50, ETHUSDT: 0.05, ...
        self.price_delta = self.tick_size

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
        price = 0
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

    def place_limit_order(self):
        """
            The first time we place a limit order for this trade entry, trade_start_price=0.
            All subsequents orders will have a value for trade_start_price that will be used
            to calculate a stop_loss equal to the first original order. All orders placed
            within a trade entry should have the same stop loss.
        """
        tradable_balance = self.get_tradable_balance()

        price = self.get_entry_price(self.signal['Side'])

        # Calculate trade size (qty) based on leverage
        qty = tradable_balance / price
        if self.signal['Side'] == OrderSide.Buy:
            lev = float(self._config['trading']['leverage_long'])
        else:
            lev = float(self._config['trading']['leverage_short'])
        qty = self.adj_qty(qty * lev)

        order = Order(
            side=self.signal['Side'],
            symbol=self.pair,
            order_type=OrderType.Limit,
            qty=qty,
            price=price,
            stop_loss=self.sig_stop_loss_amount
        )
        order.order_id = self._orders.place_order(order, 'TradeEntry')['order_id']
        time.sleep(self.PAUSE_TIME)
        return order

    def update_order_price(self, order_id, cur_order_price):
        new_entry_price = self.get_entry_price(self.signal['Side'])
        new_stop_loss = self.get_stop_loss(self.signal['Side'], new_entry_price)
        # Re-validate that the update is really required
        if (self.signal['Side'] == OrderSide.Buy and new_entry_price > cur_order_price) \
                or (self.signal['Side'] == OrderSide.Sell and new_entry_price < cur_order_price):
            result = self._exchange.replace_active_order_pr_sl(order_id, new_entry_price, new_stop_loss)
            self._logger.info(f"Updated {self.side_l_s} Limit Order[{order_id[-8:]}: "
                              f"price={new_entry_price:.2f}, sl={new_stop_loss:.2f}]")

            # Wait until update appears on websocket
            while True:
                order_dict = self._exchange.query_orders_rt_by_id(self.pair, order_id)
                if (order_dict and order_dict['price'] == new_entry_price) or \
                        (order_dict and order_dict['order_status'] in
                         [OrderStatus.Filled, OrderStatus.Rejected, OrderStatus.PendingCancel, OrderStatus.Cancelled]):
                    break

    def cancel_order(self, order_id):
        result = self._exchange.cancel_active_order(order_id)

        # Sometimes the order gets filled before we have time to cancel
        order_dict = self._exchange.query_orders_rt_by_id(self.pair, order_id)
        while not order_dict or order_dict['order_status'] not in [OrderStatus.Cancelled, OrderStatus.Filled]:
            time.sleep(self.PAUSE_TIME)
            order_dict = self._exchange.query_orders_rt_by_id(self.pair, order_id)

        if order_dict['order_status'] == OrderStatus.Cancelled:
            self._logger.info(f"Cancelled {self.side_l_s} Limit Order {order_id[-8:]}.")
        elif order_dict['order_status'] == OrderStatus.Filled:
            self._logger.info(f"While trying to cancel, {self.side_l_s} Limit Order {order_id[-8:]} has been filled.")
        return order_dict['order_status']

    def enter_trade(self):
        prev_line = ''

        start_time = time.time()
        order_obj = self.place_limit_order()
        trade_start_qty = order_obj.qty
        trade_start_price = order_obj.price
        abort_price_diff = round(self.abort_price_pct * trade_start_price, 2)
        cum_trade_qty = 0

        time.sleep(self.PAUSE_TIME)
        while True:
            # Wait for the order to appear on websocket
            while True:
                order_dict = self._exchange.get_order_by_id_hybrid(self.pair, order_obj.order_id)
                if order_dict:
                    break

            order_id = order_dict['order_id']
            order_status = order_dict['order_status']
            order_qty = order_dict['qty']
            order_price = order_dict['price']
            cum_exec_qty = order_dict['cum_exec_qty']

            elapsed_time = time.time() - start_time
            current_price = self.get_current_ob_price(self.signal['Side'])
            price_diff = abs(round(current_price - trade_start_price, 2))

            # Crossed time threshold, abort.
            if round(elapsed_time, 1) > self.abort_seconds:
                status = self.cancel_order(order_id)
                if status == OrderStatus.Cancelled:
                    self.adjust_tp_order(order_id)
                    cum_trade_qty += cum_exec_qty
                    assert (cum_exec_qty == self.take_profit_cum_qty)
                    self._logger.info(f'{self.side_l_s} Limit Entry Aborting. '
                                      f'elapsed_time={round(elapsed_time, 1)}s > abort_threshold={self.abort_seconds}s')
                    break

            # Crossed price threshold, abort.
            if price_diff > abort_price_diff:
                status = self.cancel_order(order_id)
                if status == OrderStatus.Cancelled:
                    self.adjust_tp_order(order_id)
                    cum_trade_qty += cum_exec_qty
                    assert (cum_exec_qty == self.take_profit_cum_qty)
                    if self.signal['Side'] == OrderSide.Buy:
                        abort_price = trade_start_price + abort_price_diff
                        self._logger.info(f'{self.side_l_s} Limit Entry Aborting. current_price={current_price:.2f} > '
                                          f'abort_price={abort_price:.2f}')
                    else:
                        abort_price = trade_start_price - abort_price_diff
                        self._logger.info(f'{self.side_l_s} Limit Entry Aborting. current_price={current_price:.2f} < '
                                          f'abort_price={abort_price:.2f}')
                    break

            # Check order status and take action
            # Order Statuses: Created, New, PartiallyFilled, Filled, Rejected, PendingCancel, Cancelled
            match order_status:
                case OrderStatus.Created | OrderStatus.New:
                    self.update_order_price(order_id, order_price)
                    self.adjust_tp_order(order_id)
                    continue
                case OrderStatus.PartiallyFilled:
                    self.update_order_price(order_id, order_price)
                    self.adjust_tp_order(order_id)
                    continue
                case OrderStatus.Filled:
                    self.adjust_tp_order(order_id)
                    self._logger.info(f"Filled {self.side_l_s} Limit Order[{order_id[-8:]}: "
                                      f"qty={cum_exec_qty}/{order_qty} last_exec_price={order_price:.2f}]")
                    cum_trade_qty += cum_exec_qty
                    assert(cum_exec_qty == self.take_profit_cum_qty)
                    break
                # Rejected, PendingCancel, Cancelled
                case _:
                    self.adjust_tp_order(order_id)
                    cum_trade_qty += cum_exec_qty
                    assert (cum_exec_qty == self.take_profit_cum_qty)
                    ob_price = self.get_current_ob_price(self.signal['Side'])
                    self._logger.info(
                        f"{order_status} {self.side_l_s} Order[{order_id[-8:]}: qty={cum_exec_qty}/{order_qty}, "
                        f"orderbook={ob_price:.2f} = order_price={order_price:.2f}]. Retrying ...")
                    order_obj = self.place_limit_order()
                    self.take_profit_order_id = None
                    self.take_profit_cum_qty = 0
                    self.adjust_tp_order(order_obj.order_id)
                    continue

        exec_time = time.time() - start_time
        LimitEntry.nb_trades += 1

        # Get position summary.
        # NOTE: The qty and avg_price are only valid if the position was zero prior to this trade entry.
        # It also happens that the position has closed already by sl/tp by the time we arrive at this line.
        position = self._position.get_position(self.signal['Side'])
        qty = round(position['size'], 10) if position else 0
        avg_price = position['entry_price'] if position else 0
        position_value = position['position_value'] if position else 0
        cum_trade_qty = round(cum_trade_qty, 10)
        msg = f'{LimitEntry.nb_trades} {self.side_l_s} limit trade entry completed. Exec[{utils.seconds_to_human_readable(exec_time)}], ' \
              f'qty[{cum_trade_qty}/{trade_start_qty}], '
        # Position has been closed by sl/tp
        if position_value != 0:
            msg += f'pos_value[{position_value:.2f}], avg_price[{avg_price:.2f}], ' \
                   f'slip[{(avg_price - self.signal["EntryPrice"] if avg_price > 0 else 0):.2f}] '
        self._logger.info(msg)
        #TelegramBot.send_to_group(msg.replace(' limit trade entry completed. ', '. '))

        return qty, avg_price

    def adjust_tp_order(self, order_id):
        """
            Create/Update take profit limit order based on the current cum_exec_qty of the current order
        """
        tp_side = OrderSide.Buy if self.signal['Side'] == OrderSide.Sell else OrderSide.Sell
        order = self._exchange.get_order_by_id_hybrid(self.pair, order_id)

        if order and order['cum_exec_qty'] > self.take_profit_cum_qty:
            self.take_profit_cum_qty = float(order['cum_exec_qty'])
            tp_order = self._exchange.query_orders_rt_by_id(self.pair, self.take_profit_order_id)

            # No pre-existing take_profit order or if it exists it has been filled or cancelled
            # Create a new take_profit order
            if not self.take_profit_order_id or tp_order['order_status'] not in [OrderStatus.New,
                                                                                 OrderStatus.PartiallyFilled]:
                while True:
                    current_price = self.get_current_ob_price(tp_side)
                    # current_price did not cross take_profit price yet
                    if (self.signal['Side'] == OrderSide.Buy and current_price < self.sig_take_profit_amount) \
                            or (self.signal['Side'] == OrderSide.Sell and current_price > self.sig_take_profit_amount):
                        tp_order_id = self.place_tp_order(self.signal['Side'], self.take_profit_cum_qty,
                                                          self.sig_take_profit_amount)
                    # The take_profit has been crossed, re-adjust take_profit price
                    else:
                        if self.signal['Side'] == OrderSide.Buy:
                            new_take_profit = self.adj_price(current_price + self.tick_size)
                        else:
                            new_take_profit = self.adj_price(current_price - self.tick_size)
                        tp_order_id = self.place_tp_order(self.signal['Side'], self.take_profit_cum_qty,
                                                          new_take_profit)

                    tp_order = self._exchange.query_orders_rt_by_id(self.pair, tp_order_id)
                    if (not tp_order or tp_order['order_status'] \
                            in [OrderStatus.Cancelled, OrderStatus.PendingCancel, OrderStatus.Rejected]) \
                            and self._position.currently_in_position(self.signal['Side']):
                        continue
                    else:
                        break
                self.take_profit_order_id = tp_order['order_id']
                op_type = 'create'
            # We update the existing take_profit order
            else:
                tp_order = self._exchange.query_orders_rt_by_id(self.pair, self.take_profit_order_id)
                current_price = self.get_current_ob_price(tp_side)

                # The take_profit order is still active.
                if tp_order['order_status'] in [OrderStatus.Created, OrderStatus.New, OrderStatus.PartiallyFilled]:
                    # Adjust qty only. The current_price did not cross over the take_profit price
                    if (self.signal['Side'] == OrderSide.Buy and current_price < self.sig_take_profit_amount) \
                            or (self.signal['Side'] == OrderSide.Sell and current_price > self.sig_take_profit_amount):
                        self._exchange.replace_active_order_qty(
                            tp_order['order_id'],
                            self.take_profit_cum_qty
                        )
                    # Adjust qty and price. The take_profit has been crossed, re-adjust take_profit price
                    else:
                        while True:
                            if self.signal['Side'] == OrderSide.Buy:
                                new_take_profit = self.adj_price(current_price + self.tick_size)
                            else:
                                new_take_profit = self.adj_price(current_price - self.tick_size)
                            self.sig_take_profit_amount = new_take_profit
                            self._exchange.replace_active_order_qty_pr(
                                tp_order['order_id'],
                                self.take_profit_cum_qty,
                                new_take_profit
                            )
                            tp_order = self._exchange.query_orders_rt_by_id(self.pair, tp_order['order_id'])
                            if tp_order['qty'] != self.take_profit_cum_qty \
                                    or tp_order['order_status'] in [OrderStatus.Cancelled, OrderStatus.PendingCancel,
                                                                    OrderStatus.Rejected]:
                                continue
                            else:
                                break
                op_type = 'update'

            if op_type == 'update':
                self._logger.info(f"Updated {tp_side} TakeProfit Limit Order[{self.take_profit_order_id[-8:]}: "
                                  f"qty={self.take_profit_cum_qty}, tp_price={self.sig_take_profit_amount:.2f}]")



"""
    Testing Limit Order Trade Entries
"""
# ex = ExchangeBybit()
# db = Database(ex)
# Pos = Position(db, ex)
# CH = CandleHandler(ex)
#
# signal = {
#     'Pair': 'ETHUSDT',
#     'Side': 'Sell',
#     'EntryPrice': CH.get_latest_price()
# }
#
# limit_entry = LimitEntry(db, ex, Pos, signal).enter_trade()
# limit_entry = LimitEntry(db, ex, Pos, signal).enter_trade()
# limit_entry = LimitEntry(db, ex, Pos, signal).enter_trade()

#print(rapidjson.dumps(ex.query_orders_rt_by_id('ETHUSDT', 'd39c6cc0-3cb1-48a2-9773-85464e2cb510'), indent=2))

