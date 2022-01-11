import sqlalchemy as sa
from sqlalchemy import Column, Table, Integer, Date, String, Float, DateTime, BigInteger, PrimaryKeyConstraint, Index

from Logger import Logger
from sqlalchemy_utils import database_exists

from Configuration import Configuration


class Database:
    URL_TEMPLATE = 'postgresql://<username>:<password>@<address>:<port>/<db_name>'

    # Table Names
    TRADE_SIGNALS_TBL_NAME = 'TradeSignals'
    ORDERS_TBL_NAME = 'Orders'

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.name = self._config['database']['db_name']
        self.db_url = self.get_db_url()
        self.validate_db()
        self._logger.info(f"Connection to {self.name} database successful.")
        self.engine = sa.create_engine(self.db_url)
        self.metadata = sa.MetaData(self.engine)
        self.init_tables()

    def get_db_url(self):
        url = self.URL_TEMPLATE.replace('<db_name>', self._config['database']['db_name'])
        url = url.replace('<address>', self._config['database']['address'])
        url = url.replace('<port>', str(self._config['database']['port']))
        url = url.replace('<username>', self._config['database']['username'])
        url = url.replace('<password>', self._config['database']['password'])
        return url

    def validate_db(self):
        if not database_exists(self.db_url):
            raise Exception(f'{self.db_url} database does not exists.')

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

    # Log trade signals to the db
    # def add_trade_signals_df(self, df):
    #     table_name = self.TRADE_SIGNALS
    #     df.to_sql(table_name, self.engine, index=False, if_exists='append')

    # Insert trade signals using a list of dictionary
    # Assuming the table exists
    def add_trade_signals_dict(self, dict_list):
        table = self.get_table(self.TRADE_SIGNALS_TBL_NAME)
        with self.engine.connect() as connection:
            connection.execute(table.insert(), dict_list)

    # Insert orders using a list of dictionary
    # Assuming the table exists
    def add_order_dict(self, dict_list):
        table = self.get_table(self.ORDERS_TBL_NAME)
        with self.engine.connect() as connection:
            connection.execute(table.insert(), dict_list)

    # Create tables if they don't exist
    def init_tables(self):
        self.init_trade_signals_table()
        self.init_orders_table()

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
                              Column('SignalOffset', Integer, nullable=False),
                              Column('EntryPrice', Float, nullable=False),
                              Column('EMA', Float, nullable=False),
                              Column('RSI', Float, nullable=False),
                              Column('ADX', Float, nullable=False),
                              Column('Notes', String)
                              )
                self.metadata.create_all()

    def init_orders_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.ORDERS_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.ORDERS_TBL_NAME, self.metadata,
                              Column('order_id', String, index=True, nullable=False),
                              Column('user_id', String, nullable=False),
                              Column('symbol', String, nullable=False),
                              Column('side', String, nullable=False),
                              Column('reason', String, nullable=False),
                              Column('order_type', String, nullable=False),
                              Column('price', Float, nullable=False),
                              Column('qty', Float, nullable=False),
                              Column('time_in_force', String, nullable=False),
                              Column('order_status', String, nullable=False),
                              Column('last_exec_price', Float, nullable=False),
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
