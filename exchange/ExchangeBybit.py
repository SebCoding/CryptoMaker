"""
    Exchange class that implements operations done through the WebSocket API
    This class is hardcoded for the Bybit exchange
----------------------------------------------------------------------------
To see which endpoints and topics are available, check the Bybit API
documentation:
    https://bybit-exchange.github.io/docs/inverse/#t-websocket
    https://bybit-exchange.github.io/docs/linear/#t-websocket

Inverse Perpetual endpoints:
wss://stream-testnet.bybit.com/realtime
wss://stream.bybit.com/realtime

Perpetual endpoints:
wss://stream-testnet.bybit.com/realtime_public
wss://stream-testnet.bybit.com/realtime_private
wss://stream.bybit.com/realtime_public or wss://stream.bytick.com/realtime_public
wss://stream.bybit.com/realtime_private or wss://stream.bytick.com/realtime_private

Spot endpoints:
wss://stream-testnet.bybit.com/spot/quote/ws/v1
wss://stream-testnet.bybit.com/spot/quote/ws/v2
wss://stream-testnet.bybit.com/spot/ws
wss://stream.bybit.com/spot/quote/ws/v1
wss://stream.bybit.com/spot/quote/ws/v2
wss://stream.bybit.com/spot/ws

Futures Public Topics:
orderBookL2_25
orderBookL2-200
trade
insurance
instrument_info
klineV2

Futures Private Topics:
position
execution
order
stop_order
wallet

Spot Topics:
Subscribing to spot topics uses the JSON format to pass the topic name and
filters, as opposed to futures WS where the topic and filters are pass in a
single string. So, it's recommended to pass a JSON or python dict in your
subscriptions, which also be used to fetch the topic's updates. Examples can
be found in the code panel here: https://bybit-exchange.github.io/docs/spot/#t-publictopics

However, as private spot topics do not require a subscription, the following
strings can be used to fetch data:
outboundAccountInfo
executionReport
ticketInfo

"""
import pandas as pd
from websocket._exceptions import WebSocketTimeoutException
import api_keys
import constants
import datetime as dt

import utils
from Logger import Logger
from Configuration import Configuration
from pybit import HTTP, WebSocket


