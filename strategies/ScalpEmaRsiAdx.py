import talib
import datetime as dt
import constants
from Logger import Logger
from database.Database import Database
from enums import TradeSignals
from enums.TradeSignals import TradeSignals
from strategies.BaseStrategy import BaseStrategy


class ScalpEmaRsiAdx(BaseStrategy):
    # Values for interval, takeprofit and stoploss come from the config.json file

    # Trend indicator: EMA - Exponential Moving Average
    EMA_PERIODS = 40

    # Momentum indicator: RSI - Relative Strength Index
    RSI_PERIODS = 2
    RSI_MIN_SIGNAL_THRESHOLD = 20
    RSI_MAX_SIGNAL_THRESHOLD = 80

    # Trade entry RSI thresholds (by default equal to RSI min/max thresholds)
    RSI_MIN_ENTRY_THRESHOLD = 20
    RSI_MAX_ENTRY_THRESHOLD = 80

    # Volatility indicator: ADX - Average Directional Index
    ADX_PERIODS = 3
    ADX_THRESHOLD = 30

    def __init__(self, database):
        super().__init__()
        self.logger = Logger.get_module_logger(__name__)
        self.logger.info(f'Initializing strategy [{self.name}] ' + self.get_strategy_text_details())
        self.last_trade_index = self.minimum_candles_to_start
        self.db = database

    def get_strategy_text_details(self):
        details = f'EMA({self.EMA_PERIODS}), RSI({self.RSI_PERIODS}), ADX({self.ADX_PERIODS}) ' \
                  f'RSI_SIGNAL({self.RSI_MIN_SIGNAL_THRESHOLD}, {self.RSI_MAX_SIGNAL_THRESHOLD}), ' \
                  f'RSI_ENTRY({self.RSI_MIN_ENTRY_THRESHOLD}, {self.RSI_MAX_ENTRY_THRESHOLD}), ' \
                  f'ADX_THRESHOLD({self.ADX_THRESHOLD})'
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

    # Return 2 values:
    #   - DataFrame with indicators
    #   - dictionary with results
    def find_entry(self, candles_df):
        # Step 1: Add indicators and signals
        self.add_indicators_and_signals(candles_df)

        # Step2: Look for entry point
        # logger.info('Looking trading trade entry.')
        signal_list = self.data.query('signal in [-1, 1]').index
        signal_index = max(signal_list)
        data_length = len(self.data)
        # print(f'last signal index: {signal_index}')

        # We ignore all signals for candles prior to when the application
        # was started or when the last trade entry that we signaled
        if signal_index <= self.last_trade_index:
            return self.data, {'Signal': TradeSignals.NoTrade, 'SignalOffset': 0}

        long_signal = True if self.data['signal'].iloc[signal_index] == 1 else False
        short_signal = True if self.data['signal'].iloc[signal_index] == -1 else False

        start_scan = signal_index + 1
        for i, row in self.data.iloc[start_scan:].iterrows():
            # If after receiving a long signal the EMA or ADX are no longer satisfied, cancel signal
            if long_signal and (row.close < row.EMA or row.ADX < self.ADX_THRESHOLD):
                return self.data, {'Signal': TradeSignals.NoTrade, 'SignalOffset': signal_index - data_length + 1}

            # If after receiving a short signal the EMA or ADX are no longer satisfied, cancel signal
            if short_signal and (row.close > row.EMA or row.ADX < self.ADX_THRESHOLD):
                return self.data, {'Signal': TradeSignals.NoTrade, 'SignalOffset': signal_index - data_length + 1}

            # RSI exiting oversold area. Long Entry
            if long_signal and row.RSI > self.RSI_MIN_ENTRY_THRESHOLD:
                self.last_trade_index = i
                signal = {
                    'IdTimestamp': row.timestamp,
                    # 'DateTime': row.datetime.strftime(constants.DATETIME_FORMAT),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FORMAT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterLong,
                    'SignalOffset': signal_index - data_length + 1,
                    'EntryPrice': row.close,
                    'EMA': row.EMA,
                    'RSI': row.RSI,
                    'ADX': row.ADX,
                    'Notes': self.get_strategy_text_details()
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

            # RSI exiting overbought area. Short Entry
            elif short_signal and row.RSI < self.RSI_MAX_ENTRY_THRESHOLD:
                self.last_trade_index = i
                signal = {
                    'IdTimestamp': row.timestamp,
                    # 'DateTime': row.datetime.strftime(constants.DATETIME_FORMAT),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FORMAT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterShort,
                    'SignalOffset': signal_index - data_length + 1,
                    'EntryPrice': row.close,
                    'EMA': row.EMA,
                    'RSI': row.RSI,
                    'ADX': row.ADX,
                    'Notes': self.get_strategy_text_details()
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

        return self.data, {'Signal': TradeSignals.NoTrade, 'SignalOffset': signal_index - data_length + 1}
