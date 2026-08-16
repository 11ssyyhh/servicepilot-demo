# -*- coding: utf-8 -*-
"""
评估循环

基于 Golden/Badcase 数据集对 7-Agent 闭环做回归评估，输出意图准确率、
闭环解决准确率、工具成功率、端到端延迟与 Token 成本，写入
output/eval_report.json。

运行: python evaluate.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from config import SYSTEM_VERSION
from mock_systems import MockBusinessSystems
from skills import register_all_skills
from agents import create_all_agents
from manager import AgentTeamsManager
from llm import create_llm_client


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DEFAULT_DATASET = ROOT / "eval_dataset.json"
PASS_THRESHOLD = 0.8


def build_manager() -> AgentTeamsManager:
    """构建一次独立评估用的 Manager（每个 case 独立 Mock 系统）"""
    mock_systems = MockBusinessSystems()
    skills = register_all_skills(mock_systems)
    agents = create_all_agents(skills)
    return AgentTeamsManager(agents, debug=False, llm_client=create_llm_client(),
                             output_dir=OUTPUT_DIR)


def run_case(manager: AgentTeamsManager, case: Dict[str, Any]) -> Dict[str, Any]:
    """运行单个评估 case"""
    state = manager.run(
        case["input"],
        auto_approve=bool(case.get("auto_approve", True)),
        write_evidence=False,
    )
    obs = manager.get_last_observability()
    metrics = obs.metrics if obs else {}
    tool_successes = sum(1 for r in state.execution_records if r.success)
    tool_failures = sum(1 for r in state.execution_records if not r.success)
    return {
        "id": case["id"],
        "input": case["input"],
        "expected_intent": case["expected_intent"],
        "predicted_intent": state.intent,
        "expected_resolved": bool(case["expected_resolved"]),
        "resolved": bool(state.issue_resolved),
        "intent_match": state.intent == case["expected_intent"],
        "resolution_match": bool(state.issue_resolved) == bool(case["expected_resolved"]),
        "passed": state.intent == case["expected_intent"]
                  and bool(state.issue_resolved) == bool(case["expected_resolved"]),
        "latency_ms": round(float(metrics.get("e2e_latency_ms", 0.0)), 2),
        "tool_calls": len(state.execution_records),
        "tool_successes": tool_successes,
        "tool_failures": tool_failures,
        "tickets": [t.get("ticket_id") for t in state.tickets_created],
        "retrieval_confidence": round(float(state.retrieval_confidence or 0.0), 3),
        "cost_usd": round(float(metrics.get("total_cost_usd", 0.0)), 6),
    }


def run_evaluation(dataset_path: Path = DEFAULT_DATASET) -> Dict[str, Any]:
    """运行完整评估，返回聚合报告"""
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = []
    total_latency = 0.0
    total_cost = 0.0
    total_successes = 0
    total_failures = 0

    for case in dataset:
        manager = build_manager()
        result = run_case(manager, case)
        results.append(result)
        total_latency += result["latency_ms"]
        total_cost += result["cost_usd"]
        total_successes += result["tool_successes"]
        total_failures += result["tool_failures"]

    passed = sum(1 for r in results if r["passed"])
    intent_accuracy = sum(1 for r in results if r["intent_match"]) / len(results)
    resolution_accuracy = sum(1 for r in results if r["resolution_match"]) / len(results)
    tool_total = total_successes + total_failures
    report = {
        "version": SYSTEM_VERSION,
        "dataset": dataset_path.name,
        "total_cases": len(results),
        "passed_cases": passed,
        "pass_rate": round(passed / len(results), 4),
        "intent_accuracy": round(intent_accuracy, 4),
        "resolution_accuracy": round(resolution_accuracy, 4),
        "tool_success_rate": round(total_successes / tool_total, 4) if tool_total else 0.0,
        "tool_successes": total_successes,
        "tool_failures": total_failures,
        "avg_e2e_latency_ms": round(total_latency / len(results), 2),
        "total_cost_usd": round(total_cost, 6),
        "threshold": PASS_THRESHOLD,
        "cases": results,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = run_evaluation()
    print(f"评估完成 | 通过 {report['passed_cases']}/{report['total_cases']} | "
          f"通过率 {report['pass_rate']:.0%} | "
          f"意图准确率 {report['intent_accuracy']:.0%} | "
          f"闭环解决准确率 {report['resolution_accuracy']:.0%} | "
          f"工具成功率 {report['tool_success_rate']:.0%} | "
          f"平均延迟 {report['avg_e2e_latency_ms']}ms")
    print(f"报告: {OUTPUT_DIR / 'eval_report.json'}")
    if report["pass_rate"] < PASS_THRESHOLD:
        print(f"❌ 通过率低于阈值 {PASS_THRESHOLD:.0%}")
        return 1
    print("✅ 通过率达标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
