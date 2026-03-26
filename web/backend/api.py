"""
API 路由
"""

import os
import json
import re
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .schemas import (
    Session, SessionListResponse, PreviewResponse,
    PatchResponse, Settings, ChangeDetail, ChangeType, WSMessage,
    AIRewriteResponse, PatchRequest, BackupInfo, RestoreResponse, DiffItem
)

# 导入核心模块
from codex_session_patcher.core import (
    RefusalDetector,
    SessionParser,
    extract_text_content,
    get_assistant_messages,
    get_reasoning_items,
    MOCK_RESPONSE,
)

router = APIRouter()

# 默认路径
DEFAULT_SESSION_DIR = os.path.expanduser("~/.codex/sessions/")
DEFAULT_MEMORY_FILE = os.path.expanduser("~/.codex/memories/MEMORY.md")
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.codex-patcher/config.json")


# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: WSMessage):
        for connection in self.active_connections:
            await connection.send_json(message.model_dump())


manager = ConnectionManager()


# 全局检测器实例
_detector = RefusalDetector()


def check_session_refusal(file_path: str) -> tuple[bool, int]:
    """检查会话是否包含拒绝内容 - 扫描所有助手消息"""
    count = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'response_item':
                        payload = data.get('payload', {})
                        if payload.get('type') == 'message' and payload.get('role') == 'assistant':
                            content = extract_text_content(data)
                            if _detector.detect(content):
                                count += 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return count > 0, count


# 缓存
_session_cache = {}
_cache_time = 0
CACHE_TTL = 5  # 缓存 5 秒


def list_sessions(session_dir: str = DEFAULT_SESSION_DIR, skip_refusal_check: bool = False) -> list[Session]:
    """列出所有会话

    Args:
        session_dir: 会话目录
        skip_refusal_check: 是否跳过拒绝检测（用于加速列表加载）
    """
    sessions = []

    if not os.path.exists(session_dir):
        return sessions

    for root, dirs, files in os.walk(session_dir):
        for f in files:
            if f.endswith(".jsonl"):
                full_path = os.path.join(root, f)
                try:
                    stat = os.stat(full_path)
                    mtime = stat.st_mtime
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                    # 提取日期和 ID
                    match = re.match(r'rollout-(\d{4}-\d{2}-\d{2})T[\d-]+-([a-f0-9-]+)\.jsonl', f)
                    if match:
                        date = match.group(1)
                        session_id = match.group(2)[:8]
                    else:
                        date = mtime_str[:10]
                        session_id = f[:8]

                    # 跳过拒绝检测以加速列表加载
                    if skip_refusal_check:
                        has_refusal = False
                        refusal_count = 0
                    else:
                        has_refusal, refusal_count = check_session_refusal(full_path)

                    # 检查是否有备份文件
                    backup_count = 0
                    session_dir_path = os.path.dirname(full_path)
                    for bak_file in os.listdir(session_dir_path):
                        if bak_file.startswith(f + ".") and bak_file.endswith(".bak"):
                            backup_count += 1

                    sessions.append(Session(
                        id=session_id,
                        filename=f,
                        path=full_path,
                        date=date,
                        mtime=mtime_str,
                        size=stat.st_size,
                        has_refusal=has_refusal,
                        refusal_count=refusal_count,
                        has_backup=backup_count > 0,
                        backup_count=backup_count
                    ))
                except Exception:
                    continue

    # 按修改时间降序排序
    sessions.sort(key=lambda x: x.mtime, reverse=True)
    return sessions


