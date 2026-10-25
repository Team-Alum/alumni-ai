from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class LoginRequest(BaseModel):
    username: Optional[str] = ""
    email: Optional[str] = ""
    password: Optional[str] = None
    login_method: str = "username" # "google", "username", "alum", "guest"
    is_team_alum: bool = False


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    login_method: str
    is_team_alum: bool
    token: str
    name_adjusted: bool = False

class FileAttachment(BaseModel):
    name: str
    type: Optional[str] = "text/plain"
    size: Optional[int] = 0
    pages: Optional[int] = None
    text: Optional[str] = ""

class FileExtractRequest(BaseModel):
    name: str
    content_base64: str
    type: Optional[str] = None

class FileExtractResponse(BaseModel):
    name: str
    type: str
    size: int
    pages: Optional[int] = 1
    text: str
    char_count: int

class ChatMessage(BaseModel):
    id: Optional[int] = None
    session_id: str
    sender: str
    content: str
    mode: str = "professional"
    created_at: Optional[str] = None
    sources: Optional[List[Dict[str, str]]] = None
    suggested_questions: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., max_length=100000, description="User prompt up to 100,000 characters")
    mode: str = "professional" # "professional", "basic", "sarcastic"
    category: Optional[str] = "general"
    custom_api_key: Optional[str] = None
    web_research: Optional[bool] = False
    attachments: Optional[List[Dict[str, Any]]] = None
    use_memory: Optional[bool] = True

class ChatResponse(BaseModel):
    session_id: str
    user_message: ChatMessage
    ai_message: ChatMessage
    sources: Optional[List[Dict[str, str]]] = None
    suggested_questions: Optional[List[str]] = None
    memory_used: Optional[bool] = False

class ResearchQueryRequest(BaseModel):
    query: str = Field(..., max_length=1000, description="Topic or query to research across the web")
    session_id: Optional[str] = None
    mode: Optional[str] = "professional"
    custom_api_key: Optional[str] = None
    depth: Optional[str] = "deep"

class ResearchQueryResponse(BaseModel):
    session_id: str
    query: str
    research_summary: str
    sources: List[Dict[str, str]]
    answer: str
    suggested_questions: List[str]
    provider: str

class ResearchSuggestionItem(BaseModel):
    category: str
    icon: str
    title: str
    query: str
    description: Optional[str] = ""

class SessionCreateRequest(BaseModel):
    title: str
    category: str = "general"
    mode: str = "professional"

class SessionItem(BaseModel):
    id: str
    user_id: str
    title: str
    category: str
    mode: str
    created_at: str
    updated_at: str

class VoiceQueryRequest(BaseModel):
    query: str = Field(..., max_length=1000)
    mode: str = "professional"
    session_id: Optional[str] = None
    custom_api_key: Optional[str] = None
    speaker: Optional[str] = None
    language: Optional[str] = None # "auto", "hi-IN", "en-IN"

class VoiceQueryResponse(BaseModel):
    reply: str
    audio_text: str
    mode: str
    audio_base64: Optional[str] = None
    provider: Optional[str] = "sarvam_bulbul"
    should_speak: bool = True
    action: Optional[str] = None # "stop", "open_settings", "close_settings", "open_browser", "toggle_theme", etc.
    language: Optional[str] = "en-IN"

class AnalyticsSummaryResponse(BaseModel):
    total_queries: int
    total_users: int
    total_sessions: int
    queries_today: Optional[int] = 0
    active_users_7d: Optional[int] = 0
    avg_latency_ms: float
    provider_distribution: Dict[str, int]
    mode_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    daily_volume: List[Dict[str, Any]]

class AnalyticsEventItem(BaseModel):
    id: int
    user_id: str
    session_id: str
    prompt_chars: int
    response_chars: int
    latency_ms: int
    provider_used: str
    fallback_count: int
    mode: str
    status: str
    created_at: str
    username: Optional[str] = None
    email: Optional[str] = None


class BrowserSearchRequest(BaseModel):
    query: str = Field(..., max_length=300)
    max_results: int = 5

class BrowserBrowseRequest(BaseModel):
    url: str

class CodeRunRequest(BaseModel):
    code: str = Field(..., max_length=5000)
    language: str = "python"
