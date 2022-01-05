import talib

import constants
import logger
from enums import TradeStatus
from enums.TradeStatus import TradeStatus
from strategies.BaseStrategy import BaseStrategy

logger = logger.init_custom_logger(__name__)

class ScalpEmaRsiAdx(BaseStrategy):
    # Values for interval, takeprofit and stoploss come from the config.json file

    # Ratio of the total account balance allowed to be traded.
    # Positive float between 0.0 and 1.0
    TRADABLE_BALANCE_RATIO = 1.0

    # Trend indicator: EMA - Exponential Moving Average
    EMA_PERIODS = 40

    # Momentum indicator: RSI - Relative Strength Index
    RSI_PERIODS = 2
    RSI_MIN_SIGNAL_THRESHOLD = 19
    RSI_MAX_SIGNAL_THRESHOLD = 81

    # Trade entry RSI thresholds (by default equal to RSI min/max thresholds)
    RSI_MIN_ENTRY_THRESHOLD = 30
    RSI_MAX_ENTRY_THRESHOLD = 70

    # Volatility indicator: ADX - Average Directional Index
    ADX_PERIODS = 3
    ADX_THRESHOLD = 30

    def __init__(self):
        super().__init__()
        logger.info(f'Initializing strategy [{self.name}] ' + self.get_strategy_text_details())
        self.last_trade_index = self.minimum_candles_to_start

    def get_strategy_text_details(self):
        details = f'EMA({self.EMA_PERIODS}), RSI({self.RSI_PERIODS}), ADX({self.ADX_PERIODS}) ' \
                  f'RSI_SIGNAL({self.RSI_MIN_SIGNAL_THRESHOLD}, {self.RSI_MAX_SIGNAL_THRESHOLD}), ' \
                  f'RSI_ENTRY({self.RSI_MIN_ENTRY_THRESHOLD}, {self.RSI_MAX_ENTRY_THRESHOLD}), '
        return details

    # Step 1: Calculate indicator values required to determine long/short signals
    def add_indicators_and_signals(self, candles_df):
        # logger.info('Adding indicators and signals to data.')
        df = candles_df.copy()
        # Set proper data types
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)

        # Trend Indicator. EMA-50
        df['EMA'] = talib.EMA(df['close'], timeperiod=self.EMA_PERIODS)

        # Momentum Indicator. RSI-3
        df['RSI'] = talib.RSI(df['close'], timeperiod=self.RSI_PERIODS)

        # Volatility Indicator. ADX-5
        df['ADX'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.ADX_PERIODS)

        df['signal'] = 0

        # Populate long signals
        df.loc[
            (
                    (df['close'] > df['EMA']) &  # price > EMA
                    (df['RSI'] < self.RSI_MIN_SIGNAL_THRESHOLD) &  # RSI < RSI_MIN_THRESHOLD
                    (df['ADX'] > self.ADX_THRESHOLD)  # ADX > ADX_THRESHOLD
            ),
            'signal'] = 1

        # Populate short signals
        df.loc[
            (
                    (df['close'] < df['EMA']) &  # price < EMA-50
                    (df['RSI'] > self.RSI_MAX_SIGNAL_THRESHOLD) &  # RSI > RSI_MAX_THRESHOLD
                    (df['ADX'] > self.ADX_THRESHOLD)  # ADX > ADX_THRESHOLD
            ),
            'signal'] = -1

        self.data = df
        return self.data

    def find_entry(self):
        # logger.info('Looking trading trade entry.')
        signal_list = self.data.query('signal in [-1, 1]').index
        signal_index = max(signal_list)
        # print(f'last signal index: {signal_index}')

        # We ignore all signals for candles prior to when the application
        # was started or when the last trade entry that we signaled
        if signal_index <= self.last_trade_index:
            return \
                {
                    'TradeStatus': TradeStatus.NoTrade,
                    'signal_index': signal_index
                }

        long_signal = True if self.data['signal'].iloc[signal_index] == 1 else False
        short_signal = True if self.data['signal'].iloc[signal_index] == -1 else False

        start_scan = signal_index + 1
        for i, row in self.data.iloc[start_scan:].iterrows():
            # If after receiving a long signal the EMA or ADX are no longer satisfied, cancel signal
            if long_signal and (row.close < row.EMA or row.ADX < self.ADX_THRESHOLD):
                return \
                    {
                        'TradeStatus': TradeStatus.NoTrade,
                        'signal_index': signal_index
                    }

            # If after receiving a short signal the EMA or ADX are no longer satisfied, cancel signal
            if short_signal and (row.close > row.EMA or row.ADX < self.ADX_THRESHOLD):
                return \
                    {
                        'TradeStatus': TradeStatus.NoTrade,
                        'signal_index': signal_index
                    }

            # RSI exiting oversold area. Long Entry
            if long_signal and row.RSI > self.RSI_MIN_ENTRY_THRESHOLD:
                self.last_trade_index = i
                return \
                    {
                        'TradeStatus': TradeStatus.EnterLong,
                        'signal_index': signal_index,
                        'datetime': row.datetime.strftime(constants.DATETIME_FORMAT),
                        'entry_price': row.close,
                        'EMA': row.EMA,
                        'RSI': row.RSI,
                        'ADX': row.ADX,
                    }

            # RSI exiting overbought area. Short Entry
            elif short_signal and row.RSI < self.RSI_MAX_ENTRY_THRESHOLD:
                self.last_trade_index = i
                return \
                    {
                        'TradeStatus': TradeStatus.EnterShort,
                        'signal_index': signal_index,
                        'datetime': row.datetime.strftime(constants.DATETIME_FORMAT),
                        'entry_price': row.close,
                        'EMA': row.EMA,
                        'RSI': row.RSI,
                        'ADX': row.ADX,
                    }

        return \
            {
                'TradeStatus': TradeStatus.NoTrade,
                'signal_index': signal_index
            }