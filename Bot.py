import os
import sys
import time
from typing import Any, Callable

import rapidjson
import websocket

from CandleHandler import CandleHandler
from Configuration import Configuration
from Orders import Orders
from Position import Position
from WalletUSDT import WalletUSDT
from database.Database import Database
from enums import TradeSignals
from enums.BybitEnums import OrderSide
from enums.EntryMode import EntryMode
from enums.TradeSignals import TradeSignals
# from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger
from trade_entry.LimitEntry import LimitEntry
from trade_entry.MarketEntry import MarketEntry


class Bot:
    _candles_df = None
    _wallet = None

    STATUS_BAR_CHAR = chr(0x2588)
    STATUS_BAR_LENGTH = 20

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        net = '** Testnet **' if self._config['exchange']['testnet'] else 'Mainnet'
        self.interval = self._config['trading']['interval']
        self._logger.info(f"Initializing Bot to trade [{self.pair}][{self.interval}] on "
                          f"{self._config['exchange']['name']} {net}.")
        self.status_bar = self.moving_status_bar(self.STATUS_BAR_CHAR, self.STATUS_BAR_LENGTH)
        # self.stake_currency = self._config['exchange']['stake_currency']
        self._last_throttle_start_time = 0.0
        self.throttle_secs = self._config['bot']['throttle_secs']

        self._exchange = ExchangeBybit()
        self.db = Database(self._exchange)
        self._candle_handler = CandleHandler(self._exchange)
        self._position = Position(self.db, self._exchange)
        self.strategy = globals()[self._config['strategy']['name']](self.db)
        self._logger.info(f'Trading Settings:\n' + rapidjson.dumps(self._config['trading'], indent=2))
        self._logger.info(f'Limit Entry Settings:\n' + rapidjson.dumps(self._config['limit_entry'], indent=2))

    # Heart of the Bot. Work done at each iteration.
    def run(self):
        # Step 1: Get fresh candle data
        self._candles_df, data_changed = self._candle_handler.get_refreshed_candles()

        # Step 2: Calculate Indicators, Signals and Find Entries
        if data_changed:
            df, signal = self.strategy.find_entry(self._candles_df)

            # Step 3: Check if we received an entry signal and we are not in an open position
            if signal['Signal'] in [TradeSignals.EnterLong, TradeSignals.EnterShort] \
                    and not self._position.currently_in_position():
                Bot.beep(5, 2500, 100)
                df_print = df.drop(columns=['start', 'end'], axis=1)
                self._logger.info(f'\n{df_print.tail(10).to_string()} \n')
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
            self.db.sync_all_tables(self.pair)
            self._logger.info("Application Terminated by User.")
        except (websocket.WebSocketTimeoutException,
                websocket.WebSocketAddressException) as e:
            self._logger.exception(e)
            Bot.beep(1, 500, 5000)
            raise e
            # restart(10)
        except Exception as e:
            self._logger.exception(e)
            Bot.beep(1, 500, 5000)
            raise e

    def run_forever2(self):
        self._logger.info(f"Initializing Main Loop.")

        self.db.sync_all_user_trade_records(self.pair)
        exit(1)

        # print(self._wallet.to_string() + "\n")
        # print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        # print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')
        #
        # order1 = Order(OrderSide.Buy, self.pair, OrderType.Limit, 0.1, 10000, take_profit=11000, stop_loss=9000)
        # result = self._orders.place_limit_order(order1, 'TakeProfit')
        # print("Order Result:\n", rapidjson.dumps(result, indent=2))
        #
        # self._orders.update_db_order_stop_loss_by_id(result['order_id'], 777)
        #
        # self._wallet.update_wallet()
        # print(self._wallet.to_string() + "\n")
        # print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        # print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')
        #
        # order2 = Order(Side.Sell, self.pair, OrderType.Market, 0.001, take_profit=35000, stop_loss=50000)
        # result = self._orders.place_limit_order(order2)
        # print("Order Result:\n", rapidjson.dumps(result, indent=2))
        #
        # self._wallet.update_wallet()
        # print(self._wallet.to_string() + "\n")
        # print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        # print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')

        # with open('trace.txt', 'w') as f:
        #     while True:
        #         self.print_candles_and_entries(f)
        #         time.sleep(0.5)
        # self.throttle(self.print_candles_and_entries, throttle_secs=5, f=f)

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

            if result['Signal'] in [TradeSignals.EnterLong, TradeSignals.EnterShort]:
                f.write('')
                print()
                f.write('\n' + df.tail(10).to_string())
                print('\n' + df.tail(10).to_string())
                f.write(f"\nLast valid signal offset: {result['SignalOffset']}\n")
                print(f"Last valid signal offset: {result['SignalOffset']}\n")
                f.write(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
                print(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
