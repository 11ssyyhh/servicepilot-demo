# -*- coding: utf-8 -*-
"""
Agent模块 - 7个职能Agent

模拟AgentTeams中的Worker角色。每个Agent有明确的职责边界，通过共享状态
(SharedState)协作；Agent不直接操作业务系统，通过Skill完成任务。
全部Agent调用纳入 Trace/Log/Metrics，高风险操作经过审批、幂等与回滚点记录。
"""

import re
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import nullcontext
from typing import Any, Dict, List, Optional

from shared_state import SharedState
from config import INTENT_TYPES, RETRIEVAL_HUMAN_THRESHOLD, RETRIEVAL_ANSWER_THRESHOLD


class BaseAgent(ABC):
    """Agent基类 - 模拟AgentTeams Worker"""

    def __init__(self, name: str, role: str, skills: Dict = None):
        self.name = name
        self.role = role
        self.skills = skills or {}
        self.decision_boundary = ""
        self.tracer = None
        self.llm = None

    @abstractmethod
    def process(self, state: SharedState) -> SharedState:
        """处理任务，读写共享状态"""
        pass

    def trace(self, name: str, span_type: str = "agent",
              attributes: Dict = None):
        """记录一段 Span；未注入 tracer 时为空操作"""
        if self.tracer is None:
            return nullcontext()
        return self.tracer.span(name, span_type, attributes)

    def add_log(self, level: str, event: str, **attrs):
        if self.tracer is not None:
            self.tracer.add_log(level, event, agent=self.name, **attrs)

    def call_llm(self, task: str, prompt: str, attributes: Dict = None):
        """调用可插拔 LLM；未配置时返回 None，规则引擎结果同样写入 Metrics"""
        if self.llm is None:
            return None
        attrs = dict(attributes or {})
        with self.trace(f"llm.{task}", "llm", attrs) as span:
            result = self.llm.complete(
                prompt, system="你是ServicePilot智能客服系统的辅助引擎，只输出结构化结果。"
            )
            if span is not None:
                span.attributes.update({
                    "model": result.model,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                    "latency_ms": result.latency_ms,
                    "cost_usd": result.cost_usd,
                })
            if self.tracer is not None:
                self.tracer.inc("llm_calls")
                self.tracer.inc("total_tokens", result.total_tokens)
                self.tracer.inc("total_cost_usd", result.cost_usd)
        return result

    def log(self, state: SharedState, message: str):
        """记录Agent动作到时间线"""
        state.add_message("agent", message, agent_name=self.name)

    def call_skill(self, skill_name: str, **kwargs) -> Dict[str, Any]:
        """调用Skill - Agent不直接操作业务系统"""
        if skill_name not in self.skills:
            return {"success": False, "error": f"Skill {skill_name} 未注册"}
        return self.skills[skill_name].execute(**kwargs)


def extract_order_id(message: str) -> Optional[str]:
    """从用户消息中提取订单号"""
    match = re.search(r"ORD[A-Za-z0-9_]{4,}", message)
    return match.group(0) if match else None


class IntentRouterAgent(BaseAgent):
    """意图路由Agent - 识别意图、情绪、紧急度，分发任务"""

    def __init__(self, skills: Dict = None):
        super().__init__("IntentRouter", "意图路由Agent", skills)
        self.decision_boundary = "仅做路由，不生成最终回复"

    def process(self, state: SharedState) -> SharedState:
        user_msg = state.get_last_user_message()
        if not user_msg:
            return state

        with self.trace("IntentRouter", "agent", {"input": user_msg.content[:60]}):
            self.log(state, f"收到用户消息: {user_msg.content[:30]}...")

            intent_result = self.call_skill("IntentClassifier", message=user_msg.content)
            state.intent = intent_result["result"]

            # LLM 意图校验（规则引擎直接返回候选，真实 LLM 可纠正）
            llm_result = self.call_llm(
                "intent.validate",
                f"用户消息:{user_msg.content}\n候选意图:{state.intent}",
                {"candidate": state.intent},
            )
            if llm_result and llm_result.text.strip() in INTENT_TYPES:
                state.intent = llm_result.text.strip()

            sentiment_result = self.call_skill("SentimentDetector", message=user_msg.content)
            state.sentiment = sentiment_result["result"]["score"]

            route_result = self.call_skill("ProblemTypeRouter", intent=state.intent)
            problem_type = route_result["result"]["type"]

            if sentiment_result["result"]["score"] < 0.3 or problem_type == "complaint":
                state.urgency = "high"
            else:
                state.urgency = "normal"

            state.add_audit("intent.routed", "IntentRouter", {
                "intent": state.intent,
                "sentiment": state.sentiment,
                "urgency": state.urgency,
            })
            self.add_log("info", "intent.routed",
                         intent=state.intent, urgency=state.urgency)
            self.log(state, f"意图={state.intent}, 情绪={state.sentiment:.2f}, 紧急度={state.urgency}")
        return state


