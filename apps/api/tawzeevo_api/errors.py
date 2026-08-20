class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class AuthenticationError(AppError):
    def __init__(
        self,
        code: str = "INVALID_AUTHENTICATION",
        message: str = "Authentication is invalid or expired",
        *,
        clear_refresh_cookie: bool = False,
    ) -> None:
        super().__init__(401, code, message)
        self.clear_refresh_cookie = clear_refresh_cookie
