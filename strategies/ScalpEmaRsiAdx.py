import rapidjson
import talib
import datetime as dt
import constants
from enums.BybitEnums import OrderSide
from logging_.Logger import Logger
from enums import TradeSignals
from enums.TradeSignals import TradeSignals
from strategies.BaseStrategy import BaseStrategy


class ScalpEmaRsiAdx(BaseStrategy):
    """
        Implementation of the Scalping Strategy found here:
        https://www.youtube.com/watch?v=vBM0imYSzxI
        Using EMA RSI ADX Indicators

        Values for interval, takeprofit and stoploss come from the config.json file
    """

    # Trend indicator: EMA - Exponential Moving Average
    EMA_PERIODS = 50

    # % over/under the EMA that can be tolerated to determine if the long/short trade can be placed
    # Value should be between 0 and 1
    EMA_TOLERANCE = 0

    # Momentum indicator: RSI - Relative Strength Index
    RSI_PERIODS = 2
    RSI_MIN_SIGNAL = 20
    RSI_MAX_SIGNAL = 80

    # Trade entry RSI thresholds (by default equal to RSI min/max thresholds)
    RSI_MIN_ENTRY = 30
    RSI_MAX_ENTRY = 70

    # Volatility indicator: ADX - Average Directional Index
    ADX_PERIODS = 3
    ADX_THRESHOLD = 30

    def __init__(self, database, exchange):
        super().__init__(database, exchange)
        self._logger = Logger.get_module_logger(__name__)
        self._logger.info(f'Initializing the {self.name} strategy: ' + self.get_strategy_text_details())
        self._logger.info(f'Strategy Settings:\n' + rapidjson.dumps(self._config['strategy'], indent=2))
        self.last_trade_index = self.minimum_candles_to_start
        self.data = None

    def get_strategy_text_details(self):
        details = f'EMA({self.EMA_PERIODS}'
        if self.EMA_TOLERANCE > 0:
            details += ', tolerance={self.EMA_TOLERANCE}'
        details += f'), RSI({self.RSI_PERIODS}, signal[{self.RSI_MIN_SIGNAL}, {self.RSI_MAX_SIGNAL}], ' \
                   f'entry[{self.RSI_MIN_ENTRY}, {self.RSI_MAX_ENTRY}]), ADX({self.ADX_PERIODS}, {self.ADX_THRESHOLD})'
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

        # Trend Indicator. EMA
        df['EMA'] = talib.EMA(df['close'], timeperiod=self.EMA_PERIODS)

        # Momentum Indicator. RSI
        df['RSI'] = talib.RSI(df['close'], timeperiod=self.RSI_PERIODS)

        # Volatility Indicator. ADX
        df['ADX'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.ADX_PERIODS)

        # EMA Tolerance columns
        df['EMA_Long'] = df['EMA'] - df['EMA'] * self.EMA_TOLERANCE
        df['EMA_Short'] = df['EMA'] + df['EMA'] * self.EMA_TOLERANCE

        df['signal'] = 0

        # Populate long signals
        df.loc[
            (
                    (df['close'] > df['EMA_Long']) &  # price > (EMA - Tolerance)
                    (df['RSI'] < self.RSI_MIN_SIGNAL) &  # RSI < RSI_MIN_THRESHOLD
                    (df['ADX'] > self.ADX_THRESHOLD)  # ADX > ADX_THRESHOLD
            ),
            'signal'] = 1

        # Populate short signals
        df.loc[
            (
                    (df['close'] < df['EMA_Short']) &  # price < (EMA + Tolerance)
                    (df['RSI'] > self.RSI_MAX_SIGNAL) &  # RSI > RSI_MAX_THRESHOLD
                    (df['ADX'] > self.ADX_THRESHOLD)  # ADX > ADX_THRESHOLD
            ),
            'signal'] = -1

        self.data = df

        if self._config['bot']['display_dataframe']:
            df_print = df.drop(columns=['start', 'end', 'timestamp'], axis=1)
            msg = '\n' + df_print.round(2).tail(10).to_string() + '\n'
            self._logger.info(msg)

    # Return 2 values:
    #   - DataFrame with indicators
    #   - dictionary with results
    def find_entry2(self):
        """
            New version. This version assumes that on an entry, the previous row will contain the signal.
            This only works when RSI_SIGNAL and RSI_ENTRY and the same.
            Otherwise, there could be a gap between the signal and the entry.

            Return 2 values:
              - DataFrame with indicators
              - dictionary with results
        """
        # Step 1: Get fresh candle data
        candles_df, data_changed = self._candle_handler.get_refreshed_candles()

        if data_changed:
            # Step 2: Add indicators and signals
            self.add_indicators_and_signals(candles_df)

            # Step3: Look for entry point
            # logger.info('Looking trading trade entry.')

            # Get last row of the dataframe
            row = self.data.iloc[-1]

            long_signal = True if self.data['signal'].iloc[-2] == 1 else False
            short_signal = True if self.data['signal'].iloc[-2] == -1 else False

            # Long Entry
            if long_signal \
                    and row.close > row.EMA_Long \
                    and row.RSI > self.RSI_MIN_ENTRY \
                    and row.ADX >= self.ADX_THRESHOLD:
                signal = {
                    'IdTimestamp': row.timestamp,
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterLong,
                    "Side": OrderSide.Buy,
                    'EntryPrice': row.close,
                    'IndicatorValues': f"EMA={round(row.EMA, 2)}, RSI={round(row.RSI, 2)}, ADX={round(row.ADX, 2)}",
                    'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

            # Short Entry
            if short_signal \
                    and row.close < row.EMA_Short \
                    and row.RSI < self.RSI_MAX_ENTRY \
                    and row.ADX >= self.ADX_THRESHOLD:
                signal = {
                    'IdTimestamp': int(row.timestamp),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterShort,
                    "Side": OrderSide.Sell,
                    'EntryPrice': row.close,
                    'IndicatorValues': f"EMA={round(row.EMA, 2)}, RSI={round(row.RSI, 2)}, ADX={round(row.ADX, 2)}",
                    'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

        return self.data, {'Signal': TradeSignals.NoTrade}

    def find_entry(self):
        """
            Return 2 values:
              - DataFrame with indicators
              - dictionary with results
        """
        # Step 1: Get fresh candle data
        candles_df, data_changed = self._candle_handler.get_refreshed_candles()

        if data_changed:
            # Step 2: Add indicators and signals
            self.add_indicators_and_signals(candles_df)

            # Step3: Look for entry point
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
                if long_signal and (row.close < row.EMA_Long or row.ADX < self.ADX_THRESHOLD):
                    return self.data, {'Signal': TradeSignals.NoTrade, 'SignalOffset': signal_index - data_length + 1}

                # If after receiving a short signal the EMA or ADX are no longer satisfied, cancel signal
                if short_signal and (row.close > row.EMA_Short or row.ADX < self.ADX_THRESHOLD):
                    return self.data, {'Signal': TradeSignals.NoTrade, 'SignalOffset': signal_index - data_length + 1}

                # RSI exiting oversold area. Long Entry
                if long_signal and row.RSI > self.RSI_MIN_ENTRY:
                    self.last_trade_index = i
                    signal = {
                        'IdTimestamp': int(row.timestamp),
                        'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                        'Pair': row.pair,
                        'Interval': self.interval,
                        'Signal': TradeSignals.EnterLong,
                        'Side': OrderSide.Buy,
                        'EntryPrice': row.close,
                        'IndicatorValues': f"EMA={round(row.EMA, 2)}, RSI={round(row.RSI, 2)}, ADX={round(row.ADX, 2)}",
                        'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"

                    }
                    self.db.add_trade_signals_dict(signal)
                    return self.data, signal

                # RSI exiting overbought area. Short Entry
                elif short_signal and row.RSI < self.RSI_MAX_ENTRY:
                    self.last_trade_index = i
                    signal = {
                        'IdTimestamp': int(row.timestamp),
                        'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                        'Pair': row.pair,
                        'Interval': self.interval,
                        'Signal': TradeSignals.EnterShort,
                        'Side': OrderSide.Sell,
                        'EntryPrice': row.close,
                        'IndicatorValues': f"EMA={round(row.EMA, 2)}, RSI={round(row.RSI, 2)}, ADX={round(row.ADX, 2)}",
                        'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                    }
                    self.db.add_trade_signals_dict(signal)
                    return self.data, signal

        return self.data, {'Signal': TradeSignals.NoTrade}
