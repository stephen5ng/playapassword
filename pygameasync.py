from aiohttp import web
import asyncio
import logging
import pygame

class Clock:
    def __init__(self, time_func=pygame.time.get_ticks):
        self.time_func = time_func
        self.last_tick = time_func() or 0

    async def tick(self, fps=0):
        if 0 >= fps:
            return

        end_time = (1.0 / fps) * 1000
        current = self.time_func()
        time_diff = current - self.last_tick
        delay = (end_time - time_diff) / 1000

        self.last_tick = current
        if delay < 0:
            delay = 0

        await asyncio.sleep(delay)

class EventEngine:
    def __init__(self):
        self.listeners = {}

    def on(self, event):
        if event not in self.listeners:
            self.listeners[event] = []

        def wrapper(func, *args):
            self.listeners[event].append(func)
            return func

        return wrapper

    # this function is purposefully not async
    # code calling this will do so in a "fire-and-forget" manner, and shouldn't be
    # slowed down by needing to await a result
    def trigger(self, event, *args, **kwargs):
        print(f"eventengine trigger {event}, {args}")
        asyncio.create_task(self.async_trigger(event, *args, **kwargs))

    # whatever gets triggered is just added to the current asyncio event loop,
    # which we then trust to run eventually
    async def async_trigger(self, event, *args, **kwargs):
        logging.info(f"async_trigger: {event}, {self.listeners}")
        print(f"async_trigger: {event}, {self.listeners}")
        if event in self.listeners:
            print(f"in list: {event}")
            handlers = [func(*args, **kwargs) for func in self.listeners[event]]
            print(f"handlers: {handlers}")
            # schedule all listeners to run
            return await asyncio.gather(*handlers)
        else:
            raise Exception(f"async_trigger: no event {event} in {self.listeners}")


class WebFrontend:
    def __init__(self, port=8081):
        self.port = port
        self.runner = None
        self.app = web.Application()

    async def startup(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "localhost", self.port)
        await site.start()

    async def shutdown(self):
        if self.runner:
            await self.runner.cleanup()