def preview_session(file_path: str, mock_response: str = MOCK_RESPONSE,
                   custom_keywords: dict = None) -> PreviewResponse:
    """预览会话修改"""
    changes = []

    # 创建检测器
    detector = RefusalDetector(custom_keywords)

    try:
        # 读取完整文件
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return PreviewResponse(has_changes=False, changes=[])

    # 解析 JSONL
    parsed_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed_lines.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    assistant_msgs = get_assistant_messages(parsed_lines)
    for idx, msg in assistant_msgs:
        content = extract_text_content(msg)
        if detector.detect(content):
            changes.append(ChangeDetail(
                line_num=idx + 1,
                type=ChangeType.REPLACE,
                original=content[:500] + ('...' if len(content) > 500 else ''),
                replacement=mock_response
            ))

    # 计算推理内容数量（会在执行时自动删除）
    reasoning_items = get_reasoning_items(parsed_lines)
    reasoning_count = len(reasoning_items)

    return PreviewResponse(
        has_changes=len(changes) > 0,
        changes=changes,
        reasoning_count=reasoning_count
    )


def patch_session(file_path: str, mock_response: str = MOCK_RESPONSE,
                 custom_keywords: dict = None, create_backup: bool = True,
                 replacements: dict = None) -> PatchResponse:
    """执行会话清理

    Args:
        replacements: {line_num: replacement_text} 按行号指定替换文本
    """
    changes = []
    if replacements is None:
        replacements = {}

    # 创建检测器
    detector = RefusalDetector(custom_keywords)

    try:
        # 创建备份
        backup_path = None
        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{file_path}.{timestamp}.bak"
            shutil.copy2(file_path, backup_path)

        # 解析会话
        parser = SessionParser()
        lines = parser.parse_session_jsonl(file_path)

        # 处理助手消息
        import copy
        assistant_msgs = get_assistant_messages(lines)
        for msg_idx, msg in assistant_msgs:
            content = extract_text_content(msg)
            if detector.detect(content):
                # 优先使用 AI 生成的按行替换文本
                line_num = msg_idx + 1
                replacement = replacements.get(line_num, mock_response)

                updated = copy.deepcopy(msg)
                payload = updated.get('payload', {})
                content_list = payload.get('content', [])

                if isinstance(content_list, list):
                    for item in content_list:
                        if isinstance(item, dict) and item.get('type') == 'output_text':
                            item['text'] = replacement
                else:
                    payload['content'] = [{'type': 'output_text', 'text': replacement}]

                lines[msg_idx] = updated
                changes.append(ChangeDetail(
                    line_num=line_num,
                    type=ChangeType.REPLACE,
                    original=content[:500] + ('...' if len(content) > 500 else ''),
                    replacement=replacement
                ))

        # 删除推理内容
        reasoning_items = get_reasoning_items(lines)
        if reasoning_items:
            for idx, item in reasoning_items:
                payload = item.get('payload', {})
                summary = payload.get('summary', [])
                # summary 是数组，提取所有 text 字段
                if isinstance(summary, list) and summary:
                    texts = [s.get('text', '') for s in summary if isinstance(s, dict)]
                    content = ' '.join(texts)[:100]
                elif payload.get('encrypted_content'):
                    content = '加密推理内容'
                else:
                    content = None

                if content:
                    changes.append(ChangeDetail(
                        line_num=idx + 1,
                        type=ChangeType.DELETE,
                        content=content + ('...' if len(content) >= 100 else '')
                    ))
            # 标记删除
            for idx, _ in reasoning_items:
                lines[idx] = None

        # 过滤并保存
        lines = [line for line in lines if line is not None]
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')

        return PatchResponse(
            success=True,
            message="会话清理完成",
            backup_path=backup_path,
            changes=changes
        )

    except Exception as e:
        return PatchResponse(
            success=False,
            message=f"清理失败: {str(e)}"
        )


def load_settings() -> Settings:
    """加载设置"""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Settings(**data)
        except Exception:
            pass
    return Settings()


