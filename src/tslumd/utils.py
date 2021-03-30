try:
    import loguru
    from loguru import logger
except ImportError: # pragma: no cover
    loguru = None
    import logging
    logger = logging.getLogger(__name__)
import functools
import inspect

if loguru is not None:
    logger_catch = logger.catch
else:
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
                    logger.error(f'Error in {f!r}', exc_info=True)
        return wrapper
