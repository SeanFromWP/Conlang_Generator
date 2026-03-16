import os, sys
from flask import Flask, session

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.dirname(current_dir)

if src_path not in sys.path:
    sys.path.insert(0, src_path)

import conlang.paths as paths

def create_app():
    app = Flask(__name__)
    app.secret_key = "conlanger_secret_key"

    os.makedirs(paths.PROJECTS_ROOT, exist_ok=True)

    from routes.api import api_bp
    from routes.views import views_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'Parabola',
            'current_project': session.get('current_project', 'None')
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
