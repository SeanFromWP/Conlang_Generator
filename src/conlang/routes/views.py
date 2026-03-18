import os
import json
import io
from flask import Blueprint, render_template, request, redirect, url_for, session, send_from_directory, abort
from werkzeug.utils import secure_filename
import conlang.paths as paths
from conlang.utils import utils

views_bp = Blueprint('views', __name__)

# --- 核心防禦工具 ---
def is_safe_yaml(filename):
    return filename.lower().endswith(('.yaml', '.yml'))

# --- 1. 專案管理 (Portal) ---
@views_bp.route('/', methods=['GET', 'POST'])
def portal():
    if request.method == 'POST':
        project_name = secure_filename(request.form.get('project_name', '').strip())
        if project_name:
            # 建立專案目錄並初始化
            paths.get_project_dir(project_name)
            session['current_project'] = project_name
            return redirect(url_for('views.portal'))

    all_projects = []
    project_files = {}

    if os.path.exists(paths.PROJECTS_ROOT):
        all_projects = [d for d in os.listdir(paths.PROJECTS_ROOT) 
                        if os.path.isdir(os.path.join(paths.PROJECTS_ROOT, d))]
        
        for p in all_projects:
            p_path = os.path.join(paths.PROJECTS_ROOT, p)
            # 僅列出該專案資料夾下的 YAML 檔名
            files = [f for f in os.listdir(p_path) if is_safe_yaml(f)]
            project_files[p] = files

    return render_template('portal.html', 
                           projects=all_projects, 
                           project_files=project_files, 
                           current=session.get('current_project'))

@views_bp.route('/export_file/<filename>')
def export_file(filename):
    curr_proj = session.get('current_project')
    if not curr_proj:
        abort(403, description="Please select a project first.")

    safe_name = secure_filename(filename)
    if not is_safe_yaml(safe_name):
        abort(403, description="Access denied.")

    # 確保只從目前選定的專案資料夾下載
    project_dir = paths.get_project_dir(curr_proj)
    return send_from_directory(project_dir, safe_name, as_attachment=True)

@views_bp.route('/import', methods=['POST'])
def import_project():
    uploaded_files = request.files.getlist('project_files')
    if not uploaded_files or uploaded_files[0].filename == '':
        return "Error: No files selected", 400

    first_path = uploaded_files[0].filename
    path_parts = [p for p in first_path.split('/') if p]
    project_name = secure_filename(path_parts[0] if len(path_parts) > 1 else "Imported_Project")

    target_dir = paths.get_project_dir(project_name)
    
    saved_count = 0
    for file in uploaded_files:
        fname = secure_filename(os.path.basename(file.filename))
        # 保護關鍵檔名，避免被外部匯入覆蓋
        if fname in ['ipa.yaml', 'master.yaml']:
            fname = f"imported_{fname}"

        if is_safe_yaml(fname):
            file.save(os.path.join(target_dir, fname))
            saved_count += 1
            
    if saved_count == 0:
        return "Error: No valid YAML files found.", 400

    session['current_project'] = project_name
    return redirect(url_for('views.portal'))

@views_bp.route('/select_project/<name>')
def select_project(name):
    session['current_project'] = secure_filename(name)
    return redirect(url_for('views.portal'))

# --- 2. 核心編輯器 (IPA, Syntax, Morphology) ---
@views_bp.route('/ipa', methods=['GET', 'POST'])
def ipa_tool():
    # 使用重構後的 utils，獲取專案私有的 config
    config, config_file = utils.get_config()
    # IPA 參考資料維持讀取系統唯讀檔
    ipa_data = utils.load_yaml(paths.DEFAULT_IPA)
    
    if request.method == 'POST':
        if request.form.get('action_type') == 'reset_ipa':
            config.pop('phonology', None)
        else:
            phon = config.setdefault('phonology', {})
            phon['inventory_consonants'] = sorted(list(set(request.form.getlist('ipa_consonant'))))
            phon['inventory_vowels'] = sorted(list(set(request.form.getlist('ipa_vowel'))))
            phon['inventory'] = phon['inventory_consonants'] + phon['inventory_vowels']
        
        utils.save_config(config)
        return redirect(url_for('views.ipa_tool')) 
    return render_template('ipa.html', ipa=ipa_data, config=config)

