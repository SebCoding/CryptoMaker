import sys
import time

import numpy as np
import rapidjson
import talib
import datetime as dt
import constants
import utils
from CandleHandler import CandleHandler
from enums.BybitEnums import OrderSide
from enums.SignalMode import SignalMode
from logging_.Logger import Logger
from enums import TradeSignals
from enums.TradeSignals import TradeSignals
from strategies.BaseStrategy import BaseStrategy
from datetime import timedelta


class UltimateScalper(BaseStrategy):
    """
        UltimateScalper Strategy
        ------------------------
        Inspired from these videos:
         - Best Crypto Scalping Strategy for the 5 Min Time Frame
           https://www.youtube.com/watch?v=V82HZbDO-rI
         - 83% WIN RATE 5 Minute ULTiMATE Scalping Trading Strategy!
           https://www.youtube.com/watch?v=XHhpCyIpJ50

        Use 3 EMA, RSI, ADX and MACD histogram in the lower 1m timeframe to determine trade entries.
    """
    settings = {
        # Trend indicator: EMA - Exponential Moving Average
        'EMA_Fast': 9,
        'EMA_Slow': 55,
        'EMA_Trend': 200,
        # Momentum indicator: RSI - Relative Strength Index
        'RSI': 4,
        'RSI_Low': 19,
        'RSI_High': 81,
        # ADX: Average Directional Index
        # Not initially in this strategy, but added as an optional parameter
        'ADX': 17,
        'ADX_Threshold': 24,  # set to 0 to disable ADX
        # Trend following momentum indicator:
        # MACD - Moving Average Convergence Divergence
        'MACD_Fast': 12,
        'MACD_Slow': 24,
        'MACD_Signal': 9,
        # Bollinger Bands around the MACD Histogram
        'BB_Length': 34,
        'BB_Mult': 1
    }

    def __init__(self, database, exchange):
        super().__init__(database, exchange)
        self._logger = Logger.get_module_logger(__name__)

        if self._config['strategy']['signal_mode'] in ['realtime', 'sub_interval']:
            msg = f"The UltimateScalper strategy does not support {self._config['strategy']['signal_mode']} signal mode."
            self._logger.error(msg)
            sys.exit(1)

        self._logger.info(f'Initializing the {self.name} strategy.')
        msg = f"Strategy Settings:\n{rapidjson.dumps(self._config['strategy'] | self.settings, indent=2)}"
        self._logger.info(msg)
        # self.last_trade_index = self.minimum_candles_to_start

        # The MACD Histogram is calculated based on the 1min timeframe
        min_in_interval = utils.convert_interval_to_sec(self.interval) / 60
        min_candles_1m = int(self._config['strategy']['minimum_candles_to_start']) * min_in_interval

        if self._config['strategy']['signal_mode'] in ['interval', 'sub_interval']:
            signal_mode_1m = 'interval'
        else:
            signal_mode_1m = 'realtime'
        self._candle_handler_1m = CandleHandler(
            exchange,
            interval='1m',
            signal_mode=signal_mode_1m,
            minimum_candles_to_start=min_candles_1m
        )
        self.data_1m = None

    def get_strategy_text_details(self):
        details = f"EMA({self.settings['EMA_Fast']}, {self.settings['EMA_Slow']}, {self.settings['EMA_Trend']}), " \
                  f"RSI({self.settings['RSI']}, {self.settings['RSI_Low']}, {self.settings['RSI_High']})"
        if self.settings['ADX_Threshold'] > 0:
            details += f", ADX({self.settings['ADX']}, {self.settings['ADX_Threshold']})"
        details += f", MACD({self.settings['MACD_Fast']}, {self.settings['MACD_Slow']}, {self.settings['MACD_Signal']})"
        details += f", BB({self.settings['BB_Length']}, {self.settings['BB_Mult']})"
        return details

    # Calculate indicator values required to determine long/short signals
    def add_indicators_and_signals(self, candles_df):
        # logger.info('Adding indicators and signals to data.')
        df = candles_df.copy()

        # EMA: Exponential Moving Average
        df['EMA_Fast'] = talib.EMA(df['close'], timeperiod=self.settings['EMA_Fast'])
        df['EMA_Slow'] = talib.EMA(df['close'], timeperiod=self.settings['EMA_Slow'])
        df['EMA_Trend'] = talib.EMA(df['close'], timeperiod=self.settings['EMA_Trend'])

        # RSI: Momentum Indicator
        df['RSI'] = talib.RSI(df['close'], timeperiod=self.settings['RSI'])

        # ADX: Volatility Indicator
        df['ADX'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.settings['ADX'])

        # Drop rows with no EMA_Trend (usually first 200 rows for EMA200)
        df.dropna(subset=['EMA_Trend'], how='all', inplace=True)

        # Calculate MACD  and Bollinger bands on 1m timeframe
        macd, macdsignal, macdhist = talib.MACD(self.data_1m['close'],
                                                fastperiod=self.settings["MACD_Fast"],
                                                slowperiod=self.settings["MACD_Slow"],
                                                signalperiod=self.settings["MACD_Signal"])
        self.data_1m['MACDHist'] = macdhist
        self.data_1m['BB_Basis'] = talib.EMA(self.data_1m['MACDHist'], self.settings['BB_Length'])
        self.data_1m['BB_Mult'] = self.settings['BB_Mult']
        self.data_1m['BB_Dev'] = self.data_1m['BB_Mult'] * \
                                 talib.STDDEV(self.data_1m['MACDHist'], self.settings['BB_Length'])
        self.data_1m['BB_Upper'] = self.data_1m['BB_Basis'] + self.data_1m['BB_Dev']
        self.data_1m['BB_Lower'] = self.data_1m['BB_Basis'] - self.data_1m['BB_Dev']

        # Drop rows with no BB_Basis values
        self.data_1m.dropna(subset=['BB_Basis'], how='all', inplace=True)

        # We use inner join here to trim rows at the beginning and the end where data is missing.
        # Candle data does not end at the same point for all intervals
        df = df.reset_index().merge(self.data_1m[['end_time', 'MACDHist', 'BB_Upper', 'BB_Lower']],
                                    on="end_time", how='inner').set_index('index')
        df.loc[:, 'signal'] = 0
        # Enter long trade
        df.loc[
            (
                    (df['EMA_Fast'] > df['EMA_Slow']) &
                    (df['EMA_Slow'] > df['EMA_Trend']) &
                    (df['RSI'] > self.settings['RSI_Low']) &
                    (df['ADX'] > self.settings['ADX_Threshold']) &
                    (df['MACDHist'] <= df['BB_Lower'])
            ),
            'signal'] = 1

        # Enter short trade
        df.loc[
            (
                    (df['EMA_Fast'] < df['EMA_Slow']) &
                    (df['EMA_Slow'] < df['EMA_Trend']) &
                    (df['RSI'] < self.settings['RSI_High']) &
                    (df['ADX'] > self.settings['ADX_Threshold']) &
                    (df['MACDHist'] >= df['BB_Upper'])
            ),
            'signal'] = -1

        self.data = df

        if self._config['bot']['display_dataframe']:
            df_print = df.drop(columns=['start', 'end', 'timestamp'], axis=1)
            # print('\n\n' + self.data_1m.round(2).head(10).to_string())
            # print('\n\n' + self.data_1m.round(2).tail(10).to_string())
            # print('\n\n' + df_print.round(2).head(10).to_string())
            print('\n\n' + df_print.round(2).tail(10).to_string())

    # Return 2 values:
    #   - DataFrame with indicators
    #   - dictionary with results
    def find_entry(self):
        # Get fresh candle data
        candles_df, data_changed = self._candle_handler.get_refreshed_candles()
        if data_changed:
            # print(candles_df.tail(10).to_string() + '\n')
            while True:
                candles_df_1m, data_changed_1m = self._candle_handler_1m.get_refreshed_candles()
                if candles_df_1m is not None and candles_df_1m.iloc[-1]['end'] >= candles_df.iloc[-1]['end']:
                    # print(candles_df_1m.tail(10).to_string() + '\n')
                    self.data_1m = candles_df_1m.copy()
                    break
                else:
                    time.sleep(1)  # wait 1s

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
                ind_values = f"EMA=({row.EMA_Fast}, {row.EMA_Slow}, {row.EMA_Trend}), " \
                             f"RSI({row.RSI}, {row.RSI_Low}, {row.RSI_High}), " \
                             f"ADX({row.ADX}, {row.ADX_Threshold}), " \
                             f"MACDHist({row.MACDHist}), BB_Lower({row.BB_Lower})"
                signal = {
                    'IdTimestamp': int(row.timestamp),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterLong,
                    "Side": OrderSide.Buy,
                    'EntryPrice': row.close,
                    'IndicatorValues': ind_values,
                    'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

            # Short Entry
            if short_signal:
                ind_values = f"EMA=({row.EMA_Fast}, {row.EMA_Slow}, {row.EMA_Trend}), " \
                             f"RSI({row.RSI}, {row.RSI_Low}, {row.RSI_High}), " \
                             f"ADX({row.ADX}, {row.ADX_Threshold}), " \
                             f"MACDHist({row.MACDHist}), BB_Upper({row.BB_Upper})"
                signal = {
                    'IdTimestamp': int(row.timestamp),
                    'DateTime': dt.datetime.fromtimestamp(row.timestamp / 1000000).strftime(constants.DATETIME_FMT),
                    'Pair': row.pair,
                    'Interval': self.interval,
                    'Signal': TradeSignals.EnterShort,
                    "Side": OrderSide.Sell,
                    'EntryPrice': row.close,
                    'IndicatorValues': ind_values,
                    'Details': f"{self._config['strategy']['name']}: {self.get_strategy_text_details()}"
                }
                self.db.add_trade_signals_dict(signal)
                return self.data, signal

        return self.data, {'Signal': TradeSignals.NoTrade}
