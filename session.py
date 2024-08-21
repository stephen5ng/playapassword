import logging

logger = logging.getLogger(__name__)

base_url = "http://localhost:8080/"

class SafeSession:
    def __init__(self, original_context_manager):
        self.original_context_manager = original_context_manager

    async def __aenter__(self):
        response = await self.original_context_manager.__aenter__()
        if response.status != 200:
            c = (await response.content.read()).decode()
            logger.error(c)
            raise Exception(f"Bad response: {c}")
        return response

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.original_context_manager.__aexit__(exc_type, exc_value, traceback)

async def get(session, url, params={}):
    async with SafeSession(session.get(base_url + url, params=params)) as response:
        return (await response.content.read()).decode()
