import asyncio
import base64
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_messages_by_session, init_db
import fitz

init_db()
client = TestClient(app)

def test_file_extract_and_chat_attachment():
    print("Testing File Extraction and Chat Attachment Flow...")
    
    # 1. Verify Frontend UI Elements in static/index.html
    home_res = client.get("/")
    assert home_res.status_code == 200
    html_content = home_res.text
    assert 'id="attach-file-btn"' in html_content, "Missing attach-file-btn in UI"
    assert 'id="file-upload-input"' in html_content, "Missing file-upload-input in UI"
    assert 'id="attachment-tray"' in html_content, "Missing attachment-tray in UI"
    assert 'id="drag-drop-overlay"' in html_content, "Missing drag-drop-overlay in UI"
    assert 'id="file-preview-modal"' in html_content, "Missing file-preview-modal in UI"
    assert 'id="guest-login-btn"' in html_content, "Missing guest-login-btn in UI"
    print("Frontend Attachment & Guest UI Elements Verified [PASS]")

    # 2. Login to get token
    login_res = client.post("/api/auth/login", json={
        "username": "Rohan Mehta",
        "email": f"rohan-{uuid.uuid4().hex[:8]}@example.com",
        "password": "pass1234Secure",
        "login_method": "email",
        "is_team_alum": False
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Test Text / Python Code extraction
    py_code = 'def hello_world():\n    return "Alumni AI with OpenCode Zen"\nprint(hello_world())'
    b64_code = base64.b64encode(py_code.encode("utf-8")).decode("utf-8")
    
    extract_res = client.post("/api/files/extract", json={
        "name": "hello.py",
        "content_base64": b64_code,
        "type": "text/x-python"
    }, headers=headers)
    assert extract_res.status_code == 200, f"Code extract failed: {extract_res.text}"
    data = extract_res.json()
    assert data["name"] == "hello.py"
    assert "Alumni AI" in data["text"]
    assert data["char_count"] == len(py_code)
    print("Python code extraction: [PASS]")

    # 3. Create a synthetic PDF using PyMuPDF and test PDF extraction
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Alumni AI Autonomous Reasoning Paper\nAuthor: Sudarshan Hadmode\nFounder of Team Alum", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_res = client.post("/api/files/extract", json={
        "name": "research_paper.pdf",
        "content_base64": b64_pdf,
        "type": "application/pdf"
    }, headers=headers)
    assert pdf_res.status_code == 200, f"PDF extract failed: {pdf_res.text}"
    pdf_data = pdf_res.json()
    assert pdf_data["pages"] >= 1
    assert "Autonomous Reasoning" in pdf_data["text"]
    print("PyMuPDF PDF extraction: [PASS]")

    # 4. Test Chat Message with Attachment
    chat_res = client.post("/api/chat", json={
        "message": "Please review this Python function and explain what it does.",
        "mode": "professional",
        "attachments": [
            {
                "name": "hello.py",
                "type": "text/x-python",
                "size": len(py_code),
                "text": py_code
            }
        ]
    }, headers=headers)
    assert chat_res.status_code == 200, f"Chat with attachment failed: {chat_res.text}"
    chat_data = chat_res.json()
    session_id = chat_data["session_id"]
    assert chat_data["user_message"]["attachments"] is not None
    assert len(chat_data["user_message"]["attachments"]) == 1
    assert chat_data["user_message"]["attachments"][0]["name"] == "hello.py"
    print("Chat message with file attachment: [PASS]")

    # 5. Verify database persistence and session history restoration
    messages = get_messages_by_session(session_id)
    user_msg_db = messages[0]
    assert user_msg_db["attachments"] is not None
    assert user_msg_db["attachments"][0]["name"] == "hello.py"
    print("Database persistence of attachments: [PASS]")

    print("\n=======================================================")
    print("ALL FILE EXTRACTION & ATTACHMENT TESTS PASSED 100%!")
    print("=======================================================\n")

if __name__ == "__main__":
    test_file_extract_and_chat_attachment()
