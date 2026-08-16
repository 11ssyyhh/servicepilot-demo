# -*- coding: utf-8 -*-
"""
Agent模块 - 7个职能Agent
模拟AgentTeams中的Worker角色
每个Agent有明确的职责边界，通过共享状态(SharedState)协作
Agent不直接操作业务系统，通过调用Skill完成任务
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from shared_state import SharedState


class BaseAgent(ABC):
    """Agent基类 - 模拟AgentTeams Worker"""
    
    def __init__(self, name: str, role: str, skills: Dict = None):
        self.name = name
        self.role = role
        self.skills = skills or {}
        self.decision_boundary = ""
    
    @abstractmethod
    def process(self, state: SharedState) -> SharedState:
        """
        处理任务，读写共享状态
        这是Agent的核心方法，模拟AgentTeams中Worker的任务执行
        """
        pass
    
    def log(self, state: SharedState, message: str):
        """记录Agent动作到时间线"""
        state.add_message("agent", message, agent_name=self.name)
    
    def call_skill(self, skill_name: str, **kwargs) -> Dict[str, Any]:
        """调用Skill - Agent不直接操作业务系统，通过Skill调用"""
        if skill_name not in self.skills:
            return {"success": False, "error": f"Skill {skill_name} 未注册"}
        return self.skills[skill_name].execute(**kwargs)


class IntentRouterAgent(BaseAgent):
    """
    意图路由Agent (对应Alert Intake)
    接收用户问题，识别意图、情绪、紧急度，分发任务
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("IntentRouter", "意图路由Agent", skills)
        self.decision_boundary = "仅做路由，不生成最终回复"
    
    def process(self, state: SharedState) -> SharedState:
        user_msg = state.get_last_user_message()
        if not user_msg:
            return state
        
        self.log(state, f"收到用户消息: {user_msg.content[:30]}...")
        
        # 1. 意图分类
        intent_result = self.call_skill("IntentClassifier", message=user_msg.content)
        state.intent = intent_result["result"]
        
        # 2. 情绪检测
        sentiment_result = self.call_skill("SentimentDetector", message=user_msg.content)
        state.sentiment = sentiment_result["result"]["score"]
        
        # 3. 问题类型路由
        route_result = self.call_skill("ProblemTypeRouter", intent=state.intent)
        problem_type = route_result["result"]["type"]
        
        # 4. 紧急度判断
        if sentiment_result["result"]["score"] < 0.3 or problem_type == "complaint":
            state.urgency = "high"
        else:
            state.urgency = "normal"
        
        self.log(state, f"意图={state.intent}, 情绪={state.sentiment:.2f}, 紧急度={state.urgency}")
        return state


