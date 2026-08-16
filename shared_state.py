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
    timestamp: float = field(default_factory=time.time)


@dataclass
class SharedState:
    """
    共享状态 - 模拟AgentTeams的Conversation State
    贯穿整个客服会话生命周期，所有Agent读写此状态
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = "anonymous"
    
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
                      success: bool, risk_level: str = "L0"):
        """记录工具执行"""
        record = ExecutionRecord(
            skill_name=skill_name, input_params=input_params,
            output_result=output, success=success, risk_level=risk_level
        )
        self.execution_records.append(record)
        self.timeline.append({
            "time": time.strftime("%H:%M:%S"),
            "agent": "ToolExecutor",
            "action": f"执行 {skill_name} -> {'成功' if success else '失败'}",
        })
        return record
    
    def request_approval(self, action: str, reason: str, risk_level: str = "L2"):
        """请求人工审批 (高风险操作)"""
        approval = {
            "id": str(uuid.uuid4())[:8],
            "action": action,
            "reason": reason,
            "risk_level": risk_level,
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
    
    def approve(self, approval_id: str, approved: bool = True, approver: str = "user"):
        """审批操作"""
        for app in self.pending_approvals:
            if app["id"] == approval_id:
                app["status"] = "approved" if approved else "rejected"
                app["approver"] = approver
                self.approval_history.append(app)
                self.pending_approvals.remove(app)
                self.timeline.append({
                    "time": time.strftime("%H:%M:%S"),
                    "agent": approver,
                    "action": f"[审批{'通过' if approved else '拒绝'}] {app['action']}",
                })
                return app
        return None
    
    def get_last_user_message(self) -> Optional[Message]:
        """获取最后一条用户消息"""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None
    
    def to_dict(self) -> Dict:
        """导出为字典（用于日志/报告）"""
        return {
            "session_id": self.session_id,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "urgency": self.urgency,
            "risk_level": self.overall_risk_level,
            "issue_resolved": self.issue_resolved,
            "satisfaction": self.satisfaction_score,
            "message_count": len(self.messages),
            "execution_count": len(self.execution_records),
            "summary": self.conversation_summary,
        }
