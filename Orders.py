import time

import pandas as pd

from Configuration import Configuration
from Logger import Logger
from enums.BybitEnums import TimeInForce, OrderType


class Order:
    def __init__(self, side, symbol, order_type, qty, price=0, take_profit=0, stop_loss=0, reduce_only=False):
        self.side = side
        self.symbol = symbol
        self.order_type = order_type
        self.qty = qty
        self.price = price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.time_in_force = TimeInForce.GTC if order_type == OrderType.Market else TimeInForce.PostOnly
        self.close_on_trigger = False
        self.reduce_only = reduce_only

    def to_string(self):
        order_str = f'[symbol={self.symbol} type={self.order_type} side={self.side} qty={self.qty}'
        if self.order_type == 'Limit':
            order_str += f' price={self.price}'
        if self.take_profit > 0:
            order_str += f' tp={self.take_profit}'
        if self.stop_loss > 0:
            order_str += f' sl={self.stop_loss}'
        if self.reduce_only:
            order_str += f' reduce_only={self.reduce_only}'
        order_str += f' time_in_force={self.time_in_force}]'
        return order_str


class Orders:
    _orders = None

    def __init__(self, exchange, database):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._pair = self._config['exchange']['pair']
        self._exchange = exchange
        self._stake_currency = self._config['exchange']['stake_currency']
        self.db = database
        self.refresh_orders()

    # Order Statuses that can be used as filter:
    # Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
    def refresh_orders(self, order_status=None):
        data = self._exchange.get_orders(self._pair, order_status)
        if data:
            self._orders = data

    def get_orders(self, order_status=None):
        self.refresh_orders(order_status)
        return self._orders

    orders = property(get_orders)

    # returns a DataFrame containing the Long/Short positions
    def get_orders_df(self, order_status=None):
        self.refresh_orders(order_status)
        df = pd.DataFrame(self._orders)
        # Only keep relevant columns and reorder
        # df = df.loc[:,
        #      ['symbol', 'leverage', 'side', 'size', 'position_value', 'entry_price', 'liq_price',
        #       'is_isolated', 'position_margin', 'unrealised_pnl', 'stop_loss', 'take_profit', 'trailing_stop']]
        # df.rename(columns={'open_time': 'start'}, inplace=True)
        return df

    """
        Place an active order.
        Params (* are mandatory):
            *side: Buy, Sell
            *symbol: BTCUSDT 
            *order_type: Market, Limit
            *qty: (Order quantity in BTC)
            *price: (Order price. Required if you make limit price order)
            take_profit: (Take profit price, only take effect upon opening the position)
            stop_loss: (Stop loss price, only take effect upon opening the position)
    """
    def place_order(self, order, reason):
        self._logger.info(f"Placing {reason} {order.order_type} Order: " + order.to_string())
        result = self._exchange.place_order(order)
        if result:
            result['reason'] = reason
            self.db.add_order_dict(result)
        return result

