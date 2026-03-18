import os
import yaml
import shutil
from flask import session
import conlang.paths as paths

def load_yaml(path):
    if not os.path.exists(path): 
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError:
            return {}

def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

def get_current_project_file(filename, seed_template=None):
    """
    獲取檔案路徑。
    如果檔案不存在且提供了 seed_template，則從模板初始化一份。
    """
    p_name = session.get('current_project')
    if not p_name:
        # 如果沒選專案，直接讀取系統預設模板 (防止汙染)
        return seed_template if seed_template else ""
        
    project_dir = paths.get_project_dir(p_name)
    target_path = os.path.join(project_dir, filename)
    
    # --- 自動初始化邏輯 ---
    # 如果該專案內還沒有這個檔案，就從範本拷貝一份
    if not os.path.exists(target_path) and seed_template and os.path.exists(seed_template):
        shutil.copy(seed_template, target_path)
        
    return target_path

def get_config():
    """獲取 config (master.yaml 的副本)"""
    # 專案內的 master 資料我們統一定名為 config.yaml 以示區別
    path = get_current_project_file('config.yaml', seed_template=paths.DEFAULT_MASTER)
    return load_yaml(path), path

def save_config(data):
    path = get_current_project_file('config.yaml', seed_template=paths.DEFAULT_MASTER)
    save_yaml(path, data)

def get_lexicon():
    """獲取詞典資料"""
    path = get_current_project_file('dict.yaml')
    return load_yaml(path), path

def load_ipa_data():
    """IPA 資料通常是唯讀的系統資料"""
    return load_yaml(paths.DEFAULT_IPA)