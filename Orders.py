import pandas as pd

from Configuration import Configuration
from Logger import Logger


class Orders:
    _orders = None

    def __init__(self, exchange):
        self.logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._pair = self._config['exchange']['pair']
        self._exchange = exchange
        self._stake_currency = self._config['exchange']['stake_currency']
        self.refresh_orders()

    # Order Statuses that can be used as filter:
    # Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
    def refresh_orders(self):
        data = self._exchange.get_orders(self._pair, order_status=None)
        if data:
            self._orders = data

    def get_orders(self):
        self.refresh_orders()
        return self._orders

    orders = property(get_orders)

    # returns a DataFrame containing the Long/Short positions
    def get_orders_df(self):
        self.refresh_orders()
        df = pd.DataFrame(self._orders)
        # Only keep relevant columns and reorder
        # df = df.loc[:,
        #      ['symbol', 'leverage', 'side', 'size', 'position_value', 'entry_price', 'liq_price',
        #       'is_isolated', 'position_margin', 'unrealised_pnl', 'stop_loss', 'take_profit', 'trailing_stop']]
        #df.rename(columns={'open_time': 'start'}, inplace=True)
        return df

    """
        Place an active order.
        Params (* are mandatory):
            *side: Buy, Sell
            *symbol: BTCUSDT 
            *order_type: Market, Limit
            *qty: (Order quantity in BTC)
            *price: (Order price. Required if you make limit price order)
            *time_in_force: PostOnly, GoodTillCancel, ImmediateOrCancel, FillOrKill
            *close_on_trigger: true, false
            *reduce_only: true, false
            stop_loss: (Stop loss price, only take effect upon opening the position)
    """
    def place_order(self, side, symbol, order_type, qty, price, time_in_force, close_on_trigger, reduce_only,
                    stop_loss):
        pass
