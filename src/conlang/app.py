import os, json
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import conlang.paths as paths
from conlang.lexicon import generator
from conlang.utils import utils

app = Flask(__name__)
app.secret_key = "conlanger_secret_key"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\..'))
PROJECTS_ROOT = os.path.join(BASE_DIR, 'projects')
os.makedirs(PROJECTS_ROOT, exist_ok=True)

# ==========================================
# 核心工具函式
# ==========================================

def get_current_project_file(filename):
    """獲取當前選定專案路徑下的檔案"""
    p_name = session.get('current_project', '_default_')
    project_dir = os.path.join(PROJECTS_ROOT, p_name)
    os.makedirs(project_dir, exist_ok=True)
    return os.path.join(project_dir, filename)

def get_config():
    """標準化獲取 config 資料與檔案路徑"""
    path = get_current_project_file('config.yaml')
    return utils.load_yaml(path) or {}, path

@app.context_processor
def inject_globals():
    return {
        'app_name': 'Gugugaga',
        'current_project': session.get('current_project', 'None')
    }

# ==========================================
# 1. 專案管理 (Project Management)
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def portal():
    if request.method == 'POST':
        project_name = request.form.get('project_name', '').strip()
        if project_name:
            # 自動建立專案目錄
            project_path = os.path.join(PROJECTS_ROOT, project_name)
            if not os.path.exists(project_path):
                os.makedirs(project_path)
            
            session['current_project'] = project_name
            # 直接重導向回首頁即可看到新專案
            return redirect(url_for('portal'))

    # 確保專案根目錄存在
    if not os.path.exists(PROJECTS_ROOT):
        os.makedirs(PROJECTS_ROOT)
        
    all_projects = [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
    
    # 渲染 portal.html，傳入專案列表與當前 session 中的專案
    return render_template('portal.html', 
                           projects=all_projects, 
                           current=session.get('current_project'))

@app.route('/select_project/<name>')
def select_project(name):
    session['current_project'] = name
    return redirect(url_for('portal'))

# ==========================================
# 2. 核心編輯器 (Linguistic Components)
# ==========================================

@app.route('/ipa', methods=['GET', 'POST'])
def ipa_tool():
    config, config_file = get_config()
    ipa_data = utils.load_yaml(paths.IPA_FILE)

    if request.method == 'POST':
        if request.form.get('action_type') == 'reset_ipa':
            config.pop('phonology', None)
        else:
            phon = config.setdefault('phonology', {})
            phon['inventory_consonants'] = sorted(list(set(request.form.getlist('ipa_consonant'))))
            phon['inventory_vowels'] = sorted(list(set(request.form.getlist('ipa_vowel'))))
            phon['inventory'] = phon['inventory_consonants'] + phon['inventory_vowels']
        
        utils.save_yaml(config_file, config)
        return redirect(url_for('ipa_tool')) 

    return render_template('ipa.html', ipa=ipa_data, config=config)

@app.route('/ipa_management', methods=['GET', 'POST'])
def ipa_management():
    config, config_file = get_config()
    if request.method == 'POST':
        phon = config.setdefault('phonology', {})
        weights = {'consonants': {}, 'vowels': {}}
        c_list = phon.get('inventory_consonants', [])
        v_list = phon.get('inventory_vowels', [])

        for key, value in request.form.items():
            if key.startswith('weight_'):
                p = key.replace('weight_', '')
                val = int(value or 10)
                if p in c_list: weights['consonants'][p] = val
                elif p in v_list: weights['vowels'][p] = val

        phon.update({
            'weights': weights,
            'custom_order': request.form.get('custom_order_data', ""),
            'categories': json.loads(request.form.get('custom_categories_json', '{}'))
        })
        
        utils.save_yaml(config_file, config)
        return redirect(url_for('ipa_management'))
    
    return render_template('ipa_management.html', config=config, ipa=utils.load_yaml(paths.IPA_FILE))

@app.route('/syntax', methods=['GET', 'POST'])
def syntax():
    config, config_file = get_config()
    master = utils.load_yaml(paths.MASTER_FILE)
    
    if request.method == 'POST':
        if request.form.get('action_type') == 'reset':
            utils.save_yaml(config_file, {'phonology': config.get('phonology', {})})
            return redirect(url_for('syntax'))

        new_config = config.copy()
        
        # 清空語法區塊防止舊數據殘留 (確保 bool 被取消勾選後會變為 False/不存在)
        for key in list(new_config.keys()):
            if key.startswith('sec_'):
                del new_config[key]

        # 第一階段：解析表單重建基礎數據
        for raw_key, values in request.form.lists():
            if '|' not in raw_key or raw_key.startswith('order|') or raw_key == 'action_type':
                continue
            
            parts = raw_key.split('|')
            vals = [v.strip() for v in values if v.strip()]
            if not vals: continue

            if parts[0] == 'bools':
                section, feature = parts[1], parts[2]
                new_config.setdefault(section, {}).setdefault('bools', {})[feature] = True
            elif parts[0] == 'settings':
                section, feature = parts[1], parts[2]
                new_config.setdefault(section, {}).setdefault('settings', {})[feature] = vals
            elif len(parts) == 2:
                section, category = parts[0], parts[1]
                new_config.setdefault(section, {})[category] = vals

        # 第二階段：強制應用自定義排序順序
        for raw_key in request.form.keys():
            if not raw_key.startswith('order|'): continue
            
            sorted_list = request.form.get(raw_key).split()
            path = raw_key.replace('order|', '').split('|')
            
            if path[0] == 'settings' and len(path) == 3:
                sec, feat = path[1], path[2]
                if sec in new_config and 'settings' in new_config[sec] and feat in new_config[sec]['settings']:
                    curr = new_config[sec]['settings'][feat]
                    new_config[sec]['settings'][feat] = [x for x in sorted_list if x in curr]
            elif len(path) == 2:
                sec, cat = path[0], path[1]
                if sec in new_config and cat in new_config[sec]:
                    curr = new_config[sec][cat]
                    if isinstance(curr, list):
                        new_config[sec][cat] = [x for x in sorted_list if x in curr]

        utils.save_yaml(config_file, new_config)
        return redirect(url_for('syntax'))
    
    return render_template('syntax.html', master=master, config=config)

@app.route('/morphology', methods=['GET', 'POST'])
def morphology_mgr():
    config, config_file = get_config()

    if request.method == 'POST':
        new_morphology = {}

        # 處理維度 (Dimensions)
        for key, values in request.form.lists():
            if key.startswith('dims|'):
                section = key.split('|')[1].replace('[]', '')
                dims = [v.strip() for v in values if v.strip()]
                if dims:
                    new_morphology.setdefault(section, {})['selected_matrix_dims'] = dims

        # 處理標記 (Markers)
        for key in request.form:
            if key.startswith('matrix|') and '|content[]' in key:
                parts = key.split('|')
                if len(parts) < 4: continue
                
                section, combo_key = parts[1], parts[2]
                contents = request.form.getlist(key)
                pairs = [{'marker': c.strip()} for c in contents if c.strip()]
                
                if pairs:
                    sec_data = new_morphology.setdefault(section, {})
                    sec_data.setdefault('markers', {})[combo_key] = pairs

        config['morphology'] = new_morphology
        utils.save_yaml(config_file, config)
        return redirect(url_for('morphology_mgr'))

    return render_template('morphology.html', config=config)

# ==========================================
# 3. 字典與詞庫 (Lexicon & Dictionary)
# ==========================================

@app.route('/lexicon')
def lexicon():
    config, _ = get_config()
    return render_template('lexicon.html', config=config)

@app.route('/dictionary')
def view_dictionary():
    lex_file = get_current_project_file('lexicon.yaml')
    word_list = (utils.load_yaml(lex_file) or {}).get('words', [])
    return render_template('dictionary.html', dictionary=word_list)

def _update_lexicon(callback):
    """內部字典更新封裝"""
    try:
        lex_file = get_current_project_file('lexicon.yaml')
        lex_data = utils.load_yaml(lex_file) or {'words': []}
        callback(lex_data['words'], request.json)
        utils.save_yaml(lex_file, lex_data)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/dictionary/api/add', methods=['POST'])
def api_add_entry():
    return _update_lexicon(lambda words, data: words.insert(0, {
        'word': data['word'], 
        'pos': data['pos'], 
        'translation': data['translation'],
        'ipa': data['ipa'], 
        'syllables': data['ipa'].split('.') if data['ipa'] else []
    }))

@app.route('/dictionary/api/update', methods=['POST'])
def api_update_entry():
    def update_logic(words, data):
        index = data.get('index')
        if index is not None and 0 <= index < len(words):
            # 更新該索引的內容
            words[index] = {
                'word': data['word'],
                'pos': data['pos'],
                'translation': data['translation'],
                'ipa': data['ipa'],
                'syllables': data['ipa'].split('.') if data['ipa'] else []
            }
        else:
            raise ValueError("Invalid index")
            
    return _update_lexicon(update_logic)

@app.route('/dictionary/api/delete', methods=['POST'])
def api_delete_entry():
    return _update_lexicon(lambda words, data: words.pop(data.get('index')) if 0 <= data.get('index') < len(words) else None)

# ==========================================
# 4. 生成器 API (Generator API)
# ==========================================

@app.route('/api/generate_words', methods=['POST'])
def api_generate_words():
    try:
        data = request.get_json()
        swadesh = data.get('swadesh_list', [])
        config, _ = get_config()
        
        generated = generator.func(
            count=len(swadesh) if swadesh else int(data.get('count', 20)),
            config=config.get('phonology', {}),
            pattern=data.get('pattern', 'CVC'),
            min_syl=int(data.get('min_syl', 1)),
            max_syl=int(data.get('max_syl', 3)),
            translations=swadesh
        )
        return jsonify({"status": "success", "words": generated})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)