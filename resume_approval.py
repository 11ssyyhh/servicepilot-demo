# -*- coding: utf-8 -*-
"""
人工审批后续跑

读取 output/pending_approvals.json 与 output/approval_decisions.json，
把审批结果写回共享状态，并从 ToolExecutor 继续执行后续闭环，生成新的
Trace/Log/Metrics/Session/Summary 证据，形成「待审批 -> 人工决策 -> 自动续跑」的完整链路。

运行:
    python approval_server.py 8080   # 先启动审批台
    python main.py 1                 # 生成待审批会话（output/）
    python resume_approval.py [approval_id]  # 审批后自动续跑
"""

import json
import sys
from pathlib import Path

from mock_systems import MockBusinessSystems
from skills import register_all_skills
from agents import create_all_agents
from manager import AgentTeamsManager
from llm import create_llm_client
from shared_state import SharedState


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_manager() -> AgentTeamsManager:
    mock_systems = MockBusinessSystems()
    skills = register_all_skills(mock_systems)
    agents = create_all_agents(skills)
    return AgentTeamsManager(agents, debug=False, llm_client=create_llm_client(),
                             output_dir=OUTPUT_DIR)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    approval_id = sys.argv[1] if len(sys.argv) > 1 else None
    pending_path = OUTPUT_DIR / "pending_approvals.json"
    decisions_path = OUTPUT_DIR / "approval_decisions.json"
    if not pending_path.exists():
        print("未找到待审批记录，请先运行: python main.py 1")
        return 1

    pending = _read_json(pending_path)
    decisions = _read_json(decisions_path) if decisions_path.exists() else []
    if not pending:
        print("当前没有待审批事项")
        return 0

    resume_path = OUTPUT_DIR / "resume_state.json"
    state_path = resume_path if resume_path.exists() else OUTPUT_DIR / "session.json"
    if not state_path.exists():
        print("未找到会话快照，无法续跑")
        return 1

    state = SharedState.from_dict(_read_json(state_path))
    applied = 0
    for approval in pending:
        if approval_id and approval["id"] != approval_id:
            continue
        decision = next(
            (d for d in decisions
             if d.get("id") == approval["id"] or d.get("approval_id") == approval["id"]),
            None,
        )
        if decision is None:
            continue
        state.approve(
            approval["id"],
            approved=bool(decision.get("approved")),
            approver=decision.get("approver") or "web_operator",
            reason=decision.get("reason"),
        )
        applied += 1
        print(f"✅ 已应用审批决策: {approval['action']} -> "
              f"{'通过' if decision.get('approved') else '拒绝'} | 审批人={decision.get('approver')}")

    if applied == 0:
        print("未找到匹配的审批决策。请先在审批台完成通过/拒绝后再续跑。")
        return 1

    manager = build_manager()
    manager.debug = True
    state = manager.resume(state, start_at="ToolExecutor")
    print(f"\n✅ 续跑完成 | Session: {state.session_id} | Trace: {state.trace_id}")
    print(f"   解决状态: {'已解决' if state.issue_resolved else '未解决，转人工'}")
    print(f"   执行记录: {len(state.execution_records)} | 审批记录: {len(state.approval_history)}")
    if state.tickets_created:
        print(f"   工单: {', '.join(t.get('ticket_id', '') for t in state.tickets_created)}")
    print(f"   证据: {OUTPUT_DIR / 'trace.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
