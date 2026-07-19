"""Business exception definitions

The service layer raises these exceptions; the API layer is responsible for
converting them to HTTP responses.
"""


class BusinessException(Exception):
    """Business exception
    
    Args:
        message: Error message
        status_code: HTTP status code (404/400/409, etc.)
    """
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
