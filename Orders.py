import pandas as pd
import arrow

import constants
from Configuration import Configuration
from logging_.Logger import Logger
from enums.BybitEnums import TimeInForce, OrderType, OrderSide


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

    def __init__(self, database, exchange):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        self.exchange = exchange
        self.stake_currency = self._config['exchange']['stake_currency']
        self.db = database
        self.refresh_orders()

    # Order Statuses that can be used as filter:
    # Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
    def refresh_orders(self, order_status=None):
        data = self.exchange.get_orders(self.pair, order_status)
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
    def place_order(self, order, reason=''):
        result = self.exchange.place_order(order)
        if result:
            # result['reason'] = reason
            result['take_profit'] = order.take_profit
            result['stop_loss'] = order.stop_loss

            # No price for market orders
            if order.order_type == OrderType.Market:
                result['price'] = 0

            created_time = arrow.get(result['created_time']).to('local').datetime
            created_time = created_time.strftime(constants.DATETIME_FMT)
            result['created_time'] = created_time

            updated_time = arrow.get(result['updated_time']).to('local').datetime
            updated_time = updated_time.strftime(constants.DATETIME_FMT)
            result['updated_time'] = updated_time

            # self._logger.info(f"{created_time} Confirmed {reason} {order.order_type} Order: " + order.to_string())

            side = 'Long' if order.side == OrderSide.Buy else 'Short'
            self._logger.info(f"Created {side} {reason} {order.order_type} Order{order.to_string()}.")
            #self.db.add_order_dict(result)
        return result

    def update_db_order_stop_loss_by_id(self, order_id, new_stop_loss):
        self.db.update_order_stop_loss_by_id(order_id, new_stop_loss)
        self._logger.info(f'DB Order: {order_id} has been updated with new stop_loss={new_stop_loss}.')




