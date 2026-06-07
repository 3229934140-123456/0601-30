import click
from .services import (
    get_media, watch_episode, get_seasons, set_rating,
    add_tags, remove_tags, list_all_tags, set_status,
    update_media
)
from .formatting import (
    success, error, info, warning, print_media_detail,
    print_season_progress, console
)


@click.command()
@click.argument("media_id", type=int)
@click.option("--season", "-s", type=int, default=1, help="季数，默认第1季")
@click.option("--episode", "-e", type=int, help="看到第几集（默认+1集）")
@click.option("--next", "next_ep", is_flag=True, help="看下一集（默认行为）")
@click.option("--finish", is_flag=True, help="标记该季看完")
def watch(media_id, season, episode, next_ep, finish):
    """记录观看进度"""

    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    if media["type"] != "tv":
        from datetime import datetime
        if finish:
            update_media(media_id, {
                "status": "finished",
                "last_watched_at": datetime.now().isoformat()
            })
            success(f"已看完：{media['title']}")
        else:
            set_status(media_id, "watching")
            success(f"开始观看：{media['title']}")
        return

    seasons = get_seasons(media_id)
    season_map = {s["season_number"]: s for s in seasons}

    if season not in season_map:
        warning(f"第{season}季不存在，已自动创建")
        from .services import add_season
        add_season(media_id, season)
        current_watched = 0
    else:
        current_watched = season_map[season]["watched_episodes"] or 0

    if finish:
        season_data = season_map.get(season)
        if season_data and season_data.get("total_episodes"):
            episode = season_data["total_episodes"]
        else:
            error("该季没有设置总集数，无法标记完成")
            return
    elif episode is None:
        episode = current_watched + 1

    if episode <= current_watched:
        info(f"第{season}季第{episode}集已经看过了")
        print_season_progress(get_seasons(media_id))
        return

    result = watch_episode(media_id, season, episode)
    success(f"已记录：{media['title']} 第{season}季第{episode}集")

    if result["status"] == "finished":
        info("🎉 恭喜！这部剧已全部看完")

    updated = get_media(media_id)
    print_season_progress(updated.get("seasons", []))


@click.command()
@click.argument("media_id", type=int)
@click.argument("rating", type=float)
@click.option("--review", "-r", help="短评内容")
def rate(media_id, rating, review):
    """评分和写短评"""

    if rating < 0 or rating > 10:
        error("评分必须在 0-10 之间")
        return

    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    if set_rating(media_id, rating, review):
        success(f"已评分：{media['title']} ⭐ {rating:.1f}")
        if review:
            info(f"短评：{review}")
    else:
        error("评分失败")


@click.command(name="search")
@click.argument("keyword", required=False)
@click.option("--tag", "-t", help="按标签搜索")
@click.option("--director", "-d", help="按导演搜索")
@click.option("--cast", "-c", help="按演员搜索")
@click.option("--type", "media_type", type=click.Choice(["movie", "tv"]), help="按类型筛选")
@click.option("--status", "-s", type=click.Choice(["watchlist", "watching", "finished", "dropped"]),
              help="按状态筛选")
def search_cmd(keyword, tag, director, cast, media_type, status):
    """搜索本地片库"""

    from .services import search_media
    from .formatting import print_media_list

    if not keyword and not tag and not director and not cast:
        error("请提供搜索关键词或筛选条件")
        return

    results = search_media(
        keyword or "",
        media_type=media_type,
        status=status,
        tag=tag,
        director=director,
        cast=cast
    )

    title = "搜索结果"
    conditions = []
    if keyword:
        conditions.append(f"\"{keyword}\"")
    if tag:
        conditions.append(f"#{tag}")
    if director:
        conditions.append(f"导演:{director}")
    if cast:
        conditions.append(f"演员:{cast}")
    if conditions:
        title += ": " + " ".join(conditions)

    print_media_list(results, title=title)


@click.command()
def calendar():
    """查看本周更新日历"""

    from .services import get_weekly_calendar
    from .formatting import print_calendar

    items = get_weekly_calendar()
    print_calendar(items)


@click.command(name="export")
@click.option("--output", "-o", default="film_tracker.md", help="输出文件名")
@click.option("--status", "-s", type=click.Choice(["watchlist", "watching", "finished", "dropped"]),
              help="按状态筛选导出")