class KnowledgeRetrieverAgent(BaseAgent):
    """知识检索Agent - RAG检索知识库/FAQ/产品文档/历史案例"""

    def __init__(self, skills: Dict = None):
        super().__init__("KnowledgeRetriever", "知识检索Agent", skills)
        self.decision_boundary = "仅检索不决策，置信度低于阈值触发转人工建议"

    def process(self, state: SharedState) -> SharedState:
        user_msg = state.get_last_user_message()
        if not user_msg:
            return state

        with self.trace("KnowledgeRetriever", "agent",
                        {"query": user_msg.content[:60], "intent": state.intent}):
            self.log(state, f"开始检索知识库，意图={state.intent}")

            faq_result = self.call_skill("FAQRetrieval", query=user_msg.content,
                                         top_k=3, intent_hint=state.intent)
            state.retrieved_answers = list(faq_result["result"])
            state.retrieval_confidence = float(faq_result["confidence"] or 0.0)

            with self.trace("rag.faq", "rag.retrieve",
                            {"hits": len(faq_result["result"]),
                             "confidence": state.retrieval_confidence}):
                self.tracer.inc("rag_retrievals") if self.tracer else None

            if state.retrieval_confidence < 0.7:
                doc_result = self.call_skill("ProductDocRAG", query=user_msg.content)
                for item in doc_result["result"]:
                    item["answer"] = item["doc"]
                    item["source"] = "product_doc"
                    item["evidence"] = {"doc": item["doc"], "score": item["score"]}
                state.retrieved_answers.extend(doc_result["result"])
                state.retrieval_confidence = max(
                    state.retrieval_confidence, float(doc_result["confidence"] or 0.0)
                )

            case_result = self.call_skill("HistoryCaseSearch", query=user_msg.content)
            for item in case_result["result"]:
                item["answer"] = item["solution"]
                item["source"] = "history_case"
                item["evidence"] = {"case_id": item["case_id"], "score": item["score"]}
            state.retrieved_answers.extend(case_result["result"])
            state.retrieval_confidence = max(
                state.retrieval_confidence, float(case_result["confidence"] or 0.0)
            )
            state.retrieval_confidence = round(state.retrieval_confidence, 4)

            evidence = [
                {"source": r.get("source"), "score": r.get("score")}
                for r in state.retrieved_answers[:3]
            ]
            with self.trace("rag.combine", "rag.retrieve",
                            {"confidence": state.retrieval_confidence, "evidence": evidence}):
                pass

            if state.retrieval_confidence < RETRIEVAL_HUMAN_THRESHOLD:
                state.needs_human = True
                self.add_log("warn", "rag.low_confidence",
                             confidence=state.retrieval_confidence)
                self.log(state, f"⚠️ 检索置信度={state.retrieval_confidence:.2f}，建议转人工")
            else:
                state.needs_human = False

            self.log(state, f"检索到{len(state.retrieved_answers)}条结果，"
                           f"置信度={state.retrieval_confidence:.2f}")
        return state


