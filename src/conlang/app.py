import yaml, os, shutil, json
import conlang.paths as paths
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from conlang.lexicon import generator
from conlang.utils import utils

app = Flask(__name__)
app.secret_key = "conlanger_secret_key"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECTS_ROOT = os.path.join(BASE_DIR, 'projects')
os.makedirs(PROJECTS_ROOT, exist_ok=True)

# --- 核心工具函式 ---

def get_current_project_file(filename):
    """獲取當前專案內的檔案路徑，僅在函式內部呼叫以避免 Context 錯誤"""
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
        'app_name': 'Conlanger',
        'current_project': session.get('current_project', 'None')
    }

# --- 0. Project Management ---
@app.route('/projects', methods=['GET', 'POST'])
def manage_projects():
    if request.method == 'POST':
        project_name = request.form.get('project_name', '').strip()
        if project_name:
            session['current_project'] = project_name
            return redirect(url_for('manage_projects'))

    all_projects = [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
    return render_template('projects.html', projects=all_projects, current=session.get('current_project'))

@app.route('/select_project/<name>')
def select_project(name):
    session['current_project'] = name
    return redirect(url_for('portal'))

@app.route('/')
def portal():
    return render_template('portal.html')

@app.route('/syntax', methods=['GET', 'POST'])
def syntax():
    config, config_file = get_config()
    master = utils.load_yaml(paths.MASTER_FILE)
    
    if request.method == 'POST':
        if request.form.get('action_type') == 'reset':
            # 只保留 phonology，其餘抹平
            utils.save_yaml(config_file, {'phonology': config.get('phonology', {})})
            return redirect(url_for('syntax'))

        # 1. 繼承原始設定 (確保 phonology 完好無損)
        new_config = config.copy()
        
        # 2. 先清空所有語法區塊 (sec_ 開頭)，確保格式不被舊數據污染
        # 這樣沒勾選的 bool 就不會殘留在 YAML 裡，達成 False 的效果
        for key in list(new_config.keys()):
            if key.startswith('sec_'):
                del new_config[key]

        # --- 第一階段：重建基礎數據 (含 Bools 字典) ---
        for raw_key, values in request.form.lists():
            # 跳過排序欄位與控制欄位
            if '|' not in raw_key or raw_key.startswith('order|') or raw_key == 'action_type':
                continue
            
            parts = raw_key.split('|')
            vals = [v.strip() for v in values if v.strip()]
            if not vals: continue

            # A. 處理 bools -> 產生 key: true (對應你提供的標準格式)
            if parts[0] == 'bools':
                section, feature = parts[1], parts[2]
                new_config.setdefault(section, {}).setdefault('bools', {})[feature] = True
            
            # B. 處理 settings -> 產生 key: [list]
            elif parts[0] == 'settings':
                section, feature = parts[1], parts[2]
                new_config.setdefault(section, {}).setdefault('settings', {})[feature] = vals
            
            # C. 處理直接分類 (如 opt_word_order) -> 產生 key: [list]
            elif len(parts) == 2:
                section, category = parts[0], parts[1]
                new_config.setdefault(section, {})[category] = vals

        # --- 第二階段：強制順序覆蓋 ---
        for raw_key in request.form.keys():
            if not raw_key.startswith('order|'): continue
            
            sorted_list = request.form.get(raw_key).split()
            path = raw_key.replace('order|', '').split('|')
            
            if path[0] == 'settings' and len(path) == 3:
                sec, feat = path[1], path[2]
                # 只有當該 feature 真的有被勾選時才排序，避免產生空數據
                if sec in new_config and 'settings' in new_config[sec] and feat in new_config[sec]['settings']:
                    curr = new_config[sec]['settings'][feat]
                    # 交集過濾，確保排序後的清單只包含目前存在的標籤
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
        # 1. 初始化全新的頂層 morphology 結構
        new_morphology = {}

        # 2. 處理勾選的維度 (Dimensions)
        # 使用 .lists() 確保能拿完整清單
        for key, values in request.form.lists():
            if key.startswith('dims|'):
                section = key.split('|')[1].replace('[]', '')
                dims = [v.strip() for v in values if v.strip()]
                
                if dims:
                    # 確保 section 存在，並寫入維度
                    new_morphology.setdefault(section, {})['selected_matrix_dims'] = dims

        # 3. 處理矩陣內的標記 (Markers)
        for key in request.form:
            if key.startswith('matrix|') and '|content[]' in key:
                parts = key.split('|')
                if len(parts) < 4: continue
                
                section = parts[1]
                combo_key = parts[2]
                
                # 獲取該組合下的所有輸入內容
                contents = request.form.getlist(key)
                
                # 僅保留非空 marker
                pairs = [{'marker': c.strip()} for c in contents if c.strip()]
                
                if pairs:
                    # 確保 section 字典存在
                    sec_data = new_morphology.setdefault(section, {})
                    # 確保 markers 字典存在並存入
                    sec_data.setdefault('markers', {})[combo_key] = pairs

        # 4. 將結果寫入頂層，確保 phonology 和 sec_ 區塊不受影響
        config['morphology'] = new_morphology
        utils.save_yaml(config_file, config)
        
        return redirect(url_for('morphology_mgr'))

    return render_template('morphology.html', config=config)

# --- 2. Phonology (IPA) ---
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
        c_list, v_list = phon.get('inventory_consonants', []), phon.get('inventory_vowels', [])

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

# --- 3. Lexicon & API ---
@app.route('/lexicon')
def lexicon():
    config, _ = get_config()
    return render_template('lexicon.html', config=config)

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

# --- 4. Dictionary Management ---
@app.route('/dictionary')
def view_dictionary():
    lex_file = get_current_project_file('lexicon.yaml')
    word_list = (utils.load_yaml(lex_file) or {}).get('words', [])
    return render_template('dictionary.html', dictionary=word_list)

def _update_lexicon(callback):
    """內部字典操作封裝"""
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
        'word': data['word'], 'pos': data['pos'], 'translation': data['translation'],
        'ipa': data['ipa'], 'syllables': data['ipa'].split('.') if data['ipa'] else []
    }))

@app.route('/dictionary/api/delete', methods=['POST'])
def api_delete_entry():
    return _update_lexicon(lambda words, data: words.pop(data.get('index')) if 0 <= data.get('index') < len(words) else None)

if __name__ == '__main__':
    app.run(debug=True, port=5000)