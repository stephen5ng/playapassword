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
from PIL import Image
import pygame
from pygame import Color
from pygame.image import tobytes as image_to_string
import string
import sys
import time

from cube_async import get_sse_messages, trigger_events_from_sse
from pygameasync import Clock, EventEngine
from session import get as session_get

logger = logging.getLogger(__name__)

ch = logging.StreamHandler()
logging.basicConfig(filename="wordle.log")
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

events = EventEngine()

SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3

TICKS_PER_SECOND = 45

FONT = "Courier"
ANTIALIAS = 1

offscreen_canvas = None

class UsedLetters:
    USED_COLORS = [Color(c) for c in ["grey", "red", "yellow", "green"]]
    USED_LETTER_SIZE = 18

    def __init__(self, width, height):
        self.font = pygame.font.SysFont(FONT, UsedLetters.USED_LETTER_SIZE)
        self.surface = pygame.Surface((width, height))
        one_letter = self.font.render("Q", ANTIALIAS, Color("white"))
        self.letter_width, self.letter_height = one_letter.get_bounding_rect().size
        self.top_margin = one_letter.get_bounding_rect().top
        self.left_margin = (width - 13*self.letter_width)/2

    def draw(self, used_letters):
        for i, letter in enumerate(string.ascii_uppercase):
            color = UsedLetters.USED_COLORS[used_letters[letter]]
            rendered_letter = self.font.render(letter, ANTIALIAS, color)
            pos = (self.left_margin+self.letter_width*(i - (0 if i<13 else 13)),
                  (-self.top_margin if i < 13 else -self.top_margin + self.letter_height))
            self.surface.blit(rendered_letter, pos)

    def update(self, window, pos):
        window.blit(self.surface, pos)


class Guesses:
    LETTER_SIZE = 50
    COLORS = [Color(c) for c in ["white", "white", "yellow", "green"]]

    def __init__(self):
        self.font = pygame.font.SysFont(FONT, Guesses.LETTER_SIZE)
        one_letter = self.font.render("Q", ANTIALIAS, Color("white"))
        self.letter_width, self.letter_height = one_letter.get_bounding_rect().size
        logger.info(f"pre letter dimensions: {(self.letter_width, self.letter_height)}")
        self.letter_width = int(1.3 * self.letter_width)
        self.letter_height = int(1.05 * self.letter_height)
        logger.info(f"letter dimensions: {(self.letter_width, self.letter_height)}")

    def draw(self, current_guess, guesses, colors):
        print(f"drawing: {current_guess}, {guesses}, {colors}")
        self.surface = pygame.Surface((self.letter_width*Game.WORDLE_LENGTH, SCREEN_HEIGHT))

        for prev_guess_ix, prev_guess in enumerate(guesses):
            for i in range(len(prev_guess)):
                letter = self.font.render(prev_guess[i], ANTIALIAS,
                    Guesses.COLORS[self.colors[prev_guess_ix][i]])
                offset = (self.letter_width - letter.get_rect().width) / 2
                print(f"this size: {prev_guess[i]}: {letter.get_rect().size}, offset: {offset}")
                self.surface.blit(letter, (i*self.letter_width, prev_guess_ix * self.letter_height))

        for i in range(len(current_guess)):
            letter = self.font.render(current_guess[i], ANTIALIAS, Color("white"))
            pos = (i*self.letter_width, len(guesses)*self.letter_height)
            self.surface.blit(letter, pos)

        self.pos = ((SCREEN_WIDTH/2 - (self.letter_width*Game.WORDLE_LENGTH)/2), 0)
        logger.info(f"draw pos: {self.pos}")

    def update(self, window):
        print(f"updating: {self.pos}")
        window.blit(self.surface, self.pos)

