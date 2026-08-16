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
    """FAQ检索Skill - 常见问题向量检索(简化版)"""
    
    def __init__(self):
        super().__init__("FAQRetrieval", "knowledge", "常见问题向量检索")
    
    def execute(self, query: str, top_k: int = 3, **kwargs) -> Dict[str, Any]:
        # 简化版：基于关键词匹配，实际可用向量数据库
        results = []
        query_words = set(re.findall(r'[\u4e00-\u9fa5]+', query))
        
        for item in KNOWLEDGE_BASE:
            q_words = set(re.findall(r'[\u4e00-\u9fa5]+', item["q"]))
            overlap = len(query_words & q_words)
            if overlap > 0:
                results.append({
                    "question": item["q"],
                    "answer": item["a"],
                    "category": item["category"],
                    "score": overlap / max(len(q_words), 1),
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:top_k]
        confidence = top_results[0]["score"] if top_results else 0.0
        
        return {
            "success": True,
            "result": top_results,
            "confidence": min(confidence, 0.95),
            "total_found": len(results),
        }


class ProductDocRAG(BaseSkill):
    """产品文档RAG Skill (Mock版)"""
    
    def __init__(self):
        super().__init__("ProductDocRAG", "knowledge", "产品文档RAG检索")
    
    def execute(self, query: str, product_id: str = None, **kwargs) -> Dict[str, Any]:
        # Mock: 返回模拟的产品文档片段
        mock_docs = [
            {"doc": "产品支持7天无理由退换货，质量问题30天内包换。", "source": "售后政策.pdf"},
            {"doc": "产品保修期为1年，非人为损坏免费维修。", "source": "保修条款.pdf"},
        ]
        return {
            "success": True,
            "result": mock_docs,
            "confidence": 0.7,
        }


class HistoryCaseSearch(BaseSkill):
    """历史工单案例检索Skill (Mock版)"""
    
    def __init__(self):
        super().__init__("HistoryCaseSearch", "knowledge", "历史工单案例检索")
    
    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        mock_cases = [
            {"case_id": "WO202608001", "problem": "物流延迟", "solution": "联系快递加急，补偿5元优惠券"},
        ]
        return {"success": True, "result": mock_cases, "confidence": 0.6}


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
                approved: bool = False, **kwargs) -> Dict[str, Any]:
        if not approved:
            return {
                "success": False,
                "result": None,
                "confidence": 0.0,
                "error": "退款为高风险操作，需要人工审批",
                "need_approval": True,
                "risk_level": "L2",
            }
        result = self.mock_system.process_refund(order_id, reason, amount)
        return {
            "success": result.get("success", False),
            "result": result.get("data"),
            "confidence": 1.0 if result.get("success") else 0.0,
            "risk_level": "L2",
            "approved": True,
        }


class AddressUpdate(BaseSkill):
    """地址修改Skill - 低风险操作(L1)"""
    
    def __init__(self, mock_system):
        super().__init__("AddressUpdate", "execution", "收货地址修改")
        self.mock_system = mock_system
        self.risk_level = "L1"
    
    def execute(self, order_id: str, new_address: str, **kwargs) -> Dict[str, Any]:
        result = self.mock_system.update_address(order_id, new_address)
        return {
            "success": result.get("success", False),
            "result": result.get("data"),
            "confidence": 1.0 if result.get("success") else 0.0,
            "risk_level": "L1",
            "error": result.get("error"),
        }


class TicketCreate(BaseSkill):
    """人工工单创建Skill"""
    
    def __init__(self, mock_system):
        super().__init__("TicketCreate", "execution", "人工工单创建")
        self.mock_system = mock_system
    
    def execute(self, problem_desc: str, priority: str = "normal", **kwargs) -> Dict[str, Any]:
        result = self.mock_system.create_ticket(problem_desc, priority)
        return {
            "success": result.get("success", False),
            "result": result.get("data"),
            "confidence": 1.0 if result.get("success") else 0.0,
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


class ServiceReport(BaseSkill):
    """服务报告生成Skill"""
    
    def __init__(self):
        super().__init__("ServiceReport", "memory", "服务报告生成")
    
    def execute(self, state_dict: Dict, **kwargs) -> Dict[str, Any]:
        report = {
            "session_id": state_dict.get("session_id"),
            "intent": state_dict.get("intent"),
            "resolved": state_dict.get("issue_resolved"),
            "satisfaction": state_dict.get("satisfaction_score"),
            "agent_count": 7,
            "skill_calls": state_dict.get("execution_count", 0),
            "risk_level": state_dict.get("risk_level"),
            "duration": "模拟时长: 45秒",
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
        # 治理类
        "ComplianceCheck": ComplianceCheck(),
        "SensitiveWordFilter": SensitiveWordFilter(),
        "RiskEscalation": RiskEscalation(),
        # 沉淀类
        "ConversationSummary": ConversationSummary(),
        "ServiceReport": ServiceReport(),
    }
    return skills
