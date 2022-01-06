import sqlalchemy as sa
from sqlalchemy import Column, Table, Integer, Date, String, Float, DateTime, BigInteger, PrimaryKeyConstraint, Index

import logger
from sqlalchemy_utils import database_exists

from configuration import Configuration

logger = logger.init_custom_logger(__name__)


class Database:
    URL_TEMPLATE = 'postgresql://<username>:<password>@<address>:<port>/<db_name>'

    # Table Names
    TRADE_ENTRIES_TBL_NAME = 'TradeEntries'

    def __init__(self):
        self.config = Configuration.get_config()
        self.name = self.config['database']['db_name']
        self.db_url = self.get_db_url()
        self.validate_db_url()
        self.engine = sa.create_engine(self.db_url)
        self.metadata = sa.MetaData(self.engine)
        self.init_tables()

    def get_db_url(self):
        url = self.URL_TEMPLATE.replace('<db_name>', self.config['database']['db_name'])
        url = url.replace('<address>', self.config['database']['address'])
        url = url.replace('<port>', str(self.config['database']['port']))
        url = url.replace('<username>', self.config['database']['username'])
        url = url.replace('<password>', self.config['database']['password'])
        return url

    def validate_db_url(self):
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
                    logger.info(f'SQL Query Result: {row}')

    # Log trade entries to the db
    # def add_trade_entries_df(self, df):
    #     table_name = self.TRADE_ENTRIES
    #     df.to_sql(table_name, self.engine, index=False, if_exists='append')

    # Insert trade entries using a list of dictionary
    # Assuming the table exists
    def add_trade_entries_dict(self, dict_list):
        table = self.get_table(self.TRADE_ENTRIES_TBL_NAME)
        with self.engine.connect() as connection:
            connection.execute(table.insert(), dict_list)

    # Create tables if they don't exist
    def init_tables(self):
        self.init_trade_entries_table()

    def init_trade_entries_table(self):
        with self.engine.connect() as connection:
            if not self.engine.has_table(connection, self.TRADE_ENTRIES_TBL_NAME):
                # Create a table with the appropriate Columns
                table = Table(self.TRADE_ENTRIES_TBL_NAME, self.metadata,
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
