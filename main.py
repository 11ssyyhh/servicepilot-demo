# -*- coding: utf-8 -*-
"""
ServicePilot - 智能客服多Agent自主闭环系统
GOAI世界人工智能开源大赛 Agent Infra赛道 初赛Demo

这是一个可直接运行的Demo，模拟AgentTeams的Manager-Workers架构
实现7个Agent协同的智能客服自主闭环

运行方式: python main.py
"""

import sys
import json
from mock_systems import MockBusinessSystems
from skills import register_all_skills
from agents import create_all_agents
from manager import AgentTeamsManager


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    ServicePilot v0.1.0                       ║
║           智能客服多Agent自主闭环系统                          ║
║           GOAI Agent Infra 赛道初赛Demo                       ║
╠══════════════════════════════════════════════════════════════╣
║  架构: AgentTeams Manager-Workers (7个职能Agent)              ║
║  闭环: 意图识别→知识检索→任务规划→工具执行→质量审核→验证→沉淀  ║
║  安全: L0-L3四级风险管控，高风险操作审批+回滚+审计              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def demo_scenario_1_order_query(manager):
    """Demo场景1: 订单查询 (L0只读，全自动闭环)"""
    print("\n" + "█"*60)
    print("█ Demo场景1: 订单查询 (L0 只读诊断，全自动执行)")
    print("█"*60)
    state = manager.run("我的订单ORD20260816001现在什么状态了？帮我查一下")
    return state


def demo_scenario_2_refund(manager):
    """Demo场景2: 退款申请 (L2高风险，需审批)"""
    print("\n" + "█"*60)
    print("█ Demo场景2: 退款申请 (L2 高风险，需人工审批)")
    print("█"*60)
    state = manager.run("我要退款，订单ORD20260816001不想要了", auto_approve=True)
    return state


def demo_scenario_3_address_change(manager):
    """Demo场景3: 修改地址 (L1低风险，自动执行)"""
    print("\n" + "█"*60)
    print("█ Demo场景3: 修改收货地址 (L1 低风险，自动执行)")
    print("█"*60)
    state = manager.run("帮我把订单ORD20260816001的收货地址改成南京市玄武区zzz路3号")
    return state


def demo_scenario_4_complaint(manager):
    """Demo场景4: 投诉 (高紧急度，自动转人工)"""
    print("\n" + "█"*60)
    print("█ Demo场景4: 用户投诉 (高紧急度，自动创建工单)")
    print("█"*60)
    state = manager.run("你们什么垃圾客服！等了三天都没解决问题，我要投诉！")
    return state


def interactive_mode(manager):
    """交互模式 - 用户手动输入"""
    print("\n💬 进入交互模式，输入 'quit' 退出\n")
    while True:
        try:
            user_input = input("👤 你: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 再见！")
                break
            if not user_input:
                continue
            manager.run(user_input)
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


def main():
    print_banner()
    
    # 1. 初始化Mock业务系统 (模拟MCP适配器对接订单/工单/支付/物流)
    print("🔧 初始化Mock业务系统 (订单/工单/支付/物流)...")
    mock_systems = MockBusinessSystems()
    
    # 2. 注册所有Skill (15+核心Skill)
    print("📦 注册Skill体系 (诊断/知识/执行/治理/沉淀 5大类)...")
    skills = register_all_skills(mock_systems)
    print(f"   已注册 {len(skills)} 个Skill")
    
    # 3. 创建所有Agent (7个职能Agent)
    print("🤖 创建Agent团队 (7个职能Agent)...")
    agents = create_all_agents(skills)
    for name, agent in agents.items():
        print(f"   - {name}: {agent.role}")
    
    # 4. 创建Manager (AgentTeams编排器)
    print("🎯 启动AgentTeams Manager...")
    manager = AgentTeamsManager(agents, debug=True)
    
    # 5. 运行Demo场景
    print("\n" + "="*60)
    print("📋 选择运行模式:")
    print("  1. 自动演示4个场景 (订单查询/退款/改地址/投诉)")
    print("  2. 交互模式 (手动输入)")
    print("  3. 仅运行订单查询场景")
    print("="*60)
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("请选择 (1/2/3，默认1): ").strip() or "1"
    
    if choice == "1":
        demo_scenario_1_order_query(manager)
        demo_scenario_2_refund(manager)
        demo_scenario_3_address_change(manager)
        demo_scenario_4_complaint(manager)
    elif choice == "2":
        interactive_mode(manager)
    elif choice == "3":
        demo_scenario_1_order_query(manager)
    else:
        print("无效选择，运行默认场景")
        demo_scenario_1_order_query(manager)
    
    print("\n✅ Demo运行完成！")
    print("📌 提示: 本Demo使用纯Python模拟AgentTeams架构，无外部依赖")
    print("📌 复赛将接入真实AgentTeams平台和业务系统API")


if __name__ == "__main__":
    main()
