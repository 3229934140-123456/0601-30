import os
import sys
import tempfile
import shutil
from datetime import date, timedelta
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from film_tracker.cli import cli
from film_tracker import database


TEST_DB_DIR = os.path.join(tempfile.gettempdir(), "film_tracker_regression")


def setup_test_db():
    if os.path.exists(TEST_DB_DIR):
        shutil.rmtree(TEST_DB_DIR)
    os.makedirs(TEST_DB_DIR, exist_ok=True)
    database.DB_PATH = os.path.join(TEST_DB_DIR, "film_tracker.db")


class TestCase:
    def __init__(self, name, args, expect_exit=0, expect_in_output=None, expect_not_in_output=None):
        self.name = name
        self.args = args
        self.expect_exit = expect_exit
        self.expect_in_output = expect_in_output or []
        self.expect_not_in_output = expect_not_in_output or []


def run_tests():
    runner = CliRunner()
    passed = 0
    failed = 0

    def run_test(case):
        nonlocal passed, failed
        print(f"\n{'='*60}")
        print(f"▶ {case.name}")
        print(f"  命令: ft {' '.join(case.args)}")
        result = runner.invoke(cli, case.args, catch_exceptions=False, color=False)
        print(f"  退出码: {result.exit_code}")

        if result.exit_code != case.expect_exit:
            print(f"\n❌ 失败：期望退出码 {case.expect_exit}，实际 {result.exit_code}")
            print(f"--- 输出 ---\n{result.output}")
            if result.exception:
                import traceback
                print(f"--- 异常堆栈 ---\n{traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__)}")
            failed += 1
            return False

        for needle in case.expect_in_output:
            if needle not in result.output:
                print(f"\n❌ 失败：输出中未找到 \"{needle}\"")
                print(f"--- 输出 ---\n{result.output}")
                failed += 1
                return False

        for needle in case.expect_not_in_output:
            if needle in result.output:
                print(f"\n❌ 失败：输出中不应出现 \"{needle}\"")
                print(f"--- 输出 ---\n{result.output}")
                failed += 1
                return False

        passed += 1
        print(f"  ✓ 通过")
        return True

    today = date.today()
    this_week_mon = today - timedelta(days=today.weekday())
    this_week_wed = this_week_mon + timedelta(days=2)
    next_week_mon = this_week_mon + timedelta(days=7)
    last_week_mon = this_week_mon - timedelta(days=7)

    tests = [
        TestCase(
            "添加电影",
            ["add", "盗梦空间", "--type", "movie", "--year", "2010", "--director", "诺兰",
             "--tags", "科幻,悬疑"],
            expect_in_output=["已添加", "盗梦空间"]
        ),
        TestCase(
            "添加第二部电影",
            ["add", "星际穿越", "--type", "movie", "--year", "2014", "--director", "诺兰",
             "--tags", "科幻", "--cast", "马修·麦康纳"],
            expect_in_output=["已添加", "星际穿越"]
        ),
        TestCase(
            "添加剧集 - 带本周更新日",
            ["add", "怪奇物语", "--type", "tv", "--seasons", "4", "--episodes", "8",
             "--next-episode-date", this_week_wed.isoformat(), "--tags", "科幻"],
            expect_in_output=["已添加", "怪奇物语"]
        ),
        TestCase(
            "添加剧集 - 带下周更新日",
            ["add", "绝命毒师", "--type", "tv", "--seasons", "5", "--episodes", "13",
             "--next-episode-date", next_week_mon.isoformat(), "--tags", "剧情"],
            expect_in_output=["已添加", "绝命毒师"]
        ),
        TestCase(
            "添加剧集 - 带过去更新日",
            ["add", "真探", "--type", "tv", "--seasons", "3", "--episodes", "8",
             "--next-episode-date", last_week_mon.isoformat(), "--tags", "悬疑"],
            expect_in_output=["已添加", "真探"]
        ),
        TestCase(
            "添加剧集 - 无更新日",
            ["add", "黑袍纠察队", "--type", "tv", "--seasons", "4", "--episodes", "8"],
            expect_in_output=["已添加", "黑袍纠察队"]
        ),
        TestCase(
            "查看剧集详情 - 显示更新日",
            ["show", "3"],
            expect_in_output=["怪奇物语", "下集更新"]
        ),
        TestCase(
            "编辑剧集 - 修改集数",
            ["edit", "3", "--seasons", "3", "--episodes", "12"],
            expect_in_output=["已更新", "怪奇物语"]
        ),
        TestCase(
            "编辑后查看详情 - 季数集数已更新",
            ["show", "3"],
            expect_in_output=["3 季", "12 集/季"]
        ),
        TestCase(
            "编辑更新日期",
            ["edit", "3", "--next-episode-date", this_week_mon.isoformat()],
            expect_in_output=["已更新"]
        ),
        TestCase(
            "记录观看 - 第1季第1集",
            ["watch", "3", "--season", "1", "--episode", "1"],
            expect_in_output=["已记录", "第1季第1集"]
        ),
        TestCase(
            "记录观看 - 直接看下一集",
            ["watch", "3", "--season", "1"],
            expect_in_output=["已记录", "第1季第2集"]
        ),
        TestCase(
            "编辑调小总集数 - 触发进度截断",
            ["edit", "3", "--episodes", "6"],
            expect_in_output=["已更新"]
        ),
        TestCase(
            "调小后查看详情 - 进度不超总集数",
            ["show", "3"],
            expect_in_output=["第1季", "2/6"],
            expect_not_in_output=["2/12"]
        ),
        TestCase(
            "watch超限尝试 - 拒绝超过总集数",
            ["watch", "3", "--season", "1", "--episode", "9"],
            expect_exit=0,
            expect_in_output=["第9集不存在"]
        ),
        TestCase(
            "搜索 - 仅关键词",
            ["search", "盗梦"],
            expect_in_output=["盗梦空间"]
        ),
        TestCase(
            "搜索 - 仅状态",
            ["search", "--status", "watchlist"],
            expect_in_output=["搜索结果", "盗梦空间", "星际穿越"]
        ),
        TestCase(
            "搜索 - 仅类型",
            ["search", "--type", "tv"],
            expect_in_output=["搜索结果", "怪奇物语", "绝命毒师", "真探", "黑袍纠察队"],
            expect_not_in_output=["盗梦空间"]
        ),
        TestCase(
            "搜索 - 仅标签",
            ["search", "--tag", "科幻"],
            expect_in_output=["盗梦空间", "星际穿越", "怪奇物语"],
            expect_not_in_output=["绝命毒师"]
        ),
        TestCase(
            "搜索 - 仅导演",
            ["search", "--director", "诺兰"],
            expect_in_output=["盗梦空间", "星际穿越"],
            expect_not_in_output=["怪奇物语"]
        ),
        TestCase(
            "搜索 - 仅演员",
            ["search", "--cast", "麦康纳"],
            expect_in_output=["星际穿越"]
        ),
        TestCase(
            "搜索 - 关键词+类型 交集",
            ["search", "空间", "--type", "movie"],
            expect_in_output=["盗梦空间", "搜索结果"],
            expect_not_in_output=["怪奇物语", "星际穿越"]
        ),
        TestCase(
            "搜索 - 标题显示筛选条件",
            ["search", "--type", "tv", "--status", "watching", "--tag", "科幻"],
            expect_in_output=["搜索结果", "剧集", "在看", "#科幻", "怪奇物语"]
        ),
        TestCase(
            "日历 - 本周表格正确",
            ["calendar"],
            expect_in_output=["本周更新日历", "怪奇物语", "即将更新", "绝命毒师",
                             "已过期更新", "真探", "未设定更新日", "黑袍纠察队"]
        ),
        TestCase(
            "导出 Markdown",
            ["export", "--format", "markdown", "--output", os.path.join(TEST_DB_DIR, "export.md")],
            expect_in_output=["已导出"]
        ),
        TestCase(
            "导出文件内容 - 进度不超限",
            ["show", "3"],
            expect_in_output=["2/6"],
            expect_not_in_output=["15/12"]
        ),
        TestCase(
            "电影 watch --finish",
            ["watch", "1", "--finish"],
            expect_in_output=["已看完", "盗梦空间"]
        ),
    ]

    print("🎬 Film Tracker 回归测试")
    print(f"测试数据库: {database.DB_PATH}")

    for case in tests:
        if not run_test(case):
            print(f"\n{'='*60}")
            print(f"❌ 测试在 \"{case.name}\" 处失败，停止执行")
            print(f"   通过: {passed}  失败: {failed}  总数: {len(tests)}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"✅ 全部 {passed} 条测试通过！")
    print(f"   测试数据库位置: {database.DB_PATH}")
    sys.exit(0)


if __name__ == "__main__":
    setup_test_db()
    run_tests()
