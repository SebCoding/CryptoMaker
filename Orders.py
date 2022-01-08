from Logger import Logger


class Orders:
    _orders_topic_name = 'order'
    _stop_orders_topic_name = 'stop_order'

    def __init__(self, exchange_ws):
        self.logger = Logger.get_module_logger(__name__)
        self._exchange_ws = exchange_ws
        self.update_orders()
        self.update_stop_orders()

    def update_orders(self):
        data = self._exchange_ws.private_ws.fetch(self._orders_topic_name)
        if data:
            pass
        # else:
        #     self.logger.debug("Websocket has no orders data available.")

    def update_stop_orders(self):
        data = self._exchange_ws.private_ws.fetch(self._stop_orders_topic_name)
        if data:
            pass
        # else:
        #     self.logger.debug("Websocket has no orders data available.")
