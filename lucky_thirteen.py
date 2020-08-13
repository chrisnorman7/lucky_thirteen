"""A game where you have to select numbers making up 13."""

import os
import os.path
from json import dump, load
from pathlib import Path
from random import randint
from time import time
from typing import Any, Dict, List, Optional, Tuple

from earwax import Action, ActionMenu
from earwax import Game as EarwaxGame
from earwax import Level, get_buffer
from pyglet.clock import schedule_once, unschedule
from pyglet.resource import get_settings_path
from pyglet.window import Window, key, mouse
from synthizer import Buffer, BufferGenerator, Context, DirectSource

# The app name.
app_name: str = os.path.splitext(__file__)[0]

# The type for board coordinates.
Coordinates = Tuple[int, int]

# The directory where voice packs are stored.
voices_directory = Path('sounds', 'voices')

# The speed the player can move. Set to None to allow movement at any time, and
# disable key repeat.
move_speed: Optional[float] = None

# The maximum number that should be randomly generated.
max_number: int = 13


class Board:
    """The board where numbers and the player's coordinates are stored."""

    # The randomly generated numbers.
    numbers: Dict[Coordinates, List[int]] = {}

    # The list of coordinates that are currently selected.
    selected: List[Coordinates] = []

    # The player's coordinates.
    x: int = 0
    y: int = 0

    @property
    def coords(self) -> Coordinates:
        """Return the current coordinates."""
        return (self.x, self.y)

    def empty_tile(self) -> bool:
        """Returns True if the current tile is blank."""
        return self.numbers[self.coords] == []


class Game(EarwaxGame):
    """A game with the grid attached."""
    def __init__(self) -> None:
        self.ctx: Optional[Context] = None
        self.intro_generator: Optional[BufferGenerator] = None
        self.music_source: Optional[DirectSource] = None
        self.music_generator: Optional[BufferGenerator] = None
        self.music_volume: float = 0.25
        self.sound_source: Optional[DirectSource] = None
        self.sound_generator: Optional[BufferGenerator] = None
        self.board_size: int = 5
        self.board_depth: int = max_number
        self.board: Board = Board()
        self.voice: str = os.listdir(voices_directory)[0]
        self.settings_file: Path = Path(
            get_settings_path(app_name), app_name + '.json'
        )
        super().__init__()

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
        string = os.path.join('voices', self.voice, string)
        return self.play_sound(string)

    def play_music(self, filename: str) -> None:
        """Play (and loop) some music."""
        path: Path = Path('sounds', 'music') / filename
        buf: Buffer = get_buffer('file', str(path))
        if self.music_source is None:
            self.music_source = DirectSource(self.ctx)
            self.music_source.gain = self.music_volume
        if self.music_generator is None:
            self.music_generator = BufferGenerator(self.ctx)
            self.music_generator.looping = True
            self.music_source.add_generator(self.music_generator)
        self.music_generator.buffer = buf

    def show_selection(self) -> None:
        """Show the currently-selected number."""
        coords: Coordinates = game.board.coords
        if coords in self.board.selected:
            return self.play_sound('select.wav')
        phrase: str
        if self.board.empty_tile():
            phrase = 'wild.wav'
        else:
            phrase = f'{self.board.numbers[coords][-1]}.wav'
        self.speak(phrase)

    def before_run(self) -> None:
        """Play the intro audio."""
        if self.settings_file.is_file():
            with self.settings_file.open('r') as f:
                data: Dict[str, Any] = load(f)
            self.music_volume = data.get('music_volume', self.music_volume)
            self.voice = data.get('voice', self.voice)
        self.ctx = Context()
        self.push_level(intro_level)

    def on_close(self) -> None:
        """Save the current configuration."""
        data: Dict[str, Any] = {
            'music_volume': self.music_volume,
            'voice': self.voice
        }
        parent: Path = self.settings_file.parent
        if not parent.is_dir():
            parent.mkdir()
        with self.settings_file.open('w') as f:
            dump(data, f, indent='  ')

    def check_selection(self) -> None:
        """Check to see if the selection is less than (still selecting) equal
        to (winning) or greater than (losing) 13."""
        value: int = 0
        c: Coordinates
        for c in self.board.selected:
            value += self.board.numbers[c][-1]
        if value == max_number:
            self.win()
        elif value > max_number:
            self.lose()
        else:
            return self.play_sound('select.wav')

    def win(self) -> None:
        """They have made exactly 13."""
        for c in self.board.selected:
            self.board.numbers[c].pop()
        self.board.selected.clear()
        if any(self.board.numbers.values()):
            self.play_sound('win.wav')
        else:
            self.replace_level(win_level)

    def lose(self) -> None:
        """They have made more than 13."""
        self.play_sound('lose.wav')
        for c in self.board.selected:
            self.board.numbers[c].append(randint(1, max_number))
        self.board.selected.clear()


game = Game()


class IntroLevel(Level):
    """Add on_push event."""

    def on_push(self) -> None:
        """Start the music playing."""
        game.play_music('intro.mp3')
        game.speak('intro.wav')


