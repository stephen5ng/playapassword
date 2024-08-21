#!/usr/bin/env python3

# From https://python-forum.io/thread-23029.html

import platform
if platform.system() != "Darwin":
    from rgbmatrix import graphics
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    from runtext import RunText
import aiohttp
import asyncio
import json
import logging
import os
from PIL import Image
import pygame
from pygame import Color
from pygame.image import tobytes as image_to_string
import pygame.freetype as ft
import random
import string
import sys
import time

from cube_async import get_sse_messages, trigger_events_from_sse
from pygameasync import Clock, EventEngine
from session import get as session_get

logger = logging.getLogger(__name__)

ch = logging.StreamHandler()
logging.basicConfig(filename="password.log")
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

events = EventEngine()

SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3

TICKS_PER_SECOND = 45

offscreen_canvas = None

game_name = "password"

def render_text(font, surface, text, color):
    words = text.split(' ')
    w, h = surface.get_size()
    line_spacing = font.get_sized_height() + 2
    x, y = 0, line_spacing
    space = font.get_rect(' ')

    for word in words:
        bounds = font.get_rect(word)
        if x + bounds.width + bounds.x >= w:
            x, y = 0, y + line_spacing
        font.render_to(surface, (x, y - bounds.y), None, color)
        x += bounds.width + space.width

    return y

class Title:
    LETTER_SIZE = 24

    def __init__(self, font, width, height):
        self.font = font
        self.surface = pygame.Surface((width, height))

    def draw(self):
        self.font.render_to(self.surface, (0, 0), game_name.upper(), "green", size=Title.LETTER_SIZE)

    def update(self, window, pos):
        window.blit(self.surface, pos)


class Answer:
    LETTER_SIZE = 22

    def __init__(self, font, width, height):
        self.font = font
        self.surface = pygame.Surface((width, height))
        self.answer = "ANSWER"

    def draw(self):
        self.surface.fill((0, 0, 0))
        _, r = self.font.render(self.answer, size=Answer.LETTER_SIZE)
        self.font.render_to(self.surface, (int((SCREEN_WIDTH - r.width)/2), 0), self.answer,
            fgcolor="red", size=Answer.LETTER_SIZE)

    def update(self, window, pos):
        window.blit(self.surface, pos)


class Instructions:
    LETTER_SIZE = 16

    def __init__(self, font, width, height):
        self.font = font
        self.surface = pygame.Surface((width, height))
        with open(f"{game_name}_instructions.txt", "r") as file:
            self.text = file.read().rstrip()

    def draw(self):
        self.font.size = Instructions.LETTER_SIZE
        self.height = render_text(self.font, self.surface, self.text,  "white")
        print(f"height {self.height}")

    def update(self, window, pos):
        pos = (pos[0], pos[1]-self.height)
        window.blit(self.surface, pos)

class Game:
    def __init__(self, session):
        self.all_words = []
        with open("./allwords.txt", 'r') as f:
            lines = f.readlines()
        self.all_words.extend([line.strip().upper() for line in lines])

        self._session = session
        events.on(f"game.push_start")(self.start)
        events.on(f"game.push_next_answer")(self.next_answer)
        events.on(f"game.push_shutdown")(self.shutdown)
        answer_font = pygame.freetype.Font(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "Courier New.ttf"))
        font = pygame.freetype.Font(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "DIN Alternate Bold.ttf"))
        self.title_display = Title(font, SCREEN_WIDTH, int(SCREEN_HEIGHT/10))
        self.instructions_display = Instructions(font, SCREEN_WIDTH, int(SCREEN_HEIGHT/2))
        self.answer_display = Answer(answer_font, SCREEN_WIDTH, int(SCREEN_HEIGHT/10))
        self.dirty = True

    def draw(self):
        print("drawing")
        self.answer_display.draw()
        self.dirty = True

    async def start(self):
        self.answers = list(self.all_words)
        random.shuffle(self.answers)

        self.answer_display.answer = self.answers.pop()
        self.title_display.draw()
        self.instructions_display.draw()
        self.draw()

    async def stop(self):
        return await session_get(self._session, "stop")

    async def update(self, window):
        if self.dirty:
            print("updating")
            self.instructions_display.update(window, (0, SCREEN_HEIGHT-5))
            self.title_display.update(window, (0, 0))
            self.answer_display.update(window, (0, SCREEN_HEIGHT/2 - 20))
            # self.instructions_display.update(window, (0, 0))
            self.dirty = False

    async def shutdown(self, shutdown_now):
        print(f"exiting: {shutdown_now}")
        if shutdown_now[0]:
            sys.exit(0)

    async def next_answer(self):
        self.answer_display.answer = self.answers.pop() if self.answers else "GAME OVER"
        self.draw()

async def main():
    global game_name
    start = True
    window = pygame.display.set_mode(
        (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    if platform.system() != "Darwin":
        run_text = RunText()
        run_text.process()
        game_name = run_text.args.game
        matrix = run_text.matrix
        offscreen_canvas = matrix.CreateFrameCanvas()

    clock = Clock()
    async with aiohttp.ClientSession(
        timeout = aiohttp.ClientTimeout(total=60*60*24*7)) as session:
        game = Game(session)
        tasks = []
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_start",
                "http://localhost:8080/push_start")))
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_next_answer",
                "http://localhost:8080/push_next_answer")))
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_shutdown",
                "http://localhost:8080/push_shutdown")))

        await game.start()
        game.draw()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    key = pygame.key.name(event.key).upper()
                    # logger.info(f"key: {key}")
                    if key == "SPACE":
                        await game.start()
                    elif key == "RETURN":
                        print(f"RETURN")
                        await game.next_answer()
                        game.draw()
            await game.update(screen)
            if platform.system() != "Darwin":
                pixels = image_to_string(screen, "RGB")
                img = Image.frombytes("RGB", (screen.get_width(), screen.get_height()), pixels)
                img = img.rotate(-90, Image.NEAREST, expand=1)
                offscreen_canvas.SetImage(img)
                matrix.SwapOnVSync(offscreen_canvas)
            window.blit(pygame.transform.scale(screen, window.get_rect().size), (0, 0))
            pygame.display.flip()
            await clock.tick(TICKS_PER_SECOND)

        for t in tasks:
            t.cancel()

if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    if len(sys.argv) > 1:
        game_name = sys.argv[1]
    pygame.mixer.init(22050)
    logger.info("pygame.init()")
    pygame.init()
    pygame.freetype.init()
    logger.info("pygame.init() done")
    asyncio.run(main())
    pygame.quit()
