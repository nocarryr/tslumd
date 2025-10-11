try:
    import loguru               # type: ignore[missing-import]
    from loguru import logger   # type: ignore[missing-import]
except ImportError:             # pragma: no cover
    loguru = None
    import logging
    logger = logging.getLogger(__name__)
import functools
import inspect

if loguru is not None:
    logger_catch = logger.catch # type: ignore[assignment]
else:
    def logger_catch(f):
        if inspect.iscoroutinefunction(f):
            @functools.wraps(f)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await f(*args, **kwargs)
                except Exception as exc:
                    logger.exception(exc)
                    # raise
            return async_wrapper

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except Exception as exc:
                logger.error(f'Error in {f!r}', exc_info=True)
        return wrapper
