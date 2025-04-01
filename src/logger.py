from rich.console import Console
from rich.table import Table
import logging
from datetime import datetime

# Cấu hình logger với rich
console = Console()

class RichLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        self.logger.addHandler(handler)

    def info(self, message: str):
        self.logger.info(message)
        console.print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [bold green][INFO][/bold green] {message}")

    def warn(self, message: str):
        self.logger.warning(message)
        console.print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [bold yellow][WARN][/bold yellow] {message}")

    def error(self, message: str):
        self.logger.error(message)
        console.print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [bold red][ERROR][/bold red] {message}")

    def info_table(self, data: dict, title: str):
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Max Pool Size", f"{data['maxPoolSize']} {data['unit']}")
        table.add_row("Total Staked", f"{data['totalStaked']} {data['unit']}")
        table.add_row("Available Space", f"{data['availableSpace']} {data['unit']}")
        console.print(table)

logger = RichLogger("link-staking-cron")