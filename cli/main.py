"""QualiAI CLI entry point."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
from core.executor import PlaywrightExecutor
from core.planner import AITestPlanner
from core.reporter import HTMLReporter


@click.group()
def cli():
    """QualiAI — AI-Powered Testing Agent.

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
    click.echo("🧪 QualiAI 测试启动")
    click.echo("═" * 40)

    # 1. 规划
    planner = AITestPlanner(model=model, api_key=api_key)
    steps = planner.plan(description, base_url=url)

    click.echo(f"\n📋 生成 {len(steps)} 个测试步骤:")
    for s in steps:
        icon = {"navigate": "🌐", "click": "🖱", "type": "⌨️",
                "assert": "🔍", "wait": "⏳", "scroll": "📜"}.get(s["action"], "•")
        click.echo(f"  {icon} [{s['step']}] {s['action']}: {s.get('desc', '')}")

    # 2. 执行
    click.echo(f"\n🚀 开始执行...")
    executor = PlaywrightExecutor(headless=True)
    results = executor.run(steps)

    # 3. 输出
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    click.echo(f"\n📊 结果: {passed}/{total} 通过 ({total - passed} 失败)")

    # 4. 报告
    report_dir = output or os.path.join(os.getcwd(), "reports")
    reporter = HTMLReporter(report_dir)
    report_path = reporter.generate(description, steps, results)
    click.echo(f"\n📄 报告已生成: {report_path}")
    click.echo(f"   打开: file://{report_path}")


@cli.command()
@click.argument("scenario_path")
@click.option("--output", "-o", default="", help="报告输出目录")
def replay(scenario_path, output):
    """重播已保存的测试场景"""
    import json
    with open(scenario_path) as f:
        scenario = json.load(f)

    click.echo(f"🔄 重播场景: {scenario.get('name', 'unnamed')}")
    click.echo("═" * 40)

    steps = scenario.get("steps", [])
    click.echo(f"\n📋 {len(steps)} 个步骤")

    executor = PlaywrightExecutor(headless=True)
    results = executor.run(steps)

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    click.echo(f"\n📊 结果: {passed}/{total} 通过")

    report_dir = output or os.path.join(os.getcwd(), "reports")
    reporter = HTMLReporter(report_dir)
    report_path = reporter.generate(scenario.get("name", "replay"), steps, results)
    click.echo(f"\n📄 报告: file://{report_path}")


if __name__ == "__main__":
    cli()
