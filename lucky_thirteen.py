"""A game where you have to select numbers making up 13."""

import os.path
from pathlib import Path
from random import randint, sample
from typing import List, Optional

from earwax import (ActionMenu, Config, ConfigValue, Game, GameBoard,
                    IntroLevel, Point, PointDirections, Track)
from pyglet.window import Window, key, mouse

NumberList = List[int]

# The app name.
app_name: str = os.path.splitext(__file__)[0]

# The main game object.
game: Game = Game(name=app_name)

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
    pass  # No configuration has been saved yet.


@game.event
def after_run() -> None:
    """Save configuration values."""
    if not config_dir.is_dir():
        config_dir.mkdir()
    with config_file.open('w') as f:
        config.save(f)


# All the points that have numbers attached to them.
points: List[Point] = []


class Board(GameBoard[NumberList]):
    """The game board.

    The tiles that have been selected and the player's points are stored here.
    """

    # The list of coordinates that are currently selected.
    selected: List[Point] = []

    # The player's points.
    points: int = 0

    def empty_tile(self) -> bool:
        """Returns ``True`` if the current tile is empty."""
        return self.current_tile == []

    def play_sound(self, filename: str) -> None:
        """Play the given file."""
        if game.interface_sound_player is not None:
            game.interface_sound_player.play_path(Path('sounds', filename))

    def check_selection(self) -> None:
        """Check to see if the selection is less than (still selecting) equal
        to (winning) or greater than (losing) 13."""
        value: int = 0
        p: Point
        for p in self.selected:
            value += self.get_tile(p)[-1]
        if value == config.max_number.value:
            self.win()
        elif value > config.max_number.value:
            self.lose()
        else:
            self.play_sound('select.wav')

    def win(self) -> None:
        """They have made exactly 13."""
        p: Point
        for p in self.selected:
            self.get_tile(p).pop()
        self.selected.clear()
        for p in points:
            if self.get_tile(p):
                self.play_sound('win.wav')
                break  # There are numbers left.
        else:
            game.replace_level(win_level)

    def lose(self) -> None:
        """They have made more than 13."""
        self.play_sound('lose.wav')
        p: Point
        for p in self.selected:
            self.get_tile(p).append(randint(1, config.max_number.value))
        self.selected.clear()

    def on_push(self) -> None:
        """Populate the board."""
        super().on_push()
        self.coordinates.x = 0
        self.coordinates.y = 0
        self.dispatch_event('on_move', Point(0, 0, 0), self.current_tile)


def build_tile(p: Point) -> NumberList:
    """Build a list of numbers to use."""
    points.append(p)
    return sample(
        range(1, config.max_number.value + 1), config.max_number.value
    )


board: Board = Board(
    game, Point(config.board_size.value, config.board_size.value, 1),
    build_tile
)

main_music: Track = Track(
    music_directory / 'main.mp3', gain=config.music_volume.value
)
board.tracks.append(main_music)


@board.event
def on_move(direction: Point, tile: NumberList) -> None:
    """Show the current number."""
    if board.coordinates in board.selected:
        return board.play_sound('select.wav')
    phrase: str
    if not tile:
        phrase = 'wild.wav'
    else:
        phrase = f'{tile[-1]}.wav'
    speak(phrase)


@board.event
def on_move_fail(direction: Point) -> None:
    """Play the wall sound."""
    board.play_sound('wall.wav')


def speak(string: str) -> None:
    """Play a from the voices directory."""
    if game.interface_sound_player is not None:
        game.interface_sound_player.play_path(
            voices_directory / config.voice.value / string
        )


intro_level: IntroLevel = IntroLevel(
    game, board, voices_directory / config.voice.value / 'intro.wav', None
)
intro_level.action('Skip', symbol=key.RETURN, joystick_button=0)(
    intro_level.skip
)

