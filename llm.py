# -*- coding: utf-8 -*-
"""
可插拔 LLM 适配器

默认使用规则引擎（RuleLLM）保证零依赖可运行；配置 OpenAI 兼容接口后
自动切换真实 LLM，并把 Token 用量与成本写入 Metrics。

环境变量：
    SERVICE_PILOT_LLM_API_KEY    API Key（设置后启用 OpenAI 兼容客户端）
    SERVICE_PILOT_LLM_BASE_URL   OpenAI 兼容 Base URL
    SERVICE_PILOT_LLM_MODEL      模型名，默认 qwen-plus
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class LLMResult:
    """一次 LLM 调用的标准化结果"""
    text: str
    model: str = "rule-engine"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class BaseLLM:
    """LLM 适配器基类"""

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0,
             max_tokens: Optional[int] = None) -> LLMResult:
        raise NotImplementedError

    def complete(self, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.0, max_tokens: Optional[int] = None) -> LLMResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)


class RuleLLM(BaseLLM):
    """
    规则引擎兜底 LLM

    零依赖、确定性、可离线运行；在真实 LLM 不可用或超时时保持闭环可演示。
    """

    def __init__(self):
        self.model = "rule-engine"

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0,
             max_tokens: Optional[int] = None) -> LLMResult:
        started = time.time()
        text = self._rule_answer(messages)
        latency = round((time.time() - started) * 1000, 2)
        prompt_tokens = sum(max(1, len(m.get("content", "")) // 2) for m in messages)
        completion_tokens = max(1, len(text) // 2)
        return LLMResult(
            text=text,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency,
            cost_usd=0.0,
        )

    def _rule_answer(self, messages: List[Dict[str, str]]) -> str:
        text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
        # 意图校验：返回 prompt 中已给定的候选标签
        for candidate in ("order_query", "refund", "address_change", "complaint",
                          "logistics_query", "return", "invoice", "account", "product_consult"):
            if f"候选意图:{candidate}" in text or f"candidate:{candidate}" in text:
                return candidate
        # 摘要草稿：规则引擎默认保留草稿
        if "摘要草稿:" in text:
            idx = text.find("摘要草稿:")
            return text[idx + len("摘要草稿:"):].split("用户消息:")[0].strip()
        # 回复润色：规则引擎默认保留草稿
        if "草稿回复:" in text:
            idx = text.find("草稿回复:")
            return text[idx + len("草稿回复:"):].split("\n")[0].strip()
        return text


class OpenAICompatLLM(BaseLLM):
    """OpenAI 兼容 LLM 客户端（通义千问等）"""

    def __init__(self, api_key: str, base_url: str, model: str = "qwen-plus",
                 metrics_callback: Optional[Callable[[LLMResult], None]] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.metrics_callback = metrics_callback
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai 未安装，无法启用 OpenAICompatLLM") from exc
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0,
             max_tokens: Optional[int] = None) -> LLMResult:
        started = time.time()
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = self.client.chat.completions.create(**kwargs)
        latency = round((time.time() - started) * 1000, 2)
        usage = resp.usage
        result = LLMResult(
            text=resp.choices[0].message.content or "",
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            latency_ms=latency,
            cost_usd=self._estimate_cost(getattr(usage, "prompt_tokens", 0) or 0,
                                         getattr(usage, "completion_tokens", 0) or 0),
        )
        if self.metrics_callback:
            self.metrics_callback(result)
        return result

    @staticmethod
    def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
        # 通义千问 qwen-plus 大致价格（元/1K token，估算）
        return round(prompt_tokens * 0.0008 / 1000 + completion_tokens * 0.002 / 1000, 6)


def create_llm_client(metrics_callback: Optional[Callable[[LLMResult], None]] = None) -> BaseLLM:
    """按配置创建 LLM 客户端；未配置或依赖缺失时回退规则引擎"""
    api_key = os.getenv("SERVICE_PILOT_LLM_API_KEY", "").strip()
    base_url = os.getenv("SERVICE_PILOT_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    model = os.getenv("SERVICE_PILOT_LLM_MODEL", "qwen-plus").strip()
    if api_key:
        try:
            return OpenAICompatLLM(api_key=api_key, base_url=base_url, model=model,
                                   metrics_callback=metrics_callback)
        except Exception:
            return RuleLLM()
    return RuleLLM()
