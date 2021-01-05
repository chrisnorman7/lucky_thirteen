"""A game where you have to select numbers making up 13."""

from pathlib import Path
from random import randint, sample
from typing import List, Optional

from earwax import (ActionMenu, Config, ConfigValue, Game, GameBoard,
                    IntroLevel, Point, PointDirections, Track, hat_directions)
from earwax.track import TrackTypes
from pyglet.window import Window, key, mouse

NumberList = List[int]

# The app name.
app_name: str = 'Lucky Thirteen'

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
        4, name='The length of each side of the board'
    )
    max_number: ConfigValue = ConfigValue(
        13, name='The maximum number that should be generated'
    )


config: GameConfig = GameConfig()
config_dir: Path = game.get_settings_path()
config_file: Path = config_dir / 'config.yaml'
earwax_config: Path = config_dir / 'earwax.yaml'


@game.event
def setup() -> None:
    """Load configuration from disk."""
    if config_file.is_file():
        with config_file.open('r') as f:
            config.load(f)
        intro_level.sound_path = (
            voices_directory / config.voice.value / 'intro.wav'
        )
        if earwax_config.is_file():
            with earwax_config.open('r') as f:
                game.config.load(f)


@game.event
def after_run() -> None:
    """Save configuration values."""
    if not config_dir.is_dir():
        config_dir.mkdir()
    with config_file.open('w') as f:
        config.save(f)
    with earwax_config.open('w') as f:
        game.config.save(f)


class Board(GameBoard[NumberList]):
    """The game board.

    The tiles that have been selected and the player's points are stored here.
    """

    # The list of coordinates that are currently selected.
    selected: List[Point] = []

    def empty_tile(self) -> bool:
        """Return ``True`` if the current tile is empty."""
        return self.current_tile == []

    def play_sound(self, filename: str) -> None:
        """Play the given file."""
        if game.interface_sound_manager is not None:
            game.interface_sound_manager.play_path(
                sounds_directory / filename, True
            )

    def check_selection(self) -> None:
        """Check the current selection.

        Checks to see if the selection is less than (still selecting) equal to
        (winning) or greater than (losing) 13.
        """
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
        for p in self.populated_points:
            if len(self.get_tile(p)) > 0:
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


def build_tile(p: Point) -> NumberList:
    """Build a list of numbers to use."""
    return sample(
        range(1, config.max_number.value + 1), config.max_number.value
    )


board: Board = Board(
    game, Point(config.board_size.value, config.board_size.value, 0),
    build_tile
)


@board.event
def on_push() -> None:
    """Speak the current tile."""
    board.populate()
    board.dispatch_event('on_move', Point(0, 0, 0))


@board.event
def on_move(direction: Point) -> None:
    """Show the current number."""
    if board.coordinates in board.selected:
        return board.play_sound('select.wav')
    phrase: str
    if board.empty_tile():
        phrase = 'wild.wav'
    else:
        phrase = f'{board.current_tile[-1]}.wav'
    speak(phrase)


@board.event
def on_move_fail(direction: Point) -> None:
    """Play the wall sound."""
    board.play_sound('wall.wav')


board.action(
    'Move left', symbol=key.LEFT, interval=move_speed,
    hat_direction=hat_directions.LEFT
)(board.move(PointDirections.west))

board.action(
    'Move right', symbol=key.RIGHT, interval=move_speed,
    hat_direction=hat_directions.RIGHT
)(board.move(PointDirections.east))

board.action(
    'Move forward', symbol=key.UP, interval=move_speed,
    hat_direction=hat_directions.UP
)(board.move(PointDirections.north))

board.action(
    'Move backwards', symbol=key.DOWN, interval=move_speed,
    hat_direction=hat_directions.DOWN
)(board.move(PointDirections.south))


def set_music_volume(value: float) -> None:
    """Set the music volume."""
    game.config.sound.music_volume.value = value
    t: Track
    for t in (intro_music, main_music):
        if t.sound_manager is not None:
            t.sound_manager.gain = value


@board.action('Music volume up', symbol=key.M, joystick_button=5)
def music_up() -> None:
    """Increase the music volume."""
    set_music_volume(min(1.0, game.config.sound.music_volume.value + 0.05))


@board.action(
    'Music volume down', symbol=key.M, modifiers=key.MOD_SHIFT,
    joystick_button=4
)
def music_down() -> None:
    """Reduce the music volume."""
    set_music_volume(max(0.0, game.config.sound.music_volume.value - 0.05))


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
            board.dispatch_event('on_move', Point(0, 0, 0))
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
    """Speak the depth of the currently selected stack."""
    l: int = len(board.current_tile)
    if not l or l > config.max_number.value:
        board.play_sound('fail.wav')
    else:
        speak(f'{l}.wav')


@board.action(
    'Help menu', symbol=key.SLASH, modifiers=key.MOD_SHIFT, joystick_button=1
)
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


@board.action(
    'Quit the game', symbol=key.Q, modifiers=key.MOD_CTRL, joystick_button=7
)
def quit_game() -> None:
    """Quit the game."""
    game.stop()


def speak(string: str) -> None:
    """Play a path from the voices directory."""
    if game.interface_sound_manager is not None:
        game.interface_sound_manager.play_path(
            voices_directory / config.voice.value / string, True
        )


main_music: Track = Track(
    'file', str(music_directory / 'main.mp3'), TrackTypes.music
)
board.tracks.append(main_music)

intro_level: IntroLevel = IntroLevel(
    game, board, voices_directory / config.voice.value / 'intro.wav', None
)
intro_level.action('Skip', symbol=key.RETURN, joystick_button=0)(
    intro_level.skip
)

intro_music: Track = Track(
    'file', str(music_directory / 'intro.mp3'), TrackTypes.music
)
intro_level.tracks.append(intro_music)

win_level: IntroLevel = IntroLevel(
    game, intro_level, sounds_directory / 'won.wav', 1.0
)


win_level.action('Skip', symbol=key.RETURN, joystick_button=0)(
    win_level.skip
)

level: IntroLevel
for level in (intro_level, win_level):
    level.action(
        'Exit', symbol=key.ESCAPE, mouse_button=mouse.RIGHT, joystick_button=7
    )(lambda: game.window.dispatch_event('on_close'))

if __name__ == '__main__':
    window: Window = Window(caption=app_name)
    game.run(window, initial_level=intro_level)