@views_bp.route('/ipa_management', methods=['GET', 'POST'])
def ipa_management():
    config, _ = utils.get_config()
    if request.method == 'POST':
        phon = config.setdefault('phonology', {})
        weights = {'consonants': {}, 'vowels': {}}
        c_list = phon.get('inventory_consonants', [])
        v_list = phon.get('inventory_vowels', [])
        
        for key, value in request.form.items():
            if key.startswith('weight_'):
                p = key.replace('weight_', '')
                try:
                    val = int(value or 10)
                except ValueError:
                    val = 10
                if p in c_list: weights['consonants'][p] = val
                elif p in v_list: weights['vowels'][p] = val
        
        phon.update({
            'weights': weights,
            'custom_order': request.form.get('custom_order_data', ""),
            'categories': json.loads(request.form.get('custom_categories_json', '{}'))
        })
        utils.save_config(config)
        return redirect(url_for('views.ipa_management'))
    return render_template('ipa_management.html', config=config, ipa=utils.load_yaml(paths.DEFAULT_IPA))

@views_bp.route('/syntax', methods=['GET', 'POST'])
def syntax():
    config, _ = utils.get_config()
    # 讀取系統唯讀範本作為結構參考，不讀取 PACKAGE_DIR 下的 master.yaml
    master = utils.load_yaml(paths.DEFAULT_MASTER)
    
    if request.method == 'POST':
        if request.form.get('action_type') == 'reset':
            # 重置時，僅保留音韻設定，儲存到專案私有的 config
            utils.save_config({'phonology': config.get('phonology', {})})
            return redirect(url_for('views.syntax'))
            
        new_config = config.copy()
        for key in list(new_config.keys()):
            if key.startswith('sec_'): del new_config[key]
            
        for raw_key, values in request.form.lists():
            if '|' not in raw_key or raw_key.startswith('order|') or raw_key == 'action_type': continue
            parts = raw_key.split('|')
            vals = [v.strip() for v in values if v.strip()]
            if not vals: continue
            
            if parts[0] == 'bools':
                new_config.setdefault(parts[1], {}).setdefault('bools', {})[parts[2]] = True
            elif parts[0] == 'settings':
                new_config.setdefault(parts[1], {}).setdefault('settings', {})[parts[2]] = vals
            elif len(parts) == 2:
                new_config.setdefault(parts[0], {})[parts[1]] = vals
                
        # 排序邏輯
        for raw_key in request.form.keys():
            if not raw_key.startswith('order|'): continue
            sorted_list = request.form.get(raw_key).split()
            p = raw_key.replace('order|', '').split('|')
            if p[0] == 'settings' and len(p) == 3:
                sec, feat = p[1], p[2]
                if sec in new_config and 'settings' in new_config[sec] and feat in new_config[sec]['settings']:
                    curr = new_config[sec]['settings'][feat]
                    new_config[sec]['settings'][feat] = [x for x in sorted_list if x in curr]
            elif len(p) == 2:
                sec, cat = p[0], p[1]
                if sec in new_config and cat in new_config[sec]:
                    curr = new_config[sec][cat]
                    if isinstance(curr, list):
                        new_config[sec][cat] = [x for x in sorted_list if x in curr]
                        
        utils.save_config(new_config)
        return redirect(url_for('views.syntax'))
    return render_template('syntax.html', master=master, config=config)

@views_bp.route('/morphology', methods=['GET', 'POST'])
def morphology_mgr():
    config, _ = utils.get_config()
    if request.method == 'POST':
        new_morphology = {}
        for key, values in request.form.lists():
            if key.startswith('dims|'):
                section = key.split('|')[1].replace('[]', '')
                dims = [v.strip() for v in values if v.strip()]
                if dims: new_morphology.setdefault(section, {})['selected_matrix_dims'] = dims
        for key in request.form:
            if key.startswith('matrix|') and '|content[]' in key:
                parts = key.split('|')
                if len(parts) < 4: continue
                section, combo_key = parts[1], parts[2]
                contents = request.form.getlist(key)
                pairs = [{'marker': c.strip()} for c in contents if c.strip()]
                if pairs: new_morphology.setdefault(section, {}).setdefault('markers', {})[combo_key] = pairs
        
        config['morphology'] = new_morphology
        utils.save_config(config)
        return redirect(url_for('views.morphology_mgr'))
    return render_template('morphology.html', config=config)

# --- 3. 字典與詞庫 ---
@views_bp.route('/lexicon')
def lexicon():
    config, _ = utils.get_config()
    return render_template('lexicon.html', config=config)

@views_bp.route('/dictionary')
def view_dictionary():
    # get_lexicon 內部也已經改為 Session 感知
    lex_data, _ = utils.get_lexicon()
    return render_template('dictionary.html', dictionary=lex_data.get('words', []))