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
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx

logger = logger.init_custom_logger(__name__)


class Bot:
    candles_df = None

    def __init__(self):
        self.config = Configuration.get_config()
        self.last_throttle_start_time = 0.0
        self.throttle_secs = self.config['bot']['throttle_secs']
        self.pair = self.config['exchange']['pair']
        self.strategy = globals()[self.config['strategy']['name']]()
        self.candle_handler = CandleHandler()

    def print_candles_and_entries(self, f):
        self.candles_df, data_changed = self.candle_handler.get_refreshed_candles()
        if data_changed:
            df, result = self.strategy.find_entry(self.candles_df)
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

    def run_forever(self):
        with open('trace.txt', 'w') as f:
            while True:
                self.print_candles_and_entries(f)
                time.sleep(0.5)
                #self.throttle(self.print_candles_and_entries, throttle_secs=0.5, f=f)

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
        self.last_throttle_start_time = time.time()
        logger.debug("========================================")
        result = func(*args, **kwargs)
        time_passed = time.time() - self.last_throttle_start_time
        sleep_duration = max(throttle_secs - time_passed, 0.0)
        logger.debug(f"Throttling '{func.__name__}()': sleep for {sleep_duration:.2f} s, "
                     f"last iteration took {time_passed:.2f} s.")
        time.sleep(sleep_duration)
        return result
