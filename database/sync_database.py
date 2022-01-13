from database.Database import Database
from exchange.ExchangeBybit import ExchangeBybit

PAIR = 'BTCUSDT'


def main():
    exchange = ExchangeBybit()
    db = Database(exchange)
    db.sync_all_tables(PAIR)


"""
    For this code to run properly in PyCharm you need to set your 'Working Directory' 
    to the main folder of CryptoMaker in your Run Configuration at the top right of the window.
"""

if __name__ == '__main__':
    main()
