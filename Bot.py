import datetime as dt
import os
import sys
import time

import pandas as pd
import rapidjson

from Logger import Logger
from CandleHandler import CandleHandler
from Configuration import Configuration
from Orders import Orders, Order
from Position import Position
from database.Database import Database
from enums import TradeSignals
from enums.BybitEnums import Side, OrderType, OrderStatus
from enums.TradeSignals import TradeSignals
from typing import Any, Callable

from exchange.ExchangeBybit import ExchangeBybit
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx

from WalletUSDT import WalletUSDT


class Bot:
    _candles_df = None
    _wallet = None

    MIN_TRADE_AMOUNT = 20

    STATUS_BAR_CHAR = chr(0x2588)
    STATUS_BAR_LENGTH = 20

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        net = '** Testnet **' if self._config['exchange']['testnet'] else 'Mainnet'
        self._logger.info(f"Initializing Bot to run on: {self._config['exchange']['name']} {net}.")
        self._last_throttle_start_time = 0.0
        self.throttle_secs = self._config['bot']['throttle_secs']
        self.pair = self._config['exchange']['pair']
        self.stake_currency = self._config['exchange']['stake_currency']
        self.db = Database()
        self.strategy = globals()[self._config['strategy']['name']](self.db)

        self._exchange = ExchangeBybit()
        self._candle_handler = CandleHandler(self._exchange)
        self._wallet = WalletUSDT(self._exchange, self.stake_currency)
        self._position = Position(self._exchange)
        self._orders = Orders(self._exchange, self.db)
        self.status_bar = self.moving_status_bar(self.STATUS_BAR_CHAR, self.STATUS_BAR_LENGTH)

    # Heart of the Bot. Work done at each iteration.
    def run(self):
        # Step 1: Get fresh candle data
        self._candles_df, data_changed = self._candle_handler.get_refreshed_candles()

        # Step 2: Calculate Indicators, Signals and Find Entries
        if data_changed:
            df, result = self.strategy.find_entry(self._candles_df)

            # Step 3: Check if we received an entry signal and we are not in an open position
            if result['Signal'] in [TradeSignals.EnterLong, TradeSignals.EnterShort] \
                    and not self._position.currently_in_position():
                Bot.beep(5, 2500, 100)
                print(df.tail(10).to_string() + '\n')
                print(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
                result = self.enter_trade(result['Signal'])

    def enter_trade(self, signal):
        entry_mode = self._config['trading']['trade_entry_mode']
        take_profit_pct = self._config['trading']['take_profit']
        stop_loss_pct = self._config['trading']['stop_loss']
        tradable_ratio = self._config['trading']['tradable_balance_ratio']
        side = Side.Buy if signal == TradeSignals.EnterLong else Side.Sell
        side_tp = Side.Buy if side == Side.Sell else Side.Sell  # TP is opposite side of the order
        balance = self._wallet.free
        current_price = self._candle_handler.get_latest_price()

        tradable_balance = balance * tradable_ratio
        if tradable_balance < self.MIN_TRADE_AMOUNT:
            return None

        amount = round(tradable_balance / current_price, 4)
        stop_loss = current_price * stop_loss_pct
        take_profit = current_price * take_profit_pct

        if side == Side.Buy:
            stop_loss = current_price - stop_loss
            take_profit = current_price + take_profit
            assert (stop_loss < current_price < take_profit)
        if side == Side.Sell:
            stop_loss = current_price + stop_loss
            take_profit = current_price - take_profit
            assert (stop_loss > current_price > take_profit)

        stop_loss = round(stop_loss, 0)
        take_profit = round(take_profit, 0)

        # Place Market Order
        if entry_mode == 'taker':
            order = Order(side=side, symbol=self.pair, order_type=OrderType.Market, qty=amount, stop_loss=stop_loss)
            result = self._orders.place_order(order, 'TradeEntry')
            time.sleep(1)  # Sleep to let the order info be available by http or websocket

            tp_order = Order(side=side_tp, symbol=self.pair, order_type=OrderType.Limit, qty=amount, price=take_profit,
                             reduce_only=True)
            while not self._position.currently_in_position(side):
                time.sleep(0.5)
            result = self._orders.place_order(tp_order, 'TakeProfit')
            time.sleep(1)  # Sleep to let the order info be available by http or websocket

        # Place Limit Order
        elif entry_mode == 'maker':
            msg = f'Config Error: trade_entry_mode={entry_mode} not yet implemented'
            self._logger(msg)
            raise Exception(msg)

        return True

    def run_forever(self):
        self._logger.info(f'Trading Settings:\n' + rapidjson.dumps(self._config['trading'], indent=2))
        self._logger.info(f"Starting Main Loop with throttling = {self.throttle_secs} sec.")
        try:
            while True:
                sys.stdout.write(next(self.status_bar))
                sys.stdout.flush()
                self.throttle(self.run, throttle_secs=self.throttle_secs)
                print('\r', end='')
                sys.stdout.flush()
        except Exception as e:
            self._logger.exception(e)
            raise e
            Bot.beep(3, 500, 1000)

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

    def run_forever2(self):
        self._logger.info(f"Initializing Main Loop.")

        print(self._wallet.to_string() + "\n")
        print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')

        order1 = Order(Side.Buy, self.pair, OrderType.Limit, 0.1, 10000, take_profit=11000, stop_loss=9000)
        result = self._orders.place_order(order1, 'TakeProfit')
        print("Order Result:\n", rapidjson.dumps(result, indent=2))

        # self._wallet.update_wallet()
        # print(self._wallet.to_string() + "\n")
        # print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        # print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')
        #
        # order2 = Order(Side.Sell, self.pair, OrderType.Market, 0.001, take_profit=35000, stop_loss=50000)
        # result = self._orders.place_order(order2)
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
