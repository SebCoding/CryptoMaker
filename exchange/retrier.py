"""
    To use these decorators:
     - from retrier import retrier, retrier_async
    Then add decorators like in the following examples:
    ---------------------------------------------------
    @retrier(retries=API_FETCH_ORDER_RETRY_COUNT)
    def fetch_order(...)
    ---------------------------------------------------
    @retrier
    def cancel_order(...)
    ---------------------------------------------------
     @retrier_async
     async def _async_fetch_trades(...)
"""
import asyncio
from functools import wraps
import time
import ccxt

import constants
import logger

logger = logger.init_custom_logger(__name__)


def calculate_backoff(retry_count, max_retries):
    """
    Calculate backoff
    """
    return (max_retries - retry_count) ** 2 + 1


def retrier_async(f):
    async def wrapper(*args, **kwargs):
        count = kwargs.pop('count', constants.API_RETRY_COUNT)
        try:
            return await f(*args, **kwargs)
        except ccxt.BaseError as ex:
            logger.warning('%s() returned exception: "%s"', f.__name__, ex)
            if count > 0:
                logger.warning('retrying %s() still for %s times', f.__name__, count)
                count -= 1
                kwargs.update({'count': count})
                if isinstance(ex, ccxt.DDoSProtection):
                    backoff_delay = calculate_backoff(count + 1, constants.API_RETRY_COUNT)
                    logger.info(f"Applying DDosProtection backoff delay: {backoff_delay}")
                    await asyncio.sleep(backoff_delay)
                return await wrapper(*args, **kwargs)
            else:
                logger.warning('Giving up retrying: %s()', f.__name__)
                raise ex

    return wrapper


def retrier(_func=None, retries=constants.API_RETRY_COUNT):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            count = kwargs.pop('count', retries)
            try:
                return f(*args, **kwargs)
            except ccxt.BaseError as ex:
                logger.warning('%s() returned exception: "%s"', f.__name__, ex)
                if count > 0:
                    logger.warning('retrying %s() still for %s times', f.__name__, count)
                    count -= 1
                    kwargs.update({'count': count})
                    if isinstance(ex, (ccxt.DDoSProtection, ccxt.OrderNotFound)):
                        # increasing backoff
                        backoff_delay = calculate_backoff(count + 1, retries)
                        logger.info(f"Applying DDosProtection backoff delay: {backoff_delay}")
                        time.sleep(backoff_delay)
                    return wrapper(*args, **kwargs)
                else:
                    logger.warning('Giving up retrying: %s()', f.__name__)
                    raise ex

        return wrapper

    # Support both @retrier and @retrier(retries=2) syntax
    if _func is None:
        return decorator
    else:
        return decorator(_func)
