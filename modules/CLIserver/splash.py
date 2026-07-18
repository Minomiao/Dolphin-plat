"""启动动画：Dolphin ASCII 艺术与进度条。"""
import time

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

from modules.bootstrap import constants
from .state import ui

_console = Console()

_DOLPHIN_ART = constants.DOLPHIN_ART
_DEEPSLEEPING = constants.DEEPSLEEPING_TEXT


def progress_bar(percent, label):
    """更新启动进度条。"""
    if ui.progress is None:
        ui.progress = Progress(
            BarColumn(bar_width=25, style="dim", complete_style="cyan", finished_style="cyan"),
            TextColumn("[bright_blue]{task.percentage:>3.0f}%"),
            TextColumn("{task.description}"),
        )
        ui.progress.start()
        ui.progress.add_task("", total=100)
        ui.progress.console.print()
    ui.progress.tasks[0].completed = percent
    ui.progress.tasks[0].description = label
    ui.progress.refresh()
    if percent >= 100:
        ui.progress.stop()
        ui.progress = None


def print_dolphin():
    """打印 Dolphin ASCII 艺术。"""
    _console.print(Text(_DOLPHIN_ART, style="bright_blue"))


def show_splash():
    """显示启动 splash。"""
    print_dolphin()
    print()
