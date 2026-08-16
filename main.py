# -*- coding: utf-8 -*-
"""
ServicePilot - 智能客服多Agent自主闭环系统
GOAI世界人工智能开源大赛 Agent Infra赛道 初赛Demo

运行方式:
    python main.py          自动演示5个场景
    python main.py 2        交互模式
    python main.py 3        仅运行订单查询场景

运行完成后，output/ 下生成 trace/log/metrics/session/summary 证据文件。
"""

import sys
from pathlib import Path

from config import SYSTEM_VERSION
from mock_systems import MockBusinessSystems
from skills import register_all_skills
from agents import create_all_agents
from manager import AgentTeamsManager
from llm import create_llm_client


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


def print_banner():
    """打印欢迎横幅"""
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                    ServicePilot v{SYSTEM_VERSION}                       ║
║           智能客服多Agent自主闭环系统                          ║
║           GOAI Agent Infra 赛道初赛Demo                       ║
╠══════════════════════════════════════════════════════════════╣
║  架构: AgentTeams Manager-Workers (7个职能Agent)              ║
║  闭环: 意图识别→知识检索→任务规划→工具执行→质量审核→验证→沉淀  ║
║  安全: L0-L3四级风险管控，高风险操作审批+回滚+审计              ║
║  可观测: Trace/Log/Metrics + 评估回放                          ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def demo_scenario_1_order_query(manager):
    """Demo场景1: 订单查询 (L0只读，全自动闭环)"""
    print("\n" + "█"*60)
    print("█ Demo场景1: 订单查询 (L0 只读诊断，全自动执行)")
    print("█"*60)
    return manager.run("我的订单ORD20260816001现在什么状态了？帮我查一下")


def demo_scenario_2_refund_approved(manager):
    """Demo场景2: 退款申请 (L2高风险，自动审批通过后执行)"""
    print("\n" + "█"*60)
    print("█ Demo场景2: 退款申请 (L2 高风险，审批通过 → 幂等执行 → 审计)")
    print("█"*60)
    return manager.run("我要退款，订单ORD20260816001不想要了", auto_approve=True,
                       approver="demo_admin")


def demo_scenario_3_refund_rejected(manager):
    """Demo场景3: 退款申请 (L2高风险，审批拒绝后转人工)"""
    print("\n" + "█"*60)
    print("█ Demo场景3: 退款申请 (L2 高风险，审批拒绝 → 转人工)")
    print("█"*60)
    return manager.run("我要退款，订单ORD20260816002不想要了", auto_approve=False,
                       approver="demo_admin")


def demo_scenario_4_address_change(manager):
    """Demo场景4: 修改地址 (L1低风险，执行失败自动转人工)"""
    print("\n" + "█"*60)
    print("█ Demo场景4: 修改收货地址 (L1 执行失败 → 自动转人工)")
    print("█"*60)
    return manager.run("帮我把订单ORD20260816001的收货地址改成南京市玄武区zzz路3号")


def demo_scenario_5_complaint(manager):
    """Demo场景5: 投诉 (高紧急度，自动创建高优先级工单)"""
    print("\n" + "█"*60)
    print("█ Demo场景5: 用户投诉 (高紧急度，自动创建工单)")
    print("█"*60)
    return manager.run("你们什么垃圾客服！等了三天都没解决问题，我要投诉！")


def demo_scenario_6_return(manager):
    """Demo场景6: 退货咨询 (知识库自动回复)"""
    print("\n" + "█"*60)
    print("█ Demo场景6: 退货咨询 (RAG知识库自动闭环)")
    print("█"*60)
    return manager.run("我要申请退货，流程是什么？")


def demo_scenario_7_unknown(manager):
    """Demo场景7: 未知问题 (低置信度，自动转人工)"""
    print("\n" + "█"*60)
    print("█ Demo场景7: 未知问题 (RAG低置信度 -> 自动转人工)")
    print("█"*60)
    return manager.run("今天天气怎么样？")


def interactive_mode(manager):
    """交互模式 - 用户手动输入"""
    print("\n💬 进入交互模式，输入 'quit' 退出\n")
    while True:
        try:
            user_input = input("👤 你: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 再见！")
                break
            if not user_input:
                continue
            manager.run(user_input)
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    print_banner()

    print("🔧 初始化Mock业务系统 (订单/工单/支付/物流)...")
    mock_systems = MockBusinessSystems()

    print("📦 注册Skill体系 (诊断/知识/执行/治理/沉淀 5大类)...")
    skills = register_all_skills(mock_systems)
    print(f"   已注册 {len(skills)} 个Skill")

    print("🤖 创建Agent团队 (7个职能Agent)...")
    agents = create_all_agents(skills)
    for name, agent in agents.items():
        print(f"   - {name}: {agent.role}")

    print("🎯 启动AgentTeams Manager...")
    llm_client = create_llm_client()
    print(f"   LLM适配器: {type(llm_client).__name__} (可配置 OpenAI 兼容接口)")
    manager = AgentTeamsManager(agents, debug=True, llm_client=llm_client,
                                output_dir=OUTPUT_DIR)

    print("\n" + "="*60)
    print("📋 选择运行模式:")
    print("  1. 自动演示7个场景 (订单/退款通过/退款拒绝/改地址/投诉/退货/未知转人工)")
    print("  2. 交互模式 (手动输入)")
    print("  3. 仅运行订单查询场景")
    print("="*60)

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("请选择 (1/2/3，默认1): ").strip() or "1"

    if choice == "1":
        demo_scenario_1_order_query(manager)
        demo_scenario_2_refund_approved(manager)
        demo_scenario_3_refund_rejected(manager)
        demo_scenario_4_address_change(manager)
        demo_scenario_5_complaint(manager)
        demo_scenario_6_return(manager)
        demo_scenario_7_unknown(manager)
    elif choice == "2":
        interactive_mode(manager)
    elif choice == "3":
        demo_scenario_1_order_query(manager)
    else:
        print("无效选择，运行默认场景")
        demo_scenario_1_order_query(manager)

    print("\n✅ Demo运行完成！")
    print(f"📁 证据输出目录: {OUTPUT_DIR}")
    for name in ("trace.jsonl", "logs.jsonl", "metrics.json", "session.json", "summary.json"):
        print(f"   - {OUTPUT_DIR / name}")
    print("📌 提示: 本Demo默认使用零依赖规则引擎，设置 SERVICE_PILOT_LLM_API_KEY 可切换真实LLM")
    print("📌 复赛将接入真实AgentTeams平台和业务系统API")


if __name__ == "__main__":
    main()
