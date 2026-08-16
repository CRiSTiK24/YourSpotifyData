import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable

from src.database import get_connection

from .exceptions import NotConnected


async def run_periodic(
    work: Callable[[sqlite3.Connection, int], Awaitable[None]],
    *,
    interval_seconds: float,
    logger: logging.Logger,
    connected_user_ids: Callable[[sqlite3.Connection], list[int]],
) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        con = get_connection()
        try:
            user_ids = connected_user_ids(con)
        finally:
            con.close()
        for user_id in user_ids:
            con = get_connection()
            try:
                await work(con, user_id)
            except NotConnected:
                pass
            except Exception:
                logger.exception("periodic task failed for user %d", user_id)
            finally:
                con.close()
