from datetime import time
import datetime as dt

import pandas as pd

import constants
from database.Database import Database
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger

logger = Logger.get_module_logger(__name__)


# Sync all Closed P&L entries for this pair found on Bybit with the ClosedPnL table stored locally
# Start timestamp point for result, in seconds
# End timestamp point for result, in seconds
def sync_closed_pnl(pair, start_time, end_time):
    db = Database()
    exchange = ExchangeBybit()
    list_records = []
    page = 1
    while True:
        result = exchange._get_closed_profit_and_loss(pair, start_time, end_time, page=page)
        if result['data']:
            list_records = list_records + result['data']
            page += 1
        else:
            break

    # Convert created_at timestamp to datetime string
    df = pd.DataFrame(list_records)
    df['created_at'] = [dt.datetime.fromtimestamp(x).strftime(constants.DATETIME_FMT) for x in df.created_at]
    df.sort_values(by=['id'])
    dict_list = df.to_dict('records')

    db.add_closed_pnl_dict(dict_list)


start_time = dt.datetime(2000, 1, 1).timestamp()
end_time = dt.datetime(2023, 1, 1).timestamp()

sync_closed_pnl('BTCUSDT', start_time, end_time)