class KnowledgeRetrieverAgent(BaseAgent):
    """
    知识检索Agent (对应RCA Analyst)
    RAG检索知识库/FAQ/产品文档，给出候选答案
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("KnowledgeRetriever", "知识检索Agent", skills)
        self.decision_boundary = "仅检索不决策，置信度<0.6触发转人工"
    
    def process(self, state: SharedState) -> SharedState:
        user_msg = state.get_last_user_message()
        if not user_msg:
            return state
        
        self.log(state, f"开始检索知识库，意图={state.intent}")
        
        # 1. FAQ检索
        faq_result = self.call_skill("FAQRetrieval", query=user_msg.content, top_k=3)
        state.retrieved_answers = faq_result["result"]
        state.retrieval_confidence = faq_result["confidence"]
        
        # 2. 产品文档RAG (如需要)
        if state.retrieval_confidence < 0.7:
            doc_result = self.call_skill("ProductDocRAG", query=user_msg.content)
            state.retrieved_answers.extend(doc_result["result"])
        
        # 3. 历史案例检索
        case_result = self.call_skill("HistoryCaseSearch", query=user_msg.content)
        state.retrieved_answers.extend(case_result["result"])
        
        self.log(state, f"检索到{len(state.retrieved_answers)}条结果，置信度={state.retrieval_confidence:.2f}")
        
        # 置信度过低，标记需要转人工
        if state.retrieval_confidence < 0.3:
            self.log(state, "⚠️ 检索置信度过低，建议转人工")
        
        return state


class TaskPlannerAgent(BaseAgent):
    """
    任务规划Agent (对应Planner)
    拆解复杂问题，规划多步处理流程，判断是否需要工具/人工
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("TaskPlanner", "任务规划Agent", skills)
        self.decision_boundary = "规划但不执行，高风险必须标注审批节点"
    
    def process(self, state: SharedState) -> SharedState:
        self.log(state, f"开始任务规划，意图={state.intent}")
        
        # 根据意图生成执行计划
        plan = self._generate_plan(state)
        state.task_plan = plan
        
        # 评估整体风险等级
        max_risk = "L0"
        for step in plan:
            if step.get("risk_level", "L0") in ["L2", "L3"]:
                max_risk = "L2"
                break
            elif step.get("risk_level") == "L1":
                max_risk = "L1"
        state.overall_risk_level = max_risk
        
        self.log(state, f"规划{len(plan)}步执行，整体风险={state.overall_risk_level}")
        return state
    
    def _generate_plan(self, state: SharedState) -> List[Dict]:
        """根据意图生成执行计划"""
        intent = state.intent
        plan = []
        
        if intent == "order_query":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery", 
                 "params": {"order_id": "ORD20260816001"}, "risk_level": "L0",
                 "desc": "查询订单状态"},
                {"step": 2, "action": "generate_reply", "risk_level": "L0",
                 "desc": "基于查询结果生成回复"},
            ]
        elif intent == "refund":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": "ORD20260816001"}, "risk_level": "L0",
                 "desc": "查询订单确认退款资格"},
                {"step": 2, "action": "risk_assessment", "skill": "RiskEscalation",
                 "params": {"action": "refund", "amount": 299.0}, "risk_level": "L2",
                 "desc": "评估退款风险(L2，需审批)"},
                {"step": 3, "action": "request_approval", "risk_level": "L2",
                 "desc": "请求用户确认退款"},
                {"step": 4, "action": "process_refund", "skill": "RefundProcess",
                 "params": {"order_id": "ORD20260816001", "reason": "用户申请退款"}, 
                 "risk_level": "L2", "need_approval": True,
                 "desc": "执行退款(审批通过后)"},
            ]
        elif intent == "address_change":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": "ORD20260816001"}, "risk_level": "L0",
                 "desc": "查询订单状态确认是否可改地址"},
                {"step": 2, "action": "update_address", "skill": "AddressUpdate",
                 "params": {"order_id": "ORD20260816001", 
                           "new_address": "江苏省南京市玄武区zzz路3号"},
                 "risk_level": "L1", "desc": "修改收货地址(L1，自动执行)"},
            ]
        elif intent == "logistics_query":
            plan = [
                {"step": 1, "action": "query_order", "skill": "OrderQuery",
                 "params": {"order_id": "ORD20260816001"}, "risk_level": "L0",
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
            # 默认：基于知识库回复
            plan = [
                {"step": 1, "action": "generate_reply_from_kb", "risk_level": "L0",
                 "desc": "基于检索结果生成回复"},
            ]
        
        return plan


class ToolExecutorAgent(BaseAgent):
    """
    工具执行Agent (对应Executor)
    调用业务系统API：查订单、改地址、退款、创建工单等
    严格遵守风险等级，L2+需要审批令牌
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("ToolExecutor", "工具执行Agent", skills)
        self.decision_boundary = "L1以下自动执行，L2+需审批令牌"
    
    def process(self, state: SharedState) -> SharedState:
        self.log(state, f"开始执行任务计划，共{len(state.task_plan)}步")
        
        for step in state.task_plan:
            # 跳过需要审批但未审批的步骤
            if step.get("need_approval") and not self._check_approved(state, step["action"]):
                self.log(state, f"⏸️ 步骤{step['step']}({step['action']})需要审批，暂停执行")
                continue
            
            if "skill" not in step:
                continue
            
            self.log(state, f"执行步骤{step['step']}: {step['desc']}")
            
            # 调用Skill执行
            result = self.call_skill(step["skill"], **step.get("params", {}))
            
            # 记录执行结果
            state.add_execution(
                skill_name=step["skill"],
                input_params=step.get("params", {}),
                output=result.get("result"),
                success=result.get("success", False),
                risk_level=step.get("risk_level", "L0"),
            )
            
            if not result.get("success"):
                self.log(state, f"❌ 执行失败: {result.get('error', '未知错误')}")
                # 执行失败，创建工单转人工
                ticket_result = self.call_skill("TicketCreate", 
                    problem_desc=f"自动处理失败: {step['desc']}", priority="normal")
                if ticket_result.get("success"):
                    self.log(state, f"已创建转人工工单: {ticket_result['result']['ticket_id']}")
                break
        
        return state
    
    def _check_approved(self, state: SharedState, action: str) -> bool:
        """检查操作是否已审批"""
        for approval in state.approval_history:
            if approval["action"] == action and approval["status"] == "approved":
                return True
        return False


class QualityGuardAgent(BaseAgent):
    """
    质量风控Agent (对应RiskGuard)
    审核回复内容、敏感词、合规性，高风险动作触发人工审批
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("QualityGuard", "质量风控Agent", skills)
        self.decision_boundary = "有权拦截任何输出，高风险强制转人工"
    
    def process(self, state: SharedState) -> SharedState:
        self.log(state, "开始质量审核")
        
        # 生成待审核回复 (简化版，实际由LLM生成)
        draft_reply = self._generate_draft_reply(state)
        
        # 1. 敏感词过滤
        sensitive_result = self.call_skill("SensitiveWordFilter", text=draft_reply)
        if not sensitive_result.get("safe", True):
            state.quality_issues.append(f"敏感词命中: {sensitive_result['result']['hits']}")
            draft_reply = sensitive_result["result"]["filtered_text"]
        
        # 2. 合规检查
        compliance_result = self.call_skill("ComplianceCheck", text=draft_reply)
        if not compliance_result["result"]["passed"]:
            state.quality_issues.append(f"合规问题: {compliance_result['result']['violations']}")
        
        # 3. 高风险操作审批检查
        if state.overall_risk_level in ["L2", "L3"]:
            # 检查是否有待审批项
            if state.pending_approvals:
                self.log(state, f"⚠️ 存在{len(state.pending_approvals)}项待审批，回复中需提示用户确认")
                draft_reply += "\n\n⚠️ 本次操作涉及高风险动作，需要您确认后执行。"
        
        # 审核通过
        if not state.quality_issues:
            state.quality_check_passed = True
            self.log(state, "✅ 质量审核通过")
        else:
            self.log(state, f"⚠️ 审核发现{len(state.quality_issues)}个问题: {state.quality_issues}")
        
        # 保存最终回复
        state.add_message("agent", draft_reply, agent_name="QualityGuard")
        return state
    
    def _generate_draft_reply(self, state: SharedState) -> str:
        """生成草稿回复 (简化版)"""
        if state.intent == "order_query":
            last_exec = state.execution_records[-1] if state.execution_records else None
            if last_exec and last_exec.success:
                order = last_exec.output_result
                return (f"您好，您的订单{order['order_id']}状态为{order['status']}，"
                       f"商品：{order['product']}，物流：{order['logistics']['status']}。"
                       f"如有其他问题请随时告诉我。")
            return "您好，正在为您查询订单信息，请稍候。"
        
        elif state.intent == "refund":
            return ("您好，已为您查询到订单信息。退款申请需要您确认后提交，"
                   "确认后1-3个工作日原路返回。请问是否确认申请退款？")
        
        elif state.intent == "address_change":
            last_exec = state.execution_records[-1] if state.execution_records else None
            if last_exec and last_exec.success:
                return f"您好，收货地址已修改成功，新地址：{last_exec.output_result['new_address']}"
            return "您好，正在为您处理地址修改。"
        
        elif state.intent == "logistics_query":
            return "您好，您的包裹正在运输中，预计明天送达。"
        
        elif state.intent == "complaint":
            return "非常抱歉给您带来不好的体验，已为您创建高优先级工单，客服会尽快联系您。"
        
        # 默认基于知识库
        if state.retrieved_answers:
            return state.retrieved_answers[0].get("answer", "您好，请问有什么可以帮您？")
        return "您好，请问有什么可以帮您？"


class VerifierAgent(BaseAgent):
    """
    效果验证Agent (对应Verifier)
    确认问题是否解决，用户是否满意，生成服务报告
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("Verifier", "效果验证Agent", skills)
        self.decision_boundary = "仅验证不执行，未解决自动重规划或转人工"
    
    def process(self, state: SharedState) -> SharedState:
        self.log(state, "开始效果验证")
        
        # 简化版验证：检查是否有成功的执行记录或知识库回复
        has_successful_execution = any(r.success for r in state.execution_records)
        has_knowledge_answer = len(state.retrieved_answers) > 0 and state.retrieval_confidence > 0.5
        
        if has_successful_execution or has_knowledge_answer:
            state.issue_resolved = True
            state.satisfaction_score = 0.85  # 模拟满意度
            self.log(state, "✅ 问题已解决，满意度=0.85")
        else:
            state.issue_resolved = False
            state.satisfaction_score = 0.3
            self.log(state, "❌ 问题未解决，触发重规划/转人工")
            # 创建转人工工单
            ticket_result = self.call_skill("TicketCreate",
                problem_desc=f"自动处理未解决: {state.intent}", priority="high")
            if ticket_result.get("success"):
                self.log(state, f"已创建转人工工单: {ticket_result['result']['ticket_id']}")
        
        return state


class MemoryScribeAgent(BaseAgent):
    """
    记忆沉淀Agent (对应Postmortem)
    记录对话、更新知识库、生成复盘报告
    """
    
    def __init__(self, skills: Dict = None):
        super().__init__("MemoryScribe", "记忆沉淀Agent", skills)
        self.decision_boundary = "仅写入，需人工审核后才更新正式知识库"
    
    def process(self, state: SharedState) -> SharedState:
        self.log(state, "开始记忆沉淀")
        
        # 1. 生成对话摘要
        messages_dict = [{"role": m.role, "content": m.content} for m in state.messages]
        summary_result = self.call_skill("ConversationSummary", messages=messages_dict)
        state.conversation_summary = summary_result["result"]
        
        # 2. 生成服务报告
        report_result = self.call_skill("ServiceReport", state_dict=state.to_dict())
        
        # 3. 知识库更新建议
        if not state.issue_resolved:
            state.knowledge_update_suggestions.append(
                f"建议补充意图={state.intent}的相关FAQ"
            )
        
        self.log(state, f"已生成服务报告，知识库更新建议{len(state.knowledge_update_suggestions)}条")
        return state


# ============ Agent注册 ============

def create_all_agents(skills: Dict) -> Dict[str, BaseAgent]:
    """创建所有Agent实例"""
    agents = {
        "IntentRouter": IntentRouterAgent(skills),
        "KnowledgeRetriever": KnowledgeRetrieverAgent(skills),
        "TaskPlanner": TaskPlannerAgent(skills),
        "ToolExecutor": ToolExecutorAgent(skills),
        "QualityGuard": QualityGuardAgent(skills),
        "Verifier": VerifierAgent(skills),
        "MemoryScribe": MemoryScribeAgent(skills),
    }
    return agents
