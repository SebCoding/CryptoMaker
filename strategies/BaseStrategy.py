from abc import ABC, abstractmethod

from CandleHandler import CandleHandler
from Configuration import Configuration


class BaseStrategy(ABC):
    # Optimal timeframe for the strategy.
    interval = '5m'

    # Ratio of the total account balance allowed to be traded.
    # Positive float between 0.0 and 1.0
    # tradable_balance_ratio = 1.0

    # Optimal takeprofit designed for the strategy.
    # 0.01 = 1%
    # takeprofit = 0.01

    # Optimal stoploss designed for the strategy.
    # -0.01 = -1%
    # stoploss = -0.01

    # Trailing stoploss
    # trailing_stop = False

    # candles + indicators dataframe
    data = None

    # Minimum number of candles required before we can start trading.
    # After the 1st candle received from the websocket from the exchange,
    # INIT_CANDLES_COUNT-1 historical candles will be downloaded and
    # inserted it prior to it in the dataframe so that we can
    # start trading as soon as the application is started
    minimum_candles_to_start = 0

    def __init__(self, database, exchange):
        super().__init__()
        self.name = self.__class__.__name__
        self._config = Configuration.get_config()
        self.interval = self._config['trading']['interval']
        self.minimum_candles_to_start = self._config['strategy']['minimum_candles_to_start']
        self.db = database
        self.exchange = exchange
        self._candle_handler = CandleHandler(exchange)

    @abstractmethod
    def get_strategy_text_details(self):
        pass

    @abstractmethod
    def add_indicators_and_signals(self, candles_df):
        pass

    @abstractmethod
    def find_entry(self):
        pass

    def save_enry_to_db(self):
        pass
