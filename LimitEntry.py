from Orderbook import Orderbook


class LimitEntry:

    orderbook = Orderbook()

    # We do not place orders when the spread is greater than "spread_tolerance"
    spread_tolerance = 1.0

    # When we place an order the price = orderbook_top + "price_delta"
    price_delta = 0.5

    @classmethod
    def enter_trade(cls, side, tentative_entry_price, qty, stop_loss):
        pass