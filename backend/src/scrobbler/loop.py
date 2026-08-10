import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable

from src.database import get_connection

from .exceptions import NotConnected


# Kept separate from service.py: service.py needs run_periodic, and run_periodic
# would need service.get_status to gate each tick if it lived there instead of
# taking require_connected as a callback — importing service.py back into itself
# via this module would be a circular import. Do not merge back.
async def run_periodic(
    work: Callable[[sqlite3.Connection], Awaitable[None]],
    *,
    interval_seconds: float,
    logger: logging.Logger,
    require_connected: Callable[[sqlite3.Connection], bool],
) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        con = get_connection()
        try:
            if require_connected(con):
                await work(con)
        except NotConnected:
            pass
        except Exception:
            logger.exception("periodic task failed")
        finally:
            con.close()
