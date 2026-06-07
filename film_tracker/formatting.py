from typing import Optional, Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

STATUS_LABELS = {
    "watchlist": "📋 待看",
    "watching": "🎬 在看",
    "finished": "✅ 已看",
    "dropped": "💔 弃剧",
}

STATUS_COLORS = {
    "watchlist": "yellow",
    "watching": "blue",
    "finished": "green",
    "dropped": "red",
}

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日", "未设定"]


def format_media_item(media: Dict, index: int = None) -> str:
    parts = []
    if index is not None:
        parts.append(f"[dim]{index}.[/dim]")

    parts.append(f"[bold]{media['title']}[/bold]")

    if media.get("original_title") and media["original_title"] != media["title"]:
        parts.append(f"[dim]({media['original_title']})[/dim]")

    if media.get("year"):
        parts.append(f"[cyan]{media['year']}[/cyan]")

    type_icon = "🎬" if media["type"] == "movie" else "📺"
    parts.append(f"{type_icon}")

    status = media.get("status", "watchlist")
    color = STATUS_COLORS.get(status, "white")
    label = STATUS_LABELS.get(status, status)
    parts.append(f"[{color}]{label}[/{color}]")

    if media.get("rating") is not None:
        parts.append(f"⭐ {media['rating']:.1f}")

    if media.get("rewatch_count", 0) > 0:
        parts.append(f"🔁 x{media['rewatch_count']}")

    return " ".join(parts)


def print_media_list(items: List[Dict], title: str = "片单"):
    if not items:
        console.print(Panel("[dim]暂无数据[/dim]", title=title, border_style="dim"))
        return

    table = Table(title=title, box=box.ROUNDED, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("标题", style="bold")
    table.add_column("年份", style="cyan", width=6)
    table.add_column("类型", width=6)
    table.add_column("状态")
    table.add_column("评分", style="yellow", width=8)
    table.add_column("标签", style="magenta")

    for i, item in enumerate(items, 1):
        type_label = "电影" if item["type"] == "movie" else "剧集"
        status = item.get("status", "watchlist")
        status_label = STATUS_LABELS.get(status, status)
        status_color = STATUS_COLORS.get(status, "white")
        rating = f"{item['rating']:.1f}" if item.get("rating") else "-"
        tags = ", ".join(item.get("tags_list", [])) or "-"

        table.add_row(
            str(i),
            item["title"],
            str(item.get("year", "-")),
            type_label,
            f"[{status_color}]{status_label}[/{status_color}]",
            rating,
            tags
        )

    console.print(table)
    console.print(f"共 [bold]{len(items)}[/bold] 条记录")


def print_media_detail(media: Dict):
    type_label = "电影" if media["type"] == "movie" else "剧集"
    status = media.get("status", "watchlist")
    status_label = STATUS_LABELS.get(status, status)
    status_color = STATUS_COLORS.get(status, "white")

    title_text = Text()
    title_text.append(media["title"], style="bold magenta")
    if media.get("original_title") and media["original_title"] != media["title"]:
        title_text.append(f"  ({media['original_title']})", style="dim")

    info_lines = []
    info_lines.append(f"[bold]类型:[/bold] {type_label}")
    info_lines.append(f"[bold]年份:[/bold] {media.get('year', '-')}")
    info_lines.append(f"[bold]状态:[/bold] [{status_color}]{status_label}[/{status_color}]")
    info_lines.append(f"[bold]导演:[/bold] {media.get('director') or '-'}")
    info_lines.append(f"[bold]主演:[/bold] {media.get('cast') or '-'}")
    info_lines.append(f"[bold]类型标签:[/bold] {media.get('genre') or '-'}")

    if media["type"] == "movie" and media.get("runtime"):
        info_lines.append(f"[bold]片长:[/bold] {media['runtime']} 分钟")

    if media["type"] == "tv":
        info_lines.append(f"[bold]季数:[/bold] {media.get('total_seasons', '-')} 季")
        if media.get("total_episodes"):
            info_lines.append(f"[bold]总集数:[/bold] {media['total_episodes']} 集")

    if media.get("rating") is not None:
        info_lines.append(f"[bold]评分:[/bold] ⭐ {media['rating']:.1f}")

    if media.get("rewatch_count", 0) > 0:
        info_lines.append(f"[bold]重看:[/bold] 🔁 {media['rewatch_count']} 次")

    if media.get("tags_list"):
        tags_str = " ".join(f"[{t}]" for t in media["tags_list"])
        info_lines.append(f"[bold]标签:[/bold] [magenta]{tags_str}[/magenta]")

    if media.get("review"):
        info_lines.append("")
        info_lines.append(f"[bold]短评:[/bold] {media['review']}")

    if media.get("summary"):
        info_lines.append("")
        info_lines.append(f"[bold]简介:[/bold] {media['summary']}")

    info_content = "\n".join(info_lines)
    console.print(Panel(info_content, title=title_text, border_style="magenta"))

    if media["type"] == "tv" and media.get("seasons"):
        print_season_progress(media["seasons"])


def print_season_progress(seasons: List[Dict]):
    table = Table(title="季集进度", box=box.SIMPLE, show_header=True)
    table.add_column("季", style="cyan", width=6)
    table.add_column("进度", style="green")
    table.add_column("比例", style="yellow", width=10)

    for s in seasons:
        watched = s.get("watched_episodes", 0) or 0
        total = s.get("total_episodes")

        if total:
            bar_len = 30
            filled = int(bar_len * watched / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            progress_str = f"{bar}  {watched}/{total}"
            percent = f"{watched/total*100:.0f}%"
        else:
            progress_str = f"已看 {watched} 集"
            percent = "-"

        table.add_row(f"第{s['season_number']}季", progress_str, percent)

    console.print(table)


def print_calendar(items: List[Dict]):
    if not items:
        console.print(Panel("[dim]本周没有更新剧集[/dim]", title="📅 本周更新日历", border_style="dim"))
        return

    grouped = {i: [] for i in range(8)}
    for item in items:
        wd = item.get("_weekday", 7)
        grouped[wd].append(item)

    table = Table(title="📅 本周更新日历", box=box.ROUNDED, show_lines=True)
    table.add_column("星期", style="bold cyan", width=10)
    table.add_column("剧集")

    for wd in range(8):
        day_items = grouped[wd]
        day_name = WEEKDAYS[wd]

        if day_items:
            item_texts = []
            for item in day_items:
                date_info = ""
                if item.get("_date_obj"):
                    date_info = f"[dim]({item['_date_obj'].strftime('%m/%d')})[/dim]"

                status = item.get("status", "watchlist")
                color = STATUS_COLORS.get(status, "white")
                icon = "🎬" if status == "watching" else "📋"
                item_texts.append(f"{icon} [{color}]{item['title']}[/{color}] {date_info}")
            content = "\n".join(item_texts)
        else:
            content = "[dim]无更新[/dim]"

        table.add_row(day_name, content)

    console.print(table)


def success(msg: str):
    console.print(f"[green]✓ {msg}[/green]")


def error(msg: str):
    console.print(f"[red]✗ {msg}[/red]")


def info(msg: str):
    console.print(f"[blue]ℹ {msg}[/blue]")


def warning(msg: str):
    console.print(f"[yellow]⚠ {msg}[/yellow]")
