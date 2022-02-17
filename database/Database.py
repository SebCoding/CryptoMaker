import sys

import pandas as pd
import sqlalchemy as sa
import arrow
from sqlalchemy import Column, Table, Integer, String, Float, DateTime, BigInteger
import datetime as dt

import constants
from enums.BybitEnums import OrderStatus
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger
from sqlalchemy_utils import database_exists
from sqlalchemy.engine.reflection import Inspector
from Configuration import Configuration


class Database:
    """
        TODO: Replace all => self.engine.has_table(connection, table_name)
              by => self.inspector.has_table(table_name, schema='public')
    """
    URL_TEMPLATE = 'postgresql://<username>:<password>@<address>:<port>/<db_name>'

    # Table Names
    TRADE_SIGNALS_TBL_NAME = 'TradeSignals'
    ORDERS_TBL_NAME = 'Orders'
    CLOSED_PNL_TBL_NAME = 'ClosedPnL'
    USER_TRADES_TBL_NAME = 'UserTrades'
    COND_ORDERS_TBL_NAME = 'CondOrders'

    def __init__(self, exchange):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._exchange = exchange
        self.name = self._config['database']['db_name']
        self.confirm_db_name()
        self.db_url = self.get_db_url()
        self.validate_db()
        self._logger.info(f"Connection to {self.name} database successful.")
        self.engine = sa.create_engine(self.db_url)
        self.inspector = Inspector.from_engine(self.engine)
        self.metadata = sa.MetaData(self.engine)
        self.init_tables()

    def confirm_db_name(self):
        # Switch to test database if user forgot to change it
        if self._config['exchange']['testnet'] and 'test' not in self.name.lower():
            while True:
                self._logger.info(f'You are running on Testnet. The db_name does not appear to be the test database.')
                answer = input(f'Please confirm that you wish to continue with db_name={self.name} (y/n): ')
                if answer in ['y', 'n']:
                    break
            if answer == 'n':
                self._logger.error(f'Please update the config.json with the correct db_name.')
                sys.exit(0)

    def get_db_url(self):
        url = self.URL_TEMPLATE.replace('<db_name>', self.name)
        url = url.replace('<address>', self._config['database']['address'])
        url = url.replace('<port>', str(self._config['database']['port']))
        url = url.replace('<username>', self._config['database']['username'])
        url = url.replace('<password>', self._config['database']['password'])
        return url

    def validate_db(self):
        if not database_exists(self.db_url):
            msg = f'{self.db_url} database does not exists.'
            raise Exception(msg)

    # Get table object by table name.
    def get_table(self, table_name):
        table = sa.Table(table_name, self.metadata, autoload=True, autoload_with=self.engine)
        return table

    # Execute a SQL query on the database
    def exec_sql_query(self, query):
        with self.engine.connect() as connection:
            result = connection.execute(query)
            if result.rowcount > 0:
                for row in result:
                    self._logger.info(f'SQL Query Result: {row}')

    def table_name_exists(self, name):
        return self.inspector.has_table(name, schema='public')

    # Create tables if they don't exist
    def init_tables(self):
        self.init_trade_signals_table()
        self.init_orders_table()
        self.init_closed_pnl_table()
        self.init_user_trades_table()
        self.init_conditional_orders_table()

    def sync_all_tables(self, pairs):
        for pair in pairs:
            self.sync_all_order_records(pair)
            self.sync_all_closed_pnl_records(pair)
            self.sync_all_user_trade_records(pair)
            self.sync_all_conditional_order_records(pair)

    """
        -----------------------------------------------------------------------------
           Trade Signals
        -----------------------------------------------------------------------------
    """

    def init_trade_signals_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.TRADE_SIGNALS_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.TRADE_SIGNALS_TBL_NAME, self.metadata,
                              Column('IdTimestamp', BigInteger, index=True, nullable=False),
                              Column('DateTime', DateTime, index=True, nullable=False),
                              Column('Pair', String, nullable=False),
                              Column('Interval', String, nullable=False),
                              Column('Signal', String, nullable=False),
                              Column('Side', String, nullable=False),
                              Column('EntryPrice', Float, nullable=False),
                              Column('IndicatorValues', String),
                              Column('Details', String)
                              )
                self.metadata.create_all()

    # Insert trade signals using a list of dictionary
    # Assuming the table exists
    def add_trade_signals_dict(self, dict_list):
        table = self.get_table(self.TRADE_SIGNALS_TBL_NAME)
        with self.engine.connect() as connection:
            connection.execute(table.insert(), dict_list)

    """
        -----------------------------------------------------------------------------
           Orders
        -----------------------------------------------------------------------------
    """
    def init_orders_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.ORDERS_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.ORDERS_TBL_NAME, self.metadata,
                              Column('order_id', String, index=True, nullable=False, primary_key=True),
                              Column('user_id', String, nullable=False),
                              Column('symbol', String, nullable=False),
                              Column('side', String, nullable=False),
                              # Column('reason', String),
                              Column('order_type', String, nullable=False),
                              Column('price', Float, nullable=False),
                              Column('qty', Float, nullable=False),
                              Column('time_in_force', String, nullable=False),
                              Column('order_status', String, nullable=False),
                              Column('take_profit', Float),
                              Column('stop_loss', Float),
                              Column('last_exec_price', Float),
                              Column('cum_exec_qty', Float),
                              Column('cum_exec_value', Float),
                              Column('cum_exec_fee', Float),
                              Column('order_link_id', String),
                              Column('reduce_only', String, nullable=False),
                              Column('close_on_trigger', String, nullable=False),
                              Column('created_time', DateTime, index=True, nullable=False),
                              Column('updated_time', DateTime, index=True, nullable=False)
                              )
                self.metadata.create_all()

    # Insert orders using a list of dictionary
    # Assuming the table exists
    def add_order_dict(self, dict_list):
        table = self.get_table(self.ORDERS_TBL_NAME)
        with self.engine.connect() as connection:
            connection.execute(table.insert(), dict_list)

    def update_order_stop_loss_by_id(self, order_id, new_stop_loss):
        table = self.get_table(self.ORDERS_TBL_NAME)
        update_statement = table.update().where(table.c.order_id == order_id).values(stop_loss=new_stop_loss)
        with self.engine.connect() as connection:
            connection.execute(update_statement)

    def sync_all_order_records(self, pair):
        self._logger.info(f'Syncing all Order records.')
        table = self.get_table(self.ORDERS_TBL_NAME)
        dict_list = self._exchange.get_all_order_records(pair)
        if dict_list:
            records_df = pd.DataFrame(dict_list)

            with self.engine.connect() as connection:
                # Delete all rows in the table that do not have a status of Filled or Cancelled
                # These orders might have an updated version so we re-insert
                connection.execute(table.delete().where(
                    table.c.symbol == pair and
                    table.c.order_status not in [OrderStatus.Filled, OrderStatus.Cancelled])
                )

                # Get list of PK (order_id) in the table to not insert already existing rows
                query = f'SELECT "order_id" FROM public."{self.ORDERS_TBL_NAME}"'
                existing_ids_list = pd.read_sql(query, connection)['order_id'].tolist()

                # Delete rows that already exist in the db
                df = records_df[~records_df['order_id'].isin(existing_ids_list)]

                if len(df) > 0:
                    connection.execute(table.insert(), df.to_dict('records'))

    """
        -----------------------------------------------------------------------------
           Closed P&L
        -----------------------------------------------------------------------------
    """
    def init_closed_pnl_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.CLOSED_PNL_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.CLOSED_PNL_TBL_NAME, self.metadata,
                              Column('id', Integer, index=True, nullable=False, primary_key=True),
                              Column('user_id', Integer, index=True, nullable=False),
                              Column('symbol', String, nullable=False),
                              Column('order_id', String, index=True, nullable=False),
                              Column('side', String, nullable=False),
                              Column('qty', Float, nullable=False),
                              Column('order_price', Float, nullable=False),
                              Column('order_type', String, nullable=False),
                              Column('exec_type', String, nullable=False),
                              Column('closed_size', Float, nullable=False),
                              # Closed position value
                              Column('cum_entry_value', Float, nullable=False),
                              # Average entry price
                              Column('avg_entry_price', Float, nullable=False),
                              # Cumulative trading value of position closing orders
                              Column('cum_exit_value', Float, nullable=False),
                              # Average exit price
                              Column('avg_exit_price', Float, nullable=False),
                              # Closed Profit and Loss
                              Column('closed_pnl', Float, nullable=False),
                              # The number of fills in a single order
                              Column('fill_count', Integer, nullable=False),
                              Column('leverage', Float, nullable=False),
                              Column('created_at', DateTime, index=True, nullable=False)
                              )
                self.metadata.create_all()

    # Sync all Closed P&L entries for this pair found on Bybit
    # Insert Closed P&L contained in a list of dictionaries
    # Assuming the table exists, inserting only none existing entries
    def sync_all_closed_pnl_records(self, pair):
        self._logger.info(f'Syncing all Closed P&L records.')
        table = self.get_table(self.CLOSED_PNL_TBL_NAME)
        dict_list = self._exchange.get_all_closed_pnl_records(pair)
        if dict_list:
            records_df = pd.DataFrame(dict_list)

            # Delete all rows in the table
            # with self.engine.connect() as connection:
            #     connection.execute(table.delete())

            # Get list of PK (Id) in the table to not insert already existing rows
            query = f'SELECT "id" FROM public."{self.CLOSED_PNL_TBL_NAME}"'
            with self.engine.connect() as connection:
                existing_ids_list = pd.read_sql(query, connection)['id'].tolist()

                # Delete rows that already exist in the db
                df = records_df[~records_df['id'].isin(existing_ids_list)]

                if len(df) > 0:
                    connection.execute(table.insert(), df.to_dict('records'))

    """
        -----------------------------------------------------------------------------
           User Trades
        -----------------------------------------------------------------------------
    """
    def init_user_trades_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.USER_TRADES_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.USER_TRADES_TBL_NAME, self.metadata,
                              Column('exec_id', String, nullable=False, index=True),
                              Column('order_id', String, index=True, nullable=False),
                              # Column('order_link_id', String),
                              Column('side', String, nullable=False),
                              Column('symbol', String, nullable=False),
                              # Column('price', Float),  # Abandoned!!
                              Column('order_price', Float, nullable=False),
                              Column('order_qty', Float, nullable=False),
                              Column('order_type', String, nullable=False),  # OrderType Enum
                              Column('fee_rate', Float),
                              Column('exec_price', Float),
                              Column('exec_type', String, nullable=False),  # ExecType Enum
                              Column('exec_qty', Float, nullable=False),
                              Column('exec_fee', Float, nullable=False),
                              Column('exec_value', Float, nullable=False),
                              Column('leaves_qty', Float),
                              # The corresponding closing size of the closing order
                              Column('closed_size', Float),
                              # Liquidity Enum, only valid while exec_type is Trade, AdlTrade, BustTrade
                              Column('last_liquidity_ind', String),
                              # Column('trade_time', DateTime, index=True, nullable=False),
                              Column('trade_time_ms', DateTime, index=True, nullable=False)
                              )
                self.metadata.create_all()

    def sync_all_user_trade_records(self, pair):
        self._logger.info(f'Syncing all User Trade records.')
        table = self.get_table(self.USER_TRADES_TBL_NAME)
        dict_list = self._exchange.get_user_trades_records(pair)
        if dict_list:
            to_insert_df = pd.DataFrame(dict_list)
            to_insert_df = to_insert_df.drop(['order_link_id', 'price', 'trade_time'], axis=1)

            # records_df.sort_values(['order_id'], inplace=True)
            # print(records_df.to_string()); exit(1)

            # Get list of PK exec_id in the table to not re-insert (already existing rows)
            query = f'SELECT "exec_id" FROM public."{self.USER_TRADES_TBL_NAME}"'
            with self.engine.connect() as connection:
                existing_ids_list = pd.read_sql(query, connection)['exec_id'].tolist()

                # Delete rows that already exist in the db
                df = to_insert_df[~to_insert_df['exec_id'].isin(existing_ids_list)]

                if len(df) > 0:
                    connection.execute(table.insert(), df.to_dict('records'))

    """
        -----------------------------------------------------------------------------
           Stop Orders (Conditionals)
        -----------------------------------------------------------------------------
    """
    def init_conditional_orders_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.COND_ORDERS_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.COND_ORDERS_TBL_NAME, self.metadata,
                              Column('stop_order_id', String, index=True, nullable=False, primary_key=True),
                              Column('user_id', String, nullable=False),
                              Column('symbol', String, nullable=False),
                              Column('side', String, nullable=False),
                              Column('order_type', String, nullable=False),
                              Column('price', Float, nullable=False),
                              Column('qty', Float, nullable=False),
                              Column('time_in_force', String, nullable=False),
                              Column('order_status', String, nullable=False),
                              Column('trigger_price', Float, nullable=False),
                              Column('order_link_id', String),
                              Column('created_time', DateTime, index=True, nullable=False),
                              Column('updated_time', DateTime, index=True, nullable=False),
                              Column('take_profit', Float),
                              Column('stop_loss', Float),
                              Column('tp_trigger_by', String),
                              Column('sl_trigger_by', String),
                              Column('base_price', Float),
                              Column('trigger_by', String),
                              Column('reduce_only', String, nullable=False),
                              Column('close_on_trigger', String, nullable=False),
                              )
                self.metadata.create_all()

    def sync_all_conditional_order_records(self, pair):
        self._logger.info(f'Syncing all Conditional Order records.')
        table = self.get_table(self.COND_ORDERS_TBL_NAME)
        dict_list = self._exchange.get_all_conditional_order_records(pair)
        if dict_list:
            records_df = pd.DataFrame(dict_list)

            with self.engine.connect() as connection:
                # Delete all rows in the table that do not have a status of Filled or Cancelled
                # These orders might have an updated version so we re-insert
                connection.execute(table.delete().where(
                    table.c.symbol == pair and
                    table.c.order_status not in [OrderStatus.Filled, OrderStatus.Cancelled])
                )

                # Get list of PK (order_id) in the table to not insert already existing rows
                query = f'SELECT "stop_order_id" FROM public."{self.COND_ORDERS_TBL_NAME}"'
                existing_ids_list = pd.read_sql(query, connection)['stop_order_id'].tolist()

                # Delete rows that already exist in the db
                df = records_df[~records_df['stop_order_id'].isin(existing_ids_list)]

                if len(df) > 0:
                    connection.execute(table.insert(), df.to_dict('records'))