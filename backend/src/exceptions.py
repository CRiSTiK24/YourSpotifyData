from html import escape

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from src.html import page


async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    content = f"""
<h1>Error {exc.status_code}</h1>
<p style="color:#8b949e">{escape(str(exc.detail))}</p>
<a class="back-link" href="/">← Back to home</a>
"""
    response = page(content)
    response.status_code = exc.status_code
    return response
