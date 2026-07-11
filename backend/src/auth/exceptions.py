from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse


class NotAuthenticated(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")


async def not_authenticated_handler(request: Request, exc: NotAuthenticated) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=302)
