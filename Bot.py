import datetime as dt
import time

import rapidjson

from Logger import Logger
import utils
from CandleHandler import CandleHandler
from Configuration import Configuration
from Orders import Orders, Order
from Position import Position
from enums import TradeSignalsStates
from enums.TradeSignalsStates import TradeSignalsStates
from typing import Any, Callable, Dict, Optional

from exchange.ExchangeBybit import ExchangeBybit
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx

from WalletUSDT import WalletUSDT


class Bot:
    _candles_df = None
    _wallet = None

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        net = 'Testnet' if self._config['exchange']['testnet'] else 'Mainnet'
        self._logger.info(f"Initializing Bot to run on {self._config['exchange']['name']} {net}.")
        self._last_throttle_start_time = 0.0
        self.throttle_secs = self._config['bot']['throttle_secs']
        self.pair = self._config['exchange']['pair']
        self.stake_currency = self._config['exchange']['stake_currency']
        self.strategy = globals()[self._config['strategy']['name']]()

        self._exchange = ExchangeBybit()
        self._candle_handler = CandleHandler(self._exchange)
        self._wallet = WalletUSDT(self._exchange, self.stake_currency)
        self._position = Position(self._exchange)
        self._orders = Orders(self._exchange)

    """
           Example of testing: throttle()
           def test_throttle_with_assets(mocker, default_conf) -> None:
               def throttled_func(nb_assets=-1):
                   return nb_assets

               worker = get_patched_worker(mocker, default_conf)

               result = worker.throttle(throttled_func, throttle_secs=0.1, nb_assets=777)
               assert result == 777

               result = worker.throttle(throttled_func, throttle_secs=0.1)
               assert result == -1
       """

    def throttle(self, func: Callable[..., Any], throttle_secs: float, *args, **kwargs) -> Any:
        """
        Throttles the given callable that it
        takes at least `min_secs` to finish execution.
        :param func: Any callable
        :param throttle_secs: throttling interation execution time limit in seconds
        :return: Any (result of execution of func)
        """
        self._last_throttle_start_time = time.time()
        self._logger.debug("========================================")
        result = func(*args, **kwargs)
        time_passed = time.time() - self._last_throttle_start_time
        sleep_duration = max(throttle_secs - time_passed, 0.0)
        self._logger.debug(f"Throttling '{func.__name__}()': sleep for {sleep_duration:.2f} s, "
                           f"last iteration took {time_passed:.2f} s.")
        time.sleep(sleep_duration)
        return result

    def print_candles_and_entries(self, f):
        self._candles_df, data_changed = self._candle_handler.get_refreshed_candles()
        if data_changed:
            df, result = self.strategy.find_entry(self._candles_df)
            f.write('')
            print()
            f.write('\n' + df.tail(10).to_string())
            print('\n' + df.tail(10).to_string())
            f.write(f"\nLast valid signal offset: {result['SignalOffset']}\n")
            print(f"Last valid signal offset: {result['SignalOffset']}\n")
            print(self._wallet.to_string())
            print(self._position.get_positions_df().to_string())
            print(self._orders.get_orders_df().to_string())
            exit(1)


            if result['Signal'] in [TradeSignalsStates.EnterLong, TradeSignalsStates.EnterShort]:
                f.write('')
                print()
                f.write('\n' + df.tail(10).to_string())
                print('\n' + df.tail(10).to_string())
                f.write(f"\nLast valid signal offset: {result['SignalOffset']}\n")
                print(f"Last valid signal offset: {result['SignalOffset']}\n")
                f.write(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
                print(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")

    def run_forever(self):
        self._logger.info(f"Initializing Main Loop.")

        print(self._wallet.to_string()+"\n")
        print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        print('Orders:\n' + self._orders.get_orders_df(order_status='New').to_string() + '\n')

        order1 = Order('Buy', self.pair, 'Limit', 0.1, 10000, take_profit=11000, stop_loss=9000)
        result = self._orders.place_order(order1)
        print("Order Result:\n", rapidjson.dumps(result, indent=2))

        self._wallet.update_wallet()
        print(self._wallet.to_string()+"\n")
        print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        print('Orders:\n' + self._orders.get_orders_df(order_status='New').to_string() + '\n')

        order2 = Order('Sell', self.pair, 'Market', 0.001, take_profit=35000, stop_loss=50000)
        result = self._orders.place_order(order2)
        print("Order Result:\n", rapidjson.dumps(result, indent=2))

        self._wallet.update_wallet()
        print(self._wallet.to_string()+"\n")
        print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        print('Orders:\n' + self._orders.get_orders_df(order_status='New').to_string() + '\n')

        # with open('trace.txt', 'w') as f:
        #     while True:
        #         self.print_candles_and_entries(f)
        #         time.sleep(0.5)
                # self.throttle(self.print_candles_and_entries, throttle_secs=5, f=f)
