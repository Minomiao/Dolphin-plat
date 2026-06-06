"""
上下文管理器: 负责构建、压缩和优化发送给模型的消息列表。

职责:
- 将 system prompt + 对话历史拼接为 API 所需的 messages 格式
- 预留上下文压缩、token 预算管理、滑动窗口等扩展点
"""

from modules.logger import get_logger

log = get_logger("Dolphin.context")

# 上下文窗口告警阈值
_WARN_THRESHOLD = 0.70   # 70%: 提醒用户
_HIGH_THRESHOLD = 0.85   # 85%: 建议清理
_CRITICAL_THRESHOLD = 0.95  # 95%: 强烈建议清理



class ContextManager:
    """管理发送给 API 的上下文消息列表。"""

    def __init__(self, get_system_prompt):
        self._get_system_prompt = get_system_prompt

    def prepare_messages(self, messages: list) -> list:
        """构建最终发送给 API 的完整消息列表。

        Args:
            messages: 当前的对话历史列表 (self.messages)
        扩展点:
        - 上下文压缩: 对 messages 做裁剪/摘要
        - 滑动窗口: 只保留最近 N 轮
        """
        system_message = {"role": "system", "content": self._get_system_prompt()}

        # ---- 上下文压缩注入点 ----
        # messages = self._compress(messages)

        # 确保 system 在最前面且不重复
        if messages and messages[0].get("role") == "system":
            # 替换原 system 为最新，但不在原列表上修改
            return [system_message] + messages[1:]
        else:
            return [system_message] + messages

    def check_context_usage(self, messages: list, context_window: int) -> dict | None:
        """检查当前上下文用量，在接近窗口上限时返回告警信息。

        Args:
            messages: 当前对话历史
            context_window: 模型的上下文窗口大小 (由调用方从 config 传入)

        Returns:
            None 表示使用率正常；dict 包含 usage_ratio / context_window / estimated_tokens / level
        """
        estimated = self._estimate_tokens(messages)
        ratio = estimated / context_window

        level = None
        if ratio >= _CRITICAL_THRESHOLD:
            level = "critical"
        elif ratio >= _HIGH_THRESHOLD:
            level = "high"
        elif ratio >= _WARN_THRESHOLD:
            level = "warn"

        if level is None:
            return None

        log.info(
            f"上下文用量告警: {ratio:.1%} ({estimated}/{context_window} tokens), level={level}"
        )
        return {
            "usage_ratio": ratio,
            "context_window": context_window,
            "estimated_tokens": estimated,
            "level": level,
        }

    def _estimate_tokens(self, messages: list) -> int:
        """估算消息列表的 token 数量 (近似算法)。

        中文约 1 字 = 1.5 token，英文约 1 词 ≈ 1.3 token。
        这里采用粗略平均: 字符数 / 3 作为 token 数估算。
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                # 粗略估算: 每 3 个字符 ≈ 1 token
                total += max(1, len(content) // 3)
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "")
                    name = fn.get("name", "")
                    total += max(1, len(args) // 3)
                    total += max(1, len(name) // 3)
            if msg.get("reasoning_content"):
                rc = msg["reasoning_content"]
                if isinstance(rc, str):
                    total += max(1, len(rc) // 3)
        return total

    # ---------- 预留扩展方法 ----------

    def _compress(self, messages: list) -> list:
        """上下文压缩 (待实现)。"""
        return messages
