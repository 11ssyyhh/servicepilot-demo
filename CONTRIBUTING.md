# 参与贡献

ServicePilot 欢迎以下类型贡献：

- 新增/改进 Skill（标准 Schema + 失败处理 + 安全边界）
- 补充 Golden/Badcase 评估用例
- 完善 MCP 契约与真实系统适配器
- 修复缺陷、补充测试与文档

## 开发流程

```bash
python main.py 1              # 运行 5 场景闭环
python -m unittest discover -s tests -t . -v   # 26 项测试
python evaluate.py            # 回归评估
python replay.py              # 回放最近一次会话
```

## 提交规范

- 每个 PR 聚焦一个改动点，附带测试与文档更新。
- 新 Skill 必须在 `docs/03-Skill清单.md` 补充输入输出、失败处理、安全边界与复用价值。
- 涉及写操作必须携带 `idempotency_key` 与回滚点。
- 所有新代码保持零外部依赖（规则引擎兜底）；真实 LLM 通过 `llm.py` 适配器接入。

## License

本项目代码采用 MIT License，文档采用 CC BY 4.0。
