import time

import rapidjson

from Configuration import Configuration
from Orders import Orders
from Position import Position
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums.BybitEnums import OrderSide
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger
from trade_entry.LimitEntry import LimitEntry


class Executions:
    """
        Returned by the pybit
        "data": [
            {
                "symbol": "BTCUSDT",
                "side": "Sell",
                "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                "exec_id": "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6",
                "order_link_id": "",
                "price": 11527.5,
                "order_qty": 0.001,
                "exec_type": "Trade",
                "exec_qty": 0.001,
                "exec_fee": 0.00864563,
                "leaves_qty": 0,
                "is_maker": false,
                "trade_time": "2020-08-12T21:16:18.142746Z"
            }
        ]
    """

    def __init__(self, exchange):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        self.exchange = exchange
        self.ws = self.exchange.ws_private
        self.last_timestamp = 0

    def get_execution(self):
        while True:
            data = self.ws.fetch(self.exchange.execution_topic_name)
            if data:
                print(rapidjson.dumps(data, indent=2))
                time.sleep(0.5)


# ex = ExchangeBybit()
# db = Database(ex)
# Wal = WalletUSDT(ex)
# Ord = Orders(db, ex)
# Pos = Position(db, ex)
#
# my_exec = Executions(ex)
# limit_entry = LimitEntry(db, ex, Wal, Ord, Pos)
# limit_entry.enter_trade(OrderSide.Buy)
#
# data = my_exec.get_execution()
# print(rapidjson.dumps(data, indent=2))
