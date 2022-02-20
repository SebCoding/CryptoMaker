import arrow
import pandas as pd
import rapidjson

import api_keys
import constants
import datetime as dt

import pybit
import utils
from enums.SignalMode import SignalMode
from logging_.Logger import Logger
from Configuration import Configuration
from Orders import Order
from enums.BybitEnums import OrderType
from pybit import HTTP, WebSocket


class ExchangeBybit:
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
    name = None
    use_testnet = False

    # HTTP: REST API
    _http_endpoint = None

    # session_unauth = None
    session_auth = None

    # websocket endpoints
    _ws_endpoint_public = None
    _ws_endpoint_private = None

    # Private Topics
    wallet_topic_name = 'wallet'
    position_topic_name = 'position'
    order_topic_name = 'order'
    execution_topic_name = 'execution'

    # Websockets
    ws_public = None
    ws_private = None

    # Bybit WS only support: ['1', '3', '5', '15', '30', '60', '120', '240', '360', 'D', 'W', 'M']
    interval_map = {
        '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
        '1h': '60', '2h': '120', '4h': '240', '6h': '360',
        '1d': 'D', '1w': 'W', '1M': 'M'
    }

    def __init__(self, extra_interval=None):
        """
            extra_interval: Can be used a strategy needs data from an additional timeframe.
            For example: UltimateScalper works in 3m or 5m, but also requires 1m for MACD histogram
        """
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.interval = self.interval_map[self._config['trading']['interval']]
        self.extra_interval = self.interval_map[extra_interval] if extra_interval else None
        self.name = str(self._config['exchange']['name']).capitalize()
        self.pair = self._config['exchange']['pair']
        self.stake_currency = self._config['exchange']['stake_currency']
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
            self._http_endpoint = self._config['exchange']['http']['linear_mainnet2']
            self._ws_endpoint_public = self._config['exchange']['websockets']['ws_linear_public_mainnet2']
            self._ws_endpoint_private = self._config['exchange']['websockets']['ws_linear_private_mainnet2']
            self.api_key = api_keys.BYBIT_API_KEY
            self.api_secret = api_keys.BYBIT_API_SECRET

        # Market type hardcoded for linear
        if self._config['exchange']['market_type'] != 'linear':
            msg = f"Unsupported market type [{self._config['exchange']['market_type']}]."
            self._logger.error(msg)
            raise Exception(msg)

        # HTTP Session
        self.create_http_session()
        self.reset_trading_settings(self.pair)
        self.pair_details_dict = self.get_pair_details()

        # Connect websockets and subscribe to topics
        self._public_topics = self.build_public_topics_list()
        self._private_topics = self.build_private_topics_list()

        self.subscribe_to_topics()

    def validate_pair(self):
        if 'USDT' not in self.pair:
            msg = f'Application only supports USDT perpetuals.'
            self._logger.error(msg)
            raise Exception(msg)

    """
        ----------------------------------------------------------------------------
           Websockets Related Methods
        ----------------------------------------------------------------------------
    """

    def subscribe_to_topics(self):
        logger = Logger.get_module_logger('pybit')
        # public subscriptions
        self.ws_public = WebSocket(
            self._ws_endpoint_public,
            subscriptions=self._public_topics,
            ping_interval=25,
            ping_timeout=24,
            max_data_length=500,
            logger=logger
        )

        # private subscriptions, connect with authentication
        self.ws_private = WebSocket(
            self._ws_endpoint_private,
            subscriptions=self._private_topics,
            api_key=self.api_key,
            api_secret=self.api_secret,
            ping_interval=25,
            ping_timeout=24,
            max_data_length=500,
            logger=logger
        )

    def build_public_topics_list(self):
        topic_list = [
            self.get_candle_topic(self.pair, self.interval),
            self.get_orderbook25_topic(self.pair)
        ]
        if self.extra_interval and self.extra_interval not in topic_list:
            topic_list.append(self.get_candle_topic(self.pair, self.extra_interval))
        return topic_list

    def build_private_topics_list(self):
        # topic_list = ['position', 'execution', 'order', 'stop_order', 'wallet']
        topic_list = [
            self.wallet_topic_name,
            self.position_topic_name,
            self.order_topic_name,
            self.execution_topic_name
        ]
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

    """
        ----------------------------------------------------------------------------
           HTTP Related Methods
        ----------------------------------------------------------------------------
    """

    def create_http_session(self):
        force_retry = True
        max_retries = 4  # default is 3
        retry_delay = 3  # default is 3 seconds
        request_timeout = self._config['exchange']['http']['timeout']  # default is 10 seconds
        log_requests = True
        logging_level = self._config['logging']['logging_level']  # default is logging_.INFO
        spot = False  # spot or futures
        logger = Logger.get_module_logger('pybit')

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
            logger=logger,
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

    def get_pair_details(self):
        """
            A trade_pair_details dictionary
            {
                'name': 'ETHUSDT',
                'alias': 'ETHUSDT',
                'status': 'Trading',
                'base_currency': 'ETH',
                'quote_currency': 'USDT',
                'price_scale': 2,
                'taker_fee': '0.00075',
                'maker_fee': '-0.00025',
                'leverage_filter': {
                    'min_leverage': 1,
                    'max_leverage': 50,
                    'leverage_step': '0.01'
                },
                'price_filter': {
                    'min_price': '0.05',
                    'max_price': '99999.9',
                    'tick_size': '0.05'
                },
                'lot_size_filter': {
                    'max_trading_qty': 200,
                    'min_trading_qty': 0.01,
                    'qty_step': 0.01
                }
            }
        """
        data = self.session_auth.query_symbol()
        if data:
            _list = data['result']
            if _list:
                for i in _list:
                    if i['name'] == self.pair:
                        return i
        return None

    def get_candle_data(self, pair, from_time, to_time, interval, verbose=False):
        """
            get_candle_data(): from_time, to_time must be timestamps
        """
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
        df['start_time'] = [dt.datetime.fromtimestamp(x) for x in df.open_time]
        df.rename(columns={'open_time': 'start'}, inplace=True)
        df['end'] = df['start'].map(lambda start: utils.adjust_from_time_timestamp(start, interval, 1, backward=False))
        df['end_time'] = [dt.datetime.fromtimestamp(x) for x in df.end]
        df['timestamp'] = 0

        # Only keep relevant columns OHLCV and re-order
        df = df.loc[:, ['start', 'end', 'start_time', 'end_time', 'pair',
                        'open', 'high', 'low', 'close', 'volume', 'confirm', 'timestamp']]

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
        data = self.ws_private.fetch(self.wallet_topic_name)
        if data:
            return data
        else:
            data = self.session_auth.get_wallet_balance()
            if data:
                return data['result'][self.stake_currency]
        return None

    # Get my position list.
    def get_position(self, pair):
        data = self.ws_private.fetch(self.position_topic_name)
        if data and self.pair in data.keys():
            pos = []
            if 'Buy' in data[self.pair].keys():
                pos.append(data[self.pair]['Buy'])
            if 'Sell' in data[self.pair].keys():
                pos.append(data[self.pair]['Sell'])
            return pos  # Return list of dict
        else:
            data = self.session_auth.my_position(symbol=pair)
            if data:
                return data['result']  # Return list of dict
        return None

    def get_orders(self, pair, page=1, order_status=None):
        """
            Because order creation/cancellation is asynchronous, there can be a data delay in
            this endpoint. You can get real-time order info with the Query Active Order
            (real-time) endpoint.
            Returns list of active orders for this 'pair'

            Order Statuses that can be used as filter:
            Created, Rejected, New, PartiallyFilled, Filled, Cancelled, PendingCancel
        """
        data = self.ws_private.fetch(self.order_topic_name)
        if data:
            return data  # Return list
        else:
            data = self.session_auth.get_active_order(
                symbol=pair,
                order='asc',
                page=page,
                limit=50,  # Limit for data size per page, max size is 50
                order_status=order_status
            )
            if data:
                return data['result']['data']
        return None

    # Get all orders with all statuses for this pair stored on Bybit
    def get_all_order_records(self, pair):
        list_records = []
        page = 1
        while True:
            result = self.session_auth.get_active_order(
                symbol=pair,
                order='asc',
                page=page,
                limit=50  # Limit for data size per page, max size is 50
            )
            if result and result['result']['data']:
                list_records = list_records + result['result']['data']
                page += 1
            else:
                break
        if list_records:
            # Convert created_at timestamp to datetime string
            df = pd.DataFrame(list_records)
            df['created_time'] = \
                [arrow.get(x).to('local').datetime.strftime(constants.DATETIME_FMT) for x in df.created_time]
            df['updated_time'] = \
                [arrow.get(x).to('local').datetime.strftime(constants.DATETIME_FMT) for x in df.updated_time]
            df.sort_values(by=['created_time'], ascending=True)
            dict_list = df.to_dict('records')
            return dict_list
        return None

    # Get all conditional orders with all statuses for this pair stored on Bybit
    def get_all_conditional_order_records(self, pair):
        list_records = []
        page = 1
        while True:
            result = self.session_auth.get_conditional_order(
                symbol=pair,
                order='asc',
                page=page,
                limit=50  # Limit for data size per page, max size is 50
            )
            if result and result['result']['data']:
                list_records = list_records + result['result']['data']
                page += 1
            else:
                break
        if list_records:
            # Convert created_at timestamp to datetime string
            df = pd.DataFrame(list_records)
            df['created_time'] = \
                [arrow.get(x).to('local').datetime.strftime(constants.DATETIME_FMT) for x in df.created_time]
            df['updated_time'] = \
                [arrow.get(x).to('local').datetime.strftime(constants.DATETIME_FMT) for x in df.updated_time]
            df.sort_values(by=['created_time'], ascending=True)
            dict_list = df.to_dict('records')
            return dict_list
        return None

    # Get active order by id, using websocket or realtime http method
    def get_order_by_id_hybrid(self, pair, order_id):
        data = self.ws_private.fetch(self.order_topic_name)
        if data:
            for order in data:
                if order['order_id'] == order_id:
                    return order
            return None
        else:
            data = self.session_auth.query_active_order(symbol=pair, order_id=order_id)
            return data['result']

    # Get active order by id
    def get_order_by_id_ws_only(self, pair, order_id):
        data = self.ws_private.fetch(self.order_topic_name)
        if data:
            for order in data:
                if order['order_id'] == order_id:
                    return order
        return None

    # Query real-time active order information. If only order_id or order_link_id are passed,
    # a single order will be returned; otherwise, returns up to 500 unfilled orders.
    def query_orders_rt(self, pair, order_status=None):
        data = self.session_auth.query_active_order(pair=pair, order_status=order_status)
        if data:
            return data['result']
        return None

    def query_orders_rt_by_id(self, pair, order_id):
        data = self.session_auth.query_active_order(symbol=pair, order_id=order_id)
        return data['result']

    def place_order(self, o: Order):
        """
            Place an active order.
            Params (* are mandatory):
                *side: Buy, Sell
                *symbol: BTCUSDT
                *order_type: Market, Limit
                *qty: (Order quantity in BTC)
                *price: (Order price. Required if you make limit price order)
                *time_in_force: PostOnly, GoodTillCancel, ImmediateOrCancel, FillOrKill
                *close_on_trigger: true, false
                *reduce_only: true, false
                *order_link_id: (Unique user-set order ID. Maximum length of 36 characters)
                take_profit: (Take profit price, only take effect upon opening the position)
                stop_loss: (Stop loss price, only take effect upon opening the position)
                tp_trigger_by: LastPrice, IndexPrice, MarkPrice
                sl_trigger_by: LastPrice, IndexPrice, MarkPrice
                position_idx: 0, 1, 2 (Modes: 0-One-Way Mode, 1-Buy side of both side mode, 2-Sell side of both side mode)
        """
        data = None
        try:
            if o.order_type == OrderType.Market:
                data = self.session_auth.place_active_order(
                    side=o.side,
                    symbol=o.symbol,
                    order_type=o.order_type,
                    qty=o.qty,
                    take_profit=o.take_profit,
                    stop_loss=o.stop_loss,
                    time_in_force=o.time_in_force,
                    close_on_trigger=False,
                    reduce_only=o.reduce_only,
                    order_link_id=o.order_link_id
                )
            elif o.order_type == OrderType.Limit:
                data = self.session_auth.place_active_order(
                    side=o.side,
                    symbol=o.symbol,
                    order_type=o.order_type,
                    qty=o.qty,
                    price=o.price,
                    take_profit=o.take_profit,
                    stop_loss=o.stop_loss,
                    time_in_force=o.time_in_force,
                    close_on_trigger=False,
                    reduce_only=o.reduce_only,
                    order_link_id=o.order_link_id
                )
        except pybit.exceptions.InvalidRequestError as e:
            # 130125: Current position is zero, cannot fix reduce-only order qty
            if e.status_code not in [130125]:
                self._logger.exception(e)
                raise e
        return data['result'] if data else None

    def replace_active_order(self, **kwargs):
        """
            replace_active_order() can modify/amend your active orders.
            Params:         mandatory   type    description
            - order_id:	        false	string	Order ID. Required if not passing order_link_id
            - order_link_id:	false	string	Unique user-set order ID. Required if not passing order_id
            - symbol	        true	string	Symbol
            - p_r_qty	        false	integer	New order quantity. Do not pass this field if you don't want modify it
            - p_r_price	        false	number	New order price. Do not pass this field if you don't want modify it
            - take_profit	    false	number	New take_profit price, also known as stop_px.
                                                Do not pass this field if you don't want modify it
            - stop_loss	        false	number	New stop_loss price, also known as stop_px.
                                                Do not pass this field if you don't want modify it
            - tp_trigger_by	    false	string	Take profit trigger price type, default: LastPrice
            - sl_trigger_by	    false	string	Stop loss trigger price type, default: LastPrice
         """
        try:
            result = self.session_auth.replace_active_order(**kwargs)
            return result
        except pybit.exceptions.InvalidRequestError as e:
            # 20001: Order not exists or too late to replace
            # 30076 Order not modified
            # 30032: Can not initiate replace_ao while still having pending item
            if e.status_code not in [20001, 30076, 30032]:
                self._logger.exception(e)
                raise e
            result = kwargs
            result['ret_code'] = e.status_code
            result['ret_msg'] = e.message
            self._logger.error(result)
        return result

    #
    # def replace_active_order_qt_pr_sl(self, order_id, new_qty, new_price, new_stop_loss):
    #     """
    #         replace_active_order() can modify/amend your active orders.
    #         Params:
    #          - p_r_qty: New order quantity. Do not pass this field if you don't want modify it
    #          - p_r_price: New order price. Do not pass this field if you don't want modify it
    #          - take_profit: New take_profit price, also known as stop_px. Do not pass this field if you don't want modify it
    #          - stop_loss: New stop_loss price, also known as stop_px. Do not pass this field if you don't want modify it
    #      """
    #     try:
    #         result = self.session_auth.replace_active_order(
    #             symbol=self.pair,
    #             order_id=order_id,
    #             p_r_qty=new_qty,
    #             p_r_price=new_price,
    #             stop_loss=new_stop_loss
    #         )
    #         return result
    #     except pybit.exceptions.InvalidRequestError as e:
    #         # 20001: Order not exists or too late to replace
    #         # 30076 Order not modified
    #         # 30032: Can not initiate replace_ao while still having pending item
    #         if e.status_code not in [20001, 30076, 30032]:
    #             self._logger.exception(e)
    #             raise e
    #         result = {'order_id': order_id, 'new_qty': new_qty, 'new_price': new_price, 'new_stop_loss': new_stop_loss,
    #                   'ret_code': e.status_code, 'ret_msg': e.message}
    #         self._logger.error(result)
    #     return result
    #
    # def replace_active_order_pr_sl(self, order_id, new_price, new_stop_loss):
    #     """
    #         replace_active_order() can modify/amend your active orders.
    #         Params:
    #          - p_r_price: New order price. Do not pass this field if you don't want modify it
    #          - take_profit: New take_profit price, also known as stop_px. Do not pass this field if you don't want modify it
    #          - stop_loss: New stop_loss price, also known as stop_px. Do not pass this field if you don't want modify it
    #      """
    #     try:
    #         result = self.session_auth.replace_active_order(
    #             symbol=self.pair,
    #             order_id=order_id,
    #             p_r_price=new_price,
    #             stop_loss=new_stop_loss
    #         )
    #         return result
    #     except pybit.exceptions.InvalidRequestError as e:
    #         # 20001: Order not exists or too late to replace
    #         # 30076 Order not modified
    #         # 30032: Can not initiate replace_ao while still having pending item
    #         if e.status_code not in [20001, 30076, 30032]:
    #             self._logger.exception(e)
    #             raise e
    #         result = {'order_id': order_id, 'new_price': new_price, 'new_stop_loss': new_stop_loss,
    #                   'ret_code': e.status_code, 'ret_msg': e.message}
    #         self._logger.error(result)
    #     return result
    #
    # def replace_active_order_pr(self, order_id, new_price):
    #     """
    #         replace_active_order() can modify/amend your active orders.
    #         Params:
    #          - p_r_price: New order price. Do not pass this field if you don't want modify it
    #          - take_profit: New take_profit price, also known as stop_px. Do not pass this field if you don't want modify it
    #          - stop_loss: New stop_loss price, also known as stop_px. Do not pass this field if you don't want modify it
    #      """
    #     try:
    #         result = self.session_auth.replace_active_order(
    #             symbol=self.pair,
    #             order_id=order_id,
    #             p_r_price=new_price
    #         )
    #         return result
    #     except pybit.exceptions.InvalidRequestError as e:
    #         # 20001: Order not exists or too late to replace
    #         # 30076 Order not modified
    #         # 30032: Can not initiate replace_ao while still having pending item
    #         if e.status_code not in [20001, 30076, 30032]:
    #             self._logger.exception(e)
    #             raise e
    #         result = {'order_id': order_id, 'new_price': new_price, 'ret_code': e.status_code, 'ret_msg': e.message}
    #         self._logger.error(result)
    #     return result
    #
    # def replace_active_order_qty_pr(self, order_id, new_qty, new_price):
    #     """
    #         replace_active_order() can modify/amend your active orders.
    #         Params:
    #           - p_r_qty: New order quantity. Do not pass this field if you don't want modify it
    #      """
    #     try:
    #         result = self.session_auth.replace_active_order(
    #             symbol=self.pair,
    #             order_id=order_id,
    #             p_r_qty=new_qty,
    #             p_r_price=new_price
    #         )
    #         return result
    #     except pybit.exceptions.InvalidRequestError as e:
    #         # 20001: Order not exists or too late to replace
    #         # 30076 Order not modified
    #         # 30032: Can not initiate replace_ao while still having pending item
    #         if e.status_code not in [20001, 30076, 30032]:
    #             self._logger.exception(e)
    #             raise e
    #         result = {'order_id': order_id, 'new_qty': new_qty, 'ret_code': e.status_code, 'ret_msg': e.message}
    #         self._logger.error(result)
    #     return result
    #
    # def replace_active_order_qty(self, order_id, new_qty):
    #     """
    #         replace_active_order() can modify/amend your active orders.
    #         Params:
    #           - p_r_qty: New order quantity. Do not pass this field if you don't want modify it
    #      """
    #     try:
    #         result = self.session_auth.replace_active_order(
    #             symbol=self.pair,
    #             order_id=order_id,
    #             p_r_qty=new_qty
    #         )
    #         return result
    #     except pybit.exceptions.InvalidRequestError as e:
    #         # 20001: Order not exists or too late to replace
    #         # 30076 Order not modified
    #         # 30032: Can not initiate replace_ao while still having pending item
    #         if e.status_code not in [20001, 30076, 30032]:
    #             self._logger.exception(e)
    #             raise e
    #         result = {'order_id': order_id, 'new_qty': new_qty, 'ret_code': e.status_code, 'ret_msg': e.message}
    #         self._logger.error(result)
    #     return result

    def cancel_active_order(self, order_id):
        try:
            result = self.session_auth.cancel_active_order(
                symbol=self.pair,
                order_id=order_id
            )
            return result
        except pybit.exceptions.InvalidRequestError as e:
            # 20001: Order not exists or too late to replace
            # 30076 Order not modified
            if e.status_code not in [20001, 30076]:
                self._logger.exception(e)
                raise e
            result = {'order_id': order_id, 'ret_code': e.status_code, 'ret_msg': e.message}
            self._logger.error(result)
        return result

    def cancel_all_active_orders(self):
        try:
            result = self.session_auth.cancel_all_active_orders(
                symbol=self.pair
            )
            return result
        except pybit.exceptions.InvalidRequestError as e:
            # 20001: Order not exists or too late to replace
            # 30076 Order not modified
            if e.status_code not in [20001, 30076]:
                self._logger.exception(e)
                raise e
            result = {'ret_code': e.status_code, 'ret_msg': e.message}
        return result

    def public_trading_records(self):
        """
            Get the latest price and other information of the current pair
            TODO: not finished, never tested
        :return:
        """
        data = self.session_auth.public_trading_records(symbol=self.pair)
        if data:
            return data['result']

    # Get user's closed profit and loss records.
    # The results are ordered in descending order (the first item is the latest).
    def _get_closed_profit_and_loss(self, pair, start_time, end_time, page=1):
        result = self.session_auth.closed_profit_and_loss(
            symbol=pair,
            start_time=start_time,  # Start timestamp point for result, in seconds
            end_time=end_time,  # End timestamp point for result, in seconds
            page=page,  # Page. By default, gets first page of data. Maximum of 50 pages
            limit=50  # Limit for data size per page, max size is 50.
            # Optional parameter exec_type: not used by us
        )
        return result['result']

    # Return a dictionary with all Closed P&L records
    def get_all_closed_pnl_records(self, pair):
        start_time = dt.datetime(2000, 1, 1).timestamp()  # Make sure we pick up everything available
        end_time = dt.datetime(2030, 1, 1).timestamp()  # Make sure we pick up everything available
        list_records = []
        page = 1
        while True:
            # Start timestamp point for result, in seconds
            # End timestamp point for result, in seconds
            result = self._get_closed_profit_and_loss(pair, start_time, end_time, page=page)
            if result['data']:
                list_records = list_records + result['data']
                page += 1
            else:
                break
        if list_records:
            # Convert created_at timestamp to datetime string
            df = pd.DataFrame(list_records)
            df['created_at'] = [arrow.get(x).to('local').datetime.strftime(constants.DATETIME_FMT) for x in
                                df.created_at]
            df.sort_values(by=['id'])
            dict_list = df.to_dict('records')
            return dict_list
        return None

    # Get all orders with all statuses for this pair stored on Bybit
    def get_user_trades_records(self, pair):
        start_time = dt.datetime(2000, 1, 1).timestamp()  # Make sure we pick up everything available
        end_time = dt.datetime(2030, 1, 1).timestamp()  # Make sure we pick up everything available
        list_records = []
        page = 1
        while True:
            result = self.session_auth.user_trade_records(
                symbol=pair,
                start_time=start_time,
                end_time=end_time,
                page=page,
                # Limit for data size per page, max size is 200.
                # Default as showing 50 pieces of data per page.
                limit=200
            )
            if result and result['result']['data']:
                list_records = list_records + result['result']['data']
                page += 1
            else:
                break
        # Convert created_at timestamp to datetime string
        if list_records:
            df = pd.DataFrame(list_records)
            df['trade_time_ms'] = \
                [arrow.get(x).to('local').datetime.strftime(constants.DATETIME_FMT_MS)[:-3] for x in
                 df['trade_time_ms']]
            df.sort_values(by=['trade_time_ms'], ascending=True)
            dict_list = df.to_dict('records')
            return dict_list
        return None

    def reset_trading_settings(self, pair):
        """
            Initializes these settings on Bybit before we can start trading
             - Position Mode Switch
             - Set Auto Add Margin
             - Cross/Isolated Margin Switch
             - Leverage
             - Full/Partial Position TP/SL Mode Switch
        """
        # 1. Position Mode Switch
        # If you are in One-Way Mode, you can only open one position on Buy or Sell side;
        # If you are in Hedge Mode, you can open both Buy and Sell side positions simultaneously.
        try:
            # MergedSingle: One-Way Mode; BothSide: Hedge Mode
            mode = 'BothSide'
            res = self.session_auth.position_mode_switch(
                symbol=pair,
                # Probable bug on Bybit 'MergedSingle' does not work here. Mode gets rejected an invalid character...
                mode=mode
            )
            self._logger.info(f'[Position Mode] has been set to: {mode}')
        except pybit.exceptions.InvalidRequestError as e:
            if e.status_code not in [30083]:  # 30083 Position mode not modified
                self._logger.exception(e)
                raise e

        # 2. Set Auto Add Margin
        # Set auto add margin, or Auto-Margin Replenishment.
        try:
            auto_margin = False
            res = self.session_auth.set_auto_add_margin(
                symbol=pair,
                side="Buy",
                auto_add_margin=auto_margin
            )
            self._logger.info(f'[Set Auto Add Margin] for Long has been set to: {auto_margin}')
        except pybit.exceptions.InvalidRequestError as e:
            if e.status_code not in [130060]:  # 130060	autoAddMargin not changed
                self._logger.exception(e)
                raise e
        try:
            auto_margin = False
            res = self.session_auth.set_auto_add_margin(
                symbol=pair,
                side="Sell",
                auto_add_margin=auto_margin
            )
            self._logger.info(f'[Set Auto Add Margin] for Short has been set to: {auto_margin}')
        except pybit.exceptions.InvalidRequestError as e:
            if e.status_code not in [130060]:  # 130060	autoAddMargin not changed
                self._logger.exception(e)
                raise e

        # 3. Cross/Isolated Margin Switch
        # Switch Cross/Isolated; must set leverage value when switching from Cross to Isolated
        try:
            is_isolated = True
            buy_l = 1
            sell_l = 1
            res = self.session_auth.cross_isolated_margin_switch(
                symbol=pair,
                is_isolated=is_isolated,
                buy_leverage=buy_l,
                sell_leverage=sell_l
            )
            self._logger.info(f'[Isolated Mode] has been set to: {is_isolated}')
            self._logger.info(f'[Buy Leverage] has been set to: {buy_l}x')
            self._logger.info(f'[Sell Leverage] has been set to: {sell_l}x')
        except pybit.exceptions.InvalidRequestError as e:
            if e.status_code not in [130056]:  # 130056	Isolated not modified
                self._logger.exception(e)
                raise e

        # 4. Full/Partial Position TP/SL Mode Switch
        """
            When the tp_sl_mode is not changed because it is already at the value we want to set it too, 
            Bybit returns "130150": "Please try again later." instead of "same tp sl mode" error code 
            like in (1, 2, 3) above. In this case we look at the message instead of the error code.
            * We also modified the pybit code to not do any retries when this happens. *
        """
        try:
            tp_sl_mode = 'Full'
            res = self.session_auth.full_partial_position_tp_sl_switch(
                symbol=pair,
                tp_sl_mode=tp_sl_mode  # Possible values: Full or Partial
            )
            self._logger.info(f'[Position TP/SL Mode] has been set to: {tp_sl_mode}')
        except pybit.exceptions.InvalidRequestError as e:
            if 'same tp sl mode' not in e.message:
                self._logger.exception(e)
                raise e
