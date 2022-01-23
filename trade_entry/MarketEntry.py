import time

from CandleHandler import CandleHandler
from Orders import Order, Orders
from Position import Position
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums.BybitEnums import OrderSide, OrderType
from enums.TradeSignals import TradeSignals
from exchange.ExchangeBybit import ExchangeBybit
from telegram_.TelegramBot import TelegramBot
from trade_entry.LimitEntry import LimitEntry
from trade_entry.BaseTradeEntry import BaseTradeEntry


class MarketEntry(BaseTradeEntry):

    def __init__(self, database, exchange, position, signal):
        super().__init__(database, exchange, position, signal)

    def enter_trade(self):
        side = OrderSide.Buy if self.signal['Signal'] == TradeSignals.EnterLong else OrderSide.Sell
        self.take_profit_order_id = None
        self.take_profit_qty = 0

        tradable_ratio = self._config['trading']['tradable_balance_ratio']
        balance = self._wallet.free
        tradable_balance = balance * tradable_ratio
        if tradable_balance < self.MIN_TRADE_AMOUNT:
            return None

        # Calculate trade size (qty) based on leverage
        qty = tradable_balance / self.signal['EntryPrice']
        if side == OrderSide.Buy:
            lev = float(self._config['trading']['leverage_long'])
        else:
            lev = float(self._config['trading']['leverage_short'])
        qty = qty * lev
        # Adjust the qty to an even number of minimum trading quantities,
        # otherwise the remainder gets truncated by the exchange
        min_trade_qty = self._exchange.pair_details_dict['lot_size_filter']['min_trading_qty']
        qty = round(int(qty / min_trade_qty) * min_trade_qty, 10)

        # Place order and open position
        order_id = self.place_market_order(side, qty, self.signal['EntryPrice'], self.sig_stop_loss_amount)

        # Wait until the position is open
        while not self._position.get_position(side) and self._position.get_position(side)['size'] != qty:
            time.sleep(0.5)

        # Created the tp order(s)
        # Wait for tp orders to match the open position
        while self.take_profit_qty < qty:
            self.set_tp_on_executions(order_id)

        # Assuming at this point that the position has been opened and available on websockets
        position = self._position.get_position(side)
        entry_price = position['entry_price'] if position else 0
        qty = position['size'] if position else 0

        # Trade entry failed we exit
        if qty == 0:
            return

        # Update position stop_loss based on actual average entry price
        old_stop_loss = self._position.get_current_stop_loss(side)
        new_stop_loss = self.get_stop_loss(side, entry_price)
        if old_stop_loss != new_stop_loss:
            # Update position stop_loss if required because of entry price slippage
            self._position.set_trading_stop(side, stop_loss=new_stop_loss)

        entry_price = round(entry_price, 2)
        # now = dt.datetime.now().strftime(constants.DATETIME_FMT)
        if side == OrderSide.Buy:
            _side = 'Long'
            _lev = f"{self._config['trading']['leverage_long']}x"
        else:
            _side = 'Short'
            _lev = f"{self._config['trading']['leverage_short']}x"
        msg = f'Entered {_lev} {_side} position, avg_price={entry_price:.2f}, qty={qty}, sl={new_stop_loss:.2f}' \
              f'slip={(self.signal["EntryPrice"] - entry_price):.2f}.'
        self._logger.info(msg)
        TelegramBot.send_to_group(msg)

        return qty, entry_price

    def place_market_order(self, side, qty, price, stop_loss):
        order = Order(side=side, symbol=self.pair, order_type=OrderType.Market, qty=qty,
                      price=price, stop_loss=stop_loss)
        order_id = self._orders.place_order(order, 'TradeEntry')['order_id']
        return order_id


"""
    Testing Market Order Trade Entries
"""
# ex = ExchangeBybit()
# db = Database(ex)
# Wal = WalletUSDT(ex)
# Ord = Orders(db, ex)
# Pos = Position(db, ex)
# CH = CandleHandler(ex)
# market_entry = MarketEntry(db, ex, Wal, Ord, Pos)
#
# price = CH.get_latest_price()
#
# market_entry.enter_trade({'Signal': TradeSignals.EnterLong, 'EntryPrice': price})
#
# market_entry.enter_trade({'Signal': TradeSignals.EnterShort, 'EntryPrice': price})
