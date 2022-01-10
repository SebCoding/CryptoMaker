"""
    Position for USDT perpetual futures only.
    Hybrid class using REST API to get balances until the first update
    of the websocket that only happens after the balance in the wallet changes.
    Using websockets private topic ['position']

    Websocket
    {
       "topic": "position",
       "action": "update",
       "data": [
           {
               "user_id":  1,
               "symbol": "BTCUSD",
               "size": 11,
               "side": "Sell",
               "position_value": "0.00159252",
               "entry_price": "6907.291588174717",
               "liq_price": "7100.234",
               "bust_price": "7088.1234",
               "leverage": "1",
               "order_margin":  "1",
               "position_margin":  "1",
               "occ_closing_fee":  "0.1",
               "take_profit":  "0.1",
               "tp_trigger_by": 0,
               "stop_loss":  "0.12",
               "sl_trigger_by": "Normal",
               "realised_pnl": "Normal",
               "cum_realised_pnl": "Normal",
               "position_seq": 14,
               "tp_sl_mode": "Full",
               "position_idx": 1,
               "mode": "MergedSingle",
               "isolated": true,
               "risk_id": 0
           }
        ]
    }
"""
import pandas as pd
import rapidjson

from Configuration import Configuration
from Logger import Logger


class Position:
    _position_topic_name = 'position'

    _long_position = None
    _short_position = None

    def __init__(self, exchange):
        self.logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._pair = self._config['exchange']['pair']
        self._exchange = exchange
        self._stake_currency = self._config['exchange']['stake_currency']
        self.refresh_position()

    def refresh_position(self):
        # Data contains a list of 2 dictionaries.
        # one for Short position and the other for Long
        data = self._exchange.get_position(self._pair)
        if data:
            if data[0]['side'] == 'Buy':
                self._long_position = data[0]
            if data[1]['side'] == 'Buy':
                self._long_position = data[1]
            if data[0]['side'] == 'Sell':
                self._short_position = data[0]
            if data[1]['side'] == 'Sell':
                self._short_position = data[1]

    def get_long_position(self):
        self.refresh_position()
        return self._long_position

    def get_short_position(self):
        self.refresh_position()
        return self._short_position

    # Return a list containing 2 dictionaries
    def get_positions(self):
        self.refresh_position()
        return [self._long_position, self._short_position]

    long_position = property(get_long_position)
    short_position = property(get_short_position)
    positions = property(get_positions)

    # returns a DataFrame containing the Long/Short positions
    def get_positions_df(self):
        # No need to call: self.refresh_position(). self.positions does it internally
        df = pd.DataFrame(self.positions)

        # Only keep relevant columns and reorder
        if 'is_isolated' in df.columns:
            df.rename(columns={"is_isolated": "isolated"}, inplace=True)
        if 'unrealised_pnl' in df.columns:
            df = df.loc[:,
                 ['symbol', 'leverage', 'side', 'size', 'position_value', 'entry_price', 'liq_price',
                  'isolated', 'position_margin', 'unrealised_pnl', 'realised_pnl', 'stop_loss', 'take_profit', 'trailing_stop']]
        else:
            df = df.loc[:,
                 ['symbol', 'leverage', 'side', 'size', 'position_value', 'entry_price', 'liq_price',
                  'isolated', 'position_margin', 'realised_pnl', 'stop_loss', 'take_profit', 'trailing_stop']]

        return df

    # def get_free(self):
    #     self.update_wallet()
    #     return self._free
    #
    # def get_used(self):
    #     self.update_wallet()
    #     return self._used
    #
    # def get_total(self):
    #     self.update_wallet()
    #     return self._total
    #
    # free = property(get_free)
    # used = property(get_used)
    # total = property(get_total)
    #
    # def to_string(self) -> str:
    #     result = f'{self._stake_currency} Wallet (free: {self._free}, used: {self._used}, total: {self._total})'
    #     return result
