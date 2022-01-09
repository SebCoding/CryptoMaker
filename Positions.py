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
import rapidjson

from Configuration import Configuration
from Logger import Logger


class Positions:
    _position_topic_name = 'position'
    position_list = None

    def __init__(self, exchange_rest, exchange_ws):
        self.logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._pair = self._config['exchange']['pair']
        self._exchange_rest = exchange_rest
        self._exchange_ws = exchange_ws
        self._stake_currency = self._config['exchange']['stake_currency']
        self.refresh_positions()

    def refresh_positions(self):
        data = self._exchange_ws.private_ws.fetch(self._position_topic_name)
        if data:
            self.position_list = data
            print(f'position socket: {data}')
            exit(1)
        else:
            balances = self._exchange_rest.get_positions(self._pair)
            if balances:
                print(rapidjson.dumps(balances, indent=2))

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
