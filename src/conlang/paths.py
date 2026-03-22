import os
import uuid
from flask import session
from werkzeug.utils import secure_filename

# 基礎目錄定義
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__)) # conlang/
SRC_ROOT = os.path.abspath(os.path.join(PACKAGE_DIR, ".."))
LANG_ROOT = os.path.abspath(os.path.join(SRC_ROOT, ".."))
PROJECTS_ROOT = os.path.join(LANG_ROOT, 'projects')

# --- 系統模板 (唯讀範本) ---
DEFAULT_IPA = os.path.join(PACKAGE_DIR, 'ipa.yaml')
DEFAULT_MASTER = os.path.join(PACKAGE_DIR, 'master.yaml')

def get_user_id():
    """從 session 取得唯一 ID，確保物理隔離"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())[:8] # 8位碼足以區分本地用戶
        session.modified = True
    return session['user_id']

def get_project_dir(project_name):
    """確保專案存在於使用者的獨立路徑：projects/{user_id}/{project_name}"""
    uid = get_user_id()
    name = secure_filename(project_name.strip()) if project_name else '_default_'

    user_path = os.path.join(PROJECTS_ROOT, uid)
    path = os.path.join(user_path, name)
    
    os.makedirs(path, exist_ok=True)
    return path

def get_project_file(project_name, filename):
    return os.path.join(get_project_dir(project_name), filename)