# -*- coding: utf-8 -*-
"""
CLI 入口 - 命令行会话清理工具
"""

import os
import sys
import argparse
import shutil
from datetime import datetime

import json as _json

from .core import (
    RefusalDetector,
    SessionParser,
    extract_text_content,
    get_assistant_messages,
    get_reasoning_items,
    clean_session_jsonl,
    MOCK_RESPONSE,
)
from .core.patcher import save_session_jsonl

DEFAULT_CONFIG_FILE = os.path.expanduser('~/.codex-patcher/config.json')


def load_config():
    """加载 Web 端保存的配置"""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            pass
    return {}


def main():
    parser = argparse.ArgumentParser(
        description='Codex Session Patcher - 清理 Codex CLI 会话中的拒绝回复'
    )
    parser.add_argument(
        '--session-dir',
        default=os.path.expanduser('~/.codex/sessions/'),
        help='会话目录 (默认: ~/.codex/sessions/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅预览，不实际修改文件'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='不创建备份'
    )
    parser.add_argument(
        '--show-content',
        action='store_true',
        help='显示修改的详细内容'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='只处理最新的会话文件'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='扫描并处理所有会话文件'
    )
    parser.add_argument(
        '--web',
        action='store_true',
        help='启动 Web UI'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Web UI 监听地址 (默认: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Web UI 端口 (默认: 8080)'
    )

    args = parser.parse_args()

    # 启动 Web UI
    if args.web:
        try:
            from web.backend.main import run_server
            run_server(host=args.host, port=args.port)
        except ImportError:
            print('错误: Web 依赖未安装，请运行: pip install -e ".[web]"')
            sys.exit(1)
        return

    # CLI 模式 - 加载配置
    config = load_config()
    mock_response = config.get('mock_response', MOCK_RESPONSE)
    custom_keywords = config.get('custom_keywords', None)

    session_parser = SessionParser(args.session_dir)
    sessions = session_parser.list_sessions()

    if not sessions:
        print(f'未找到会话文件: {args.session_dir}')
        sys.exit(0)

    detector = RefusalDetector(custom_keywords)

    if args.latest:
        sessions = sessions[:1]
    elif not args.all:
        sessions = sessions[:1]

    total_modified = 0
    for session in sessions:
        print(f'\n处理会话: {session.session_id} ({session.filename})')

        try:
            lines = session_parser.parse_session_jsonl(session.path)
        except Exception as e:
            print(f'  读取失败: {e}')
            continue

        cleaned_lines, modified, changes = clean_session_jsonl(
            lines, detector, show_content=args.show_content,
            mock_response=mock_response
        )

        if not modified:
            print('  无需修改')
            continue

        print(f'  检测到 {len(changes)} 处修改:')
        for change in changes:
            if change.change_type == 'replace':
                print(f'    第 {change.line_num} 行: 替换拒绝回复')
                if args.show_content and change.original_content:
                    print(f'      原始: {change.original_content[:100]}...')
            elif change.change_type == 'delete':
                print(f'    第 {change.line_num} 行: 删除推理内容')

        if args.dry_run:
            print('  (预览模式，未修改文件)')
            continue

        # 创建备份
        if not args.no_backup:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'{session.path}.{timestamp}.bak'
            shutil.copy2(session.path, backup_path)
            print(f'  备份: {backup_path}')

        # 保存修改
        save_session_jsonl(cleaned_lines, session.path)
        print(f'  已保存修改')
        total_modified += 1

    print(f'\n完成: 共处理 {len(sessions)} 个会话，修改 {total_modified} 个')


if __name__ == '__main__':
    main()
