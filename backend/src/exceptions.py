from html import escape

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from src.html import back_link, page


async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    content = f"""
<h1>Error {exc.status_code}</h1>
<p>{escape(str(exc.detail))}</p>
{back_link("/", "← Back to home")}
"""
    response = page(content)
    response.status_code = exc.status_code
    return response
