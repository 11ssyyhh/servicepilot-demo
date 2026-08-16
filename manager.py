# -*- coding: utf-8 -*-
"""
Manager模块 - 模拟AgentTeams的Manager角色

Manager-Workers架构：Manager 负责任务拆解、Agent调度、状态流转、异常处理，
并把每次会话的 Trace/Log/Metrics 写入 output/ 供回放与审计。
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from shared_state import SharedState
from agents import BaseAgent
from observability import Observability
from masking import mask_state_snapshot


class AgentTeamsManager:
    """
    AgentTeams Manager - 多Agent编排器
    """

    def __init__(self, agents: Dict[str, BaseAgent], debug: bool = True,
                 llm_client=None, output_dir: Optional[Path] = None):
        self.agents = agents
        self.debug = debug
        self.llm_client = llm_client
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "output"
        self.observability: Optional[Observability] = None
        self.evidence: Dict[str, Path] = {}
        self.pipeline = [
            "IntentRouter",
            "KnowledgeRetriever",
            "TaskPlanner",
            "ToolExecutor",
            "QualityGuard",
            "Verifier",
            "MemoryScribe",
        ]
        for agent in self.agents.values():
            agent.llm = llm_client

    def run(self, user_message: str, auto_approve: bool = True,
            approver: str = "auto_demo", trace_id: Optional[str] = None,
            write_evidence: bool = True) -> SharedState:
        """
        运行完整的客服自主闭环
        """
        self.observability = Observability(trace_id=trace_id, output_dir=self.output_dir)
        state = SharedState()
        state.trace_id = self.observability.trace_id
        state.auto_approve = auto_approve
        state.approver = approver
        state.add_message("user", user_message)
        self.observability.mark_conversation()

        for agent in self.agents.values():
            agent.tracer = self.observability
            agent.llm = self.llm_client

        if self.debug:
            print(f"\n{'='*60}")
            print(f"🚀 ServicePilot 会话启动 | Session: {state.session_id} | Trace: {state.trace_id}")
            print(f"👤 用户: {user_message}")
            print(f"{'='*60}")

        for agent_name in self.pipeline:
            agent = self.agents[agent_name]
            span = self.observability.start_span(agent_name, "agent", {"role": agent.role})

            if self.debug:
                print(f"\n▶️ [{agent_name}] {agent.role} - 开始处理")

            try:
                state = agent.process(state)
                self.observability.end_span(span, status="ok")
                self.observability.inc("agents_called")
                if self.debug:
                    self._print_agent_result(agent_name, state)
            except Exception as e:
                self.observability.end_span(span, status="error")
                self.observability.add_log("error", "agent.error",
                                           agent=agent_name, error=str(e))
                print(f"❌ [{agent_name}] 执行异常: {str(e)}")
                state.add_message("system", f"Agent {agent_name} 异常，转人工处理")
                state.needs_human = True
                break

        self.observability.finalize()
        if self.debug:
            self._print_final_report(state)

        if write_evidence:
            self.evidence = self.observability.write_evidence(state)
            if state.pending_approvals:
                pending_path = self.output_dir / "pending_approvals.json"
                pending_path.write_text(
                    json.dumps(state.pending_approvals, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        return state

    def _print_agent_result(self, agent_name: str, state: SharedState):
        """打印Agent处理结果"""
        if agent_name == "IntentRouter":
            print(f"  📋 意图={state.intent} | 情绪={state.sentiment:.2f} | 紧急度={state.urgency}")
        elif agent_name == "KnowledgeRetriever":
            print(f"  📚 检索到{len(state.retrieved_answers)}条 | 置信度={state.retrieval_confidence:.2f}")
        elif agent_name == "TaskPlanner":
            print(f"  📝 规划{len(state.task_plan)}步 | 风险等级={state.overall_risk_level}")
            for step in state.task_plan:
                print(f"     Step {step['step']}: {step['desc']} [{step.get('risk_level','L0')}]")
        elif agent_name == "ToolExecutor":
            print(f"  🔧 执行{len(state.execution_records)}个工具调用")
            for rec in state.execution_records:
                status = "✅" if rec.success else "❌"
                idem = f" | 幂等键={rec.idempotency_key}" if rec.idempotency_key else ""
                print(f"     {status} {rec.skill_name} -> {rec.risk_level}{idem}")
            for app in state.approval_history:
                mark = "✅" if app["status"] == "approved" else "❌"
                print(f"     {mark} [审批] {app['action']} -> {app['status']} | 审批人={app.get('approver')}")
            for app in state.pending_approvals:
                print(f"     ⏸️ [待审批] {app['action']} -> {app['status']} | 原因={app.get('reason')}")
        elif agent_name == "QualityGuard":
            status = "✅通过" if state.quality_check_passed else f"⚠️{len(state.quality_issues)}个问题"
            print(f"  🛡️ 质量审核: {status}")
        elif agent_name == "Verifier":
            status = "✅已解决" if state.issue_resolved else "❌未解决，转人工"
            print(f"  ✔️ 效果验证: {status} | 满意度={state.satisfaction_score:.2f}")
            if state.tickets_created:
                print(f"     🎫 工单: {', '.join(t.get('ticket_id','') for t in state.tickets_created)}")
        elif agent_name == "MemoryScribe":
            print(f"  💾 已生成摘要和服务报告")

    def _print_final_report(self, state: SharedState):
        """打印最终报告"""
        print(f"\n{'='*60}")
        print(f"📊 服务报告 | Session: {state.session_id} | Trace: {state.trace_id}")
        print(f"{'='*60}")
        print(f"  意图: {state.intent}")
        print(f"  情绪: {state.sentiment:.2f}")
        print(f"  风险等级: {state.overall_risk_level}")
        print(f"  RAG置信度: {state.retrieval_confidence:.2f}")
        print(f"  问题解决: {'✅ 是' if state.issue_resolved else '❌ 否'}")
        print(f"  满意度: {state.satisfaction_score:.2f}")
        print(f"  Agent调用: {len(self.pipeline)}个")
        print(f"  工具调用: {len(state.execution_records)}次")
        print(f"  审批记录: {len(state.approval_history)}项")
        print(f"  工单: {', '.join(t.get('ticket_id','') for t in state.tickets_created) or '无'}")
        print(f"  对话轮次: {len(state.messages)}")
        print(f"  摘要: {state.conversation_summary[:80]}...")
        print(f"  证据: {self.output_dir / 'trace.jsonl'}")
        print(f"{'='*60}\n")

    def get_timeline(self, state: SharedState) -> List[Dict]:
        """获取执行时间线 (用于PPT/Demo展示)"""
        return state.timeline

    def get_last_observability(self) -> Optional[Observability]:
        """获取最近一次会话的可观测数据"""
        return self.observability
