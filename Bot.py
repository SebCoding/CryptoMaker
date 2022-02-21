import os
import sys
import time
from typing import Any, Callable
import traceback
import rapidjson
import websocket

import pybit
from Configuration import Configuration
from Position import Position
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums import TradeSignals
from enums.EntryMode import EntryMode
from enums.TradeSignals import TradeSignals
# from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx
# from strategies.MACD import MACD
# from strategies.UltimateScalper import UltimateScalper
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx
from strategies.MACD import MACD
from strategies.UltimateScalper import UltimateScalper
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger
from telegram_.TelegramBot import TelegramBot
from trade_entry.LimitEntry import LimitEntry
from trade_entry.MarketEntry import MarketEntry


class Bot:
    _candles_df = None
    _wallet = None

    STATUS_BAR_CHAR = chr(0x2588)
    STATUS_BAR_LENGTH = 20

    # If Bot crashes it will try to restart itself in 30 seconds
    RESTART_DELAY = 30

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.instance_name = self._config['bot']['instance_name']
        self.pair = self._config['exchange']['pair']
        net = '** Testnet **' if self._config['exchange']['testnet'] else 'Mainnet'
        self.interval = self._config['trading']['interval']
        self._logger.info(f"Initializing {self.instance_name} to trade [{self.pair}][{self.interval}] on "
                          f"{self._config['exchange']['name']} {net}")
        self.status_bar = self.moving_status_bar(self.STATUS_BAR_CHAR, self.STATUS_BAR_LENGTH)
        # self.stake_currency = self._config['exchange']['stake_currency']
        self._last_throttle_start_time = 0.0
        self.throttle_secs = self._config['bot']['throttle_secs']

        if self._config['strategy']['name'] == 'UltimateScalper':
            self._exchange = ExchangeBybit(extra_interval='1m')
        else:
            self._exchange = ExchangeBybit()

        self.db = Database(self._exchange)
        self._position = Position(self.db, self._exchange)
        self._wallet = WalletUSDT(self._exchange)
        self._logger.info(f'{self._wallet.to_string()}')
        self.strategy = globals()[self._config['strategy']['name']](self.db, self._exchange)
        self._logger.info(f'Trading Settings:\n' + rapidjson.dumps(self._config['trading'], indent=2))
        self._logger.info(f'Limit Entry Settings:\n' + rapidjson.dumps(self._config['limit_entry'], indent=2))

    # Heart of the Bot. Work done at each iteration.
    def run(self):
        # Check for an entry signal
        df, signal = self.strategy.find_entry()

        # Check if we received an entry signal and that we are not in an open position
        if signal['Signal'] in [TradeSignals.EnterLong, TradeSignals.EnterShort] \
                and not self._position.currently_in_position():
            Bot.beep(5, 2500, 100)
            df_print = df.drop(columns=['start', 'end', 'timestamp'], axis=1)
            self._logger.info(f'\n{df_print.round(2).tail(10).to_string()} \n')
            self._logger.info(f"{signal['Signal']}: {rapidjson.dumps(signal, indent=2)}")
            self.enter_trade(signal)

    def enter_trade(self, signal):
        entry_mode = self._config['trading']['trade_entry_mode']
        if entry_mode == EntryMode.Taker:
            qty, avg_price = MarketEntry(self.db, self._exchange, self._position, signal).enter_trade()
        elif entry_mode == EntryMode.Maker:
            qty, avg_price = LimitEntry(self.db, self._exchange, self._position, signal).enter_trade()

    def run_forever(self):
        self._logger.info(f"Starting Main Loop with throttling = {self.throttle_secs} sec.")
        try:
            while True:
                if bool(self._config['bot']['progress_bar']):
                    sys.stdout.write(next(self.status_bar))
                    sys.stdout.flush()
                self.throttle(self.run, throttle_secs=self.throttle_secs)
                if bool(self._config['bot']['progress_bar']):
                    print('\r', end='')
                    sys.stdout.flush()
        except KeyboardInterrupt as e:
            self._logger.info('\n')
            #self.db.sync_all_tables([self.pair])
            self._logger.info("Application Terminated by User.")
        except (websocket.WebSocketTimeoutException,
                websocket.WebSocketAddressException,
                pybit.exceptions.FailedRequestError) as e:
            self._logger.exception(e)
            self._logger.error(f"Bot Crashed. Restart in {self.RESTART_DELAY} seconds")
            TelegramBot.send_to_group(f"Application crashed. {str(e)}\n{traceback.format_exc()}")
            TelegramBot.send_to_group(f"Bot Crashed. Restart in {self.RESTART_DELAY} seconds")
            self.restart(self.RESTART_DELAY)
        except Exception as e:
            self._logger.exception(e)
            # TelegramBot.send_to_group(f'Application crashed. {str(e)}\n{traceback.format_exc()}')
            # Bot.beep(1, 500, 2000)
            raise e

    def throttle(self, func: Callable[..., Any], throttle_secs: float, *args, **kwargs) -> Any:
        """
        Throttles the given callable that it
        takes at least `min_secs` to finish execution.
        :param func: Any callable
        :param throttle_secs: throttling interation execution time limit in seconds
        :return: Any (result of execution of func)
        """
        self._last_throttle_start_time = time.time()
        # self._logger.debug("========================================")
        result = func(*args, **kwargs)
        time_passed = time.time() - self._last_throttle_start_time
        sleep_duration = max(throttle_secs - time_passed, 0.0)
        # self._logger.debug(f"Throttling '{func.__name__}()': sleep for {sleep_duration:.2f} s, "
        #                    f"last iteration took {time_passed:.2f} s.")
        time.sleep(sleep_duration)
        return result

    @staticmethod
    def spinning_cursor():
        while True:
            for cursor in '|/-\\':
                yield cursor

    # Create the list of all possible bars for the specified length
    @staticmethod
    def init_status_bar(c, length):
        # c = '#'
        c = chr(0x2588)
        bars = []
        for i in range(length + 1):
            # bar = '['
            bar = 'Bot Running: '
            for j in range(i):
                bar += c
            for j in range(i, length):
                bar += ' '
            # bar += ']'
            bars.append(bar)
        bars[0] = ''
        return bars

    @staticmethod
    def moving_status_bar(c, length):
        bars = Bot.init_status_bar(c, length)
        while True:
            for bar in bars:
                yield bar

    @staticmethod
    def beep(nb, frequency, duration):
        # frequency: Set Frequency To 2500 Hertz
        # duration: Set Duration To 1000 ms == 1 second
        if os.name == 'nt':
            import winsound
            for i in range(nb):
                winsound.Beep(frequency, duration)
                time.sleep(0.1)

    def restart(self, nb_seconds):
        # print("argv was", sys.argv)
        # print("sys.executable was", sys.executable)
        self._logger.error(f"restarting in {nb_seconds} seconds ...")
        time.sleep(nb_seconds)
        os.execv(sys.executable, ['python'] + sys.argv)