class TaskPlannerAgent(BaseAgent):
    """任务规划Agent - 拆解问题，规划多步处理流程"""

    def __init__(self, skills: Dict = None):
        super().__init__("TaskPlanner", "任务规划Agent", skills)
        self.decision_boundary = "规划但不执行，高风险必须标注审批节点"

    def process(self, state: SharedState) -> SharedState:
        with self.trace("TaskPlanner", "agent", {"intent": state.intent}) as span:
            self.log(state, f"开始任务规划，意图={state.intent}")
            plan = self._generate_plan(state)
            state.task_plan = plan
            if span is not None:
                span.attributes["plan"] = plan

            max_risk = "L0"
            for step in plan:
                if step.get("risk_level", "L0") in ("L2", "L3"):
                    max_risk = "L2"
                    break
                if step.get("risk_level") == "L1":
                    max_risk = "L1"
            state.overall_risk_level = max_risk

            self.add_log("info", "task.plan", plan=plan, risk_level=max_risk)
            self.log(state, f"规划{len(plan)}步执行，整体风险={state.overall_risk_level}")
        return state

    def _generate_plan(self, state: SharedState) -> List[Dict]:
        intent = state.intent
        order_id = extract_order_id(state.get_last_user_message().content) if state.get_last_user_message() else None
        order_id = order_id or "ORD20260816001"

        if intent == "order_query":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": order_id}, "risk_level": "L0",
                 "desc": "查询订单状态"},
                {"step": 2, "action": "generate_reply", "risk_level": "L0",
                 "desc": "基于查询结果生成回复"},
            ]
        elif intent == "refund":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": order_id}, "risk_level": "L0",
                 "desc": "查询订单确认退款资格"},
                {"step": 2, "action": "risk_assessment", "skill": "RiskEscalation",
                 "params": {"action": "refund", "amount": 299.0}, "risk_level": "L2",
                 "desc": "评估退款风险(L2，需审批)"},
                {"step": 3, "action": "request_approval", "risk_level": "L2",
                 "desc": "请求用户确认退款"},
                {"step": 4, "action": "process_refund", "skill": "RefundProcess",
                 "params": {"order_id": order_id, "reason": "用户申请退款"},
                 "risk_level": "L2", "need_approval": True,
                 "desc": "执行退款(审批通过后)"},
            ]
        elif intent == "address_change":
            new_address = None
            user_msg = state.get_last_user_message()
            if user_msg:
                addr_match = re.search(r"(改成|修改为|更改为)(.{4,40}?)(?:[。！？!?]|$)", user_msg.content)
                if addr_match:
                    new_address = addr_match.group(2).strip()
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": order_id}, "risk_level": "L0",
                 "desc": "查询订单状态确认是否可改地址"},
                {"step": 2, "action": "update_address", "skill": "AddressUpdate",
                 "params": {"order_id": order_id,
                            "new_address": new_address or "江苏省南京市玄武区zzz路3号"},
                 "risk_level": "L1", "desc": "修改收货地址(L1，自动执行)"},
            ]
        elif intent == "logistics_query":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": order_id}, "risk_level": "L0",
                 "desc": "查询订单获取物流单号"},
                {"step": 2, "action": "generate_reply", "risk_level": "L0",
                 "desc": "生成物流信息回复"},
            ]
        elif intent == "complaint":
            plan = [
                {"step": 1, "action": "create_ticket", "skill": "TicketCreate",
                 "params": {"problem_desc": "用户投诉", "priority": "high"},
                 "risk_level": "L0", "desc": "创建高优先级工单"},
                {"step": 2, "action": "generate_apology", "risk_level": "L0",
                 "desc": "生成安抚回复"},
            ]
        else:
            plan = [
                {"step": 1, "action": "generate_reply_from_kb", "risk_level": "L0",
                 "desc": "基于检索结果生成回复"},
            ]
        return plan


