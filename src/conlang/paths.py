import os

# 基礎目錄定義
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__)) # conlang/
SRC_ROOT = os.path.abspath(os.path.join(PACKAGE_DIR, ".."))
LANG_ROOT = os.path.abspath(os.path.join(SRC_ROOT, ".."))
PROJECTS_ROOT = os.path.join(LANG_ROOT, 'projects')

# --- 系統模板 (唯讀範本) ---
# 這是你放在 src/conlang/ 裡的原始檔案
DEFAULT_IPA = os.path.join(PACKAGE_DIR, 'ipa.yaml')
DEFAULT_MASTER = os.path.join(PACKAGE_DIR, 'master.yaml')

def get_project_dir(project_name):
    """確保專案資料夾存在並回傳路徑"""
    # 這裡防止 project_name 為空導致路徑指回 PROJECTS_ROOT 根部
    name = project_name.strip() if project_name else '_default_'
    path = os.path.join(PROJECTS_ROOT, name)
    os.makedirs(path, exist_ok=True)
    return path

def get_project_file(project_name, filename):
    return os.path.join(get_project_dir(project_name), filename)