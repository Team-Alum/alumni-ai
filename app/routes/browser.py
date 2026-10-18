from fastapi import APIRouter, Depends
from app.models import BrowserSearchRequest, BrowserBrowseRequest, CodeRunRequest
from app.services.browser_service import search_web, browse_url
from app.services.code_sandbox import execute_python_code
from app.security import get_current_user

router = APIRouter(prefix="/api/tools", tags=["Tools & Browser"])

@router.post("/search")
async def handle_browser_search(payload: BrowserSearchRequest, user: dict = Depends(get_current_user)):
    results = await search_web(payload.query, payload.max_results)
    return {"query": payload.query, "results": results}

@router.post("/browse")
async def handle_browse_url(payload: BrowserBrowseRequest, user: dict = Depends(get_current_user)):
    result = await browse_url(payload.url)
    return result

@router.post("/run-code")
def handle_code_run(payload: CodeRunRequest, user: dict = Depends(get_current_user)):
    result = execute_python_code(payload.code)
    return result
