import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from .database import get_connection


def add_media(data: Dict) -> int:
    conn = get_connection()
    c = conn.cursor()

    tags = data.pop("tags", "")

    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    values = list(data.values())

    c.execute(f"INSERT INTO media ({columns}) VALUES ({placeholders})", values)
    media_id = c.lastrowid

    if data.get("type") == "tv" and data.get("total_seasons", 1) > 0:
        seasons = data.get("total_seasons", 1)
        for s in range(1, seasons + 1):
            c.execute(
                "INSERT INTO seasons (media_id, season_number, total_episodes) VALUES (?, ?, ?)",
                (media_id, s, data.get("total_episodes"))
            )

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for tag_name in tag_list:
            c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
            c.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_id = c.fetchone()[0]
            c.execute(
                "INSERT OR IGNORE INTO media_tags (media_id, tag_id) VALUES (?, ?)",
                (media_id, tag_id)
            )

    conn.commit()
    conn.close()
    return media_id


def get_media(media_id: int) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM media WHERE id = ?", (media_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    media = dict(row)
    c.execute("SELECT name FROM tags t JOIN media_tags mt ON t.id = mt.tag_id WHERE mt.media_id = ?", (media_id,))
    media["tags_list"] = [r[0] for r in c.fetchall()]

    if media["type"] == "tv":
        c.execute("SELECT * FROM seasons WHERE media_id = ? ORDER BY season_number", (media_id,))
        media["seasons"] = [dict(r) for r in c.fetchall()]

    conn.close()
    return media


