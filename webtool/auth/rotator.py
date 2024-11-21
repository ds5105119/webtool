import asyncio
import copy
import time


class Scheduler:
    def __init__(
        self,
        delay: int,
        func: callable,
        func_args: tuple | None = None,
        func_kwargs: dict | None = None,
        delay_func=asyncio.sleep,
    ):
        """
        Initialize a new scheduler instance.

        :param delay: Delay between function calls
        :param func: Function to be called periodically
        :param func_args: Positional arguments for the function
        :param func_kwargs: Keyword arguments for the function
        :param delay_func: Async function used for delaying (default: asyncio.sleep)
        """
        self._run = True
        self.func = func
        self.func_args = copy.deepcopy(func_args) if func_args else ()
        self.func_kwargs = copy.deepcopy(func_kwargs) if func_kwargs else {}
        self.delay = delay
        self.delay_func = delay_func
        self._task = None

    async def _wrapper(self):
        """Internal wrapper to run the function periodically with precise timing"""
        while self._run:
            try:
                start_time = time.monotonic()
                await self.func(*self.func_args, **self.func_kwargs)
                execution_time = time.monotonic() - start_time
                sleep_time = self.delay - execution_time
                await self.delay_func(sleep_time if sleep_time > 0 else 1)
            except asyncio.CancelledError:
                break

    def cancel(self):
        """Cancel the running scheduler"""
        self._run = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def run(self):
        """Start the scheduler"""
        self._task = asyncio.create_task(self._wrapper())
        return self._task
