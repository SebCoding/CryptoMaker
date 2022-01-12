import os
import sys
import time
import datetime as dt

import rapidjson

import constants
from logging_.Logger import Logger
from CandleHandler import CandleHandler
from Configuration import Configuration
from Orders import Orders, Order
from Position import Position
from database.Database import Database
from enums import TradeSignals
from enums.BybitEnums import OrderSide, OrderType, OrderStatus
from enums.EntryMode import EntryMode
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
        self.pair = self._config['exchange']['pair']
        net = '** Testnet **' if self._config['exchange']['testnet'] else 'Mainnet'
        self._logger.info(f"Initializing Bot to trade {self.pair} on {self._config['exchange']['name']} {net}.")
        self.stake_currency = self._config['exchange']['stake_currency']
        self._last_throttle_start_time = 0.0
        self.throttle_secs = self._config['bot']['throttle_secs']

        self.db = Database()
        self._exchange = ExchangeBybit()
        self.strategy = globals()[self._config['strategy']['name']](self.db)
        self._candle_handler = CandleHandler(self._exchange)
        self._wallet = WalletUSDT(self._exchange, self.stake_currency)
        self._position = Position(self.db, self._exchange)
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
                self._logger.info(f'{df.tail(10).to_string()} \n')
                self._logger.info(f"{result['Signal']}: {rapidjson.dumps(result, indent=2)}")
                self.enter_trade(result['Signal'])

    def enter_trade(self, signal):
        entry_mode = self._config['trading']['trade_entry_mode']
        tradable_ratio = self._config['trading']['tradable_balance_ratio']
        balance = self._wallet.free
        tradable_balance = balance * tradable_ratio
        if tradable_balance < self.MIN_TRADE_AMOUNT:
            return None

        # This does not call refresh_position() internally, but we know it was just called
        # to verify that there is no ongoing position prior to placing this trade.
        # We to update the leverage in case it couldn't be set when the application started
        # because a position was open.
        self._position.set_leverage()

        side = OrderSide.Buy if signal == TradeSignals.EnterLong else OrderSide.Sell
        tentative_entry_price = self._candle_handler.get_latest_price()
        trade_amount = round(tradable_balance / tentative_entry_price, 4)
        stop_loss = self.get_stop_loss(side, tentative_entry_price)

        # Step 1: Place order and open position

        # Enter with market order (taker)
        if entry_mode == EntryMode.Taker:
            order_id = self.enter_trade_as_taker(side, trade_amount, stop_loss)
        # Enter with limit order (maker)
        elif entry_mode == EntryMode.Maker:
            order_id = self.enter_trade_as_maker(side, trade_amount, tentative_entry_price, stop_loss)

        if side == OrderSide.Buy:
            entry_price = self._position.long_position['entry_price']
            size = self._position.long_position['size']
        else:
            entry_price = self._position.short_position['entry_price']
            size = self._position.short_position['size']

        entry_price = round(entry_price, 2)
        now = dt.datetime.now().strftime(constants.DATETIME_FORMAT)
        _side = 'Long' if side == OrderSide.Buy else 'Short'
        self._logger.info(f'{now} Entered {_side} position, entry_price={entry_price} size={size}.')

        # Step 2: Place a limit take_profit order based on the confirmed position entry_price
        # side_tp = OrderSide.Buy if side == OrderSide.Sell else OrderSide.Sell
        # Calculate take_profit based the on actual position entry price
        take_profit = 0
        if side == OrderSide.Buy:
            take_profit = self.get_take_profit(side, entry_price)
        if side == OrderSide.Sell:
            take_profit = self.get_take_profit(side, entry_price)
        take_profit = round(take_profit, 0)

        tp_order = Order(side=side, symbol=self.pair, order_type=OrderType.Limit, qty=trade_amount,
                         price=take_profit, reduce_only=True)
        tp_order_id = self._orders.place_order(tp_order, 'TakeProfit')['order_id']

        # Step 3: Update position stop_loss if market order's entry_price slipped
        if tentative_entry_price != entry_price:
            old_stop_loss = self._position.get_current_stop_loss(side)
            new_stop_loss = self.get_stop_loss(side, entry_price)
            if old_stop_loss != new_stop_loss:
                # Update position stop_loss if required because of entry price slippage
                self._position.set_trading_stop(side, stop_loss=new_stop_loss)
                # Update original order with new stop_loss value
                self._orders.update_db_order_stop_loss_by_id(order_id, new_stop_loss)

        time.sleep(1)  # Sleep to let the order info be available by http or websocket

    def enter_trade_as_taker(self, side, trade_amount, stop_loss):
        order = Order(side=side, symbol=self.pair, order_type=OrderType.Market, qty=trade_amount,
                      stop_loss=stop_loss)
        order_id = self._orders.place_order(order, 'TradeEntry')['order_id']
        # Wait until the position is open
        while not self._position.currently_in_position(side):
            time.sleep(0.5)
        return order_id

    def enter_trade_as_maker(self, side, tentative_entry_price, trade_amount, stop_loss):
        msg = f'Config Error: trade_entry_mode=\'maker\' not yet implemented'
        self._logger(msg)
        raise Exception(msg)

    def get_stop_loss(self, side, price):
        stop_loss_pct = self._config['trading']['stop_loss']
        stop_loss = price * stop_loss_pct
        if side == OrderSide.Buy:
            stop_loss = price - stop_loss
        if side == OrderSide.Sell:
            stop_loss = price + stop_loss
        return round(stop_loss, 0)

    def get_take_profit(self, side, price):
        take_profit_pct = self._config['trading']['take_profit']
        take_profit = price * take_profit_pct
        if side == OrderSide.Buy:
            take_profit = price + take_profit
        if side == OrderSide.Sell:
            take_profit = price - take_profit
        return round(take_profit, 0)

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
        except KeyboardInterrupt as e:
            self._logger.info('\n')
            self._position.sync_all_closed_pnl_records(self.pair)
            self._logger.info("Application Terminated by User.")
        except Exception as e:
            self._logger.exception(e)
            Bot.beep(1, 500, 5000)
            raise e

    def run_forever2(self):
        self._logger.info(f"Initializing Main Loop.")

        print(self._wallet.to_string() + "\n")
        print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')

        order1 = Order(OrderSide.Buy, self.pair, OrderType.Limit, 0.1, 10000, take_profit=11000, stop_loss=9000)
        result = self._orders.place_order(order1, 'TakeProfit')
        print("Order Result:\n", rapidjson.dumps(result, indent=2))

        self._orders.update_db_order_stop_loss_by_id(result['order_id'], 777)

        self._wallet.update_wallet()
        print(self._wallet.to_string() + "\n")
        print('Position:\n' + self._position.get_positions_df().to_string() + "\n")
        print('Orders:\n' + self._orders.get_orders_df(order_status=OrderStatus.New).to_string() + '\n')
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
