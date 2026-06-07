import click
from rich import print
from .database import ensure_db, init_db

from .commands_basic import (
    add, edit, remove, drop, rewatch, list_cmd, show, stats
)
from .commands_watch import (
    watch, rate, search_cmd, calendar, export_cmd, tag, tags_cmd
)
from .commands_advanced import (
    import_cmd, yearstat, checkstale, watchlist, history
)


@click.group(
    help="""
Film Tracker - 终端影视追踪工具

为习惯用终端管理片单的影迷打造的影视追踪工具。
支持电影/剧集管理、季集进度追踪、打分短评、标签分类等功能。

快速开始:
  ft add "盗梦空间" --type movie --year 2010
  ft add "怪奇物语" --type tv --seasons 4 --episodes 9
  ft watch 2 --season 1 --episode 3
  ft rate 1 9.0 --review "神作"
  ft list --status watching
""",
    context_settings={"help_option_names": ["-h", "--help"]}
)
@click.version_option(version="1.0.0", prog_name="film-tracker")
def cli():
    """影视追踪 CLI 工具"""
    ensure_db()


cli.add_command(add)
cli.add_command(edit)
cli.add_command(remove, name="rm")
cli.add_command(drop)
cli.add_command(rewatch)
cli.add_command(list_cmd, name="list")
cli.add_command(show)
cli.add_command(stats)
cli.add_command(watch)
cli.add_command(rate)
cli.add_command(search_cmd, name="search")
cli.add_command(calendar)
cli.add_command(export_cmd, name="export")
cli.add_command(import_cmd, name="import")
cli.add_command(tag)
cli.add_command(tags_cmd, name="tags")
cli.add_command(yearstat)
cli.add_command(checkstale)
cli.add_command(watchlist)
cli.add_command(history)


@cli.command(name="init")
def init_cmd():
    """初始化数据库"""
    init_db()
    click.echo("数据库已初始化完成")


if __name__ == "__main__":
    cli()