intro_music: Track = Track(
    music_directory / 'intro.mp3', gain=config.music_volume.value
)
intro_level.tracks.append(intro_music)

win_level: IntroLevel = IntroLevel(
    game, intro_level, sounds_directory / 'won.wav', 1.0
)

board.action(
    'Move left', symbol=key.LEFT, interval=move_speed,
    hat_direction=(-1, 0)
)(board.move(PointDirections.west))

board.action(
    'Move right', symbol=key.RIGHT, interval=move_speed,
    hat_direction=(1, 0)
)(board.move(PointDirections.east))

board.action(
    'Move forward', symbol=key.UP, interval=move_speed,
    hat_direction=(0, 1)
)(board.move(PointDirections.north))

board.action(
    'Move backwards', symbol=key.DOWN, interval=move_speed,
    hat_direction=(0, -1)
)(board.move(PointDirections.south)
)


def set_music_volume(value: float) -> None:
    """Set the music volume."""
    config.music_volume.value = value
    t: Track
    for t in (intro_music, main_music):
        if t.source is not None:
            t.source.gain = value


@board.action('Music volume up', symbol=key.M, joystick_button=5)
def music_up() -> None:
    """Increase the music volume."""
    set_music_volume(min(1.0, config.music_volume.value + 0.05))


@board.action(
    'Music volume down', symbol=key.M, modifiers=key.MOD_SHIFT,
    joystick_button=4
)
def music_down() -> None:
    """Reduce the music volume."""
    set_music_volume(max(0.0, config.music_volume.value - 0.05))


@board.action(
    'Select tile', symbol=key.RETURN, mouse_button=mouse.LEFT,
    joystick_button=0
)
def select_tile() -> None:
    """Select the current tile."""
    if board.coordinates in board.selected:
        board.play_sound('fail.wav')
    elif board.empty_tile():
        if len(board.selected) >= 2:
            board.win()
        elif len(board.selected) == 1:
            board.get_tile(board.selected[0])[-1] = randint(
                1, config.max_number.value
            )
            board.play_sound('randomise.wav')
            board.selected.clear()
        else:
            board.current_tile.append(
                randint(1, config.max_number.value)
            )
            board.show_selection()
            board.selected.clear()
    else:
        board.selected.append(board.coordinates)
        board.check_selection()


@board.action(
    'Deselect all tiles', symbol=key.ESCAPE, mouse_button=mouse.RIGHT,
    joystick_button=2
)
def deselect_tiles() -> None:
    """Deselect all tiles."""
    if not board.selected:
        board.play_sound('fail.wav')
    else:
        board.selected.clear()
        board.play_sound('deselect.wav')


@board.action(
    'Show stack depth', symbol=key.D, mouse_button=mouse.MIDDLE,
    joystick_button=3
)
def show_depth() -> None:
    """says the depth of the currently selected stack."""
    l: int = len(board.current_tile)
    if not l or l > config.max_number.value:
        board.play_sound('fail.wav')
    else:
        speak(f'{l}.wav')


@board.action('Help menu', symbol=key.SLASH, modifiers=key.MOD_SHIFT)
def help_menu() -> None:
    """Show the help menu."""
    game.push_level(ActionMenu(game, 'Actions'))


@board.action('Change voice', symbol=key.V, joystick_button=6)
def change_voice() -> None:
    """Change the currently selected voice."""
    index: int = voices.index(config.voice.value) + 1
    if index == len(voices):
        index = 0
    config.voice.value = voices[index]
    speak('name.wav')


win_level.action('Skip', symbol=key.RETURN, joystick_button=0)(
    win_level.skip
)

level: IntroLevel
for level in (intro_level, win_level):
    level.action(
        'Exit', symbol=key.ESCAPE, mouse_button=mouse.RIGHT, joystick_button=7
    )(lambda: game.window.dispatch_event('on_close'))

if __name__ == '__main__':
    game.run(Window(caption=app_name), initial_level=intro_level)
