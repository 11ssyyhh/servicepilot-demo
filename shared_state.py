# -*- coding: utf-8 -*-
"""
共享状态模块
模拟AgentTeams中的Conversation State / Incident State
保存上下文、任务状态、审批结果、证据索引等
所有Agent通过共享状态传递信息，实现多Agent协作
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """对话消息"""
    role: str  # user / agent / system
    agent_name: Optional[str] = None
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionRecord:
    """工具执行记录"""
    skill_name: str
    input_params: Dict[str, Any]
    output_result: Any
    success: bool
    risk_level: str = "L0"
    approved: bool = False
    idempotency_key: Optional[str] = None
    rollback_point: Any = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SharedState:
    """
    共享状态 - 模拟AgentTeams的Conversation State
    贯穿整个客服会话生命周期，所有Agent读写此状态
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = "anonymous"
    trace_id: str = ""
    auto_approve: bool = True
    approver: str = "auto_demo"
    
    # 对话历史
    messages: List[Message] = field(default_factory=list)
    
    # 意图分析结果 (由IntentRouter写入)
    intent: Optional[str] = None
    sentiment: float = 0.5  # 0-1, 0最负面，1最正面
    urgency: str = "normal"  # low / normal / high / urgent
    
    # 知识检索结果 (由KnowledgeRetriever写入)
    retrieved_answers: List[Dict] = field(default_factory=list)
    retrieval_confidence: float = 0.0
    
    # 任务规划结果 (由TaskPlanner写入)
    task_plan: List[Dict] = field(default_factory=list)
    overall_risk_level: str = "L0"
    
    # 执行记录 (由ToolExecutor写入)
    execution_records: List[ExecutionRecord] = field(default_factory=list)
    
    # 质量审核结果 (由QualityGuard写入)
    quality_check_passed: bool = False
    quality_issues: List[str] = field(default_factory=list)
    
    # 验证结果 (由Verifier写入)
    issue_resolved: bool = False
    satisfaction_score: float = 0.0
    
    # 记忆沉淀 (由MemoryScribe写入)
    conversation_summary: str = ""
    knowledge_update_suggestions: List[str] = field(default_factory=list)
    
    # 审批记录 (高风险操作需要)
    pending_approvals: List[Dict] = field(default_factory=list)
    approval_history: List[Dict] = field(default_factory=list)
    audit_events: List[Dict] = field(default_factory=list)
    tickets_created: List[Dict] = field(default_factory=list)
    rollback_points: List[Dict] = field(default_factory=list)
    idempotency_keys: Dict[str, str] = field(default_factory=dict)
    needs_human: bool = False
    final_reply: str = ""
    
    # 时间线 (用于Demo展示)
    timeline: List[Dict] = field(default_factory=list)
    
    def add_message(self, role: str, content: str, agent_name: str = None, **kwargs):
        """添加对话消息"""
        msg = Message(role=role, agent_name=agent_name, content=content, metadata=kwargs)
        self.messages.append(msg)
        self.timeline.append({
            "time": time.strftime("%H:%M:%S"),
            "agent": agent_name or role,
            "action": content[:50] + "..." if len(content) > 50 else content,
        })
        return msg
    
    def add_execution(self, skill_name: str, input_params: Dict, output: Any, 
                      success: bool, risk_level: str = "L0",
                      idempotency_key: str = None, rollback_point: Any = None,
                      duration_ms: float = 0.0):
        """记录工具执行"""
        record = ExecutionRecord(
            skill_name=skill_name, input_params=input_params,
            output_result=output, success=success, risk_level=risk_level,
            idempotency_key=idempotency_key, rollback_point=rollback_point,
            duration_ms=duration_ms,
        )
        self.execution_records.append(record)
        self.timeline.append({
            "time": time.strftime("%H:%M:%S"),
            "agent": "ToolExecutor",
            "action": f"执行 {skill_name} -> {'成功' if success else '失败'}"
                      + (f" (幂等键={idempotency_key})" if idempotency_key else ""),
        })
        return record
    
    def request_approval(self, action: str, reason: str, risk_level: str = "L2",
                         idempotency_key: str = None, evidence: List[Any] = None):
        """请求人工审批 (高风险操作)"""
        approval = {
            "id": str(uuid.uuid4())[:8],
            "action": action,
            "reason": reason,
            "risk_level": risk_level,
            "idempotency_key": idempotency_key,
            "evidence": evidence or [],
            "status": "pending",
            "timestamp": time.time(),
        }
        self.pending_approvals.append(approval)
        self.timeline.append({
            "time": time.strftime("%H:%M:%S"),
            "agent": "QualityGuard",
            "action": f"[审批请求] {action} ({risk_level})",
        })
        return approval
    
    def approve(self, approval_id: str, approved: bool = True, approver: str = "user",
                reason: str = None):
        """审批操作"""
        for app in self.pending_approvals:
            if app["id"] == approval_id:
                app["status"] = "approved" if approved else "rejected"
                app["approver"] = approver
                app["approved"] = approved
                app["reason"] = reason or ("自动审批通过" if approved else "审批拒绝")
                self.approval_history.append(app)
                self.pending_approvals.remove(app)
                self.timeline.append({
                    "time": time.strftime("%H:%M:%S"),
                    "agent": approver,
                    "action": f"[审批{'通过' if approved else '拒绝'}] {app['action']}",
                })
                self.add_audit(
                    event="approval.decided",
                    actor=approver,
                    details={
                        "approval_id": app["id"],
                        "action": app["action"],
                        "approved": approved,
                        "reason": app["reason"],
                        "idempotency_key": app.get("idempotency_key"),
                    },
                )
                return app
        return None
    
    def add_audit(self, event: str, actor: str, details: Dict = None):
        """追加审计事件"""
        self.audit_events.append({
            "trace_id": self.trace_id,
            "timestamp": time.time(),
            "event": event,
            "actor": actor,
            "details": details or {},
        })
    
    def add_ticket(self, ticket: Dict):
        """记录创建的工单"""
        self.tickets_created.append(ticket)
    
    def add_rollback_point(self, action: str, point: Any, idempotency_key: str = None):
        """记录回滚点"""
        self.rollback_points.append({
            "action": action,
            "point": point,
            "idempotency_key": idempotency_key,
            "timestamp": time.time(),
        })
    
    def get_last_user_message(self) -> Optional[Message]:
        """获取最后一条用户消息"""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None
    
    def to_dict(self, full: bool = True) -> Dict:
        """导出为字典（用于日志/报告/续跑）"""
        data = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "auto_approve": self.auto_approve,
            "approver": self.approver,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "urgency": self.urgency,
            "risk_level": self.overall_risk_level,
            "retrieval_confidence": self.retrieval_confidence,
            "quality_check_passed": self.quality_check_passed,
            "quality_issues": list(self.quality_issues),
            "issue_resolved": self.issue_resolved,
            "satisfaction": self.satisfaction_score,
            "message_count": len(self.messages),
            "execution_count": len(self.execution_records),
            "summary": self.conversation_summary,
            "knowledge_update_suggestions": list(self.knowledge_update_suggestions),
            "final_reply": self.final_reply,
            "approval_history": list(self.approval_history),
            "pending_approvals": list(self.pending_approvals),
            "audit_events": list(self.audit_events),
            "tickets": list(self.tickets_created),
            "rollback_points": list(self.rollback_points),
            "needs_human": self.needs_human,
            "messages": [
                {"role": m.role, "agent": m.agent_name, "content": m.content, "timestamp": m.timestamp}
                for m in self.messages
            ],
        }
        if full:
            data.update({
                "task_plan": list(self.task_plan),
                "execution_records": [
                    {
                        "skill_name": r.skill_name,
                        "input_params": r.input_params,
                        "output_result": r.output_result,
                        "success": r.success,
                        "risk_level": r.risk_level,
                        "approved": r.approved,
                        "idempotency_key": r.idempotency_key,
                        "rollback_point": r.rollback_point,
                        "duration_ms": r.duration_ms,
                        "timestamp": r.timestamp,
                    }
                    for r in self.execution_records
                ],
                "idempotency_keys": dict(self.idempotency_keys),
                "timeline": list(self.timeline),
            })
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "SharedState":
        """从字典恢复共享状态，用于审批后续跑/回放"""
        state = cls(
            session_id=data.get("session_id") or str(uuid.uuid4())[:8],
            user_id=data.get("user_id", "anonymous"),
            trace_id=data.get("trace_id", ""),
            auto_approve=bool(data.get("auto_approve", True)),
            approver=data.get("approver", "auto_demo"),
        )
        state.intent = data.get("intent")
        state.sentiment = float(data.get("sentiment", 0.5))
        state.urgency = data.get("urgency", "normal")
        state.retrieval_confidence = float(data.get("retrieval_confidence", 0.0))
        state.task_plan = list(data.get("task_plan", []))
        state.overall_risk_level = data.get("risk_level", "L0")
        state.quality_check_passed = bool(data.get("quality_check_passed", False))
        state.quality_issues = list(data.get("quality_issues", []))
        state.issue_resolved = bool(data.get("issue_resolved", False))
        state.satisfaction_score = float(data.get("satisfaction", 0.0))
        state.conversation_summary = data.get("summary", "")
        state.knowledge_update_suggestions = list(data.get("knowledge_update_suggestions", []))
        state.final_reply = data.get("final_reply", "")
        state.pending_approvals = list(data.get("pending_approvals", []))
        state.approval_history = list(data.get("approval_history", []))
        state.audit_events = list(data.get("audit_events", []))
        state.tickets_created = list(data.get("tickets", []))
        state.rollback_points = list(data.get("rollback_points", []))
        state.idempotency_keys = dict(data.get("idempotency_keys", {}))
        state.needs_human = bool(data.get("needs_human", False))
        state.timeline = list(data.get("timeline", []))

        for msg in data.get("messages", []):
            state.messages.append(Message(
                role=msg.get("role", "user"),
                agent_name=msg.get("agent"),
                content=msg.get("content", ""),
                timestamp=float(msg.get("timestamp", time.time())),
                metadata=msg.get("metadata", {}),
            ))
        for rec in data.get("execution_records", []):
            state.execution_records.append(ExecutionRecord(
                skill_name=rec.get("skill_name", ""),
                input_params=rec.get("input_params", {}),
                output_result=rec.get("output_result"),
                success=bool(rec.get("success", False)),
                risk_level=rec.get("risk_level", "L0"),
                approved=bool(rec.get("approved", False)),
                idempotency_key=rec.get("idempotency_key"),
                rollback_point=rec.get("rollback_point"),
                duration_ms=float(rec.get("duration_ms", 0.0)),
                timestamp=float(rec.get("timestamp", time.time())),
            ))
        return state
