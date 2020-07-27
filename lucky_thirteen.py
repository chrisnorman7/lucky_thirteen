"""A game where you have to select numbers making up 13."""

import os.path
from pathlib import Path
from random import randint
from typing import Dict, List, Optional, Tuple, Generator

from earwax import Game as EarwaxGame
from earwax import get_buffer, ActionMenu
from pyglet.window import key
from synthizer import Buffer, BufferGenerator, Context, DirectSource

Coordinates = Tuple[int, int]


class Game(EarwaxGame):
    """A game with the grid attached."""
    def __init__(self) -> None:
        self.board: Dict[Coordinates, List[int]] = {}
        self.selected: List[Coordinates] = []
        self.x: int = 0
        self.y: int = 0
        self.ctx: Optional[Context] = None
        self.intro_generator: Optional[BufferGenerator] = None
        self.music_source: Optional[DirectSource] = None
        self.music_generator: Optional[BufferGenerator] = None
        self.music_volume: float = 0.0
        self.sound_source: Optional[DirectSource] = None
        self.sound_generator: Optional[BufferGenerator] = None
        self.intro: bool = True
        self.board_size: int = 5
        self.board_depth: int = 13
        super().__init__('Lucky Thirteen')

    def playing(self) -> bool:
        """Returns True if play is in progress."""
        return self.no_menu() and not self.intro

    @property
    def coords(self) -> Coordinates:
        """Return the current coordinates."""
        return (self.x, self.y)

    def empty_tile(self) -> bool:
        """Returns True if the current tile is blank."""
        return self.board[self.coords] == []

    def play_sound(self, filename: str) -> None:
        """Play the sound at the given filename."""
        path = Path('sounds') / filename
        buf: Buffer = get_buffer('file', str(path))
        if self.sound_source is None:
            self.sound_source = DirectSource(self.ctx)
        if self.sound_generator is None:
            self.sound_generator = BufferGenerator(self.ctx)
            self.sound_source.add_generator(self.sound_generator)
        self.sound_generator.buffer = buf

    def play_wall(self) -> None:
        """Play the wall sound."""
        self.play_sound('wall.wav')

    def speak(self, string: str) -> None:
        """Play a file from the voices directory."""
        string = os.path.join('voices', string)
        return self.play_sound(string)

    def play_music(self, filename: str) -> None:
        """Play (and loop) some music."""
        path: Path = Path('sounds', 'music') / filename
        buf: Buffer = get_buffer('file', str(path))
        if self.music_source is None:
            self.music_source = DirectSource(self.ctx)
        if self.music_generator is None:
            self.music_generator = BufferGenerator(self.ctx)
            self.music_generator.looping = True
            self.music_source.add_generator(self.music_generator)
        self.music_generator.buffer = buf

    def show_selection(self) -> None:
        """Show the currently-selected number."""
        coords: Coordinates = game.coords
        if coords in self.selected:
            return self.play_sound('select.wav')
        phrase: str
        if self.empty_tile():
            phrase = 'wild.wav'
        else:
            phrase = f'{self.board[coords][-1]}.wav'
        self.speak(phrase)

    def before_run(self) -> None:
        """Play the intro audio."""
        self.ctx = Context()
        self.start_intro()

    def start_intro(self, play_help: bool = True) -> None:
        """Start intro music."""
        self.play_music('intro.mp3')
        if play_help:
            self.speak('intro.wav')

    def check_selection(self) -> None:
        """Check to see if the selection is less than (still selecting) equal
        to (winning) or greater than (losing) 13."""
        value: int = 0
        c: Coordinates
        for c in self.selected:
            value += self.board[c][-1]
        if value == 13:
            self.win()
        elif value > 13:
            self.lose()
        else:
            return self.play_sound('select.wav')

    def win(self) -> None:
        """They have made exactly 13."""
        self.play_sound('win.wav')
        for c in self.selected:
            self.board[c].pop()
        self.selected.clear()
        numbers: List[int]
        for numbers in self.board.values():
            if numbers:
                # They have not won.
                break
        else:
            self.play_sound('won.wav')
            self.start_intro()

    def lose(self) -> None:
        """They have made more than 13."""
        self.play_sound('lose.wav')
        for c in self.selected:
            self.board[c].append(randint(1, 13))
        self.selected.clear()


game = Game()


@game.action('Skip intro', symbol=key.RETURN, can_run=lambda: game.intro)
def skip_intro() -> Generator[None, None, None]:
    """Skip the intro, and start the game."""
    yield
    game.intro = False
    game.play_music('main.mp3')
    x: int
    y: int
    for x in range(game.board_size):
        for y in range(game.board_size):
            coords: Tuple[int, int] = (x, y)
            game.board[coords] = []
            z: int
            for z in range(game.board_depth):
                game.board[coords].append(randint(1, 13))
    game.show_selection()


@game.action('Move left', symbol=key.LEFT, can_run=game.playing)
def left() -> None:
    """Move left."""
    if not game.x:
        return game.play_wall()
    game.x -= 1
    game.show_selection()


@game.action('Move right', symbol=key.RIGHT, can_run=game.playing)
def right() -> None:
    """Move right."""
    if game.x == (game.board_size - 1):
        return game.play_wall()
    game.x += 1
    game.show_selection()


@game.action('Move forward', symbol=key.UP, can_run=game.playing)
def forward() -> None:
    """Move forward."""
    if game.y == (game.board_size - 1):
        return game.play_wall()
    game.y += 1
    game.show_selection()


@game.action('Move backwards', symbol=key.DOWN, can_run=game.playing)
def backwards() -> None:
    """Move backwards."""
    if not game.y:
        return game.play_wall()
    game.y -= 1
    game.show_selection()


@game.action('Music volume up', symbol=key.M)
def music_up() -> None:
    """Reduce the music volume."""
    game.music_volume += 0.1
    print(game.music_volume)
    if game.music_source is not None:
        game.music_source.gain = game.music_volume


@game.action('Music volume down', symbol=key.M, modifiers=key.MOD_SHIFT)
def music_down() -> None:
    """Reduce the music volume."""
    game.music_volume -= 0.1
    print(game.music_volume)
    if game.music_source is not None:
        game.music_source.gain = game.music_volume


@game.action('Select tile', symbol=key.RETURN, can_run=game.playing)
def select_tile() -> None:
    """Select the current tile."""
    if game.coords in game.selected:
        game.play_sound('fail.wav')
    elif game.empty_tile():
        if len(game.selected) >= 2:
            game.win()
        else:
            game.show_selection()
    else:
        game.selected.append(game.coords)
        game.check_selection()


@game.action('Deselect all tiles', symbol=key.ESCAPE, can_run=game.playing)
def deselect_tiles() -> None:
    """Deselect all tiles."""
    if not game.selected:
        game.play_sound('fail.wav')
    else:
        game.selected.clear()
        game.play_sound('deselect.wav')


@game.action('Show stack depth', symbol=key.D, can_run=game.playing)
def show_depth() -> None:
    """says the depth of the currently selected stack."""
    l: int = len(game.board[game.coords])
    if not l:
        game.play_sound('fail.wav')
    else:
        game.speak(f'{l}.wav')


@game.action('Help menu', symbol=key.SLASH, modifiers=key.MOD_SHIFT)
def help_menu() -> None:
    """Show the help menu."""
    game.push_menu(ActionMenu(game))


if __name__ == '__main__':
    game.add_default_actions()
    game.run()
