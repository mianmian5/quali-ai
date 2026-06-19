"""QualiAI CLI entry point."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
from core.executor import PlaywrightExecutor
from core.planner import AITestPlanner
from core.reporter import HTMLReporter
from core.adb_executor import ADBExecutor


@click.group()
def cli():
    """QualiAI -- AI-Powered Testing Agent.

    输入自然语言描述，AI 自动执行测试并生成报告。
    """
    pass


@cli.command()
@click.argument("description", required=False, default="")
@click.option("--url", "-u", default="", help="被测应用 URL")
@click.option("--model", "-m", default="deepseek-chat", help="LLM 模型")
@click.option("--api-key", "-k", default="", help="API Key（留空使用默认）")
@click.option("--output", "-o", default="", help="报告输出目录")
@click.option("--scenario", "-s", default="", help="场景文件路径")
def run(description, url, model, api_key, output, scenario):
    """运行测试：自然语言描述测试场景"""
    click.echo("QualiAI test starting")
    click.echo("=" * 40)

    planner = AITestPlanner(model=model, api_key=api_key)
    steps = planner.plan(description, base_url=url)

    click.echo("\nGenerated %d test steps:" % len(steps))
    for s in steps:
        click.echo("  [%d] %s: %s" % (s["step"], s["action"], s.get("desc", "")))

    click.echo("\nExecuting...")
    executor = PlaywrightExecutor(headless=True)
    results = executor.run(steps)

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    click.echo("\nResult: %d/%d passed (%d failed)" % (passed, total, total - passed))

    if hasattr(executor, '_self_heal_count') and executor._self_heal_count > 0:
        click.echo("Self-healed selectors: %d" % executor._self_heal_count)

    report_dir = output or os.path.join(os.getcwd(), "reports")
    reporter = HTMLReporter(report_dir)
    report_path = reporter.generate(description or "test", steps, results)
    click.echo("\nReport: file://" + report_path)


@cli.command()
@click.argument("description", required=False, default="")
@click.option("--app", "-a", default="", help="Android App 包名")
@click.option("--device", "-d", default="", help="ADB 设备 ID")
@click.option("--output", "-o", default="", help="报告输出目录")
def android(description, app, device, output):
    """在安卓设备上运行测试"""
    click.echo("QualiAI Android test starting")
    click.echo("=" * 40)

    planner = AITestPlanner()
    steps = planner.plan(description, base_url=app)

    click.echo("\nGenerated %d test steps:" % len(steps))
    for s in steps:
        click.echo("  [%d] %s: %s" % (s["step"], s["action"], s.get("desc", "")))

    click.echo("\nExecuting on Android...")
    executor = ADBExecutor(device_id=device if device else None)
    results = executor.run(steps)

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    click.echo("\nResult: %d/%d passed (%d failed)" % (passed, total, total - passed))

    report_dir = output or os.path.join(os.getcwd(), "reports")
    reporter = HTMLReporter(report_dir)
    report_path = reporter.generate(description or "android-test", steps, results)
    click.echo("\nReport: file://" + report_path)


@cli.command()
@click.argument("scenario_path")
@click.option("--output", "-o", default="", help="报告输出目录")
def replay(scenario_path, output):
    """重播已保存的测试场景"""
    import json
    with open(scenario_path) as f:
        scenario = json.load(f)

    click.echo("Replaying: %s" % scenario.get("name", "unnamed"))
    click.echo("=" * 40)

    steps = scenario.get("steps", [])
    click.echo("%d steps" % len(steps))

    executor = PlaywrightExecutor(headless=True)
    results = executor.run(steps)

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    click.echo("Result: %d/%d passed" % (passed, total))

    report_dir = output or os.path.join(os.getcwd(), "reports")
    reporter = HTMLReporter(report_dir)
    report_path = reporter.generate(scenario.get("name", "replay"), steps, results)
    click.echo("Report: file://" + report_path)


if __name__ == "__main__":
    cli()
