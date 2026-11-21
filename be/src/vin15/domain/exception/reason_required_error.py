from .invalid_input_error import InvalidInputError


class ReasonRequiredError(InvalidInputError):
    """Quyết định từ chối / yêu cầu sửa / không duyệt bắt buộc có lý do (BR-S2). API trả 422."""
