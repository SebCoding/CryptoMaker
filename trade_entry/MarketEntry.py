

from trade_entry.TradeEntry import TradeEntry


class MarketEntry(TradeEntry):

    def __init__(self, database, exchange, wallet, orders, position):
        super().__init__(database, exchange, wallet, orders, position)
