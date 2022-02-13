import numpy as np
import rapidjson
import talib
import datetime as dt
import constants
from enums.BybitEnums import OrderSide
from logging_.Logger import Logger
from enums import TradeSignals
from enums.TradeSignals import TradeSignals
from strategies.BaseStrategy import BaseStrategy


class MACD(BaseStrategy):
    # Trend indicator: EMA - Exponential Moving Average
    EMA_PERIODS = 150

    # Trend following momentum indicator:
    # MACD - Moving Average Convergence Divergence
    MACD_FAST = 10
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    def __init__(self, database, exchange):
        super().__init__(database, exchange)
        self._logger = Logger.get_module_logger(__name__)
        self._logger.info(f'Initializing the {self.name} strategy: ' + self.get_strategy_text_details())
        self._logger.info(f'Strategy Settings:\n' + rapidjson.dumps(self._config['strategy'], indent=2))

    def get_strategy_text_details(self):
        details = f'EMA({self.EMA_PERIODS}), ' \
                  f'MACD(fast={self.MACD_FAST}, slow={self.MACD_SLOW}, signal={self.MACD_SIGNAL})'
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

        # Trend Indicator. EMA200
        df['EMA'] = talib.EMA(df['close'], timeperiod=self.EMA_PERIODS)

        # MACD - Moving Average Convergence/Divergence
        macd, macdsignal, macdhist = \
            talib.MACD(df['close'], fastperiod=self.MACD_FAST, slowperiod=self.MACD_SLOW, signalperiod=self.MACD_SIGNAL)

        df['MACD'] = macd
        df['MACDSIG'] = macdsignal

        # macdsignal over macd then 1, under 0
        df['O/U'] = np.where(df['MACDSIG'] >= df['MACD'], 1, 0)

        # macdsignal crosses macd
        df['cross'] = df['O/U'].diff()
        df['cross'] = df['cross'].fillna(0).astype(int)
        del df['O/U']

        df['signal'] = 0
        # Populate long signals
        df.loc[
            (
                    (df['close'] > df['EMA']) &  # price > ema200
                    (df['MACDSIG'] < 0) &  # macdsignal < 0
                    (df['cross'] == -1)  # macdsignal crossed under macd
            ),
            'signal'] = 1

        # Populate short signals
        df.loc[
            (
                    (df['close'] < df['EMA']) &  # price < ema200
                    (df['MACDSIG'] > 0) &  # macdsignal > 0
                    (df['cross'] == 1)  # macdsignal crossed over macd
            ),
            'signal'] = -1

        self.data = df

        if self._config['bot']['display_dataframe']:
            df_print = df.drop(columns=['start', 'end', 'timestamp'], axis=1)
            print('\n\n'+df_print.round(2).tail(10).to_string())

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

            # Get last row of the dataframe
            row = self.data.iloc[-1]

            long_signal = True if self.data['signal'].iloc[-1] == 1 else False
            short_signal = True if self.data['signal'].iloc[-1] == -1 else False

            # Long Entry
            if long_signal:
                signal = {
                    'IdTimestamp': int(row.timestamp),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterLong,
                    "Side": OrderSide.Buy,
                    'EntryPrice': row.close,
                    'IndicatorValues': f"EMA={round(row.EMA, 2)}, MACD={round(row.MACD, 2)}, MACSIG={round(row.MACDSIG, 2)}",
                    'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

            # Short Entry
            if short_signal:
                signal = {
                    'IdTimestamp': int(row.timestamp),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterShort,
                    "Side": OrderSide.Sell,
                    'EntryPrice': row.close,
                    'IndicatorValues': f"EMA={round(row.EMA, 2)}, MACD={round(row.MACD, 2)}, MACSIG={round(row.MACDSIG, 2)}",
                    'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

        return self.data, {'Signal': TradeSignals.NoTrade}

