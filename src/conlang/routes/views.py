import os, json, shutil, markdown
from flask import Blueprint, render_template, request, redirect, url_for, session, send_from_directory, abort
from werkzeug.utils import secure_filename
import conlang.paths as paths
from conlang.utils import utils

views_bp = Blueprint('views', __name__)

def is_safe_yaml(filename):
    return filename.lower().endswith(('.yaml', '.yml'))

# --- 1. 專案管理 (Portal) ---
@views_bp.route('/', methods=['GET', 'POST'])
def portal():
    # 物理隔離核心：定位到該使用者的專屬目錄
    uid = paths.get_user_id()
    user_root = os.path.join(paths.PROJECTS_ROOT, uid)
    os.makedirs(user_root, exist_ok=True)
    
    if request.method == 'POST':
        project_name = secure_filename(request.form.get('project_name', '').strip())
        if project_name:
            # 建立物理資料夾
            paths.get_project_dir(project_name)
            session['current_project'] = project_name
            return redirect(url_for('views.portal'))

    display_projects = []
    project_files = {}

    if os.path.exists(user_root):
        all_dirs = [d for d in os.listdir(user_root) if os.path.isdir(os.path.join(user_root, d))]
        for p in all_dirs:
            display_projects.append(p)
            p_path = os.path.join(user_root, p)
            files = [f for f in os.listdir(p_path) if is_safe_yaml(f)]
            project_files[p] = files

    return render_template('portal.html', 
                           projects=display_projects, 
                           project_files=project_files, 
                           current=session.get('current_project'))

@views_bp.route('/select_project/<name>')
def select_project(name):
    # 檢查該專案是否真的存在於該使用者的目錄下
    uid = paths.get_user_id()
    safe_name = secure_filename(name)
    target_path = os.path.join(paths.PROJECTS_ROOT, uid, safe_name)
    
    if os.path.isdir(target_path):
        session['current_project'] = safe_name
    return redirect(url_for('views.portal'))

@views_bp.route('/import', methods=['POST'])
def import_project():
    uploaded_files = request.files.getlist('project_files')
    if not uploaded_files or uploaded_files[0].filename == '':
        return "Error: No files selected", 400

    first_path = uploaded_files[0].filename
    path_parts = [p for p in first_path.split('/') if p]
    project_name = secure_filename(path_parts[0] if len(path_parts) > 1 else "Imported_Project")

    # 會自動建立在 projects/{uid}/{project_name}
    target_dir = paths.get_project_dir(project_name)
    
    saved_count = 0
    for file in uploaded_files:
        fname = secure_filename(os.path.basename(file.filename))
        if fname in ['ipa.yaml', 'master.yaml']:
            fname = f"imported_{fname}"

        if is_safe_yaml(fname):
            file.save(os.path.join(target_dir, fname))
            saved_count += 1
            
    if saved_count == 0:
        return "Error: No valid YAML files found.", 400

    session['current_project'] = project_name
    return redirect(url_for('views.portal'))

@views_bp.route('/export_file/<filename>')
def export_file(filename):
    curr_proj = session.get('current_project')
    if not curr_proj:
        abort(403)

    safe_name = secure_filename(filename)
    if not is_safe_yaml(safe_name):
        abort(403)

    # get_project_dir 內部已經帶有 uid 隔離
    project_dir = paths.get_project_dir(curr_proj)
    return send_from_directory(project_dir, safe_name, as_attachment=True)

@views_bp.route('/delete_project/<name>', methods=['POST'])
def delete_project(name):
    uid = paths.get_user_id()
    target_path = os.path.join(paths.PROJECTS_ROOT, uid, secure_filename(name))
    
    if os.path.exists(target_path) and os.path.isdir(target_path):
        shutil.rmtree(target_path)
        if session.get('current_project') == name:
            session.pop('current_project', None)
            
    return redirect(url_for('views.portal'))


# --- 2. 核心編輯器 ---
@views_bp.route('/ipa', methods=['GET', 'POST'])
def ipa_tool():
    config, _ = utils.get_config()
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
                try: val = int(value or 10)
                except ValueError: val = 10
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
    master = utils.load_yaml(paths.DEFAULT_MASTER)
    
    if request.method == 'POST':
        if request.form.get('action_type') == 'reset':
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

@views_bp.route('/morphology/inflectional', methods=['GET', 'POST'])
def morph_inflectional():
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
        return redirect(url_for('views.morph_inflectional'))
    return render_template('morph_inflectional.html', config=config)

@views_bp.route('/morphology/agglutinative', methods=['GET', 'POST'])
def morph_agglutinative():
    config, _ = utils.get_config()
    if request.method == 'POST':
        # 確保結構存在
        if 'morphology' not in config: config['morphology'] = {}
        
        # 我們直接覆寫 agglutinative 節點，這樣沒在表單裡的（被刪掉的）就不會留下殘留
        new_agglut = {}
        
        # 獲取所有可能的 section
        sections = ['sec_noun_syntax', 'sec_verb_syntax', 'sec_adj_syntax']
        
        for key in request.form:
            # 格式: agglut|sec|feat|opt|base
            if key.startswith('agglut|') and key.endswith('|base'):
                parts = key.split('|')
                sec, feat, opt = parts[1], parts[2], parts[3]
                
                base_val = request.form.get(key, '').strip()
                
                # 即使 base 是空的，只要用戶有在頁面上看到這個項，我們就建立結構
                # 這樣「刪除內容」才會真正生效（覆蓋掉舊的詞綴）
                conds = request.form.getlist(f"agglut|{sec}|{feat}|{opt}|cond[]")
                customs = request.form.getlist(f"agglut|{sec}|{feat}|{opt}|custom[]")
                alts = request.form.getlist(f"agglut|{sec}|{feat}|{opt}|alt[]")
                
                rules = []
                for c, cust, a in zip(conds, customs, alts):
                    if a.strip(): # 只有變體詞綴不為空時才存規則
                        rules.append({
                            'cond': c,
                            'custom': cust.strip() if c == 'custom' else '',
                            'alt': a.strip()
                        })
                
                new_agglut.setdefault(sec, {}).setdefault(feat, {})[opt] = {
                    'base': base_val,
                    'rules': rules
                }
        
        config['morphology']['agglutinative'] = new_agglut
        utils.save_config(config)
        return redirect(url_for('views.morph_agglutinative'))
        
    return render_template('morph_agglutinative.html', config=config)

# --- 3. 字典與詞庫 ---
@views_bp.route('/lexicon')
def lexicon():
    config, _ = utils.get_config()
    return render_template('lexicon.html', config=config)

@views_bp.route('/dictionary')
def view_dictionary():
    lex_data, _ = utils.get_lexicon()
    return render_template('dictionary.html', dictionary=lex_data.get('words', []))

# --- 4. 使用說明 (Guide) ---
@views_bp.route('/guide')
def show_guide():
    # 獲取目前 session 語系，預設為 zh (繁體中文)
    lang = session.get('lang', 'zh')
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, 'docs')
    
    # 組合檔案名稱，例如 guide_zh.md
    filename = f"guide_{lang}.md"
    md_path = os.path.join(docs_dir, filename)
    
    # 安全檢查：如果檔案不存在，預設回傳中文版；若中文版也不存在，則報錯
    if not os.path.exists(md_path):
        md_path = os.path.join(docs_dir, 'guide_zh.md')
        if not os.path.exists(md_path):
            return "Guide file not found.", 404
    
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    
    html_content = markdown.markdown(md_text, extensions=[
        'tables', 
        'fenced_code', 
        'toc',
        'nl2br'
    ])
    
    return render_template('guide.html', content=html_content)