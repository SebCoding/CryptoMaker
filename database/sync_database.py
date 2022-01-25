import sys

from database.Database import Database
from exchange.ExchangeBybit import ExchangeBybit

"""
    For this code to run properly in PyCharm you need to set your 'Working Directory' 
    to the main folder of CryptoMaker in your Run Configuration at the top right of the window.
"""

PAIR = 'ETHUSDT'


def main():
    exchange = ExchangeBybit()
    db = Database(exchange)
    pair = PAIR if len(sys.argv) <= 1 else sys.argv[1]
    db.sync_all_tables(pair)


if __name__ == '__main__':
    main()
