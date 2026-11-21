class AgentUnavailableError(Exception):
    """Service agent không nối được hoặc trả lỗi. API trả 503, nghiệp vụ không phụ thuộc agent vẫn chạy."""
