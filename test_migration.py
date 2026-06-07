import os
import sys
import tempfile
import sqlite3
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from film_tracker import database


def test_migration():
    test_dir = os.path.join(tempfile.gettempdir(), "film_tracker_migration_test")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)

    db_path = os.path.join(test_dir, "film_tracker.db")
    database.DB_PATH = db_path

    print("🧪 测试数据库迁移")
    print(f"   测试数据库: {db_path}")

    print("\n1️⃣ 创建旧版本数据库（无 next_episode_date 字段）")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            year INTEGER,
            director TEXT,
            cast TEXT,
            total_seasons INTEGER DEFAULT 1,
            total_episodes INTEGER,
            status TEXT DEFAULT 'watchlist',
            rating REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_watched_at TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO media (title, type, year, director, status)
        VALUES ('旧版电影', 'movie', 2020, '老导演', 'watchlist')
    """)
    c.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()
    print("   ✅ 旧库创建完成，含 1 条测试数据")

    print("\n2️⃣ 运行迁移...")
    database.ensure_db()
    print("   ✅ 迁移完成，无报错")

    print("\n3️⃣ 验证迁移结果")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("PRAGMA user_version")
    version = c.fetchone()[0]
    print(f"   schema 版本: {version} (期望: {database.SCHEMA_VERSION})")
    assert version == database.SCHEMA_VERSION, f"版本号错误: {version}"

    c.execute("PRAGMA table_info(media)")
    columns = [row[1] for row in c.fetchall()]
    print(f"   列数: {len(columns)}")
    assert "next_episode_date" in columns, "缺少 next_episode_date 列"
    print("   ✅ next_episode_date 列已添加")

    c.execute("SELECT title, status FROM media WHERE id = 1")
    row = c.fetchone()
    assert row[0] == "旧版电影", "原有数据丢失"
    print(f"   ✅ 原有数据保留: {row[0]} [{row[1]}]")

    c.execute("SELECT next_episode_date FROM media WHERE id = 1")
    date_val = c.fetchone()[0]
    assert date_val is None, "新字段应有默认值 NULL"
    print("   ✅ 新字段默认值为 NULL")

    conn.close()

    print("\n4️⃣ 测试在迁移后的库上运行命令")
    from click.testing import CliRunner
    from film_tracker.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["add", "新版测试", "--type", "movie"], catch_exceptions=False)
    print(f"   add 输出:\n{result.output}")
    assert result.exit_code == 0, f"添加失败: {result.output}"
    print("   ✅ 可以正常添加新条目")

    result = runner.invoke(cli, ["list"], catch_exceptions=False)
    print(f"   list 输出:\n{result.output}")
    assert result.exit_code == 0, f"列表失败: {result.output}"
    assert "旧版电影" in result.output, "旧数据不在列表中"
    assert "新版测试" in result.output, "新数据不在列表中"
    print("   ✅ list 命令正常显示新旧数据")

    result = runner.invoke(cli, ["calendar"], catch_exceptions=False)
    assert result.exit_code == 0, f"日历失败: {result.output}"
    print("   ✅ calendar 命令正常运行，无报错")

    print("\n✅ 迁移测试全部通过！旧库数据保留完好，新功能正常工作")

    shutil.rmtree(test_dir)
    return True


if __name__ == "__main__":
    try:
        test_migration()
    except Exception as e:
        import traceback
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        sys.exit(1)
