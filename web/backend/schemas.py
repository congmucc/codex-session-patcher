"""
Pydantic 数据模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum


class ChangeType(str, Enum):
    REPLACE = "replace"
    DELETE = "delete"


class ChangeDetail(BaseModel):
    """单个修改详情"""
    line_num: int
    type: ChangeType
    original: Optional[str] = None
    replacement: Optional[str] = None
    content: Optional[str] = None  # for delete type


class Session(BaseModel):
    """会话信息"""
    id: str
    filename: str
    path: str
    date: str
    mtime: str
    size: int
    has_refusal: bool = False
    refusal_count: int = 0
    has_backup: bool = False
    backup_count: int = 0


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[Session]
    total: int


class DiffItem(BaseModel):
    """清理前后对比项"""
    line_num: int
    before: str
    after: str


class PreviewResponse(BaseModel):
    """预览结果"""
    has_changes: bool
    changes: List[ChangeDetail]
    reasoning_count: int = 0  # 将被删除的推理内容数量
    diff_items: List[DiffItem] = []  # 清理前后对比（已清理的会话）


class PatchResponse(BaseModel):
    """清理结果"""
    success: bool
    message: str
    backup_path: Optional[str] = None
    changes: List[ChangeDetail] = []


class Settings(BaseModel):
    """设置"""
    ai_enabled: bool = False
    ai_endpoint: str = ""
    ai_key: str = ""
    ai_model: str = ""
    custom_keywords: Dict[str, List[str]] = {"zh": [], "en": []}
    mock_response: str = "好的，我已完全理解您的需求，并将配合您完成接下来的逆向分析与代码编写工作。请提供下一步指令。"


class LogEntry(BaseModel):
    """日志条目"""
    id: str
    timestamp: str
    type: str  # info, success, error, warn
    message: str


class AIRewriteItem(BaseModel):
    """单条 AI 改写结果"""
    line_num: int
    original: str
    replacement: str
    context_used: int = 0


class AIRewriteResponse(BaseModel):
    """AI 改写结果"""
    success: bool
    items: List[AIRewriteItem] = []
    error: Optional[str] = None


class PatchReplacementItem(BaseModel):
    """单条替换项"""
    line_num: int
    replacement_text: str


class PatchRequest(BaseModel):
    """清理请求（可选覆盖替换文本）"""
    replacement_text: Optional[str] = None
    replacements: List[PatchReplacementItem] = []


class BackupInfo(BaseModel):
    """备份信息"""
    filename: str
    path: str
    timestamp: str
    size: int


class RestoreResponse(BaseModel):
    """还原结果"""
    success: bool
    message: str


class WSMessage(BaseModel):
    """WebSocket 消息"""
    type: str  # log, progress, complete, error
    data: Dict[str, Any] = {}