def save_settings(settings: Settings) -> bool:
    """保存设置"""
    try:
        os.makedirs(os.path.dirname(DEFAULT_CONFIG_FILE), exist_ok=True)
        with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# API 路由

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(skip_check: bool = False, limit: int = 0):
    """获取会话列表

    Args:
        skip_check: 是否跳过拒绝检测（默认跳过，加速加载）
        limit: 返回的会话数量（默认0，返回全部）
    """
    sessions = list_sessions(skip_refusal_check=skip_check)
    limited_sessions = sessions[:limit] if limit > 0 else sessions
    return SessionListResponse(sessions=limited_sessions, total=len(sessions))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, check_refusal: bool = True):
    """获取单个会话详情

    Args:
        session_id: 会话 ID
        check_refusal: 是否检测拒绝内容
    """
    sessions = list_sessions(skip_refusal_check=not check_refusal)
    for session in sessions:
        if session.id == session_id:
            return session
    raise HTTPException(status_code=404, detail="会话不存在")


def compute_backup_diff(current_path: str, backup_path: str) -> list[DiffItem]:
    """对比当前文件和备份文件，找出助手消息的差异"""
    diff_items = []
    try:
        # 解析当前文件
        with open(current_path, 'r', encoding='utf-8') as f:
            current_lines = f.readlines()
        current_parsed = []
        for line in current_lines:
            line = line.strip()
            if line:
                try:
                    current_parsed.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # 解析备份文件
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_lines = f.readlines()
        backup_parsed = []
        for line in backup_lines:
            line = line.strip()
            if line:
                try:
                    backup_parsed.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # 提取助手消息序列（按出现顺序对齐）
        backup_assistant = get_assistant_messages(backup_parsed)
        current_assistant = get_assistant_messages(current_parsed)

        # 按序号对齐：第 N 条备份助手消息 vs 第 N 条当前助手消息
        for i in range(min(len(backup_assistant), len(current_assistant))):
            bak_idx, bak_msg = backup_assistant[i]
            cur_idx, cur_msg = current_assistant[i]
            backup_text = extract_text_content(bak_msg)
            current_text = extract_text_content(cur_msg)
            if backup_text != current_text:
                diff_items.append(DiffItem(
                    line_num=cur_idx + 1,
                    before=backup_text[:1000] + ('...' if len(backup_text) > 1000 else ''),
                    after=current_text[:1000] + ('...' if len(current_text) > 1000 else ''),
                ))

        # 检查备份中有但当前没有的推理内容
        backup_reasoning = get_reasoning_items(backup_parsed)
        current_reasoning = get_reasoning_items(current_parsed)
        removed_count = len(backup_reasoning) - len(current_reasoning)
        if removed_count > 0:
            diff_items.append(DiffItem(
                line_num=0,
                before=f'包含 {len(backup_reasoning)} 条推理内容',
                after=f'已删除 {removed_count} 条推理内容',
            ))

    except Exception:
        pass
    return diff_items


