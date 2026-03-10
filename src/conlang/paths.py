import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECTS_ROOT = os.path.join(BASE_DIR, 'projects')
MASTER_FILE = os.path.join(BASE_DIR, 'src', 'master.yaml')
IPA_FILE = os.path.join(BASE_DIR, 'src', 'ipa.yaml')

def get_project_dir(project_name):
    path = os.path.join(PROJECTS_ROOT, project_name or '_default_')
    os.makedirs(path, exist_ok=True)
    return path

def get_project_file(project_name, filename):
    return os.path.join(get_project_dir(project_name), filename)