def search_media(keyword: str, media_type: str = None, status: str = None,
                 tag: str = None, director: str = None, cast: str = None) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()

    query = "SELECT DISTINCT m.* FROM media m"
    joins = []
    conditions = []
    params = []

    if tag:
        joins.append("JOIN media_tags mt ON m.id = mt.media_id")
        joins.append("JOIN tags t ON mt.tag_id = t.id")
        conditions.append("t.name LIKE ?")
        params.append(f"%{tag}%")

    if keyword:
        conditions.append("(m.title LIKE ? OR m.original_title LIKE ? OR m.summary LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

    if media_type:
        conditions.append("m.type = ?")
        params.append(media_type)

    if status:
        conditions.append("m.status = ?")
        params.append(status)

    if director:
        conditions.append("m.director LIKE ?")
        params.append(f"%{director}%")

    if cast:
        conditions.append("m.cast LIKE ?")
        params.append(f"%{cast}%")

    if joins:
        query += " " + " ".join(joins)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY m.updated_at DESC"

    c.execute(query, params)
    results = [dict(r) for r in c.fetchall()]

    for item in results:
        c.execute("SELECT name FROM tags t JOIN media_tags mt ON t.id = mt.tag_id WHERE mt.media_id = ?", (item["id"],))
        item["tags_list"] = [r[0] for r in c.fetchall()]

    conn.close()
    return results


def list_media(status: str = None, media_type: str = None, tag: str = None,
               sort: str = "updated_at", limit: int = None) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()

    query = "SELECT m.* FROM media m"
    conditions = []
    params = []

    if status:
        conditions.append("m.status = ?")
        params.append(status)

    if media_type:
        conditions.append("m.type = ?")
        params.append(media_type)

    if tag:
        query += " JOIN media_tags mt ON m.id = mt.media_id JOIN tags t ON mt.tag_id = t.id"
        conditions.append("t.name = ?")
        params.append(tag)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    sort_columns = {
        "title": "m.title ASC",
        "rating": "m.rating DESC",
        "updated": "m.updated_at DESC",
        "created": "m.created_at DESC",
        "year": "m.year DESC",
    }
    query += f" ORDER BY {sort_columns.get(sort, sort_columns['updated'])}"

    if limit:
        query += f" LIMIT {int(limit)}"

    c.execute(query, params)
    results = [dict(r) for r in c.fetchall()]

    for item in results:
        c.execute("SELECT name FROM tags t JOIN media_tags mt ON t.id = mt.tag_id WHERE mt.media_id = ?", (item["id"],))
        item["tags_list"] = [r[0] for r in c.fetchall()]

    conn.close()
    return results


def update_media(media_id: int, data: Dict) -> bool:
    if not data:
        return False

    conn = get_connection()
    c = conn.cursor()

    data["updated_at"] = datetime.now().isoformat()

    season_change = False
    new_seasons = None
    new_episodes = None

    if "total_seasons" in data:
        season_change = True
        new_seasons = data.pop("total_seasons")
    if "total_episodes" in data:
        season_change = True
        new_episodes = data.pop("total_episodes")

    if data:
        sets = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(media_id)
        c.execute(f"UPDATE media SET {sets} WHERE id = ?", values)

    if season_change:
        c.execute("SELECT type FROM media WHERE id = ?", (media_id,))
        row = c.fetchone()
        if row and row["type"] == "tv":
            if new_seasons is not None:
                c.execute("UPDATE media SET total_seasons = ? WHERE id = ?",
                          (new_seasons, media_id))
                if new_episodes is not None:
                    c.execute("UPDATE media SET total_episodes = ? WHERE id = ?",
                              (new_episodes, media_id))

                c.execute("SELECT season_number, watched_episodes, total_episodes FROM seasons WHERE media_id = ? ORDER BY season_number", (media_id,))
                existing = {r["season_number"]: dict(r) for r in c.fetchall()}

                for s_num in range(1, new_seasons + 1):
                    if s_num in existing:
                        if new_episodes is not None:
                            c.execute(
                                "UPDATE seasons SET total_episodes = ? WHERE media_id = ? AND season_number = ?",
                                (new_episodes, media_id, s_num)
                            )
                    else:
                        c.execute(
                            "INSERT INTO seasons (media_id, season_number, total_episodes, watched_episodes) VALUES (?, ?, ?, 0)",
                            (media_id, s_num, new_episodes)
                        )

                if len(existing) > new_seasons:
                    c.execute(
                        "DELETE FROM seasons WHERE media_id = ? AND season_number > ?",
                        (media_id, new_seasons)
                    )
            elif new_episodes is not None:
                c.execute("SELECT COUNT(*) as cnt FROM seasons WHERE media_id = ?", (media_id,))
                cnt = c.fetchone()["cnt"]
                if cnt == 0:
                    c.execute(
                        "INSERT INTO seasons (media_id, season_number, total_episodes, watched_episodes) VALUES (?, 1, ?, 0)",
                        (media_id, new_episodes)
                    )
                else:
                    c.execute(
                        "UPDATE seasons SET total_episodes = ? WHERE media_id = ?",
                        (new_episodes, media_id)
                    )
                c.execute("UPDATE media SET total_episodes = ? WHERE id = ?",
                          (new_episodes, media_id))

            _normalize_season_progress(c, media_id)

    conn.commit()
    affected = True
    conn.close()
    return affected


def _normalize_season_progress(cursor, media_id: int):
    cursor.execute("SELECT id, watched_episodes, total_episodes FROM seasons WHERE media_id = ?", (media_id,))
    for row in cursor.fetchall():
        total = row["total_episodes"]
        watched = row["watched_episodes"] or 0
        if total and watched > total:
            cursor.execute(
                "UPDATE seasons SET watched_episodes = ? WHERE id = ?",
                (total, row["id"])
            )


def delete_media(media_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM media WHERE id = ?", (media_id,))
    conn.commit()
    affected = c.rowcount > 0
    conn.close()
    return affected


def check_duplicate(title: str, year: int = None, media_type: str = None) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()

    query = "SELECT * FROM media WHERE title = ?"
    params = [title]

    if year:
        query += " AND year = ?"
        params.append(year)

    if media_type:
        query += " AND type = ?"
        params.append(media_type)

    c.execute(query, params)
    results = [dict(r) for r in c.fetchall()]
    conn.close()
    return results


def watch_episode(media_id: int, season: int, episode: int) -> Dict:
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM seasons WHERE media_id = ? AND season_number = ?", (media_id, season))
    season_row = c.fetchone()

    if not season_row:
        c.execute(
            "INSERT INTO seasons (media_id, season_number, watched_episodes) VALUES (?, ?, 0)",
            (media_id, season)
        )
        c.execute("SELECT * FROM seasons WHERE id = ?", (c.lastrowid,))
        season_row = c.fetchone()

    total_episodes = season_row["total_episodes"]
    current_watched = season_row["watched_episodes"] or 0

    if total_episodes and episode > total_episodes:
        conn.close()
        return {
            "media_id": media_id,
            "season": season,
            "episode": current_watched,
            "requested_episode": episode,
            "total_episodes": total_episodes,
            "status": "over_limit",
            "already_finished": current_watched >= total_episodes
        }

    if total_episodes and current_watched >= total_episodes:
        conn.close()
        return {
            "media_id": media_id,
            "season": season,
            "episode": current_watched,
            "requested_episode": episode,
            "total_episodes": total_episodes,
            "status": "already_finished"
        }

    if episode <= current_watched:
        conn.close()
        return {
            "media_id": media_id,
            "season": season,
            "episode": current_watched,
            "requested_episode": episode,
            "total_episodes": total_episodes,
            "status": "already_watched"
        }

    new_watched = episode

    c.execute(
        "UPDATE seasons SET watched_episodes = ? WHERE id = ?",
        (new_watched, season_row["id"])
    )

    c.execute(
        "INSERT INTO watch_history (media_id, season, episode) VALUES (?, ?, ?)",
        (media_id, season, episode)
    )

    c.execute("SELECT total_seasons FROM media WHERE id = ?", (media_id,))
    total_seasons = c.fetchone()["total_seasons"] or 1

    c.execute("SELECT * FROM seasons WHERE media_id = ? ORDER BY season_number", (media_id,))
    all_seasons = c.fetchall()

    all_finished = True
    for s in all_seasons:
        total = s["total_episodes"]
        watched = s["watched_episodes"] or 0
        if total and watched < total:
            all_finished = False
            break
        if not total and watched == 0:
            all_finished = False
            break

    status = "finished" if all_finished else "watching"

    c.execute(
        "UPDATE media SET status = ?, last_watched_at = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), datetime.now().isoformat(), media_id)
    )

    conn.commit()
    conn.close()

    return {
        "media_id": media_id,
        "season": season,
        "episode": new_watched,
        "requested_episode": episode,
        "total_episodes": total_episodes,
        "status": status,
        "all_finished": all_finished
    }


def get_seasons(media_id: int) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM seasons WHERE media_id = ? ORDER BY season_number", (media_id,))
    results = [dict(r) for r in c.fetchall()]
    conn.close()
    return results


def set_rating(media_id: int, rating: float, review: str = None) -> bool:
    conn = get_connection()
    c = conn.cursor()

    data = {"rating": rating, "updated_at": datetime.now().isoformat()}
    if review is not None:
        data["review"] = review

    sets = ", ".join([f"{k} = ?" for k in data.keys()])
    values = list(data.values())
    values.append(media_id)

    c.execute(f"UPDATE media SET {sets} WHERE id = ?", values)
    conn.commit()
    affected = c.rowcount > 0
    conn.close()
    return affected


def add_tags(media_id: int, tags: List[str]) -> bool:
    conn = get_connection()
    c = conn.cursor()

    for tag_name in tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        c.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = c.fetchone()[0]
        c.execute(
            "INSERT OR IGNORE INTO media_tags (media_id, tag_id) VALUES (?, ?)",
            (media_id, tag_id)
        )

    conn.commit()
    conn.close()
    return True


def remove_tags(media_id: int, tags: List[str]) -> bool:
    conn = get_connection()
    c = conn.cursor()

    for tag_name in tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        c.execute(
            "DELETE FROM media_tags WHERE media_id = ? AND tag_id IN (SELECT id FROM tags WHERE name = ?)",
            (media_id, tag_name)
        )

    conn.commit()
    conn.close()
    return True


def list_all_tags() -> List[Tuple[str, int]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT t.name, COUNT(mt.media_id) as count
        FROM tags t LEFT JOIN media_tags mt ON t.id = mt.tag_id
        GROUP BY t.id ORDER BY count DESC, t.name ASC
    """)
    results = [(r[0], r[1]) for r in c.fetchall()]
    conn.close()
    return results


def set_status(media_id: int, status: str) -> bool:
    return update_media(media_id, {"status": status})


def increment_rewatch(media_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT rewatch_count FROM media WHERE id = ?", (media_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0
    new_count = (row["rewatch_count"] or 0) + 1
    c.execute(
        "UPDATE media SET rewatch_count = ?, updated_at = ? WHERE id = ?",
        (new_count, datetime.now().isoformat(), media_id)
    )
    conn.commit()
    conn.close()
    return new_count


def get_weekly_calendar() -> Dict[str, List]:
    conn = get_connection()
    c = conn.cursor()

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    c.execute("""
        SELECT * FROM media
        WHERE type = 'tv' AND status IN ('watching', 'watchlist')
        ORDER BY next_episode_date IS NULL, next_episode_date ASC
    """)

    weekly_items = [[] for _ in range(7)]
    unscheduled_items = []
    upcoming_items = []
    past_items = []

    for row in c.fetchall():
        item = dict(row)
        next_date = item.get("next_episode_date")

        if not next_date:
            unscheduled_items.append(item)
            continue

        try:
            nd = date.fromisoformat(next_date[:10])
        except (ValueError, TypeError):
            unscheduled_items.append(item)
            continue

        item["_date_obj"] = nd

        if nd < today:
            past_items.append(item)
        elif start_of_week <= nd <= end_of_week:
            weekly_items[nd.weekday()].append(item)
        else:
            upcoming_items.append(item)

    conn.close()
    return {
        "weekly": weekly_items,
        "upcoming": upcoming_items,
        "past": past_items,
        "unscheduled": unscheduled_items,
        "start_of_week": start_of_week,
        "end_of_week": end_of_week,
        "today": today,
    }


def get_yearly_stats(year: int) -> Dict:
    conn = get_connection()
    c = conn.cursor()

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    c.execute("""
        SELECT COUNT(*) as count,
               SUM(CASE WHEN type = 'movie' THEN 1 ELSE 0 END) as movie_count,
               SUM(CASE WHEN type = 'tv' THEN 1 ELSE 0 END) as tv_count,
               AVG(rating) as avg_rating,
               SUM(CASE WHEN type = 'movie' THEN runtime ELSE 0 END) as total_movie_runtime
        FROM media
        WHERE status = 'finished'
        AND strftime('%Y', last_watched_at) = ?
    """, (str(year),))

    row = dict(c.fetchone())

    c.execute("""
        SELECT COUNT(*) as episode_count
        FROM watch_history
        WHERE strftime('%Y', watched_at) = ?
    """, (str(year),))

    ep_row = c.fetchone()
    row["episode_count"] = ep_row[0] if ep_row else 0

    c.execute("""
        SELECT m.* FROM media m
        JOIN watch_history wh ON m.id = wh.media_id
        WHERE strftime('%Y', wh.watched_at) = ?
        GROUP BY m.id
        ORDER BY m.rating DESC NULLS LAST
        LIMIT 10
    """, (str(year),))

    row["top_rated"] = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT t.name, COUNT(*) as cnt
        FROM tags t
        JOIN media_tags mt ON t.id = mt.tag_id
        JOIN media m ON mt.media_id = m.id
        WHERE m.status = 'finished'
        AND strftime('%Y', m.last_watched_at) = ?
        GROUP BY t.id
        ORDER BY cnt DESC
        LIMIT 10
    """, (str(year),))

    row["top_tags"] = [(r[0], r[1]) for r in c.fetchall()]

    conn.close()
    return row


def get_dropped_media() -> List[Dict]:
    return list_media(status="dropped")


def get_watchlist() -> List[Dict]:
    return list_media(status="watchlist")


def add_season(media_id: int, season_number: int, total_episodes: int = None) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO seasons (media_id, season_number, total_episodes) VALUES (?, ?, ?)",
        (media_id, season_number, total_episodes)
    )
    conn.commit()

    c.execute("SELECT COUNT(*) FROM seasons WHERE media_id = ?", (media_id,))
    count = c.fetchone()[0]
    c.execute("UPDATE media SET total_seasons = ? WHERE id = ?", (count, media_id))
    conn.commit()

    season_id = c.lastrowid
    conn.close()
    return season_id


def check_stale_shows(days: int = 30) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    c.execute("""
        SELECT * FROM media
        WHERE type = 'tv' AND status = 'watching'
        AND (last_watched_at IS NULL OR last_watched_at < ?)
        ORDER BY last_watched_at ASC
    """, (cutoff,))

    results = [dict(r) for r in c.fetchall()]
    conn.close()
    return results
