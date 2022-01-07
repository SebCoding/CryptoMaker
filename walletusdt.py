"""
    Wallet for USDT perpetual futures only.
    Using websockets private topic ['wallet']
"""
import logger


class WalletUSDT:
    _wallet_topic_name = 'wallet'

    def __init__(self, exchange_ws):
        self.logger = logger.init_custom_logger(__name__)
        self._wallet_balance = 0.0
        self._available_balance = 0.0
        self._exchange_ws = exchange_ws
        self.update_wallet()

    def update_wallet(self):
        data = self._exchange_ws.private_ws.fetch(self._wallet_topic_name)
        if data:
            self._wallet_balance = data['wallet_balance']
            self._available_balance = data['available_balance']
        # else:
        #     self.logger.debug("Websocket has no wallet data available.")

    def get_wallet_balance(self):
        self.update_wallet()
        return self._wallet_balance

    def get_available_balance(self):
        self.update_wallet()
        return self._available_balance

    wallet_balance = property(get_wallet_balance)
    available_balance = property(get_available_balance)
