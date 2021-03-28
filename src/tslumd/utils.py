from loguru import logger
import functools
import inspect

def logger_catch(f):
    if inspect.iscoroutinefunction(f):
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            except Exception as exc:
                logger.exception(exc)
                # raise
    else:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except Exception as exc:
                logger.exception(exc)
                # raise
    return wrapper
