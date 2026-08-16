# -*- coding: utf-8 -*-
"""测试公共工具"""

import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def make_manager(tmp_path=None, debug=False):
    from mock_systems import MockBusinessSystems
    from skills import register_all_skills
    from agents import create_all_agents
    from manager import AgentTeamsManager
    from llm import create_llm_client

    mock_systems = MockBusinessSystems()
    skills = register_all_skills(mock_systems)
    agents = create_all_agents(skills)
    output_dir = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp(prefix="servicepilot-test-"))
    return AgentTeamsManager(agents, debug=debug, llm_client=create_llm_client(),
                             output_dir=output_dir)