class MainLevel(Level):
    """Add on_push event."""

    # The last time the mouse was used.
    last_mouse: float = 0.0

    # The minimum time between mouse moves.
    mouse_interval: float = 0.5

    def on_push(self) -> None:
        game.play_music('main.mp3')
        x: int
        y: int
        for x in range(game.board_size):
            for y in range(game.board_size):
                coords: Tuple[int, int] = (x, y)
                game.board.numbers[coords] = []
                z: int
                for z in range(game.board_depth):
                    game.board.numbers[coords].append(randint(1, max_number))
        game.show_selection()

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Move through the grid with the mouse."""
        now: float = time()
        if (now - self.last_mouse) < self.mouse_interval:
            return
        self.last_mouse = now
        a: Action
        if dx == -1:
            a = left
        elif dx == 1:
            a = right
        elif dy == -1:
            a = backwards
        else:
            a = forward
        a.run(None)


class WinLevel(Level):
    """Replace this level with the intro level after a certain amount of
    time."""

    def on_push(self) -> None:
        game.play_sound('won.wav')
        print(len(game.levels))
        print(self.actions)
        if game.music_generator is not None:
            game.music_generator.destroy()
            game.music_generator = None
        schedule_once(self.goto_intro, 2)

    def goto_intro(self, dt: float) -> None:
        """Switch to the intro level."""
        if game.level is self:
            game.replace_level(intro_level)


intro_level: IntroLevel = IntroLevel()
main_level: MainLevel = MainLevel()
win_level: WinLevel = WinLevel()


@intro_level.action('Skip intro', symbol=key.RETURN, mouse_button=mouse.LEFT)
def skip_intro() -> None:
    """Skip the intro, and start the game."""
    game.replace_level(main_level)


@main_level.action('Move left', symbol=key.LEFT, interval=move_speed)
def left() -> None:
    """Move left."""
    if not game.board.x:
        return game.play_wall()
    game.board.x -= 1
    game.show_selection()


@main_level.action('Move right', symbol=key.RIGHT, interval=move_speed)
def right() -> None:
    """Move right."""
    if game.board.x == (game.board_size - 1):
        return game.play_wall()
    game.board.x += 1
    game.show_selection()


@main_level.action('Move forward', symbol=key.UP, interval=move_speed)
def forward() -> None:
    """Move forward."""
    if game.board.y == (game.board_size - 1):
        return game.play_wall()
    game.board.y += 1
    game.show_selection()


@main_level.action('Move backwards', symbol=key.DOWN, interval=move_speed)
def backwards() -> None:
    """Move backwards."""
    if not game.board.y:
        return game.play_wall()
    game.board.y -= 1
    game.show_selection()


@main_level.action('Music volume up', symbol=key.M)
def music_up() -> None:
    """Reduce the music volume."""
    game.music_volume = min(1.0, game.music_volume + 0.1)
    if game.music_source is not None:
        game.music_source.gain = game.music_volume


@main_level.action('Music volume down', symbol=key.M, modifiers=key.MOD_SHIFT)
def music_down() -> None:
    """Reduce the music volume."""
    game.music_volume = max(0.0, game.music_volume - 0.1)
    if game.music_source is not None:
        game.music_source.gain = game.music_volume


@main_level.action('Select tile', symbol=key.RETURN, mouse_button=mouse.LEFT)
def select_tile() -> None:
    """Select the current tile."""
    if game.board.coords in game.board.selected:
        game.play_sound('fail.wav')
    elif game.board.empty_tile():
        if len(game.board.selected) >= 2:
            game.win()
        elif len(game.board.selected) == 1:
            game.board.numbers[game.board.selected[0]][-1] = randint(
                1, max_number
            )
            game.play_sound('randomise.wav')
            game.board.selected.clear()
        else:
            game.board.numbers[game.board.coords].append(
                randint(1, max_number)
            )
            game.show_selection()
            game.board.selected.clear()
    else:
        game.board.selected.append(game.board.coords)
        game.check_selection()


@main_level.action(
    'Deselect all tiles', symbol=key.ESCAPE, mouse_button=mouse.RIGHT
)
def deselect_tiles() -> None:
    """Deselect all tiles."""
    if not game.board.selected:
        game.play_sound('fail.wav')
    else:
        game.board.selected.clear()
        game.play_sound('deselect.wav')


@main_level.action('Show stack depth', symbol=key.D, mouse_button=mouse.MIDDLE)
def show_depth() -> None:
    """says the depth of the currently selected stack."""
    l: int = len(game.board.numbers[game.board.coords])
    if not l or l > max_number:
        game.play_sound('fail.wav')
    else:
        game.speak(f'{l}.wav')


@main_level.action('Help menu', symbol=key.SLASH, modifiers=key.MOD_SHIFT)
def help_menu() -> None:
    """Show the help menu."""
    game.push_level(ActionMenu('Actions', game))


@main_level.action('Change voice', symbol=key.V)
def change_voice() -> None:
    """Change the currently selected voice."""
    voices = os.listdir(voices_directory)
    index: int = voices.index(game.voice) + 1
    if index == len(voices):
        index = 0
    game.voice = voices[index]
    game.speak('name.wav')


@win_level.action(
    'Skip winning sequence', symbol=key.RETURN, mouse_button=mouse.LEFT
)
def skip_win() -> None:
    unschedule(win_level.goto_intro)
    print('Skipping win.')
    game.replace_level(intro_level)


if __name__ == '__main__':
    game.run(Window(caption=app_name))