@click.option("--type", "media_type", type=click.Choice(["movie", "tv"]), help="按类型筛选")
@click.option("--tag", "-t", help="按标签筛选")
@click.option("--format", "fmt", type=click.Choice(["markdown", "csv"]), default="markdown",
              help="导出格式")
def export_cmd(output, status, media_type, tag, fmt):
    """导出门单"""

    from .services import list_media, get_media

    items = list_media(status=status, media_type=media_type, tag=tag)

    if not items:
        warning("没有可导出的数据")
        return

    if fmt == "markdown":
        content = _export_markdown(items)
    else:
        content = _export_csv(items)

    with open(output, "w", encoding="utf-8") as f:
        f.write(content)

    success(f"已导出 {len(items)} 条记录到 {output}")


def _export_markdown(items):
    from datetime import datetime

    lines = []
    lines.append("# 影视片单")
    lines.append("")
    lines.append(f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")

    by_status = {}
    for item in items:
        s = item.get("status", "watchlist")
        by_status.setdefault(s, []).append(item)

    status_order = ["watching", "watchlist", "finished", "dropped"]
    status_names = {
        "watching": "📺 在看",
        "watchlist": "📋 待看",
        "finished": "✅ 已看完",
        "dropped": "💔 弃剧",
    }

    for s in status_order:
        if s not in by_status:
            continue
        lines.append(f"## {status_names.get(s, s)}")
        lines.append("")

        s_items = by_status[s]
        if s_items and s_items[0]["type"] == "tv" and s == "watching":
            for item in s_items:
                detail = get_media(item["id"])
                progress = ""
                if detail.get("seasons"):
                    for season in detail["seasons"]:
                        w = season.get("watched_episodes", 0) or 0
                        t = season.get("total_episodes") or "?"
                        progress += f" S{season['season_number']}: {w}/{t}"

                rating = f" ⭐{item['rating']:.1f}" if item.get("rating") else ""
                tags = f" `{', '.join(item.get('tags_list', []))}`" if item.get("tags_list") else ""
                lines.append(f"- **{item['title']}**{progress}{rating}{tags}")
                if item.get("review"):
                    lines.append(f"  > {item['review']}")
        else:
            for item in s_items:
                rating = f" ⭐{item['rating']:.1f}" if item.get("rating") else ""
                year = f" ({item['year']})" if item.get("year") else ""
                tags = f" `{', '.join(item.get('tags_list', []))}`" if item.get("tags_list") else ""
                lines.append(f"- **{item['title']}**{year}{rating}{tags}")
                if item.get("review"):
                    lines.append(f"  > {item['review']}")

        lines.append("")

    return "\n".join(lines)


def _export_csv(items):
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "类型", "年份", "状态", "评分", "导演", "标签", "短评"])

    for item in items:
        tags = ", ".join(item.get("tags_list", []))
        writer.writerow([
            item["id"],
            item["title"],
            "电影" if item["type"] == "movie" else "剧集",
            item.get("year", ""),
            item.get("status", ""),
            item.get("rating", ""),
            item.get("director", ""),
            tags,
            item.get("review", "") or ""
        ])

    return output.getvalue()


@click.command()
@click.argument("media_id", type=int)
@click.argument("tags", nargs=-1)
@click.option("--remove", "-r", is_flag=True, help="移除标签而不是添加")
def tag(media_id, tags, remove):
    """为条目添加/移除标签"""

    media = get_media(media_id)
    if not media:
        error(f"未找到 ID 为 {media_id} 的条目")
        return

    if not tags:
        info(f"当前标签：{', '.join(media.get('tags_list', [])) or '无'}")
        return

    if remove:
        remove_tags(media_id, list(tags))
        success(f"已移除标签：{', '.join(tags)}")
    else:
        add_tags(media_id, list(tags))
        success(f"已添加标签：{', '.join(tags)}")

    updated = get_media(media_id)
    info(f"当前标签：{', '.join(updated.get('tags_list', [])) or '无'}")


@click.command(name="tags")
def tags_cmd():
    """列出所有标签"""

    tags = list_all_tags()
    if not tags:
        info("暂无标签")
        return

    console.print("[bold]所有标签:[/bold]")
    for name, count in tags:
        console.print(f"  [magenta]#{name}[/magenta] ({count})")
