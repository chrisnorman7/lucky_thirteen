"""A game where you have to select numbers making up 13."""

import os
import os.path
from json import dump, load
from pathlib import Path
from random import randint
from typing import Any, Dict, Generator, List, Optional, Tuple

from earwax import ActionMenu
from earwax import Game as EarwaxGame
from earwax import get_buffer
from pyglet.clock import schedule_once
from pyglet.resource import get_settings_path
from pyglet.window import key
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
        self.music_volume: float = 0.25
        self.sound_source: Optional[DirectSource] = None
        self.sound_generator: Optional[BufferGenerator] = None
        self.intro: bool = True
        self.winning: bool = False
        self.board_size: int = 5
        self.board_depth: int = 13
        super().__init__('Lucky Thirteen')
        self.voice: str = os.listdir(voices_directory)[0]
        self.settings_file: Path = Path(
            get_settings_path(app_name), app_name + '.json'
        )

    def playing(self) -> bool:
        """Returns True if play is in progress."""
        return self.no_menu() and not self.intro and not self.winning

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
        if self.settings_file.is_file():
            with self.settings_file.open('r') as f:
                data: Dict[str, Any] = load(f)
            self.music_volume = data.get('music_volume', self.music_volume)
            self.voice = data.get('voice', self.voice)
        self.ctx = Context()
        self.start_intro()
        if self.window is not None:
            self.window.event(self.on_close)

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

    def start_intro(self) -> None:
        """Start intro music."""
        self.winning = False
        self.intro = True
        self.play_music('intro.mp3')
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
            if self.music_generator is not None:
                self.music_generator.destroy()
                self.music_generator = None
            self.winning = True
            schedule_once(lambda dt: self.start_intro(), 2)

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
    game.board = {}
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


@game.action(
    'Move left', symbol=key.LEFT, can_run=game.playing, interval=move_speed
)
def left() -> None:
    """Move left."""
    if not game.x:
        return game.play_wall()
    game.x -= 1
    game.show_selection()


@game.action(
    'Move right', symbol=key.RIGHT, can_run=game.playing, interval=move_speed
)
def right() -> None:
    """Move right."""
    if game.x == (game.board_size - 1):
        return game.play_wall()
    game.x += 1
    game.show_selection()


@game.action(
    'Move forward', symbol=key.UP, can_run=game.playing, interval=move_speed
)
def forward() -> None:
    """Move forward."""
    if game.y == (game.board_size - 1):
        return game.play_wall()
    game.y += 1
    game.show_selection()


@game.action(
    'Move backwards', symbol=key.DOWN, can_run=game.playing,
    interval=move_speed
)
def backwards() -> None:
    """Move backwards."""
    if not game.y:
        return game.play_wall()
    game.y -= 1
    game.show_selection()


@game.action('Music volume up', symbol=key.M)
def music_up() -> None:
    """Reduce the music volume."""
    game.music_volume = min(1.0, game.music_volume + 0.1)
    if game.music_source is not None:
        game.music_source.gain = game.music_volume


@game.action('Music volume down', symbol=key.M, modifiers=key.MOD_SHIFT)
def music_down() -> None:
    """Reduce the music volume."""
    game.music_volume = max(0.0, game.music_volume - 0.1)
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
        elif len(game.selected) == 1:
            game.board[game.selected[0]][-1] = randint(1, 13)
            game.play_sound('randomise.wav')
            game.selected.clear()
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


@game.action('Change voice', symbol=key.V, can_run=game.playing)
def change_voice() -> None:
    """Change the currently selected voice."""
    voices = os.listdir(voices_directory)
    index: int = voices.index(game.voice) + 1
    if index == len(voices):
        index = 0
    game.voice = voices[index]
    game.speak('name.wav')


if __name__ == '__main__':
    game.add_default_actions()
    game.run()