class ToolExecutorAgent(BaseAgent):
    """工具执行Agent - 调用业务系统 API，遵守 L0-L3 风险管控"""

    def __init__(self, skills: Dict = None):
        super().__init__("ToolExecutor", "工具执行Agent", skills)
        self.decision_boundary = "L1以下自动执行，L2+需审批令牌"
        self.write_skills = {"RefundProcess", "AddressUpdate", "TicketCreate", "RollbackOperation"}

    def process(self, state: SharedState) -> SharedState:
        with self.trace("ToolExecutor", "agent", {"plan_size": len(state.task_plan)}):
            self.log(state, f"开始执行任务计划，共{len(state.task_plan)}步")

            for step in state.task_plan:
                approval = None
                if step.get("need_approval"):
                    approval = self._ensure_approval(state, step)
                    if approval["status"] != "approved":
                        self.log(state, f"⏸️ 步骤{step['step']}({step['action']})审批未通过，暂停执行")
                        continue

                if "skill" not in step:
                    continue

                self.log(state, f"执行步骤{step['step']}: {step['desc']}")
                result = self._execute_skill(state, step, approval)

                if not result.get("success"):
                    error = result.get("error") or "未知错误"
                    self.log(state, f"❌ 执行失败: {error}")
                    ticket = self._create_escalation_ticket(
                        state, f"自动处理失败: {step['desc']} | {error}", priority="high"
                    )
                    state.needs_human = True
                    self.add_log("error", "tool.execution_failed",
                                 skill=step.get("skill"), error=error, ticket=ticket)
                    break
        return state

    def _ensure_approval(self, state: SharedState, step: Dict) -> Dict:
        action = step["action"]
        existing = next(
            (a for a in state.approval_history + state.pending_approvals
             if a["action"] == action),
            None,
        )
        if existing:
            return existing

        idem_key = state.idempotency_keys.get(action) or f"idem-{action}-{uuid.uuid4().hex[:8]}"
        state.idempotency_keys[action] = idem_key
        evidence = [
            {"step": step.get("step"), "desc": step.get("desc"),
             "skill": step.get("skill"), "risk_level": step.get("risk_level")}
        ]
        approval = state.request_approval(
            action=action,
            reason=f"{step.get('desc')} 属于高风险操作，需要人工审批",
            risk_level=step.get("risk_level", "L2"),
            idempotency_key=idem_key,
            evidence=evidence,
        )
        if self.tracer is not None:
            self.tracer.inc("approval_requests")

        if state.auto_approve:
            state.approve(
                approval["id"],
                approved=True,
                approver=state.approver,
                reason="自动演示审批：风险等级L2，操作在白名单内，证据完整",
            )
            if self.tracer is not None:
                self.tracer.inc("approvals_granted")
            self.add_log("info", "approval.auto_approved",
                         action=action, approver=state.approver)
            return next(a for a in state.approval_history if a["action"] == action)

        self.add_log("warn", "approval.requested",
                     action=action, approval_id=approval["id"])
        return approval

    def _execute_skill(self, state: SharedState, step: Dict, approval: Dict = None) -> Dict:
        skill_name = step["skill"]
        params = dict(step.get("params", {}))
        idem_key = None

        if skill_name in self.write_skills:
            idem_key = state.idempotency_keys.get(step.get("action")) or f"idem-{skill_name}-{uuid.uuid4().hex[:8]}"
            state.idempotency_keys[step.get("action") or skill_name] = idem_key
            params["idempotency_key"] = idem_key

        if skill_name == "RefundProcess":
            params["approved"] = True
            if approval:
                params["approval_id"] = approval.get("id")
                params["approver"] = approval.get("approver")

        attrs = {"skill": skill_name, "risk_level": step.get("risk_level"),
                 "idempotency_key": idem_key, "params": params}
        started = time.time()
        with self.trace(f"mcp.{skill_name}", "mcp.tool", attrs) as span:
            result = self.call_skill(skill_name, **params)
            duration_ms = round((time.time() - started) * 1000, 2)
            span.attributes.update({
                "success": result.get("success", False),
                "error": result.get("error"),
                "duration_ms": duration_ms,
            })
            if self.tracer is not None:
                self.tracer.inc("mcp_calls")
                self.tracer.inc("tool_successes" if result.get("success") else "tool_failures")

        rollback_point = result.get("rollback_point")
        if rollback_point and result.get("success"):
            state.add_rollback_point(step.get("action"), rollback_point, idem_key)

        state.add_execution(
            skill_name=skill_name,
            input_params=params,
            output=result.get("result"),
            success=result.get("success", False),
            risk_level=step.get("risk_level", "L0"),
            idempotency_key=idem_key,
            rollback_point=rollback_point,
            duration_ms=duration_ms,
        )
        if skill_name == "TicketCreate" and result.get("success"):
            ticket = result.get("result") or {}
            state.add_ticket(ticket)
            if self.tracer is not None:
                self.tracer.inc("tickets_created")
        state.add_audit("tool.executed", "ToolExecutor", {
            "skill": skill_name,
            "success": result.get("success", False),
            "risk_level": step.get("risk_level"),
            "idempotency_key": idem_key,
            "error": result.get("error"),
        })
        return result

    def _create_escalation_ticket(self, state: SharedState, problem_desc: str,
                                  priority: str = "high") -> Dict:
        idem_key = f"idem-ticket-{uuid.uuid4().hex[:8]}"
        result = self.call_skill("TicketCreate", problem_desc=problem_desc,
                                 priority=priority, idempotency_key=idem_key)
        if result.get("success"):
            ticket = result["result"]
            state.add_ticket(ticket)
            state.add_audit("ticket.created", "ToolExecutor",
                            {"ticket_id": ticket.get("ticket_id"), "priority": priority})
            if self.tracer is not None:
                self.tracer.inc("tickets_created")
            self.log(state, f"已创建转人工工单: {ticket.get('ticket_id')}")
            return ticket
        return {"error": result.get("error")}


