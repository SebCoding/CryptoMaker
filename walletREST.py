"""
    Wallet data structure
"""
import logger
import arrow
from copy import deepcopy
from typing import NamedTuple, Dict, Any

from configuration import Configuration
from exchange.ExchangeREST import ExchangeREST


class Wallet(NamedTuple):
    currency: str
    free: float = 0.0
    used: float = 0.0
    total: float = 0.0

    def to_string(self) -> str:
        result = f'Wallet[{self.currency}] free: {self.free}, used: {self.used}, total: {self.total}'
        return result


class Wallets:
    def __init__(self, exchange: ExchangeREST) -> None:
        self.logger = logger.init_custom_logger(__name__)
        self._config = Configuration.get_config()
        self._exchange = exchange
        self._wallets: Dict[str, Wallet] = {}
        self._last_wallet_refresh = 0
        self.update()

    def get_free(self, currency: str) -> float:
        balance = self._wallets.get(currency)
        if balance and balance.free:
            return balance.free
        else:
            return 0

    def get_used(self, currency: str) -> float:
        balance = self._wallets.get(currency)
        if balance and balance.used:
            return balance.used
        else:
            return 0

    def get_total(self, currency: str) -> float:
        balance = self._wallets.get(currency)
        if balance and balance.total:
            return balance.total
        else:
            return 0

    def _update_live(self) -> None:
        balances = self._exchange.get_balances()

        for currency in balances:
            if isinstance(balances[currency], dict):
                self._wallets[currency] = Wallet(
                    currency,
                    balances[currency].get('free', None),
                    balances[currency].get('used', None),
                    balances[currency].get('total', None)
                )
        # Remove currencies no longer in get_balances output
        for currency in deepcopy(self._wallets):
            if currency not in balances:
                del self._wallets[currency]

    def update(self, require_update: bool = True) -> None:
        """
        Updates wallets from the configured version.
        By default, updates from the exchange.
        Update-skipping should only be used for user-invoked /balance calls, since
        for trading operations, the latest balance is needed.
        :param require_update: Allow skipping an update if balances were recently refreshed
        """
        if require_update or (self._last_wallet_refresh + 3600 < arrow.utcnow().int_timestamp):
            self._update_live()
            self.logger.info('Wallets synced.')
            self._last_wallet_refresh = arrow.utcnow().int_timestamp

    def get_wallet(self, currency: str) -> Wallet:
        return self._wallets[currency]

    def get_all_balances(self) -> Dict[str, Any]:
        return self._wallets

    def get_available_stake_amount(self):
        """
        Return the total currently available balance in stake currency respecting tradable_balance_ratio.
        Calculated as: free amount * tradable_balance_ratio
        """
        available_amount = self.get_free(self._config['exchange']['stake_currency']) \
                           * self._config['trade']['tradable_balance_ratio']
        return available_amount
