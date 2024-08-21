#!/usr/bin/env python3

import asyncio
import json
import logging

async def get_sse_messages(session, url):
    logging.info(f"process sse: {url}")
    async with session.get(url) as response:
        while True:
            if response.status != 200:
                c = (await response.content.read()).decode()
                raise Exception(c)
            chunk = await response.content.readuntil(b"\n\n")
            # print(f"chunk: {chunk}")
            some_data = chunk.strip().decode().lstrip("data: ")
            print(f"get_sse_messages data: {some_data}")
            yield some_data

async def get_serial_messages(reader):
    while True:
        chunk = await reader.readuntil(b'\n')
        yield chunk.strip().decode().lstrip("data: ")

async def trigger_events_from_sse(session, events, event, url):
    async for message in get_sse_messages(session, url):
        events.trigger(event, *json.loads(message))
