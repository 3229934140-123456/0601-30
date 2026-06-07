import click
import json
import csv
from datetime import datetime
from .services import (
    add_media, check_duplicate, get_yearly_stats, check_stale_shows,
    get_watchlist, list_media
)
from .formatting import success, error, info, warning, console
from .formatting import print_media_list
from rich.panel import Panel
from rich.table import Table


@click.command()
@click.argument("file_path")
@click.option("--format", "fmt", type=click.Choice(["json", "csv", "imdb", "douban"]),
              default="json", help="文件格式")
@click.option("--status", default="watchlist", help="导入后的默认状态")
@click.option("--dry-run", is_flag=True, help="试运行，不实际导入")
def import_cmd(file_path, fmt, status, dry_run):
    """从外部文件导入片单

    支持格式:
    - json: JSON数组格式 [{"title": "...", "year": 2023, ...}]
    - csv: CSV格式，包含title,year,type等列
    - imdb: IMDb导出的CSV格式
    - douban: 豆瓣电影/剧集列表
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        error(f"文件不存在：{file_path}")
        return

    items = []
    if fmt == "json":
        items = _parse_json(content)
    elif fmt == "csv":
        items = _parse_csv(content)
    elif fmt == "imdb":
        items = _parse_imdb(content)
    elif fmt == "douban":
        items = _parse_douban(content)

    if not items:
        warning("没有解析到任何条目")
        return

    info(f"解析到 {len(items)} 条记录，开始导入...")

    added = 0
    skipped = 0
    failed = 0

    with click.progressbar(items, label="导入中") as bar:
        for item in bar:
            item["status"] = status
            title = item.get("title", "")
            year = item.get("year")
            media_type = item.get("type", "movie")

            if not title:
                failed += 1
                continue

            dups = check_duplicate(title, year, media_type)
            if dups:
                skipped += 1
                continue

            if not dry_run:
                try:
                    add_media(item)
                    added += 1
                except Exception:
                    failed += 1
            else:
                added += 1

    if dry_run:
        info(f"[试运行] 将导入 {added} 条，跳过 {skipped} 条重复，失败 {failed} 条")
    else:
        success(f"导入完成：新增 {added} 条，跳过重复 {skipped} 条，失败 {failed} 条")


def _parse_json(content):
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return [_normalize_item(item) for item in data]
    except json.JSONDecodeError:
        pass
    return []


def _parse_csv(content):
    import io
    reader = csv.DictReader(io.StringIO(content))
    items = []
    for row in reader:
        items.append(_normalize_item(row))
    return items


def _parse_imdb(content):
    import io
    reader = csv.DictReader(io.StringIO(content))
    items = []
    for row in reader:
        item = {
            "title": row.get("Title", ""),
            "year": int(row["Year"]) if row.get("Year", "").isdigit() else None,
            "type": "movie" if row.get("Title Type") == "movie" else "tv",
            "rating": float(row["IMDb Rating"]) if row.get("IMDb Rating") else None,
            "runtime": int(row["Runtime (mins)"]) if row.get("Runtime (mins)", "").isdigit() else None,
            "director": row.get("Directors"),
            "cast": row.get("Actors"),
            "genre": row.get("Genres"),
            "summary": row.get("Description"),
        }
        items.append(_normalize_item(item))
    return items


def _parse_douban(content):
    import io
    try:
        reader = csv.DictReader(io.StringIO(content))
        items = []
        for row in reader:
            item = {
                "title": row.get("标题", row.get("片名", "")),
                "year": int(row["年份"]) if row.get("年份", "").isdigit() else None,
                "rating": float(row["我的评分"]) if row.get("我的评分") else None,
                "director": row.get("导演"),
                "cast": row.get("主演"),
                "genre": row.get("类型"),
                "review": row.get("短评"),
                "summary": row.get("简介"),
            }
            items.append(_normalize_item(item))
        return items
    except Exception:
        return []


def _normalize_item(item):
    normalized = {}
    key_map = {
        "title": ["title", "Title", "标题", "片名", "名称"],
        "original_title": ["original_title", "originalTitle", "原名"],
        "type": ["type", "media_type", "类型"],
        "year": ["year", "Year", "年份"],
        "director": ["director", "Directors", "导演"],
        "cast": ["cast", "Actors", "actors", "主演"],
        "genre": ["genre", "Genres", "类型"],
        "runtime": ["runtime", "Runtime (mins)", "Runtime", "片长"],
        "total_seasons": ["seasons", "total_seasons", "季数"],
        "total_episodes": ["episodes", "total_episodes", "集数"],
        "summary": ["summary", "Description", "description", "简介"],
        "rating": ["rating", "我的评分", "IMDb Rating"],
        "review": ["review", "short_comment", "短评"],
        "tags": ["tags", "标签"],
        "status": ["status", "状态"],
    }

    for norm_key, possible_keys in key_map.items():
        for k in possible_keys:
            if k in item and item[k] not in (None, ""):
                val = item[k]
                if norm_key == "year" and isinstance(val, str):
                    val = int(val) if val.isdigit() else None
                if norm_key == "runtime" and isinstance(val, str):
                    val = int(val) if val.isdigit() else None
                if norm_key == "rating" and isinstance(val, str):
                    try:
                        val = float(val)
                    except ValueError:
                        val = None
                normalized[norm_key] = val
                break

    if "type" not in normalized or normalized["type"] not in ("movie", "tv"):
        normalized["type"] = "movie"

    return normalized


@click.command()
@click.argument("year", required=False, type=int)
def yearstat(year):
    """年度观影统计

    YEAR: 指定年份，默认今年
    """

    if year is None:
        year = datetime.now().year

    stats = get_yearly_stats(year)

    console.print(f"[bold magenta]📊 {year} 年度观影统计[/bold magenta]\n")

    table = Table(box=None, show_header=False)
    table.add_column(style="bold")
    table.add_column(justify="right")

    table.add_row("已看条目", str(stats.get("count") or 0))
    table.add_row("  电影", str(stats.get("movie_count") or 0))
    table.add_row("  剧集", str(stats.get("tv_count") or 0))
    table.add_row("看了集数", str(stats.get("episode_count") or 0))

    if stats.get("avg_rating") is not None:
        table.add_row("平均评分", f"⭐ {stats['avg_rating']:.1f}")

    if stats.get("total_movie_runtime"):
        hours = stats["total_movie_runtime"] // 60
        mins = stats["total_movie_runtime"] % 60
        table.add_row("电影总时长", f"{hours}小时{mins}分钟")

    console.print(Panel(table, border_style="cyan"))

    top_rated = stats.get("top_rated", [])
    if top_rated:
        console.print(f"\n[bold]🏆 年度高分 Top 10[/bold]")
        for i, item in enumerate(top_rated[:10], 1):
            rating = f"⭐ {item['rating']:.1f}" if item.get("rating") else "-"
            console.print(f"  {i:2d}. {item['title']} ({item.get('year', '?')}) - {rating}")

    top_tags = stats.get("top_tags", [])
    if top_tags:
        console.print(f"\n[bold]🏷️  年度热门标签[/bold]")
        tag_text = "  ".join(f"[magenta]#{t}[/magenta] ({c})" for t, c in top_tags)
        console.print(f"  {tag_text}")


@click.command()
@click.option("--days", "-d", type=int, default=30, help="多少天没更新算断更")
def checkstale(days):
    """检查断更的在看剧集"""

    stale_shows = check_stale_shows(days)

    if not stale_shows:
        success(f"没有断更超过 {days} 天的剧集")
        return

    warning(f"发现 {len(stale_shows)} 部可能断更的在看剧集：")
    console.print()

    for item in stale_shows:
        last_watched = item.get("last_watched_at") or "未知"
        if isinstance(last_watched, str) and "T" in last_watched:
            last_watched = last_watched.split("T")[0]
        console.print(f"  [yellow]•[/yellow] [bold]{item['title']}[/bold] - 上次观看: {last_watched}")

    console.print()
    info("可以使用 `ft drop <ID>` 标记弃剧，或者 `ft watch <ID>` 继续追更")


@click.command()
@click.option("--n", "-n", type=int, default=5, help="推荐数量")
def watchlist(n):
    """生成待看片单推荐"""

    items = get_watchlist()

    if not items:
        info("待看片单为空，快用 `ft add` 添加一些吧！")
        return

    import random
    recommendations = random.sample(items, min(n, len(items)))

    console.print(f"[bold cyan]🎲 为你推荐 {len(recommendations)} 部待看：[/bold cyan]\n")
    for i, item in enumerate(recommendations, 1):
        type_icon = "🎬" if item["type"] == "movie" else "📺"
        year = f" ({item['year']})" if item.get("year") else ""
        console.print(f"  {i}. [{item['id']}] {type_icon} [bold]{item['title']}[/bold]{year}")

    console.print()
    info("使用 `ft show <ID>` 查看详情，`ft watch <ID>` 开始观看")


@click.command()
@click.option("--year", "-y", type=int, default=None, help="指定年份")
@click.option("--month", "-m", type=int, default=None, help="指定月份")
def history(year, month):
    """查看观看历史"""

    from .database import get_connection

    conn = get_connection()
    c = conn.cursor()

    query = """
        SELECT m.title, m.type, wh.season, wh.episode, wh.watched_at
        FROM watch_history wh
        JOIN media m ON wh.media_id = m.id
        WHERE 1=1
    """
    params = []

    if year:
        query += " AND strftime('%Y', wh.watched_at) = ?"
        params.append(str(year))
    if month:
        query += " AND strftime('%m', wh.watched_at) = ?"
        params.append(f"{month:02d}")

    query += " ORDER BY wh.watched_at DESC LIMIT 100"

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    if not rows:
        info("暂无观看历史记录")
        return

    table = Table(title="📜 观看历史", box=None, show_lines=False)
    table.add_column("时间", style="dim", width=19)
    table.add_column("标题", style="bold")
    table.add_column("进度")

    for row in rows:
        watched_at = row["watched_at"].replace("T", " ")[:19]
        title = row["title"]
        if row["type"] == "tv":
            progress = f"S{row['season']}E{row['episode']}"
        else:
            progress = "🎬"

        table.add_row(watched_at, title, progress)

    console.print(table)
