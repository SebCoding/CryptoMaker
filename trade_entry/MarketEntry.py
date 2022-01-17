import time

from Orders import Order
from enums.BybitEnums import OrderSide, OrderType
from trade_entry.TradeEntry import TradeEntry


class MarketEntry(TradeEntry):

    def __init__(self, database, exchange, wallet, orders, position, candle_handler):
        super().__init__(database, exchange, wallet, orders, position)
        self._candle_handler = candle_handler

    def enter_trade(self, side):
        tradable_ratio = self._config['trading']['tradable_balance_ratio']
        balance = self._wallet.free
        tradable_balance = balance * tradable_ratio
        if tradable_balance < self.MIN_TRADE_AMOUNT:
            return None

        tentative_entry_price = self._candle_handler.get_latest_price()
        stop_loss = self.get_stop_loss(side, tentative_entry_price)

        # Calculate trade size (qty) based on leverage
        qty = tradable_balance / tentative_entry_price
        if side == OrderSide.Buy:
            lev = float(self._config['trading']['leverage_long'])
        else:
            lev = float(self._config['trading']['leverage_short'])
        qty = qty * lev
        # Adjust the qty to an even number of minimum trading quantities,
        # otherwise the remainder gets truncated by the exchange
        min_trade_qty = self._exchange.pair_details_dict['lot_size_filter']['min_trading_qty']
        qty = round(int(qty / min_trade_qty) * min_trade_qty, 10)

        # Step 1: Place order and open position
        order_id = self.place_market_order(side, qty, stop_loss)

        # Assuming at this point that the position has been opened and available on websockets
        position = self._position.get_position(side)
        entry_price = position['entry_price'] if position else 0
        qty = position['size'] if position else 0

        # Trade entry failed we exit
        if qty == 0:
            return

        entry_price = round(entry_price, 2)
        # now = dt.datetime.now().strftime(constants.DATETIME_FMT)
        if side == OrderSide.Buy:
            _side = 'Long'
            _lev = f"{self._config['trading']['leverage_long']}x"
        else:
            _side = 'Short'
            _lev = f"{self._config['trading']['leverage_short']}x"
        self._logger.info(f'Entered {_lev} {_side} position, entry_price={entry_price} size={qty}.')

        # Step 2: Place a limit take_profit order based on the confirmed position entry_price
        # Calculate take_profit based the on actual position entry price
        take_profit = 0
        if side == OrderSide.Buy:
            take_profit = self.get_take_profit(side, entry_price)
        if side == OrderSide.Sell:
            take_profit = self.get_take_profit(side, entry_price)
        take_profit = round(take_profit, 0)

        # take_profit order side is opposite has trade entry
        side_tp = OrderSide.Buy if side == OrderSide.Sell else OrderSide.Sell
        tp_order = Order(side=side_tp, symbol=self.pair, order_type=OrderType.Limit, qty=qty,
                         price=take_profit, reduce_only=True)
        tp_order_id = self._orders.place_order(tp_order, 'TakeProfit')['order_id']

        # Step 3: Update position stop_loss based on actual average entry price
        if tentative_entry_price != entry_price:
            old_stop_loss = self._position.get_current_stop_loss(side)
            new_stop_loss = self.get_stop_loss(side, entry_price)
            if old_stop_loss != new_stop_loss:
                # Update position stop_loss if required because of entry price slippage
                self._position.set_trading_stop(side, stop_loss=new_stop_loss)

                # Update original order with new stop_loss value
                # self._orders.update_db_order_stop_loss_by_id(order_id, new_stop_loss)

        time.sleep(1)  # Sleep to let the order info be available by http or websocket

    def place_market_order(self, side, qty, stop_loss):
        order = Order(side=side, symbol=self.pair, order_type=OrderType.Market, qty=qty,
                      stop_loss=stop_loss)
        order_id = self._orders.place_order(order, 'TradeEntry')['order_id']
        # Wait until the position is open
        while not self._position.currently_in_position(side):
            time.sleep(0.1)
        return order_id
