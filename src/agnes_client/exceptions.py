"""
Agnes Client Exceptions
"""

class AgnesAPIError(Exception):
    """Agnes API 调用失败"""
    pass

class AgnesTimeoutError(AgnesAPIError):
    """Agnes 超时"""
    pass

class AgnesQCFailedError(Exception):
    """QC 校验失败，200次尝试后仍未通过"""
    def __init__(self, clip_id, attempts, last_qc_result):
        self.clip_id = clip_id
        self.attempts = attempts
        self.last_qc_result = last_qc_result
        super().__init__(f"Clip {clip_id} QC failed after {attempts} attempts. Last score: {last_qc_result.overall_score}")

class AgnesRateLimitError(AgnesAPIError):
    """限流"""
    pass
