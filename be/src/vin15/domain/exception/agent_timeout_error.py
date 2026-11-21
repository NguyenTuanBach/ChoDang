from .agent_unavailable_error import AgentUnavailableError


class AgentTimeoutError(AgentUnavailableError):
    """Agent không kết thúc lượt hỏi trong thời hạn. API trả 503 như agent không khả dụng; trợ lý báo ``timeout``."""