class ExchangeBybit:
    name = None
    use_testnet = False

    # HTTP: REST API
    _http_endpoint = None
    # session_unauth = None
    session_auth = None

    # websockets
    _ws_endpoint_public = None
    _ws_endpoint_private = None
    _wallet_topic_name = 'wallet'
    _position_topic_name = 'position'
    ws_public = None
    ws_private = None


    # Bybit WS only support: ['1', '3', '5', '15', '30', '60', '120', '240', '360', 'D', 'W', 'M']
    interval_map = {
        '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
        '1h': '60', '2h': '120', '4h': '240', '6h': '360',
        '1d': 'D', '1w': 'W', '1M': 'M'
    }

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.interval = self.interval_map[self._config['strategy']['interval']]
        self.name = str(self._config['exchange']['name']).capitalize()
        self.pair = self._config['exchange']['pair']
        self.validate_pair()

        # Testnet/Mainnet
        if self._config['exchange']['testnet']:
            self.use_testnet = True
            self.name = self.name + '-Testnet'
            self._http_endpoint = self._config['exchange']['http']['linear_testnet']
            self._ws_endpoint_public = self._config['exchange']['websockets']['ws_linear_public_testnet']
            self._ws_endpoint_private = self._config['exchange']['websockets']['ws_linear_private_testnet']
            self.api_key = api_keys.TESTNET_BYBIT_API_KEY
            self.api_secret = api_keys.TESTNET_BYBIT_API_SECRET
        else:
            self.use_testnet = False
            self._http_endpoint = self._config['exchange']['linear_mainnet2']
            self._ws_endpoint_public = self._config['exchange']['websockets']['ws_linear_public_mainnet2']
            self._ws_endpoint_private = self._config['exchange']['websockets']['ws_linear_private_mainnet2']
            self.api_key = api_keys.BYBIT_API_KEY
            self.api_secret = api_keys.BYBIT_API_SECRET

        # Market type hardcoded for perpetual futures
        if self._config['exchange']['market_type'] != 'perpetual futures':
            msg = f"Unsupported market type [{self._config['exchange']['market_type']}]."
            self._logger.error(msg)
            raise Exception(msg)

        # HTTP Session
        self.create_http_session()

        # Connect websockets and subscribe to topics
        self.public_topics = self.build_public_topics_list()
        self.private_topics = self.build_private_topics_list()

        # TODO use a trier decorator to retry with timeouts
        try:
            self.subscribe_to_topics()
        except WebSocketTimeoutException as e:
            self._logger.exception(f'Websocket Timeout')
            raise e

    def create_http_session(self):
        force_retry = True
        max_retries = 4  # default is 3
        retry_delay = 3  # default is 3 seconds
        request_timeout = self._config['exchange']['http']['timeout']  # default is 10 seconds
        log_requests = True
        logging_level = self._config['logging']['logging_level']  # default is logging.INFO
        spot = False  # spot or futures

        # Authenticated
        self.session_auth = HTTP(
            endpoint=self._http_endpoint,
            api_key=self.api_key,
            api_secret=self.api_secret,
            request_timeout=request_timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            force_retry=force_retry,
            log_requests=log_requests,
            logging_level=logging_level,
            spot=spot)
        # Unauthenticated
        # self.session_unauthenticated = HTTP(
        #     endpoint=self._http_endpoint,
        #     request_timeout=request_timeout,
        #     max_retries=max_retries,
        #     retry_delay=retry_delay,
        #     force_retry=force_retry,
        #     log_requests=log_requests,
        #     logging_level=logging_level,
        #     spot=spot)

    def validate_pair(self):
        if 'USDT' not in self.pair:
            msg = f'Application only supports USDT perpetuals.'
            self._logger.error(msg)
            raise Exception(msg)

    # ===============================================================================
    #   HTTP Related Methods
    # ===============================================================================

    # from_time, to_time must be timestamps
    def get_candle_data(self, pair, from_time, to_time, interval, verbose=False):
        from_time_str = dt.datetime.fromtimestamp(from_time).strftime('%Y-%m-%d')
        to_time_str = dt.datetime.fromtimestamp(to_time).strftime('%Y-%m-%d')

        if verbose:
            print(f'Fetching {pair} data from {self.name}. Interval [{interval}],',
                  f' From[{from_time_str}], To[{to_time_str}]')

        df_list = []
        start_time = from_time
        last_datetime_stamp = start_time
        to_time_stamp = to_time

        while last_datetime_stamp < to_time_stamp:
            result = self.session_auth.query_kline(
                symbol=self.pair,
                interval=self.interval_map[interval],
                **{'from': last_datetime_stamp})[
                'result']
            tmp_df = pd.DataFrame(result, columns=['open_time', 'open', 'high', 'low', 'close', 'volume'])
            if tmp_df is None or (len(tmp_df.index) == 0):
                break
            df_list.append(tmp_df)
            last_datetime_stamp = float(max(tmp_df.open_time) + 1)  # Add 1 sec to last data received

        if df_list is None or len(df_list) == 0:
            return None

        df = pd.concat(df_list)

        # Drop rows that have a timestamp greater than to_time
        df = df[df.open_time <= int(to_time)]

        # Add columns
        df['pair'] = pair
        df['confirm'] = True
        df['datetime'] = [dt.datetime.fromtimestamp(x) for x in df.open_time]
        df.rename(columns={'open_time': 'start'}, inplace=True)
        df['end'] = df['start'].map(lambda start: utils.adjust_from_time_timestamp(start, interval, 1, backward=False))
        df['timestamp'] = 0

        # Only keep relevant columns OHLCV and re-order
        df = df.loc[:,
             ['start', 'end', 'datetime', 'pair', 'open', 'high', 'low', 'close', 'volume', 'confirm', 'timestamp']]

        # Set proper data types
        df['start'] = df['start'].astype(int)
        df['end'] = df['end'].astype(int)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['timestamp'] = df['timestamp'].astype(int)
        return df

    # Return a dictionary with balances for currencies.
    # Use 'USDT' as key to get USDT balances => data['result']['USDT']
    def get_balances(self):
        data = self.ws_private.fetch(self._wallet_topic_name)
        if data:
            return data
        else:
            data = self.session_auth.get_wallet_balance()
            if data and data['ret_msg'] == 'OK' and data['result']:
                return data['result']['USDT']

    def get_position(self, pair):
        data = self.ws_private.fetch(self._position_topic_name)
        if data:
            return data
        else:
            data = self.session_auth.my_position(symbol=pair)
            if data and data['ret_msg'] == 'OK' and data['result']:
                return data['result']

    # ===============================================================================
    #   Websockets Related Methods
    # ===============================================================================

    def subscribe_to_topics(self):
        # public subscriptions
        self.ws_public = WebSocket(
            self._ws_endpoint_public,
            subscriptions=self.public_topics,
            ping_interval=20,
            ping_timeout=15
        )

        # private subscriptions, connect with authentication
        self.ws_private = WebSocket(
            self._ws_endpoint_private,
            subscriptions=self.private_topics,
            api_key=self.api_key,
            api_secret=self.api_secret,
            ping_interval=20,
            ping_timeout=15
        )

    def build_public_topics_list(self):
        topic_list = [
            self.get_candle_topic(self.pair, self.interval),
            self.get_orderbook25_topic(self.pair)
        ]
        return topic_list

    def build_private_topics_list(self):
        topic_list = ['position', 'execution', 'order', 'stop_order', 'wallet']
        return topic_list

    @staticmethod
    def get_orderbook25_topic(pair):
        sub = "orderBookL2_25.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_orderbook200_topic(pair):
        sub = "orderBook_200.100ms.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_trade_topic(pair):
        sub = "trade.<pair>"
        return sub.replace('<pair>', pair)

    @staticmethod
    def get_instrument_info_topic(pair):
        sub = "instrument_info.100ms.<pair>"
        return sub.replace('<pair>', pair)

    # Expecting the interval in this list constants.WS_VALID_CANDLE_INTERVALS
    @classmethod
    def get_candle_topic(cls, pair, interval):
        assert (interval in constants.WS_VALID_CANDLE_INTERVALS)
        sub = 'candle.<interval>.<pair>'
        return sub.replace('<interval>', interval).replace('<pair>', pair)

    @staticmethod
    def get_liquidation_topic(pair):
        sub = "liquidation.<pair>"
        return sub.replace('<pair>', pair)

        # from_time, to_time must be timestamps