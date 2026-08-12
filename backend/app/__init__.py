"""
MiroFish Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, jsonify
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger
from .utils.auth import check_token


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中...")
        logger.info("=" * 50)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
    # Zugriffsschutz: alle /api/* Routen erfordern ein gültiges Token (außer Login)
    @app.before_request
    def require_auth():
        if request.method == 'OPTIONS':
            return None  # CORS-Preflight durchlassen
        path = request.path or ''
        # Ohne App-Token erlaubt:
        # - /health, Login + Admin-Login
        # - /api/shared/ (Empfänger geteilter Links)
        # - /api/billing/ (eigenes Admin-Token wird dort INTERN geprüft)
        # - /api/v1/ (Maschinen-API: eigener API-Key wird dort INTERN geprüft)
        if path == '/health' \
                or path.rstrip('/') == '/api/auth/login' \
                or path.rstrip('/') == '/api/auth/admin-login' \
                or path.startswith('/api/shared/') \
                or path.startswith('/api/billing/') \
                or path.startswith('/api/v1/'):
            return None
        if path.startswith('/api/'):
            token = request.headers.get('X-App-Token', '')
            if not token:
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
            if not check_token(token):
                return jsonify({"success": False, "error": "unauthorized"}), 401
        return None

    # 请求日志中间件
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, auth_bp, wizard_bp, share_bp, shared_bp, billing_bp, external_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(wizard_bp, url_prefix='/api/wizard')
    app.register_blueprint(share_bp, url_prefix='/api/share')      # Verwaltung (Login nötig)
    app.register_blueprint(shared_bp, url_prefix='/api/shared')    # öffentlich (token-scoped)
    app.register_blueprint(billing_bp, url_prefix='/api/billing')  # Abrechnung (Login nötig)
    app.register_blueprint(external_bp, url_prefix='/api/v1')      # Maschinen-API (eigener API-Key)
    
    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    # Frontend ausliefern (Produktions-Container): Vite-Build aus frontend/dist.
    # Lokal (npm run dev) existiert das Verzeichnis nicht -> Route bleibt aus,
    # Vite-Dev-Server uebernimmt wie gehabt.
    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../frontend/dist')
    )
    if os.path.isdir(frontend_dist):
        from flask import send_from_directory

        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_frontend(path):
            # API-Pfade nie mit index.html beantworten
            if path.startswith('api/'):
                return jsonify({"success": False, "error": "not_found"}), 404
            candidate = os.path.join(frontend_dist, path)
            if path and os.path.isfile(candidate):
                return send_from_directory(frontend_dist, path)
            # Vue-Router-Pfade (/billing, /share/<token>, ...) -> SPA-Einstieg
            return send_from_directory(frontend_dist, 'index.html')

        if should_log_startup:
            logger.info(f"Frontend-Auslieferung aktiv: {frontend_dist}")
    
    if should_log_startup:
        # Modell-Wächter: beim Start laut warnen, wenn ein teures oder
        # inkompatibles Modell konfiguriert ist (Lektion aus dem 80-€-Run)
        try:
            from .models.app_settings import AppSettings
            from .utils.model_guard import check_model, log_text
            active_model = AppSettings.effective_llm_model()
            logger.info(f"Aktives LLM-Modell: {active_model}"
                        + (" (Admin-Override)" if AppSettings.llm_model() else " (.env)"))
            for warning in check_model(active_model):
                logger.warning("!" * 60)
                logger.warning(f"MODELL-WARNUNG: {log_text(warning)}")
                logger.warning("!" * 60)
            cap = AppSettings.max_cost_eur()
            if cap > 0:
                logger.info(f"Kosten-Deckel pro Run: {cap:.2f} EUR")
            else:
                logger.warning("Kosten-Deckel DEAKTIVIERT (MAX_COST_EUR=0) — "
                               "Runs können unbegrenzt Kosten verursachen")
        except Exception as e:
            logger.warning(f"Modell-Wächter-Startcheck fehlgeschlagen: {e}")

        # Standard-Passwörter aktiv? Deutlich machen.
        if Config.APP_PASSWORD == 'werwolf123#':
            logger.warning("Standard-APP_PASSWORD aktiv — bitte in .env ändern")
        if Config.ADMIN_PASSWORD == 'werwolf-admin#':
            logger.warning("Standard-ADMIN_PASSWORD aktiv — bitte in .env ändern")

        # Maschinen-API: Status loggen + verwaiste Runs bereinigen
        try:
            from .services.external_pipeline import ExternalRunManager
            ExternalRunManager.recover_stale()
            if Config.EXTERNAL_API_KEY:
                logger.info("Maschinen-API /api/v1 aktiv (EXTERNAL_API_KEY gesetzt)")
            else:
                logger.info("Maschinen-API /api/v1 deaktiviert (kein EXTERNAL_API_KEY)")
        except Exception as e:
            logger.warning(f"Maschinen-API-Startcheck fehlgeschlagen: {e}")

        logger.info("MiroFish Backend 启动完成")

    return app

