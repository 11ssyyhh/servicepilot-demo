# -*- coding: utf-8 -*-
"""
ServicePilot 配置文件
包含系统配置、Agent定义、Skill注册、风险等级等
"""

# ============ 系统配置 ============
SYSTEM_NAME = "ServicePilot"
SYSTEM_VERSION = "0.1.0"
DEBUG = True

# ============ 风险等级定义 (L0-L3) ============
# 对应PPT中的安全边界设计
RISK_LEVELS = {
    "L0": {"name": "只读诊断", "auto_execute": True, "need_approval": False,
           "desc": "查询类操作，自动执行"},
    "L1": {"name": "低风险自动执行", "auto_execute": True, "need_approval": False,
           "desc": "修改地址等低风险操作，自动执行并留痕"},
    "L2": {"name": "灰度+审批", "auto_execute": False, "need_approval": True,
           "desc": "退款/销户等高风险操作，需用户确认+审批记录"},
    "L3": {"name": "只生成方案", "auto_execute": False, "need_approval": True,
           "desc": "极端风险操作，仅输出建议不执行"},
}

# ============ Agent角色定义 ============
# 对应PPT中的7个职能Agent
AGENT_DEFINITIONS = [
    {
        "name": "IntentRouter",
        "role": "意图路由Agent",
        "capabilities": ["意图识别", "情绪检测", "紧急度分级", "任务分发"],
        "inputs": ["用户原始消息"],
        "outputs": ["意图标签", "情绪值", "紧急度", "目标Agent"],
        "decision_boundary": "仅做路由，不生成最终回复",
    },
    {
        "name": "KnowledgeRetriever",
        "role": "知识检索Agent",
        "capabilities": ["FAQ检索", "产品文档RAG", "历史案例检索"],
        "inputs": ["意图", "问题关键词"],
        "outputs": ["Top-K候选答案", "证据来源", "置信度"],
        "decision_boundary": "仅检索不决策，置信度<0.6触发转人工",
    },
    {
        "name": "TaskPlanner",
        "role": "任务规划Agent",
        "capabilities": ["问题拆解", "多步规划", "工具选择", "风险预判"],
        "inputs": ["意图", "检索结果"],
        "outputs": ["执行步骤序列", "所需工具", "风险等级"],
        "decision_boundary": "规划但不执行，高风险必须标注审批节点",
    },
    {
        "name": "ToolExecutor",
        "role": "工具执行Agent",
        "capabilities": ["订单查询", "退款处理", "地址修改", "工单创建"],
        "inputs": ["执行计划", "参数"],
        "outputs": ["执行结果", "状态码", "耗时"],
        "decision_boundary": "L1以下自动执行，L2+需审批令牌",
    },
    {
        "name": "QualityGuard",
        "role": "质量风控Agent",
        "capabilities": ["内容审核", "敏感词过滤", "合规检查", "风险升级"],
        "inputs": ["待发送回复", "执行记录"],
        "outputs": ["通过/拦截/修改建议", "风险等级"],
        "decision_boundary": "有权拦截任何输出，高风险强制转人工",
    },
    {
        "name": "Verifier",
        "role": "效果验证Agent",
        "capabilities": ["问题解决确认", "满意度评估", "未解决重规划"],
        "inputs": ["对话全文", "执行结果"],
        "outputs": ["解决状态", "满意度评分", "未解决原因"],
        "decision_boundary": "仅验证不执行，未解决自动重规划或转人工",
    },
    {
        "name": "MemoryScribe",
        "role": "记忆沉淀Agent",
        "capabilities": ["对话摘要", "知识库更新建议", "服务报告生成"],
        "inputs": ["完整会话", "验证结果"],
        "outputs": ["结构化摘要", "知识库更新建议", "复盘报告"],
        "decision_boundary": "仅写入，需人工审核后才更新正式知识库",
    },
]

# ============ 意图分类体系 ============
INTENT_TYPES = [
    "order_query",      # 订单查询
    "refund",           # 退款申请
    "address_change",   # 地址修改
    "complaint",        # 投诉
    "product_consult",  # 产品咨询
    "logistics_query",  # 物流查询
    "return",           # 退货
    "invoice",          # 发票
    "account",          # 账户问题
    "other",            # 其他
]

# ============ 模拟知识库 (FAQ) ============
KNOWLEDGE_BASE = [
    {"q": "如何查询订单", "a": "您可以在'我的订单'页面查看所有订单状态，或提供订单号我帮您查询。", "category": "order_query"},
    {"q": "退款多久到账", "a": "退款申请通过后，原路返回通常1-3个工作日到账，银行卡可能延迟至7个工作日。", "category": "refund"},
    {"q": "可以修改收货地址吗", "a": "订单未发货前可以修改收货地址，已发货订单需联系快递拦截或拒收后重新下单。", "category": "address_change"},
    {"q": "物流一直不更新", "a": "物流信息可能存在延迟，建议24小时后再次查询。如超过48小时未更新，我帮您联系快递核实。", "category": "logistics_query"},
    {"q": "商品有质量问题", "a": "非常抱歉给您带来不便！请提供订单号和问题照片，我为您申请退换货，质量问题运费由我们承担。", "category": "complaint"},
    {"q": "如何申请退货", "a": "您可以在订单详情页点击'申请退货'，选择退货原因并提交，我们会在24小时内审核。", "category": "return"},
    {"q": "怎么开发票", "a": "订单完成后可在'我的订单'中申请电子发票，支持普通发票和专用发票，1-3个工作日开具。", "category": "invoice"},
]
