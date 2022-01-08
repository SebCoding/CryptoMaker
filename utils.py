import constants
import datetime as dt
from Logger import Logger

_logger = Logger.get_module_logger(__name__)


# Offsets the 'from_time' backwards from 'nb_candles' in the specified timeframe (interval).
# The offset can backward or forward in time
# Assumes 'from_time' is in seconds
def adjust_from_time_timestamp(from_time, interval, nb_candles, backward=True):
    if interval not in constants.VALID_INTERVALS:
        msg = f'Invalid interval value: {interval}'
        _logger.error(msg)
        raise Exception(msg)
    if backward:
        nb_candles = nb_candles * -1
    if 'm' in interval:
        from_time += (nb_candles * 60)
    elif 'h' in interval:
        from_time += (nb_candles * 3600)  # 60*60 = 3600
    elif 'd' in interval:
        from_time += (nb_candles * 86400)  # 24*60*60 = 86400
    elif 'w' in interval:
        from_time += (nb_candles * 604800)  # 7*24*60*60 = 604800
    return from_time


# Adjust from_time to include prior X entries for that interval
# 'from_time' must be a datetime object
def adjust_from_time_datetime(from_time, interval, include_prior):
    if interval not in constants.VALID_INTERVALS:
        msg = f'Invalid interval value: {interval}'
        _logger.error(msg)
        raise Exception(msg)

    delta = include_prior - 1
    if 'm' in interval:
        interval = interval.replace('m', '')
        from_time = from_time - dt.timedelta(minutes=int(interval) * delta)
    elif 'h' in interval:
        interval = interval.replace('h', '')
        from_time = from_time - dt.timedelta(hours=int(interval) * delta)
    elif 'd' in interval:
        from_time = from_time - dt.timedelta(days=delta)
    elif 'w' in interval:
        from_time = from_time - dt.timedelta(weeks=delta)
    return from_time