class Game:
    WORDLE_LENGTH = 5
    def __init__(self, session):
        self._session = session
        self.used_letters_height = int(SCREEN_HEIGHT/10)
        self.guesses_object = Guesses()
        self.used_letters_object = UsedLetters(SCREEN_WIDTH, self.used_letters_height)

        events.on(f"game.guesses_and_colors")(self.guesses_and_colors)
        events.on(f"game.push_start")(self.start)
        events.on(f"game.push_current_letter")(self.push_letter)
        events.on(f"game.push_guess_current")(self.guess_current_word)
        events.on(f"game.push_shutdown")(self.shutdown)

    def draw(self):
        self.guesses_object.draw(self.current_guess, self.guesses, self.colors)
        self.used_letters_object.draw(self.used_letters)

    async def guesses_and_colors(self, guesses, colors, used_letters):
        if not guesses:
            return
        print(f"Game.guesses_and_colors {guesses}, {colors}, {used_letters}")
        self.guesses = guesses
        self.colors = colors
        self.used_letters = used_letters
        logger.info(f"guess() guesses: {self.guesses}, {len(self.guesses)}")
        self.current_guess = ""
        self.draw()

    async def start(self):
        self.current_guess = ""
        self.guesses = []
        self.used_letters = {c: 0 for c in string.ascii_uppercase}
        self.colors = []
        self.draw()
        return await session_get(self._session, "start_back_end")

    async def stop(self):
        return await session_get(self._session, "stop")

    async def update(self, window):
        self.guesses_object.update(window)
        self.used_letters_object.update(window,
            (0, int(SCREEN_HEIGHT - self.used_letters_height)))

    async def push_letter(self, letter):
        return await self.enter_letter(letter[0])

    async def shutdown(self, shutdown_now):
        print(f"exiting: {shutdown_now}")
        if shutdown_now[0]:
            sys.exit(0)

    async def enter_letter(self, letter):
        print(f"enter_letter: {letter}")

        if letter == "-":
            self.current_guess = self.current_guess[:-1]
        elif len(self.current_guess) < Game.WORDLE_LENGTH:
            print(f"current guess b4: '{self.current_guess}', '{letter}'")
            self.current_guess += letter
            print(f"current guess: '{self.current_guess}'")
        self.draw()

    async def guess_current_word(self):
        await session_get(self._session, "word", {"guess": self.current_guess})

    def delete_letter(self):
        self.current_guess = self.current_guess[:-1]
        self.guesses_object.draw(self.current_guess, self.guesses, self.colors)

async def main():
    start = True
    window = pygame.display.set_mode(
        (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    if platform.system() != "Darwin":
        run_text = RunText()
        run_text.process()

        matrix = run_text.matrix
        offscreen_canvas = matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("7x13.bdf")
        textColor = graphics.Color(255, 255, 0)
        pos = offscreen_canvas.width - 40
        my_text = "wordle loading..."
        graphics.DrawText(offscreen_canvas, font, pos, 10, textColor, my_text)
        offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)

    clock = Clock()
    async with aiohttp.ClientSession(
        timeout = aiohttp.ClientTimeout(total=60*60*24*7)) as session:
        game = Game(session)
        tasks = []
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_start",
                "http://localhost:8080/push_start")))
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.guesses_and_colors",
                "http://localhost:8080/push_guesses_and_colors")))
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_current_letter",
                "http://localhost:8080/push_current_letter")))
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_guess_current",
                "http://localhost:8080/push_guess_current")))
        tasks.append(asyncio.create_task(
            trigger_events_from_sse(session, events, "game.push_shutdown",
                "http://localhost:8080/push_shutdown")))

        await game.start()
        game.draw()
        await game.update(screen)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    key = pygame.key.name(event.key).upper()
                    # logger.info(f"key: {key}")
                    if key == "SPACE":
                        await game.start()
                    elif key == "BACKSPACE":
                        logger.info("backspace")
                        game.delete_letter()
                    elif key == "RETURN":
                        if len(game.current_guess) == 5:
                            await session_get(session, "word", {"guess": game.current_guess})
                    elif len(key) == 1:
                        await game.enter_letter(key)
                        logger.info(f"key: {str(key)}")
                    else:
                        continue
                    game.draw()
                    await game.update(screen)

            if platform.system() != "Darwin":
                pixels = image_to_string(screen, "RGB")
                img = Image.frombytes("RGB", (screen.get_width(), screen.get_height()), pixels)
                img = img.rotate(90, Image.NEAREST, expand=1)
                offscreen_canvas.SetImage(img)
                matrix.SwapOnVSync(offscreen_canvas)
            window.blit(pygame.transform.scale(screen, window.get_rect().size), (0, 0))
            pygame.display.flip()
            await clock.tick(TICKS_PER_SECOND)

        for t in tasks:
            t.cancel()

if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    pygame.mixer.init(22050)

    logger.info("pygame.init()")
    pygame.init()
    logger.info("pygame.init() done")
    asyncio.run(main())
    pygame.quit()