@router.post("/sessions/{session_id}/preview", response_model=PreviewResponse)
async def preview_session_api(session_id: str):
    """预览会话修改"""
    sessions = list_sessions()
    for session in sessions:
        if session.id == session_id:
            settings = load_settings()
            result = preview_session(
                session.path,
                settings.mock_response,
                settings.custom_keywords
            )

            # 如果有备份，计算清理前后对比
            if session.has_backup:
                session_dir = os.path.dirname(session.path)
                base_name = os.path.basename(session.path)
                # 找到最新的备份
                bak_files = []
                for f in os.listdir(session_dir):
                    if f.startswith(base_name + ".") and f.endswith(".bak"):
                        bak_files.append(os.path.join(session_dir, f))
                if bak_files:
                    bak_files.sort(reverse=True)  # 最新的在前
                    result.diff_items = compute_backup_diff(session.path, bak_files[0])

            return result
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/{session_id}/ai-rewrite", response_model=AIRewriteResponse)
async def ai_rewrite_session_api(session_id: str):
    """AI 智能改写拒绝内容"""
    settings = load_settings()

    if not settings.ai_enabled:
        return AIRewriteResponse(success=False, error="AI 分析未启用，请在设置中开启")
    if not settings.ai_endpoint:
        return AIRewriteResponse(success=False, error="AI 配置不完整：缺少 API Endpoint")
    if not settings.ai_model:
        return AIRewriteResponse(success=False, error="AI 配置不完整：缺少模型名称")

    sessions = list_sessions()
    for session in sessions:
        if session.id == session_id:
            try:
                from .ai_service import generate_ai_rewrite
                result = await generate_ai_rewrite(
                    session.path, settings, settings.custom_keywords
                )
                return result
            except Exception as e:
                return AIRewriteResponse(success=False, error=str(e))
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/{session_id}/patch", response_model=PatchResponse)
async def patch_session_api(session_id: str, body: PatchRequest = None):
    """执行会话清理"""
    sessions = list_sessions()
    for session in sessions:
        if session.id == session_id:
            settings = load_settings()
            mock_response = settings.mock_response

            # 构建按行号的替换映射
            replacements_map = {}
            if body and body.replacements:
                for item in body.replacements:
                    replacements_map[item.line_num] = item.replacement_text
            elif body and body.replacement_text:
                # 兼容旧的单一替换文本
                mock_response = body.replacement_text

            # 广播开始日志
            await manager.broadcast(WSMessage(
                type="log",
                data={"level": "info", "message": f"开始处理会话: {session_id}"}
            ))

            result = patch_session(
                session.path,
                mock_response,
                settings.custom_keywords,
                replacements=replacements_map
            )

            # 广播完成日志
            if result.success:
                await manager.broadcast(WSMessage(
                    type="log",
                    data={"level": "success", "message": result.message}
                ))
            else:
                await manager.broadcast(WSMessage(
                    type="log",
                    data={"level": "error", "message": result.message}
                ))

            return result
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/sessions/{session_id}/backups")
async def list_backups(session_id: str):
    """列出会话的所有备份"""
    sessions = list_sessions(skip_refusal_check=True)
    for session in sessions:
        if session.id == session_id:
            # 查找同目录下的 .bak 文件
            session_dir = os.path.dirname(session.path)
            base_name = os.path.basename(session.path)
            backups = []
            for f in os.listdir(session_dir):
                if f.startswith(base_name + ".") and f.endswith(".bak"):
                    bak_path = os.path.join(session_dir, f)
                    stat = os.stat(bak_path)
                    # 从文件名提取时间戳: xxx.jsonl.20260327_032155.bak
                    ts_part = f[len(base_name) + 1:-4]  # 去掉前缀和 .bak
                    try:
                        ts = datetime.strptime(ts_part, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        ts = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    backups.append(BackupInfo(
                        filename=f,
                        path=bak_path,
                        timestamp=ts,
                        size=stat.st_size
                    ))
            # 按时间降序
            backups.sort(key=lambda b: b.timestamp, reverse=True)
            return backups
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/{session_id}/restore", response_model=RestoreResponse)
async def restore_session(session_id: str, backup_filename: str):
    """从备份还原会话"""
    sessions = list_sessions(skip_refusal_check=True)
    for session in sessions:
        if session.id == session_id:
            session_dir = os.path.dirname(session.path)
            backup_path = os.path.join(session_dir, backup_filename)

            if not os.path.exists(backup_path):
                return RestoreResponse(success=False, message="备份文件不存在")

            # 安全检查：确保备份文件在同一目录
            if os.path.dirname(os.path.abspath(backup_path)) != os.path.abspath(session_dir):
                return RestoreResponse(success=False, message="非法的备份路径")

            try:
                shutil.copy2(backup_path, session.path)
                await manager.broadcast(WSMessage(
                    type="log",
                    data={"level": "success", "message": f"会话 {session_id} 已从备份还原"}
                ))
                return RestoreResponse(success=True, message="还原成功")
            except Exception as e:
                return RestoreResponse(success=False, message=f"还原失败: {str(e)}")
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/settings", response_model=Settings)
async def get_settings():
    """获取设置"""
    return load_settings()


@router.put("/settings")
async def update_settings(settings: Settings):
    """更新设置"""
    if save_settings(settings):
        return {"success": True, "message": "设置已保存"}
    raise HTTPException(status_code=500, detail="保存设置失败")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
