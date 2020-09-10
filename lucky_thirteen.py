"""A game where you have to select numbers making up 13."""

import os.path
from pathlib import Path
from random import randint
from time import time
from typing import Dict, List, Optional, Tuple

from attr import Factory, attrs
from earwax import (ActionMenu, AdvancedInterfaceSoundPlayer, Box, BoxLevel,
                    Config, ConfigValue, Game, IntroLevel, Point, Track)
from pyglet.window import Window, key, mouse

# The app name.
app_name: str = os.path.splitext(__file__)[0]

# The main game object.
game: Game = Game(name=app_name)

# The type for board coordinates.
Coordinates = Tuple[float, float, float]

# The directory where sounds are stored.
sounds_directory: Path = Path('sounds')

# The directory where music files are stored.
music_directory: Path = sounds_directory / 'music'

# The directory where voice packs are stored.
voices_directory = sounds_directory / 'voices'

voices: List[str] = []

voice_name: Path
for voice_name in voices_directory.iterdir():
    voices.append(voice_name.name)

# The speed the player can move. Set to None to allow movement at any time, and
# disable key repeat.
move_speed: Optional[float] = None


class GameConfig(Config):
    """Game settings."""

    voice: ConfigValue = ConfigValue(voices[0], type_=voices)
    board_size: ConfigValue = ConfigValue(
        5, name='The length of each side of the board'
    )
    max_number: ConfigValue = ConfigValue(
        13, name='The maximum number that should be generated'
    )
    music_volume: ConfigValue = ConfigValue(
        0.2, name='The volume of game music'
    )


config: GameConfig = GameConfig()
config_dir: Path = game.get_settings_path()
config_file: Path = config_dir / 'config.yaml'

try:
    with config_file.open('r') as f:
        config.load(f)
except FileNotFoundError:
    pass  # No settings have been saved.


