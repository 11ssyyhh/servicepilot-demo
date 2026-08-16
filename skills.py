# -*- coding: utf-8 -*-
"""
Skill体系模块
对应PPT中的核心Skill体系，5大类15+Skill
每个Skill有标准化输入输出Schema、失败处理、安全边界
Agent通过调用Skill完成具体任务，不直接操作业务系统
"""

import re
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from config import KNOWLEDGE_BASE, INTENT_TYPES


class BaseSkill(ABC):
    """Skill基类 - 所有Skill的标准化接口"""
    
    def __init__(self, name: str, skill_type: str, description: str):
        self.name = name
        self.skill_type = skill_type  # diagnostic / knowledge / execution / governance / memory
        self.description = description
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行Skill，返回标准化结果
        必须包含: success(bool), result, confidence, error(可选)
        """
        pass
    
    def get_schema(self) -> Dict:
        """返回输入输出Schema (用于文档和校验)"""
        return {
            "name": self.name,
            "type": self.skill_type,
            "description": self.description,
            "input_params": self._input_schema(),
            "output": self._output_schema(),
        }
    
    def _input_schema(self) -> Dict:
        return {}
    
    def _output_schema(self) -> Dict:
        return {"success": "bool", "result": "any", "confidence": "float"}


# ============ 诊断类Skill ============

class IntentClassifier(BaseSkill):
    """意图分类Skill - 识别用户问题类型"""
    
    def __init__(self):
        super().__init__("IntentClassifier", "diagnostic", "20类客服意图分类")
        # 关键词映射 (简化版，实际可用LLM或分类模型)
        self.keyword_map = {
            "order_query": ["订单", "查单", "下单", "购买记录"],
            "refund": ["退款", "退钱", "退我钱", "款项", "不想要了", "退掉"],
            "address_change": ["地址", "改地址", "收货地址", "换地址"],
            "complaint": ["投诉", "差评", "垃圾", "骗子", "举报"],
            "product_consult": ["怎么用", "说明书", "功能", "参数", "规格"],
            "logistics_query": ["物流", "快递", "发货", "到哪了", "运输"],
            "return": ["退货", "退换", "换货", "退回"],
            "invoice": ["发票", "开票", "税号"],
            "account": ["账号", "登录", "密码", "注册"],
        }
        # 意图优先级 (分数相同时，优先级高的胜出)
        self.priority = {
            "complaint": 10, "refund": 9, "return": 8, "address_change": 7,
            "logistics_query": 6, "invoice": 5, "account": 4, "product_consult": 3,
            "order_query": 2, "other": 0,
        }
    
    def execute(self, message: str, **kwargs) -> Dict[str, Any]:
        message_lower = message.lower()
        best_intent = "other"
        best_score = 0
        best_priority = 0
        
        for intent, keywords in self.keyword_map.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            priority = self.priority.get(intent, 0)
            if score > best_score or (score == best_score and score > 0 and priority > best_priority):
                best_score = score
                best_intent = intent
                best_priority = priority
        
        confidence = min(0.5 + best_score * 0.2, 0.95)
        return {
            "success": True,
            "result": best_intent,
            "confidence": confidence,
            "all_scores": {k: sum(1 for kw in v if kw in message_lower) 
                          for k, v in self.keyword_map.items()},
        }
    
    def _input_schema(self):
        return {"message": "str - 用户原始消息"}


class SentimentDetector(BaseSkill):
    """情绪检测Skill - 5级情绪识别"""
    
    def __init__(self):
        super().__init__("SentimentDetector", "diagnostic", "情绪识别(5级)")
        self.negative_words = ["生气", "愤怒", "垃圾", "骗子", "差评", "投诉", "失望", "糟糕", "太差", "无语"]
        self.positive_words = ["谢谢", "感谢", "很好", "满意", "不错", "开心", "赞", "棒"]
    
    def execute(self, message: str, **kwargs) -> Dict[str, Any]:
        msg_lower = message.lower()
        neg_count = sum(1 for w in self.negative_words if w in msg_lower)
        pos_count = sum(1 for w in self.positive_words if w in msg_lower)
        
        # 情绪分数: 0(最负面) - 1(最正面)
        score = 0.5 + (pos_count - neg_count) * 0.15
        score = max(0.0, min(1.0, score))
        
        if score < 0.3:
            level = "very_negative"
        elif score < 0.45:
            level = "negative"
        elif score < 0.6:
            level = "neutral"
        elif score < 0.8:
            level = "positive"
        else:
            level = "very_positive"
        
        return {
            "success": True,
            "result": {"score": score, "level": level},
            "confidence": 0.8,
            "trigger_escalation": score < 0.3,  # 极负面情绪触发升级
        }


class ProblemTypeRouter(BaseSkill):
    """问题类型路由Skill - 判断售前/售后/投诉/咨询"""
    
    def __init__(self):
        super().__init__("ProblemTypeRouter", "diagnostic", "问题类型路由")
    
    def execute(self, intent: str, **kwargs) -> Dict[str, Any]:
        type_map = {
            "product_consult": "pre_sale",
            "order_query": "after_sale",
            "refund": "after_sale",
            "return": "after_sale",
            "address_change": "after_sale",
            "logistics_query": "after_sale",
            "complaint": "complaint",
            "invoice": "after_sale",
            "account": "support",
            "other": "general",
        }
        ptype = type_map.get(intent, "general")
        priority = "high" if ptype == "complaint" else "normal"
        
        return {
            "success": True,
            "result": {"type": ptype, "priority": priority},
            "confidence": 0.9,
        }


# ============ 知识类Skill ============

class FAQRetrieval(BaseSkill):
    """FAQ检索Skill - 中文 n-gram 相关性检索"""
    
    def __init__(self):
        super().__init__("FAQRetrieval", "knowledge", "常见问题向量检索(n-gram评分)")
    
    @staticmethod
    def _ngrams(text: str, n: int = 2) -> set:
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]+", "", text)
        return {text[i:i + n] for i in range(max(0, len(text) - n + 1))}
    
    def _score(self, query: str, faq: Dict, intent_hint: str = None) -> float:
        q_grams = self._ngrams(query)
        a_grams = self._ngrams(faq["q"])
        q_words = set(re.findall(r'[\u4e00-\u9fa5]+', query))
        a_words = set(re.findall(r'[\u4e00-\u9fa5]+', faq["q"]))
        
        overlap_grams = len(q_grams & a_grams)
        containment = overlap_grams / max(len(q_grams), 1)
        keyword_overlap = len(q_words & a_words) / max(len(q_words | a_words), 1)
        
        score = 0.65 * containment + 0.35 * keyword_overlap
        if intent_hint and intent_hint == faq["category"]:
            score += 0.42
        # 答案侧也参与评分，避免 FAQ 问句与用户表述差异过大
        a2_grams = self._ngrams(faq["a"])
        answer_containment = len(q_grams & a2_grams) / max(len(q_grams), 1)
        score += 0.2 * answer_containment
        return min(round(score, 4), 0.99)
    
    def execute(self, query: str, top_k: int = 3, intent_hint: str = None,
                **kwargs) -> Dict[str, Any]:
        # 中文 n-gram + 关键词 + 意图类目加权，实际环境可替换为向量检索
        results = []
        
        for item in KNOWLEDGE_BASE:
            score = self._score(query, item, intent_hint)
            results.append({
                "question": item["q"],
                "answer": item["a"],
                "category": item["category"],
                "score": score,
                "source": "faq.knowledge_base",
                "evidence": {"kb_id": item["category"], "match": "char_ngram+keyword"},
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = [r for r in results if r["score"] > 0.05][:top_k]
        confidence = top_results[0]["score"] if top_results else 0.0
        
        return {
            "success": True,
            "result": top_results,
            "confidence": min(confidence, 0.95),
            "total_scored": len(results),
            "total_found": len(top_results),
        }


class ProductDocRAG(BaseSkill):
    """产品文档RAG Skill (Mock版)"""
    
    def __init__(self):
        super().__init__("ProductDocRAG", "knowledge", "产品文档RAG检索")
    
    def execute(self, query: str, product_id: str = None, **kwargs) -> Dict[str, Any]:
        # Mock: 返回模拟的产品文档片段，并按查询相关性打分
        mock_docs = [
            {"doc": "产品支持7天无理由退换货，质量问题30天内包换。",
             "source": "售后政策.pdf", "keywords": ["退", "换货", "质量", "退款"]},
            {"doc": "产品保修期为1年，非人为损坏免费维修。",
             "source": "保修条款.pdf", "keywords": ["保修", "维修", "损坏"]},
        ]
        query_words = set(re.findall(r'[\u4e00-\u9fa5]+', query))
        scored = []
        for doc in mock_docs:
            hits = sum(1 for kw in doc["keywords"] if kw in query)
            overlap = len(query_words & set(doc["keywords"]))
            score = min(0.5 + hits * 0.2 + overlap * 0.1, 0.95)
            scored.append({"doc": doc["doc"], "source": doc["source"], "score": round(score, 3)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "success": True,
            "result": scored,
            "confidence": scored[0]["score"] if scored else 0.0,
        }


class HistoryCaseSearch(BaseSkill):
    """历史工单案例检索Skill (Mock版)"""
    
    def __init__(self):
        super().__init__("HistoryCaseSearch", "knowledge", "历史工单案例检索")
    
    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        mock_cases = [
            {"case_id": "WO202608001", "problem": "物流延迟", "solution": "联系快递加急，补偿5元优惠券",
             "keywords": ["物流", "延迟", "快递"]},
            {"case_id": "WO202608002", "problem": "退款到账慢", "solution": "核实支付渠道后加急退款",
             "keywords": ["退款", "到账"]},
            {"case_id": "WO202608003", "problem": "地址写错", "solution": "未发货订单由客服协助修改地址",
             "keywords": ["地址", "写错"]},
        ]
        scored = []
        for case in mock_cases:
            hits = sum(1 for kw in case["keywords"] if kw in query)
            score = min(0.35 + hits * 0.3, 0.95)
            scored.append({
                "case_id": case["case_id"],
                "problem": case["problem"],
                "solution": case["solution"],
                "score": round(score, 3),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "success": True,
            "result": scored,
            "confidence": scored[0]["score"] if scored else 0.0,
        }


# ============ 执行类Skill (调用Mock业务系统) ============

class OrderQuery(BaseSkill):
    """订单查询Skill"""
    
    def __init__(self, mock_system):
        super().__init__("OrderQuery", "execution", "订单状态查询")
        self.mock_system = mock_system
    
    def execute(self, order_id: str = None, phone: str = None, **kwargs) -> Dict[str, Any]:
        result = self.mock_system.query_order(order_id, phone)
        return {
            "success": result.get("success", False),
            "result": result.get("data"),
            "confidence": 1.0 if result.get("success") else 0.0,
            "error": result.get("error"),
        }


class RefundProcess(BaseSkill):
    """退款处理Skill - 高风险操作(L2)"""
    
    def __init__(self, mock_system):
        super().__init__("RefundProcess", "execution", "退款申请处理")
        self.mock_system = mock_system
        self.risk_level = "L2"
    
    def execute(self, order_id: str, reason: str, amount: float = None, 
                approved: bool = False, idempotency_key: str = None,
                approver: str = "user", approval_id: str = None, **kwargs) -> Dict[str, Any]:
        if not approved:
            return {
                "success": False,
                "result": None,
                "confidence": 0.0,
                "error": "退款为高风险操作，需要人工审批",
                "need_approval": True,
                "risk_level": "L2",
            }
        result = self.mock_system.process_refund(order_id, reason, amount, idempotency_key)
        data = result.get("data") or {}
        return {
            "success": result.get("success", False),
            "result": data,
            "confidence": 1.0 if result.get("success") else 0.0,
            "risk_level": "L2",
            "approved": True,
            "approval_id": approval_id,
            "approver": approver,
            "idempotency_key": idempotency_key,
            "rollback_point": data.get("rollback_point"),
        }


class AddressUpdate(BaseSkill):
    """地址修改Skill - 低风险操作(L1)"""
    
    def __init__(self, mock_system):
        super().__init__("AddressUpdate", "execution", "收货地址修改")
        self.mock_system = mock_system
        self.risk_level = "L1"
    
    def execute(self, order_id: str, new_address: str,
                idempotency_key: str = None, **kwargs) -> Dict[str, Any]:
        result = self.mock_system.update_address(order_id, new_address)
        data = result.get("data") or {}
        return {
            "success": result.get("success", False),
            "result": data,
            "confidence": 1.0 if result.get("success") else 0.0,
            "risk_level": "L1",
            "error": result.get("error"),
            "idempotency_key": idempotency_key,
            "rollback_point": {"order_id": order_id, "old_address": data.get("old_address")} if result.get("success") else None,
        }


class TicketCreate(BaseSkill):
    """人工工单创建Skill"""
    
    def __init__(self, mock_system):
        super().__init__("TicketCreate", "execution", "人工工单创建")
        self.mock_system = mock_system
    
    def execute(self, problem_desc: str, priority: str = "normal",
                idempotency_key: str = None, **kwargs) -> Dict[str, Any]:
        result = self.mock_system.create_ticket(problem_desc, priority, idempotency_key)
        return {
            "success": result.get("success", False),
            "result": result.get("data"),
            "confidence": 1.0 if result.get("success") else 0.0,
            "idempotency_key": idempotency_key,
        }


class RollbackOperation(BaseSkill):
    """回滚操作Skill - 用于执行失败或审计时恢复业务状态"""

    def __init__(self, mock_system):
        super().__init__("RollbackOperation", "execution", "业务回滚操作")
        self.mock_system = mock_system
        self.risk_level = "L2"

    def execute(self, order_id: str, refund_id: str = None,
                idempotency_key: str = None, **kwargs) -> Dict[str, Any]:
        result = self.mock_system.rollback_refund(order_id, refund_id, idempotency_key)
        return {
            "success": result.get("success", False),
            "result": result.get("data"),
            "confidence": 1.0 if result.get("success") else 0.0,
            "risk_level": "L2",
            "error": result.get("error"),
        }


# ============ 治理类Skill ============

class ComplianceCheck(BaseSkill):
    """合规检查Skill - 广告法/隐私合规"""
    
    def __init__(self):
        super().__init__("ComplianceCheck", "governance", "合规性检查")
        self.forbidden_words = ["最", "第一", "国家级", "绝对", "100%", "永久"]
    
    def execute(self, text: str, **kwargs) -> Dict[str, Any]:
        violations = [w for w in self.forbidden_words if w in text]
        passed = len(violations) == 0
        return {
            "success": True,
            "result": {"passed": passed, "violations": violations},
            "confidence": 0.95,
        }


class SensitiveWordFilter(BaseSkill):
    """敏感词过滤Skill"""
    
    def __init__(self):
        super().__init__("SensitiveWordFilter", "governance", "敏感词过滤")
        self.sensitive_words = ["色情", "赌博", "毒品", "反动"]
    
    def execute(self, text: str, **kwargs) -> Dict[str, Any]:
        filtered = text
        hits = []
        for w in self.sensitive_words:
            if w in text:
                hits.append(w)
                filtered = filtered.replace(w, "***")
        return {
            "success": True,
            "result": {"filtered_text": filtered, "hits": hits},
            "confidence": 1.0,
            "safe": len(hits) == 0,
        }


class RiskEscalation(BaseSkill):
    """风险升级判断Skill - 判定L0-L3风险等级"""
    
    def __init__(self):
        super().__init__("RiskEscalation", "governance", "风险升级判断")
    
    def execute(self, action: str, amount: float = 0, user_level: str = "normal", 
                **kwargs) -> Dict[str, Any]:
        # 基于动作类型和金额判断风险等级
        high_risk_actions = ["refund", "销户", "大额转账", "修改支付方式"]
        medium_risk_actions = ["address_change", "修改手机号", "优惠券发放"]
        
        if action in high_risk_actions or amount > 1000:
            level = "L2"
        elif action in medium_risk_actions or amount > 100:
            level = "L1"
        elif "query" in action or "search" in action:
            level = "L0"
        else:
            level = "L1"
        
        # VIP用户降低一级风险
        if user_level == "vip" and level != "L0":
            levels = ["L0", "L1", "L2", "L3"]
            idx = levels.index(level)
            level = levels[max(0, idx - 1)]
        
        return {
            "success": True,
            "result": {"risk_level": level, "need_approval": level in ["L2", "L3"]},
            "confidence": 0.85,
        }


# ============ 沉淀类Skill ============

class ConversationSummary(BaseSkill):
    """对话摘要Skill (简化版)"""
    
    def __init__(self):
        super().__init__("ConversationSummary", "memory", "对话摘要生成")
    
    def execute(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        # 简化版摘要，实际可用LLM生成
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        summary = f"用户咨询{len(user_msgs)}次，主要问题：" + "；".join(user_msgs[:3])
        return {
            "success": True,
            "result": summary,
            "confidence": 0.7,
            "tags": ["需要人工复核"],
        }


class KnowledgeUpdate(BaseSkill):
    """知识库更新建议Skill - 仅生成草案，正式更新需人工审核"""

    def __init__(self):
        super().__init__("KnowledgeUpdate", "memory", "知识库更新建议")

    def execute(self, intent: str = None, issue_resolved: bool = True,
                summary: str = "", **kwargs) -> Dict[str, Any]:
        suggestions = []
        if not issue_resolved:
            suggestions.append(f"建议补充意图={intent}的FAQ条目及失败处置话术")
        if summary and len(summary) > 20:
            suggestions.append("建议将该案例沉淀为历史相似案例，供后续检索复用")
        return {
            "success": True,
            "result": {"suggestions": suggestions, "requires_review": True},
            "confidence": 0.8,
        }


class ServiceReport(BaseSkill):
    """服务报告生成Skill"""
    
    def __init__(self):
        super().__init__("ServiceReport", "memory", "服务报告生成")
    
    def execute(self, state_dict: Dict, **kwargs) -> Dict[str, Any]:
        report = {
            "session_id": state_dict.get("session_id"),
            "trace_id": state_dict.get("trace_id"),
            "intent": state_dict.get("intent"),
            "resolved": state_dict.get("issue_resolved"),
            "satisfaction": state_dict.get("satisfaction_score"),
            "agent_count": 7,
            "skill_calls": state_dict.get("execution_count", 0),
            "risk_level": state_dict.get("risk_level"),
            "retrieval_confidence": state_dict.get("retrieval_confidence"),
            "approval_count": len(state_dict.get("approval_history", [])),
            "ticket_count": len(state_dict.get("tickets", [])),
            "needs_human": state_dict.get("needs_human", False),
            "duration": "真实耗时以 output/metrics.json e2e_latency_ms 为准",
        }
        return {"success": True, "result": report, "confidence": 0.9}


# ============ Skill注册中心 ============

def register_all_skills(mock_system) -> Dict[str, BaseSkill]:
    """注册所有Skill，返回Skill字典"""
    skills = {
        # 诊断类
        "IntentClassifier": IntentClassifier(),
        "SentimentDetector": SentimentDetector(),
        "ProblemTypeRouter": ProblemTypeRouter(),
        # 知识类
        "FAQRetrieval": FAQRetrieval(),
        "ProductDocRAG": ProductDocRAG(),
        "HistoryCaseSearch": HistoryCaseSearch(),
        # 执行类
        "OrderQuery": OrderQuery(mock_system),
        "RefundProcess": RefundProcess(mock_system),
        "AddressUpdate": AddressUpdate(mock_system),
        "TicketCreate": TicketCreate(mock_system),
        "RollbackOperation": RollbackOperation(mock_system),
        # 治理类
        "ComplianceCheck": ComplianceCheck(),
        "SensitiveWordFilter": SensitiveWordFilter(),
        "RiskEscalation": RiskEscalation(),
        # 沉淀类
        "ConversationSummary": ConversationSummary(),
        "KnowledgeUpdate": KnowledgeUpdate(),
        "ServiceReport": ServiceReport(),
    }
    return skills