class QualityGuardAgent(BaseAgent):
    """质量风控Agent - 内容审核、敏感词过滤、合规检查、风险升级"""

    def __init__(self, skills: Dict = None):
        super().__init__("QualityGuard", "质量风控Agent", skills)
        self.decision_boundary = "有权拦截任何输出，高风险强制转人工"

    def process(self, state: SharedState) -> SharedState:
        with self.trace("QualityGuard", "agent", {"risk_level": state.overall_risk_level}):
            self.log(state, "开始质量审核")

            draft_reply = self._generate_draft_reply(state)

            sensitive_result = self.call_skill("SensitiveWordFilter", text=draft_reply)
            if not sensitive_result.get("safe", True):
                state.quality_issues.append(f"敏感词命中: {sensitive_result['result']['hits']}")
                draft_reply = sensitive_result["result"]["filtered_text"]

            compliance_result = self.call_skill("ComplianceCheck", text=draft_reply)
            if not compliance_result["result"]["passed"]:
                state.quality_issues.append(f"合规问题: {compliance_result['result']['violations']}")

            if state.pending_approvals:
                self.log(state, f"⚠️ 存在{len(state.pending_approvals)}项待审批，回复中需提示用户确认")
                draft_reply += "\n\n⚠️ 本次操作涉及高风险动作，需要您确认后执行。"

            # LLM 润色（规则引擎原样返回草稿）
            llm_result = self.call_llm(
                "reply.polish",
                f"草稿回复:{draft_reply}\n请润色为正式客服回复，保持信息不变。",
                {"risk_level": state.overall_risk_level},
            )
            if llm_result and llm_result.text.strip():
                draft_reply = llm_result.text.strip()

            if not state.quality_issues:
                state.quality_check_passed = True
                self.log(state, "✅ 质量审核通过")
            else:
                self.log(state, f"⚠️ 审核发现{len(state.quality_issues)}个问题: {state.quality_issues}")

            state.final_reply = draft_reply
            state.add_message("agent", draft_reply, agent_name="QualityGuard")
            state.add_audit("quality.checked", "QualityGuard", {
                "passed": state.quality_check_passed,
                "issues": list(state.quality_issues),
            })
        return state

    def _generate_draft_reply(self, state: SharedState) -> str:
        if state.intent == "order_query":
            last_exec = state.execution_records[-1] if state.execution_records else None
            if last_exec and last_exec.success:
                order = last_exec.output_result
                return (f"您好，您的订单{order['order_id']}状态为{order['status']}，"
                        f"商品：{order['product']}，物流：{order['logistics']['status']}。"
                        f"如有其他问题请随时告诉我。")
            return "您好，正在为您查询订单信息，请稍候。"

        if state.intent == "refund":
            last_exec = state.execution_records[-1] if state.execution_records else None
            if last_exec and last_exec.success and last_exec.skill_name == "RefundProcess":
                data = last_exec.output_result or {}
                return (f"您好，您的退款申请已提交，退款单号{data.get('refund_id', '-')}，"
                        f"预计{data.get('expected_arrival', '1-3个工作日')}原路返回。")
            rejected = next((a for a in state.approval_history
                             if a.get("action") == "process_refund" and a.get("status") == "rejected"), None)
            if rejected:
                return "您好，您的退款申请未通过审批，已为您转人工客服进一步核实，请留意工单进度。"
            return ("您好，已为您查询到订单信息。退款申请需要您确认后提交，"
                    "确认后1-3个工作日原路返回。请问是否确认申请退款？")

        if state.intent == "address_change":
            last_exec = state.execution_records[-1] if state.execution_records else None
            if last_exec and last_exec.success:
                return f"您好，收货地址已修改成功，新地址：{last_exec.output_result['new_address']}"
            if state.tickets_created:
                ticket = state.tickets_created[-1]
                return (f"您好，正在为您处理地址修改。该订单已发货，无法在线修改地址，"
                        f"已为您创建转人工工单{ticket.get('ticket_id')}，客服将尽快协助处理。")
            return "您好，正在为您处理地址修改。"

        if state.intent == "logistics_query":
            return "您好，您的包裹正在运输中，预计明天送达。"

        if state.intent == "complaint":
            ticket_id = state.tickets_created[-1].get("ticket_id") if state.tickets_created else "-"
            return (f"非常抱歉给您带来不好的体验，已为您创建高优先级工单{ticket_id}，"
                    f"客服会在2小时内联系您处理。")

        if state.retrieved_answers:
            return state.retrieved_answers[0].get("answer", "您好，请问有什么可以帮您？")
        return "您好，请问有什么可以帮您？"


