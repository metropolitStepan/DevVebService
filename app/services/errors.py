class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class BadRequestError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=400, code=code, message=message)


class UnauthorizedError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=401, code=code, message=message)


class ForbiddenError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=403, code=code, message=message)


class NotFoundError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=404, code=code, message=message)


class ConflictError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=409, code=code, message=message)
