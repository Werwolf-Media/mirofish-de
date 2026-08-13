"""
Projektmappen ("Projekte" im UI): ein fester Realitäts-Seed (Dokumente +
optionaler Seed-Text), auf den beliebig viele Runs mit unterschiedlichen
Prompts zurückgreifen.

Speicherung als JSON + Dateien unter uploads/project_groups/<group_id>/
(gleiches Muster wie ProjectManager/BillingManager).
"""

import os
import json
import uuid
import shutil
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..config import Config

_lock = threading.Lock()

GROUPS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'project_groups')


class ProjectGroupManager:
    """Verwaltet Projektmappen (Seed-Container mit Run-Historie)."""

    @classmethod
    def _dir(cls, group_id: str) -> str:
        safe = ''.join(c for c in group_id if c.isalnum() or c == '_')
        return os.path.join(GROUPS_DIR, safe)

    @classmethod
    def _json_path(cls, group_id: str) -> str:
        return os.path.join(cls._dir(group_id), 'group.json')

    @classmethod
    def files_dir(cls, group_id: str) -> str:
        return os.path.join(cls._dir(group_id), 'files')

    # ------------------------------------------------------------ CRUD

    @classmethod
    def create(cls, name: str, seed_text: str = '', competitors=None) -> Dict[str, Any]:
        group_id = f"group_{uuid.uuid4().hex[:12]}"
        group = {
            'group_id': group_id,
            'name': (name or '').strip() or 'Unbenanntes Projekt',
            'seed_text': (seed_text or '').strip(),
            'competitors': competitors or [],
            'files': [],           # [{original_filename, saved_filename, size}]
            'runs': [],            # [{project_id, requirement, created_at}]
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        cls._save(group)
        return group

    @classmethod
    def get(cls, group_id: str) -> Optional[Dict[str, Any]]:
        try:
            with open(cls._json_path(group_id), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    @classmethod
    def list(cls) -> List[Dict[str, Any]]:
        os.makedirs(GROUPS_DIR, exist_ok=True)
        groups = []
        for name in os.listdir(GROUPS_DIR):
            g = cls.get(name)
            if g:
                groups.append(g)
        groups.sort(key=lambda g: g.get('updated_at', ''), reverse=True)
        return groups

    @classmethod
    def delete(cls, group_id: str) -> bool:
        d = cls._dir(group_id)
        if not os.path.isdir(d):
            return False
        shutil.rmtree(d, ignore_errors=True)
        return True

    @classmethod
    def _save(cls, group: Dict[str, Any]):
        group['updated_at'] = datetime.now().isoformat()
        os.makedirs(cls._dir(group['group_id']), exist_ok=True)
        path = cls._json_path(group['group_id'])
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(group, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    # ------------------------------------------------------------ Seed-Dateien

    @classmethod
    def save_file(cls, group_id: str, file_storage, original_filename: str) -> Optional[Dict[str, Any]]:
        """Upload-Datei in die Projektmappe legen und registrieren."""
        with _lock:
            group = cls.get(group_id)
            if not group:
                return None
            files_dir = cls.files_dir(group_id)
            os.makedirs(files_dir, exist_ok=True)

            ext = os.path.splitext(original_filename)[1].lower()
            safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
            file_path = os.path.join(files_dir, safe_filename)
            file_storage.save(file_path)

            entry = {
                'original_filename': original_filename,
                'saved_filename': safe_filename,
                'size': os.path.getsize(file_path),
            }
            group['files'].append(entry)
            cls._save(group)
            return entry

    @classmethod
    def disk_files(cls, group_id: str) -> List[tuple]:
        """[(original_name, pfad), ...] für run_ontology_pipeline(disk_files=...)."""
        group = cls.get(group_id)
        if not group:
            return []
        files_dir = cls.files_dir(group_id)
        return [
            (f['original_filename'], os.path.join(files_dir, f['saved_filename']))
            for f in group.get('files', [])
        ]

    # ------------------------------------------------------------ Runs

    @classmethod
    def add_run(cls, group_id: str, project_id: str, requirement: str) -> Optional[Dict[str, Any]]:
        with _lock:
            group = cls.get(group_id)
            if not group:
                return None
            group['runs'].append({
                'project_id': project_id,
                'requirement': requirement,
                'created_at': datetime.now().isoformat(),
            })
            cls._save(group)
            return group
