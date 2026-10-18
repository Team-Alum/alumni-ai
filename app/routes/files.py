import base64
import logging
from fastapi import APIRouter, HTTPException, Depends
from app.models import FileExtractRequest, FileExtractResponse
from app.security import get_current_user

logger = logging.getLogger("AlumniAI.Files")
router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/extract", response_model=FileExtractResponse)
async def extract_file_content(payload: FileExtractRequest, user: dict = Depends(get_current_user)):
    name = (payload.name or "document").strip()
    b64_content = payload.content_base64
    if not b64_content:
        raise HTTPException(status_code=400, detail="Missing file content")

    # If content includes data URL prefix like "data:application/pdf;base64,...", strip it
    if "," in b64_content:
        b64_content = b64_content.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(b64_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}")

    file_size = len(raw_bytes)
    # Check max limit (15 MB)
    if file_size > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (limit is 15MB)")

    lower_name = name.lower()
    mime_type = (payload.type or "").lower()
    is_pdf = lower_name.endswith(".pdf") or "pdf" in mime_type
    is_image = mime_type.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"))

    extracted_text = ""
    pages = 1

    if is_image:
        # Image files: extract basic metadata instead of raw binary decode
        # (no OCR/vision pipeline yet — report type, size, and a clean note)
        ext = lower_name.rsplit(".", 1)[-1] if "." in lower_name else "image"
        extracted_text = (
            f"[Attached image: {name} — format: {ext.upper()}, size: {file_size} bytes. "
            f"Vision analysis of image pixels is not enabled in this build; "
            f"describe the image content in your message if specific analysis is needed.]"
        )
    elif is_pdf:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            pages = len(doc)
            page_texts = []
            for i, page in enumerate(doc):
                page_text = page.get_text().strip()
                if page_text:
                    page_texts.append(f"--- [Page {i + 1}] ---\n{page_text}")
            extracted_text = "\n\n".join(page_texts)
            if not extracted_text.strip():
                extracted_text = f"[PDF loaded: {pages} pages with no extractable text layer or image-only scanned document]"
        except Exception as e:
            logger.warning(f"PyMuPDF error: {e}")
            raise HTTPException(status_code=422, detail=f"Failed to extract PDF text: {str(e)}")
    else:
        # Text or code file
        try:
            extracted_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                extracted_text = raw_bytes.decode("latin-1")
            except Exception as e:
                raise HTTPException(status_code=422, detail="Unable to decode file content as text")

    return {
        "name": name,
        "type": payload.type or ("image/png" if is_image else "application/pdf" if is_pdf else "text/plain"),
        "size": file_size,
        "pages": pages,
        "text": extracted_text,
        "char_count": len(extracted_text)
    }
