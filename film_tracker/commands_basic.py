import click
from .services import (
    add_media, check_duplicate, get_media, list_media,
    update_media, delete_media, set_status, increment_rewatch
)
from .formatting import success, error, info, warning, print_media_detail, console


@click.command()
@click.argument("title")
@click.option("--type", "media_type", type=click.Choice(["movie", "tv"]), default="movie", help="类型：电影或剧集")
@click.option("--year", "-y", type=int, help="年份")
@click.option("--original-title", help="原名")
@click.option("--director", "-d", help="导演")
@click.option("--cast", help="主演，逗号分隔")
@click.option("--genre", "-g", help="类型标签，逗号分隔")
@click.option("--seasons", "-s", type=int, default=1, help="总季数（剧集）")
@click.option("--episodes", "-e", type=int, help="每季集数（剧集）")
@click.option("--runtime", "-r", type=int, help="片长（分钟，电影）")
@click.option("--summary", help="简介")
@click.option("--tags", "-t", help="标签，逗号分隔")
@click.option("--status", type=click.Choice(["watchlist", "watching", "finished", "dropped"]),
              default="watchlist", help="状态")
@click.option("--force", is_flag=True, help="跳过重复检查强制添加")
def add(title, media_type, year, original_title, director, cast, genre,
        seasons, episodes, runtime, summary, tags, status, force):
    """添加影视条目到片单"""

    if not force:
        duplicates = check_duplicate(title, year, media_type)
        if duplicates:
            warning(f"发现 {len(duplicates)} 条可能重复的条目：")
            for d in duplicates:
                status_label = d.get("status", "")
                console.print(f"  - [{d['id']}] {d['title']} ({d.get('year', '?')}) [{status_label}]")
            if not click.confirm("是否继续添加？", default=False):
                error("已取消")
                return

    data = {
        "title": title,
        "type": media_type,
        "year": year,
        "original_title": original_title,
        "director": director,
        "cast": cast,
        "genre": genre,
        "total_seasons": seasons if media_type == "tv" else 1,
        "total_episodes": episodes if media_type == "tv" else None,
        "runtime": runtime if media_type == "movie" else None,
        "summary": summary,
        "tags": tags,
        "status": status,
    }

    try:
        media_id = add_media(data)
        success(f"已添加：{title} (ID: {media_id})")
        media = get_media(media_id)
        if media:
            print_media_detail(media)
    except Exception as e:
        error(f"添加失败：{e}")


@click.command()
@click.argument("media_id", type=int)
@click.option("--title", help="标题")
@click.option("--year", type=int, help="年份")
@click.option("--director", help="导演")
@click.option("--cast", help="主演")
@click.option("--genre", help="类型")
@click.option("--seasons", type=int, help="总季数")
@click.option("--episodes", type=int, help="总集数")
@click.option("--runtime", type=int, help="片长")
@click.option("--summary", help="简介")
@click.option("--status", type=click.Choice(["watchlist", "watching", "finished", "dropped"]), help="状态")
def edit(media_id, **kwargs):
    """编辑影视条目信息"""

    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    updates = {k: v for k, v in kwargs.items() if v is not None}
    if not updates:
        info("没有要更新的内容")
        return

    if update_media(media_id, updates):
        success(f"已更新：{media['title']}")
        updated = get_media(media_id)
        print_media_detail(updated)
    else:
        error("更新失败")


@click.command()
@click.argument("media_id", type=int)
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def remove(media_id, yes):
    """删除影视条目"""

    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    if not yes:
        if not click.confirm(f"确定要删除「{media['title']}」吗？", default=False):
            error("已取消")
            return

    if delete_media(media_id):
        success(f"已删除：{media['title']}")
    else:
        error("删除失败")


@click.command()
@click.argument("media_id", type=int)
def drop(media_id):
    """标记为弃剧"""
    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    if set_status(media_id, "dropped"):
        success(f"已标记弃剧：{media['title']}")
    else:
        error("操作失败")


@click.command()
@click.argument("media_id", type=int)
def rewatch(media_id):
    """记录重看一次"""
    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    count = increment_rewatch(media_id)
    success(f"已记录重看：{media['title']} (第 {count} 次重看)")


@click.command(name="list")
@click.option("--status", "-s", type=click.Choice(["watchlist", "watching", "finished", "dropped"]),
              help="按状态筛选")
@click.option("--type", "media_type", type=click.Choice(["movie", "tv"]), help="按类型筛选")
@click.option("--tag", "-t", help="按标签筛选")
@click.option("--sort", type=click.Choice(["title", "rating", "updated", "created", "year"]),
              default="updated", help="排序方式")
@click.option("--limit", "-n", type=int, help="显示数量限制")
def list_cmd(status, media_type, tag, sort, limit):
    """列出片单"""
    from .formatting import print_media_list

    items = list_media(status=status, media_type=media_type, tag=tag, sort=sort, limit=limit)

    title_parts = ["片单"]
    if status:
        from .formatting import STATUS_LABELS
        title_parts.append(STATUS_LABELS.get(status, status))
    if media_type:
        title_parts.append("电影" if media_type == "movie" else "剧集")
    if tag:
        title_parts.append(f"#{tag}")

    print_media_list(items, title=" - ".join(title_parts))


@click.command()
@click.argument("media_id", type=int)
def show(media_id):
    """查看条目详情"""
    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return
    print_media_detail(media)


@click.command()
@click.option("--watchlist", "show_watchlist", is_flag=True, help="显示待看片单")
@click.option("--watching", is_flag=True, help="显示在看片单")
@click.option("--finished", is_flag=True, help="显示已看完片单")
@click.option("--dropped", is_flag=True, help="显示弃剧片单")
@click.option("--movies", is_flag=True, help="仅电影")
@click.option("--tv", is_flag=True, help="仅剧集")
def stats(show_watchlist, watching, finished, dropped, movies, tv):
    """查看统计概览"""
    from .formatting import console, STATUS_LABELS, STATUS_COLORS
    from rich.panel import Panel
    from rich.table import Table

    all_items = list_media()

    total = len(all_items)
    by_status = {}
    by_type = {}

    for item in all_items:
        s = item.get("status", "watchlist")
        by_status[s] = by_status.get(s, 0) + 1
        t = item["type"]
        by_type[t] = by_type.get(t, 0) + 1

    table = Table(title="📊 片库统计", box=None, show_header=False)
    table.add_column(style="bold")
    table.add_column(justify="right")

    table.add_row("总条目数", str(total))
    table.add_row("电影", str(by_type.get("movie", 0)))
    table.add_row("剧集", str(by_type.get("tv", 0)))
    table.add_row("", "")

    for status_key in ["watchlist", "watching", "finished", "dropped"]:
        count = by_status.get(status_key, 0)
        label = STATUS_LABELS.get(status_key, status_key)
        color = STATUS_COLORS.get(status_key, "white")
        table.add_row(f"[{color}]{label}[/{color}]", f"[{color}]{count}[/{color}]")

    rated_items = [i for i in all_items if i.get("rating") is not None]
    if rated_items:
        avg_rating = sum(i["rating"] for i in rated_items) / len(rated_items)
        table.add_row("", "")
        table.add_row("平均评分", f"⭐ {avg_rating:.1f}")

    console.print(Panel(table, border_style="blue"))

    from .services import list_all_tags
    tags = list_all_tags()
    if tags:
        tag_text = " ".join(f"[magenta]#{t}[/magenta] ({c})" for t, c in tags[:10])
        console.print(f"\n[bold]热门标签:[/bold] {tag_text}")