@attrs(auto_attribs=True)
class Board(BoxLevel):
    """A box level, with added goodies.

    The numbers that have been generated, the tiles that have been selected,
    and the player's points are all stored here.
    """

    # The randomly generated numbers.
    numbers: Dict[Coordinates, List[int]] = Factory(dict)

    # The list of coordinates that are currently selected.
    selected: List[Coordinates] = Factory(list)

    # The player's points.
    points: int = 0

    # The sound player to use.
    sound_player: Optional[AdvancedInterfaceSoundPlayer] = None

    # The last time the mouse was used.
    last_mouse: float = 0.0

    # The minimum time between mouse moves.
    mouse_interval: float = 0.5

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Move through the grid with the mouse."""
        now: float = time()
        if (now - self.last_mouse) < self.mouse_interval:
            return
        self.last_mouse = now
        b: int
        if dx == -1:
            b = 270
        elif dx == 1:
            b = 90
        elif dy == -1:
            b = 180
        else:
            b = 0
        self.move(bearing=b)()

    def play_sound(self, filename: str) -> None:
        """Play the given file."""
        if self.sound_player is not None:
            self.sound_player.play_path(Path('sounds', filename))

    def empty_tile(self) -> bool:
        """Returns True if the current tile is blank."""
        return self.numbers[self.coordinates.floor().coordinates] == []

    def show_selection(self) -> None:
        """Show the currently selected number."""
        coords: Coordinates = self.coordinates.floor().coordinates
        if coords in self.selected:
            return self.play_sound('select.wav')
        phrase: str
        if self.empty_tile():
            phrase = 'wild.wav'
        else:
            phrase = f'{self.numbers[coords][-1]}.wav'
        speak(phrase)

    def check_selection(self) -> None:
        """Check to see if the selection is less than (still selecting) equal
        to (winning) or greater than (losing) 13."""
        value: int = 0
        c: Coordinates
        for c in self.selected:
            value += self.numbers[c][-1]
        if value == config.max_number.value:
            self.win()
        elif value > config.max_number.value:
            self.lose()
        else:
            self.play_sound('select.wav')

    def win(self) -> None:
        """They have made exactly 13."""
        c: Coordinates
        for c in self.selected:
            self.numbers[c].pop()
        self.selected.clear()
        if any(self.numbers.values()):
            self.play_sound('win.wav')
        else:
            game.replace_level(win_level)

    def lose(self) -> None:
        """They have made more than 13."""
        self.play_sound('lose.wav')
        c: Coordinates
        for c in self.selected:
            self.numbers[c].append(randint(1, config.max_number.value))
        self.selected.clear()

    def calculate_coordinates(
        self, distance: float, bearing: int
    ) -> Tuple[float, float]:
        """Use simple movement."""
        x: float = self.coordinates.x
        y: float = self.coordinates.y
        if bearing == 0:
            y += 1
        elif bearing == 90:
            x += 1
        elif bearing == 180:
            y -= 1
        elif bearing == 270:
            x -= 1
        else:
            raise RuntimeError(f'Invalid bearing : {repr(bearing)}.')
        return x, y

    def on_push(self) -> None:
        """Populate the board."""
        super().on_push()
        if self.game.audio_context is not None and self.sound_player is None:
            self.sound_player = AdvancedInterfaceSoundPlayer(
                self.game.audio_context
            )
        self.coordinates.x = 0
        self.coordinates.y = 0
        x: int
        y: int
        z: int
        for x in range(config.board_size.value):
            for y in range(config.board_size.value):
                coords: Coordinates = (x, y, 0)
                self.numbers[coords] = []
                for z in range(config.max_number.value):
                    self.numbers[coords].append(
                        randint(1, config.max_number.value)
                    )
        self.show_selection()


board: Board = Board(
    game, Box(
        Point(0, 0, 0),
        Point(config.board_size.value - 1, config.board_size.value - 1, 0)
    )
)

main_music: Track = Track(
    music_directory / 'main.mp3', gain=config.music_volume.value
)
board.tracks.append(main_music)


@board.event
def on_move() -> None:
    """Show the current number."""
    board.show_selection()


@board.event
def on_move_fail(distance, vertical, bearing) -> None:
    """Play the wall sound."""
    if board.sound_player is not None:
        board.sound_player.play_path(sounds_directory / 'wall.wav')


def speak(string: str) -> None:
    """Play a from the voices directory."""
    if board.sound_player is not None:
        board.sound_player.play_path(
            voices_directory / config.voice.value / string
        )


intro_level: IntroLevel = IntroLevel(
    game, board, voices_directory / config.voice.value / 'intro.wav', None
)
intro_level.action('Skip', symbol=key.RETURN)(intro_level.skip)

intro_music: Track = Track(
    music_directory / 'intro.mp3', gain=config.music_volume.value
)
intro_level.tracks.append(intro_music)

win_level: IntroLevel = IntroLevel(
    game, intro_level, sounds_directory / 'won.wav', 1.0
)

board.action('Move left', symbol=key.LEFT, interval=move_speed)(
    board.move(bearing=270)
)

board.action('Move right', symbol=key.RIGHT, interval=move_speed)(
    board.move(bearing=90)
)

board.action('Move forward', symbol=key.UP, interval=move_speed)(
    board.move(bearing=0)
)

board.action('Move backwards', symbol=key.DOWN, interval=move_speed)(
    board.move(bearing=180)
)


def set_music_volume(value: float) -> None:
    """Set the music volume."""
    config.music_volume.value = value
    t: Track
    for t in (intro_music, main_music):
        if t.source is not None:
            t.source.gain = value


@board.action('Music volume up', symbol=key.M)
def music_up() -> None:
    """Increase the music volume."""
    set_music_volume(min(1.0, config.music_volume.value + 0.05))


@board.action('Music volume down', symbol=key.M, modifiers=key.MOD_SHIFT)
def music_down() -> None:
    """Reduce the music volume."""
    set_music_volume(max(0.0, config.music_volume.value - 0.05))


@board.action('Select tile', symbol=key.RETURN, mouse_button=mouse.LEFT)
def select_tile() -> None:
    """Select the current tile."""
    coords: Coordinates = board.coordinates.floor().coordinates
    if coords in board.selected:
        board.play_sound('fail.wav')
    elif board.empty_tile():
        if len(board.selected) >= 2:
            board.win()
        elif len(board.selected) == 1:
            board.numbers[board.selected[0]][-1] = randint(
                1, config.max_number.value
            )
            board.play_sound('randomise.wav')
            board.selected.clear()
        else:
            board.numbers[coords].append(
                randint(1, config.max_number.value)
            )
            board.show_selection()
            board.selected.clear()
    else:
        board.selected.append(coords)
        board.check_selection()


@board.action(
    'Deselect all tiles', symbol=key.ESCAPE, mouse_button=mouse.RIGHT
)
def deselect_tiles() -> None:
    """Deselect all tiles."""
    if not board.selected:
        board.play_sound('fail.wav')
    else:
        board.selected.clear()
        board.play_sound('deselect.wav')


@board.action('Show stack depth', symbol=key.D, mouse_button=mouse.MIDDLE)
def show_depth() -> None:
    """says the depth of the currently selected stack."""
    l: int = len(board.numbers[board.coordinates.floor().coordinates])
    if not l or l > config.max_number.value:
        board.play_sound('fail.wav')
    else:
        speak(f'{l}.wav')


@board.action('Help menu', symbol=key.SLASH, modifiers=key.MOD_SHIFT)
def help_menu() -> None:
    """Show the help menu."""
    game.push_level(ActionMenu(game, 'Actions'))


@board.action('Change voice', symbol=key.V)
def change_voice() -> None:
    """Change the currently selected voice."""
    index: int = voices.index(config.voice.value) + 1
    if index == len(voices):
        index = 0
    config.voice.value = voices[index]
    speak('name.wav')


win_level.action('Skip', symbol=key.RETURN)(win_level.skip)

level: IntroLevel
for level in (intro_level, win_level):
    level.action('Exit', symbol=key.ESCAPE, mouse_button=mouse.RIGHT)(
        lambda: game.window.dispatch_event('on_close')
    )

if __name__ == '__main__':
    game.run(Window(caption=app_name), initial_level=intro_level)
    if not config_dir.is_dir():
        config_dir.mkdir()
    with config_file.open('w') as f:
        config.save(f)
