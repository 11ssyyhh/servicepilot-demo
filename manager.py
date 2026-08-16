# -*- coding: utf-8 -*-
"""
Manager模块 - 模拟AgentTeams的Manager角色
Manager-Workers架构：Manager centrally orchestrates multiple Workers
负责任务拆解、Agent调度、状态流转、异常处理
这是多Agent自主闭环的核心编排器
"""

import time
from typing import Dict, List, Optional
from shared_state import SharedState
from agents import BaseAgent


class AgentTeamsManager:
    """
    AgentTeams Manager - 多Agent编排器
    模拟AgentTeams平台的Manager-Workers协作模式
    
    核心职责：
    1. 接收用户输入，初始化会话状态
    2. 按流水线调度7个Agent执行
    3. 管理审批流程（高风险操作）
    4. 处理异常和升级
    5. 输出最终结果和服务报告
    """
    
    def __init__(self, agents: Dict[str, BaseAgent], debug: bool = True):
        self.agents = agents
        self.debug = debug
        # 定义Agent执行流水线 (自主闭环链路)
        self.pipeline = [
            "IntentRouter",        # 1. 意图路由
            "KnowledgeRetriever",  # 2. 知识检索
            "TaskPlanner",         # 3. 任务规划
            "ToolExecutor",        # 4. 工具执行
            "QualityGuard",        # 5. 质量风控
            "Verifier",            # 6. 效果验证
            "MemoryScribe",        # 7. 记忆沉淀
        ]
    
    def run(self, user_message: str, auto_approve: bool = True) -> SharedState:
        """
        运行完整的客服自主闭环
        
        Args:
            user_message: 用户输入消息
            auto_approve: 是否自动审批高风险操作(Demo模式下默认True)
        
        Returns:
            SharedState: 完整的会话状态
        """
        # 初始化会话状态
        state = SharedState()
        state.add_message("user", user_message)
        
        if self.debug:
            print(f"\n{'='*60}")
            print(f"🚀 ServicePilot 会话启动 | Session: {state.session_id}")
            print(f"👤 用户: {user_message}")
            print(f"{'='*60}")
        
        # 按流水线执行各Agent
        for agent_name in self.pipeline:
            agent = self.agents[agent_name]
            
            if self.debug:
                print(f"\n▶️ [{agent_name}] {agent.role} - 开始处理")
            
            try:
                # 执行前检查：如果有高风险待审批项，先处理审批
                if agent_name == "ToolExecutor" and state.pending_approvals:
                    self._handle_approvals(state, auto_approve)
                
                # 执行Agent
                state = agent.process(state)
                
                if self.debug:
                    self._print_agent_result(agent_name, state)
                    
            except Exception as e:
                print(f"❌ [{agent_name}] 执行异常: {str(e)}")
                # 异常处理：创建工单转人工
                state.add_message("system", f"Agent {agent_name} 异常，转人工处理")
                break
            
            # 检查是否需要提前终止 (如转人工)
            if state.urgency == "high" and agent_name == "IntentRouter":
                if self.debug:
                    print(f"⚠️ 检测到高紧急度，加速处理")
        
        if self.debug:
            self._print_final_report(state)
        
        return state
    
    def _handle_approvals(self, state: SharedState, auto_approve: bool):
        """处理待审批项 (模拟人工审批)"""
        for approval in state.pending_approvals[:]:
            if auto_approve:
                # Demo模式下自动审批
                state.approve(approval["id"], approved=True, approver="auto_demo")
                if self.debug:
                    print(f"  ✅ [自动审批] {approval['action']} - Demo模式自动通过")
            else:
                # 真实场景需要用户确认
                print(f"\n  ⚠️ [需要审批] {approval['action']}")
                print(f"     原因: {approval['reason']}")
                print(f"     风险等级: {approval['risk_level']}")
                # 这里可以等待用户输入，Demo中默认拒绝
                state.approve(approval["id"], approved=False, approver="user")
    
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
                print(f"     {status} {rec.skill_name} -> {rec.risk_level}")
        elif agent_name == "QualityGuard":
            status = "✅通过" if state.quality_check_passed else f"⚠️{len(state.quality_issues)}个问题"
            print(f"  🛡️ 质量审核: {status}")
        elif agent_name == "Verifier":
            status = "✅已解决" if state.issue_resolved else "❌未解决"
            print(f"  ✔️ 效果验证: {status} | 满意度={state.satisfaction_score:.2f}")
        elif agent_name == "MemoryScribe":
            print(f"  💾 已生成摘要和服务报告")
    
    def _print_final_report(self, state: SharedState):
        """打印最终报告"""
        print(f"\n{'='*60}")
        print(f"📊 服务报告 | Session: {state.session_id}")
        print(f"{'='*60}")
        print(f"  意图: {state.intent}")
        print(f"  情绪: {state.sentiment:.2f}")
        print(f"  风险等级: {state.overall_risk_level}")
        print(f"  问题解决: {'✅ 是' if state.issue_resolved else '❌ 否'}")
        print(f"  满意度: {state.satisfaction_score:.2f}")
        print(f"  Agent调用: {len(self.pipeline)}个")
        print(f"  工具调用: {len(state.execution_records)}次")
        print(f"  对话轮次: {len(state.messages)}")
        print(f"  摘要: {state.conversation_summary[:80]}...")
        print(f"{'='*60}\n")
    
    def get_timeline(self, state: SharedState) -> List[Dict]:
        """获取执行时间线 (用于PPT/Demo展示)"""
        return state.timeline
