import datetime as dt
import time

import rapidjson

import logger
import utils
from candlehandler import CandleHandler
from configuration import Configuration
from enums import TradeSignalsStates
from enums.TradeSignalsStates import TradeSignalsStates
from typing import Any, Callable, Dict, Optional

from exchange.ExchangeREST import ExchangeREST
from exchange.ExchangeWS import ExchangeWS
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx
from walletREST import Wallets

from walletusdt import WalletUSDT


class Bot:
    _candles_df = None
    _wallet = None

    def __init__(self):
        self.logger = logger.init_custom_logger(__name__)
        self._config = Configuration.get_config()
        self._last_throttle_start_time = 0.0
        self.throttle_secs = self._config['bot']['throttle_secs']
        self.pair = self._config['exchange']['pair']
        self.stake_currency = self._config['exchange']['stake_currency']
        self.strategy = globals()[self._config['strategy']['name']]()
        self.exchange_rest = ExchangeREST()
        self.exchange_ws = ExchangeWS()
        self._candle_handler = CandleHandler(self.exchange_rest, self.exchange_ws)
        self._wallet = WalletUSDT(self.exchange_ws)
        self._walletsREST = Wallets(self.exchange_rest)

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
            if result['Signal'] in [TradeSignalsStates.EnterLong, TradeSignalsStates.EnterShort]:
                f.write('')
                print()
                f.write('\n' + df.tail(10).to_string())
                print('\n' + df.tail(10).to_string())
                f.write(f"\nLast valid signal offset: {result['SignalOffset']}\n")
                print(f"Last valid signal offset: {result['SignalOffset']}\n")
                f.write(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
                print(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
                self._walletsREST.get_wallet('USDT').to_string()

    def run_forever(self):
        with open('trace.txt', 'w') as f:
            while True:
                self.print_candles_and_entries(f)
                time.sleep(1)
                # self.throttle(self.print_candles_and_entries, throttle_secs=5, f=f)

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
        self.logger.debug("========================================")
        result = func(*args, **kwargs)
        time_passed = time.time() - self._last_throttle_start_time
        sleep_duration = max(throttle_secs - time_passed, 0.0)
        self.logger.debug(f"Throttling '{func.__name__}()': sleep for {sleep_duration:.2f} s, "
                          f"last iteration took {time_passed:.2f} s.")
        time.sleep(sleep_duration)
        return result
