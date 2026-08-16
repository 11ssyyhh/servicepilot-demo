# -*- coding: utf-8 -*-
"""
数据脱敏模块

对手机号、邮箱、身份证、地址等 PII 做规则脱敏，保证证据文件与日志合规。
"""

import re
from typing import Dict, Tuple


_PHONE_RE = re.compile(r"1[3-9]\d{9}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_ID_RE = re.compile(r"\d{17}[\dXx]")
_ADDRESS_KEYWORDS = ("路", "街", "号", "区", "镇", "村", "小区", "大厦")


def mask_phone(text: str) -> str:
    return _PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], text)


def mask_email(text: str) -> str:
    return _EMAIL_RE.sub(lambda m: m.group(0)[:2] + "***@" + m.group(0).split("@")[-1], text)


def mask_id_card(text: str) -> str:
    return _ID_RE.sub(lambda m: m.group(0)[:4] + "**********" + m.group(0)[-4:], text)


def mask_address(text: str) -> str:
    """把常见地址中的门牌与详细部分脱敏"""
    tokens = re.split(r"([\u4e00-\u9fa5]{2,}(?:路|街|道|巷|号|小区|大厦|村|镇|区))", text)
    masked = []
    for i, token in enumerate(tokens):
        if i % 2 == 1 and token:
            masked.append(token[:2] + "***")
        else:
            masked.append(token)
    return "".join(masked)


def mask_pii(text: str) -> Tuple[str, Dict[str, int]]:
    """
    对文本执行全量 PII 脱敏，返回 (脱敏文本, 命中统计)
    """
    before = text
    hits: Dict[str, int] = {}

    text = mask_phone(text)
    hits["phone"] = len(_PHONE_RE.findall(before))
    text = mask_email(text)
    hits["email"] = len(_EMAIL_RE.findall(before))
    text = mask_id_card(text)
    hits["id_card"] = len(_ID_RE.findall(before))

    # 地址脱敏（仅当文本看起来像地址时执行，避免误伤普通句子）
    if any(kw in before for kw in _ADDRESS_KEYWORDS) and len(before) <= 200:
        text = mask_address(text)
        hits["address"] = 1
    else:
        hits["address"] = 0

    return text, hits


def mask_state_snapshot(state_dict: dict) -> dict:
    """对会话快照中的用户消息做脱敏"""
    snapshot = dict(state_dict)
    messages = snapshot.get("messages", [])
    masked_messages = []
    for msg in messages:
        item = dict(msg)
        if item.get("role") == "user":
            item["content"], _ = mask_pii(item.get("content", ""))
        masked_messages.append(item)
    snapshot["messages"] = masked_messages
    if snapshot.get("summary"):
        snapshot["summary"], _ = mask_pii(str(snapshot["summary"]))
    for key in ("task_plan", "execution_records", "rollback_points",
                "tickets", "final_reply"):
        if snapshot.get(key) is not None:
            snapshot[key] = _mask_value(snapshot[key])
    return snapshot


def _mask_value(value):
    """递归脱敏字典/列表/字符串中的 PII"""
    if isinstance(value, str):
        masked, _ = mask_pii(value)
        return masked
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    return value