class VerifierAgent(BaseAgent):
    """效果验证Agent - 确认问题是否解决，未解决自动转人工"""

    def __init__(self, skills: Dict = None):
        super().__init__("Verifier", "效果验证Agent", skills)
        self.decision_boundary = "仅验证不执行，未解决自动转人工"

    def process(self, state: SharedState) -> SharedState:
        with self.trace("Verifier", "agent", {"intent": state.intent}):
            self.log(state, "开始效果验证")
            resolved = self._check_resolved(state)

            if resolved:
                state.issue_resolved = True
                state.satisfaction_score = 0.85
                state.needs_human = False
                self.log(state, "✅ 问题已解决，满意度=0.85")
            else:
                state.issue_resolved = False
                state.satisfaction_score = 0.3
                state.needs_human = True
                self.log(state, "❌ 问题未解决，触发转人工")
                if not state.tickets_created:
                    result = self.call_skill(
                        "TicketCreate",
                        problem_desc=f"自动处理未解决: {state.intent}",
                        priority="high",
                        idempotency_key=f"idem-ticket-verify-{uuid.uuid4().hex[:8]}",
                    )
                    if result.get("success"):
                        state.add_ticket(result["result"])
                        if self.tracer is not None:
                            self.tracer.inc("tickets_created")
                        self.log(state, f"已创建转人工工单: {result['result']['ticket_id']}")

            state.add_audit("verification.checked", "Verifier", {
                "resolved": state.issue_resolved,
                "satisfaction": state.satisfaction_score,
            })
        return state

    def _check_resolved(self, state: SharedState) -> bool:
        if state.pending_approvals:
            return False
        records = state.execution_records
        if state.intent == "complaint":
            return any(r.skill_name == "TicketCreate" and r.success for r in records)
        if state.intent == "refund":
            return any(r.skill_name == "RefundProcess" and r.success for r in records)
        if state.intent == "address_change":
            return any(r.skill_name == "AddressUpdate" and r.success for r in records)
        if state.intent in ("order_query", "logistics_query"):
            return any(r.skill_name == "OrderQuery" and r.success for r in records)
        if any(r.success for r in records):
            return True
        return bool(state.retrieved_answers) and state.retrieval_confidence >= RETRIEVAL_ANSWER_THRESHOLD


class MemoryScribeAgent(BaseAgent):
    """记忆沉淀Agent - 对话摘要、知识库更新建议、服务报告"""

    def __init__(self, skills: Dict = None):
        super().__init__("MemoryScribe", "记忆沉淀Agent", skills)
        self.decision_boundary = "仅写入，需人工审核后才更新正式知识库"

    def process(self, state: SharedState) -> SharedState:
        with self.trace("MemoryScribe", "agent"):
            self.log(state, "开始记忆沉淀")

            messages_dict = [{"role": m.role, "content": m.content} for m in state.messages]
            summary_result = self.call_skill("ConversationSummary", messages=messages_dict)
            state.conversation_summary = summary_result["result"]

            # LLM 摘要（规则引擎直接返回草稿）
            llm_result = self.call_llm(
                "summary.polish",
                f"摘要草稿:{state.conversation_summary}\n用户消息:{state.conversation_summary}",
                {"intent": state.intent},
            )
            if llm_result and llm_result.text.strip():
                state.conversation_summary = llm_result.text.strip()

            kb_result = self.call_skill(
                "KnowledgeUpdate",
                intent=state.intent,
                issue_resolved=state.issue_resolved,
                summary=state.conversation_summary,
            )
            state.knowledge_update_suggestions.extend(kb_result["result"]["suggestions"])

            report_result = self.call_skill("ServiceReport", state_dict=state.to_dict())
            state.service_report = report_result.get("result")

            self.log(state, f"已生成服务报告，知识库更新建议{len(state.knowledge_update_suggestions)}条")
        return state


# ============ Agent注册 ============

def create_all_agents(skills: Dict) -> Dict[str, BaseAgent]:
    """创建所有Agent实例"""
    return {
        "IntentRouter": IntentRouterAgent(skills),
        "KnowledgeRetriever": KnowledgeRetrieverAgent(skills),
        "TaskPlanner": TaskPlannerAgent(skills),
        "ToolExecutor": ToolExecutorAgent(skills),
        "QualityGuard": QualityGuardAgent(skills),
        "Verifier": VerifierAgent(skills),
        "MemoryScribe": MemoryScribeAgent(skills),
    }
