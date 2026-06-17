from flask import Flask, request, jsonify, render_template, session, make_response
import os
import sys
import json
import logging
import requests
import hashlib
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR))
LOCAL_SETTINGS_PATH = Path(os.environ.get('MATCHPREDICT_SETTINGS_PATH', BASE_DIR / 'settings.json'))


def get_runtime_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return BASE_DIR


WORLD_CUP_RUNTIME_DIR = get_runtime_root()

load_dotenv(BASE_DIR / '.env')

def load_local_settings():
    """读取绿色版本地设置文件。"""
    if not LOCAL_SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(LOCAL_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}

def get_ai_settings(settings=None, include_environment=True):
    """读取统一 AI 配置，并兼容旧 Gemini 配置。"""
    settings = settings if settings is not None else load_local_settings()
    settings = settings if isinstance(settings, dict) else {}
    ai = settings.get('ai', {}) or {}
    gemini = settings.get('gemini', {}) or {}

    provider = str(ai.get('provider') or '').strip()
    base_url = str(ai.get('base_url') or '').strip()
    api_key = str(ai.get('api_key') or '').strip()
    model = str(ai.get('model') or '').strip()

    if not api_key and gemini.get('api_key'):
        provider = 'gemini'
        api_key = str(gemini.get('api_key') or '').strip()
        model = model or str(gemini.get('model') or '').strip()
        base_url = base_url or str(gemini.get('base_url') or '').strip()

    if include_environment:
        provider = provider or os.environ.get('AI_PROVIDER') or ('gemini' if os.environ.get('GEMINI_API_KEY') else '')
        base_url = base_url or os.environ.get('AI_BASE_URL', '')
        api_key = api_key or os.environ.get('AI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
        model = model or os.environ.get('AI_MODEL') or os.environ.get('GEMINI_MODEL', '')

    if not provider:
        provider = 'openai_compatible'
    if provider not in ('openai_compatible', 'gemini'):
        provider = 'openai_compatible'

    if not model:
        model = 'gemini-2.5-flash-lite-preview-06-17' if provider == 'gemini' else ''
    if not base_url:
        base_url = 'https://api.openai.com/v1' if provider == 'openai_compatible' else 'https://generativelanguage.googleapis.com/v1beta'

    return {
        'provider': provider,
        'base_url': base_url.rstrip('/'),
        'api_key': api_key,
        'model': model,
    }


def apply_local_settings(settings=None):
    """把本地设置应用到当前进程环境变量。"""
    settings = settings if settings is not None else load_local_settings()
    database = settings.get('database', {}) if isinstance(settings, dict) else {}
    ai = get_ai_settings(settings, include_environment=False)

    mapping = {
        'DB_HOST': database.get('host'),
        'DB_PORT': database.get('port'),
        'DB_NAME': database.get('name'),
        'DB_USER': database.get('user'),
        'DB_PASS': database.get('password'),
        'AI_PROVIDER': ai.get('provider'),
        'AI_BASE_URL': ai.get('base_url'),
        'AI_API_KEY': ai.get('api_key'),
        'AI_MODEL': ai.get('model'),
    }
    if ai.get('provider') == 'gemini':
        mapping['GEMINI_API_KEY'] = ai.get('api_key')
        mapping['GEMINI_MODEL'] = ai.get('model')

    for key, value in mapping.items():
        if value not in (None, ''):
            os.environ[key] = str(value)

def is_database_configured(settings=None, include_environment=True):
    """检查数据库是否配置完整。

    include_environment=False 用于前台设置状态，只判断 settings.json，避免旧 .env
    让绿色版首次启动误以为已经完成前台设置。
    """
    settings = settings if settings is not None else load_local_settings()
    database = settings.get('database', {}) if isinstance(settings, dict) else {}

    def value(name, env_name):
        configured_value = database.get(name)
        if configured_value:
            return configured_value
        return os.environ.get(env_name) if include_environment else ''

    required = [
        value('host', 'DB_HOST'),
        value('port', 'DB_PORT'),
        value('name', 'DB_NAME'),
        value('user', 'DB_USER'),
        value('password', 'DB_PASS'),
    ]
    return all(bool(item) for item in required)

def is_ai_configured(settings=None, include_environment=True):
    """检查是否配置了 AI Key 和模型。"""
    ai = get_ai_settings(settings, include_environment=include_environment)
    return bool(ai.get('api_key') and ai.get('model'))


def is_gemini_configured(settings=None, include_environment=True):
    """兼容旧测试/旧调用：检查是否有可用 AI 配置。"""
    return is_ai_configured(settings, include_environment=include_environment)

apply_local_settings()

# 尝试导入数据库模块
try:
    from scripts.database import prediction_db
except ImportError as e:
    logging.getLogger(__name__).warning("数据库模块导入失败: %s", e)
    prediction_db = None

# 延迟导入，避免在Vercel环境中的问题
try:
    from scripts.lottery_api import ChinaSportsLotterySpider
except ImportError as e:
    print(f"导入彩票API失败: {e}")
    ChinaSportsLotterySpider = None

try:
    from scripts.ai_predictor import AIFootballPredictor
except ImportError as e:
    print(f"导入AI预测器失败: {e}")
    AIFootballPredictor = None

# 世界杯专题模块
try:
    from scripts.worldcup.predictor import WorldCupPredictor
    from scripts.worldcup.explainer import WorldCupExplainer
    from scripts.worldcup.fixture_status import describe_fixture_status
    from scripts.worldcup.meta import build_worldcup_meta
    from scripts.worldcup.standings import build_group_standings
    from scripts.worldcup.group_simulator import simulate_group_stage
    from scripts.worldcup.bracket_rules import BracketRuleError, load_bracket_rules, validate_bracket_rules
    from scripts.worldcup.tournament_simulator import simulate_tournament
    from scripts.worldcup.evaluation import load_evaluation_report
    from scripts.worldcup.online_update import (
        DEFAULT_WORLD_CUP_UPDATE_SOURCES,
        apply_worldcup_update,
        build_worldcup_update_status,
        check_worldcup_update,
    )
except ImportError as e:
    logging.getLogger(__name__).warning("世界杯模块导入失败: %s", e)
    WorldCupPredictor = None
    WorldCupExplainer = None
    describe_fixture_status = None
    build_worldcup_meta = None
    build_group_standings = None
    simulate_group_stage = None
    BracketRuleError = None
    load_bracket_rules = None
    validate_bracket_rules = None
    simulate_tournament = None
    load_evaluation_report = None
    DEFAULT_WORLD_CUP_UPDATE_SOURCES = []
    apply_worldcup_update = None
    build_worldcup_update_status = None
    check_worldcup_update = None

WORLD_CUP_DATA_DIR = RESOURCE_DIR / 'data' / 'worldcup'

def get_worldcup_predictor():
    if not WorldCupPredictor:
        return None
    return WorldCupPredictor(WORLD_CUP_DATA_DIR, runtime_dir=WORLD_CUP_RUNTIME_DIR)

def public_fixture_payload(fixture, predictor):
    home = predictor._team_from_id(fixture.get('home_team_id')) or {}
    away = predictor._team_from_id(fixture.get('away_team_id')) or {}
    status_info = describe_fixture_status(fixture) if describe_fixture_status else {}
    return {
        'match_id': fixture.get('match_id'),
        'home_team': home.get('display_name_zh') or home.get('display_name') or fixture.get('home_team_id'),
        'away_team': away.get('display_name_zh') or away.get('display_name') or fixture.get('away_team_id'),
        'home_team_id': fixture.get('home_team_id'),
        'away_team_id': fixture.get('away_team_id'),
        'kickoff_at': fixture.get('kickoff_at'),
        'stage': fixture.get('stage'),
        'group': fixture.get('group'),
        'venue': fixture.get('venue'),
        'status': fixture.get('status'),
        'final_score': fixture.get('final_score'),
        'data_cutoff_at': predictor.data.data_cutoff_at,
        **status_info,
    }

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / 'templates'),
    static_folder=str(RESOURCE_DIR / 'static')
)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production') # 在生产环境中务必设置一个强随机 SECRET_KEY
LOCAL_FREE_MODE = os.environ.get('LOCAL_FREE_MODE', 'true').lower() in ('1', 'true', 'yes', 'on')
# Session/Cookie 配置，确保登录态可用
app.config.update(
    SESSION_COOKIE_NAME='mp_session',
    # 'None' 是为了支持跨站点请求（例如前端与后端域名不同），但要求 Secure=True (HTTPS)
    # 如果前端和后端在同一个主域的不同子域（例如 app.example.com 和 api.example.com），
    # 并且 SESSION_COOKIE_DOMAIN 设置为 '.example.com'，则 Cookie 会在子域间共享。
    SESSION_COOKIE_SAMESITE=os.environ.get('SESSION_COOKIE_SAMESITE', 'None'),
    SESSION_COOKIE_SECURE=True, # 必须为 True，因为 SameSite=None
    # 可选：通过环境变量设置 Cookie 域名（例如 .match-predict.vercel.app，注意开头的点）
    # 如果不设置，则默认为当前请求的域名。在跨子域共享时才需要设置。
    SESSION_COOKIE_DOMAIN=os.environ.get('SESSION_COOKIE_DOMAIN'),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# 配置日志
logging.basicConfig(level=logging.INFO)

# 全局变量
lottery_spider = None
ai_predictor = None

# 联赛配置（简化版）
LEAGUES = {
    "PL": "英超",
    "PD": "西甲",
    "SA": "意甲",
    "BL1": "德甲",
    "FL1": "法甲"
}

# 简化的球队数据
TEAMS_DATA = {
    "PL": ["Arsenal FC", "Manchester City FC", "Liverpool FC", "Manchester United FC", "Chelsea FC", "Tottenham Hotspur FC", "Newcastle United FC", "Brighton & Hove Albion FC"],
    "PD": ["Real Madrid CF", "FC Barcelona", "Atlético de Madrid", "Sevilla FC", "Valencia CF", "Real Betis Balompié", "Real Sociedad de Fútbol", "Athletic Club"],
    "SA": ["FC Internazionale Milano", "AC Milan", "Juventus FC", "SSC Napoli", "AS Roma", "SS Lazio", "Atalanta BC", "ACF Fiorentina"],
    "BL1": ["FC Bayern München", "Borussia Dortmund", "RB Leipzig", "Bayer 04 Leverkusen", "VfB Stuttgart", "Eintracht Frankfurt", "VfL Wolfsburg", "SC Freiburg"],
    "FL1": ["Paris Saint-Germain FC", "Olympique de Marseille", "AS Monaco FC", "Olympique Lyonnais", "OGC Nice", "Stade Rennais FC", "RC Lens", "LOSC Lille"]
}

def initialize_services():
    """初始化服务"""
    global lottery_spider, ai_predictor

    try:
        # 初始化中国体育彩票API
        if ChinaSportsLotterySpider:
            lottery_spider = ChinaSportsLotterySpider()
            app.logger.info("彩票API初始化成功")
        else:
            app.logger.warning("彩票API类未加载")
    except Exception as e:
        app.logger.error(f"彩票API初始化失败: {e}")
        lottery_spider = None

    try:
        # 初始化AI预测器
        if AIFootballPredictor:
            ai = get_ai_settings(include_environment=True)

            if not ai.get('api_key') or not ai.get('model'):
                app.logger.warning("AI Key 或模型未设置，AI预测器将不可用")
                ai_predictor = None
            else:
                ai_predictor = AIFootballPredictor(
                    api_key=ai['api_key'],
                    model_name=ai['model'],
                    provider=ai['provider'],
                    base_url=ai['base_url']
                )
                app.logger.info("AI预测器初始化成功")
        else:
            app.logger.warning("AI预测器类未加载")
    except Exception as e:
        app.logger.error(f"AI预测器初始化失败: {e}")
        ai_predictor = None

# 初始化
try:
    initialize_services()
except Exception as e:
    app.logger.error(f"服务初始化失败: {e}")

# 用户认证相关辅助函数
def hash_password(password):
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()

# 移除了 simple_create_user_db 函数，因为 prediction_db.create_user 已经足够健壮。

def get_current_user():
    """获取当前登录用户"""
    if 'user_id' in session:
        return prediction_db.get_user_by_username(session['username']) if prediction_db else None
    return None

def get_local_guest_user():
    """本机免费模式下使用的匿名访客用户。"""
    return {
        'id': None,
        'username': 'local_guest',
        'email': '',
        'user_type': 'local_free',
        'daily_predictions_used': 0,
        'total_predictions': 0,
        'membership_expires': None
    }

def require_login():
    """检查是否需要登录"""
    return get_current_user() is None

@app.after_request
def add_cors_headers(response):
    """为需要的接口添加基础CORS支持，避免OPTIONS 405。"""
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        app.logger.debug(f"为请求 {request.path} 添加了CORS头部，Origin: {origin}")
    if request.method == 'OPTIONS':
        response.status_code = 204
        app.logger.debug(f"处理OPTIONS请求: {request.path}")
    return response

def normalize_local_settings_payload(data):
    """规范化前台设置 payload。"""
    data = data or {}
    database = data.get('database', {}) or {}
    submitted_ai = data.get('ai', {}) or {}
    legacy_gemini = data.get('gemini', {}) or {}

    provider = str(submitted_ai.get('provider', '')).strip() or ('gemini' if legacy_gemini.get('api_key') else 'openai_compatible')
    if provider not in ('openai_compatible', 'gemini'):
        provider = 'openai_compatible'

    default_base_url = 'https://api.openai.com/v1' if provider == 'openai_compatible' else 'https://generativelanguage.googleapis.com/v1beta'
    default_model = 'gemini-2.5-flash-lite-preview-06-17' if provider == 'gemini' else ''
    api_key = str(submitted_ai.get('api_key') or legacy_gemini.get('api_key') or '').strip()
    model = str(submitted_ai.get('model') or legacy_gemini.get('model') or default_model).strip()
    base_url = str(submitted_ai.get('base_url') or legacy_gemini.get('base_url') or default_base_url).strip()

    return {
        'database': {
            'host': str(database.get('host', '')).strip(),
            'port': str(database.get('port', '')).strip(),
            'name': str(database.get('name', '')).strip(),
            'user': str(database.get('user', '')).strip(),
            'password': str(database.get('password', '')).strip(),
        },
        'ai': {
            'provider': provider,
            'base_url': base_url.rstrip('/'),
            'api_key': api_key,
            'model': model,
        }
    }

def get_db_params_from_settings(settings):
    """从设置字典生成 psycopg2 连接参数。"""
    database = settings.get('database', {}) if settings else {}
    return {
        'host': database.get('host') or os.environ.get('DB_HOST', ''),
        'port': int(database.get('port') or os.environ.get('DB_PORT', 5432)),
        'database': database.get('name') or os.environ.get('DB_NAME', 'postgres'),
        'user': database.get('user') or os.environ.get('DB_USER', 'postgres'),
        'password': database.get('password') or os.environ.get('DB_PASS', ''),
        'sslmode': 'prefer'
    }

@app.route('/api/local-settings/status', methods=['GET'])
def local_settings_status():
    """返回本机设置状态，不泄露密码或完整密钥。"""
    settings = load_local_settings()
    ai = get_ai_settings(settings, include_environment=False)
    ai_configured = is_ai_configured(settings, include_environment=False)
    return jsonify({
        'success': True,
        'database_configured': is_database_configured(settings, include_environment=False),
        'ai_configured': ai_configured,
        'ai_provider': ai['provider'],
        'ai_base_url': ai['base_url'],
        'ai_model': ai['model'],
        'gemini_configured': ai_configured,
        'gemini_model': ai['model'],
        'settings_file_exists': LOCAL_SETTINGS_PATH.exists()
    })

@app.route('/api/local-settings/save', methods=['POST'])
def save_local_settings():
    """保存本机设置到 settings.json，并应用到当前进程。"""
    try:
        settings = normalize_local_settings_payload(request.get_json(silent=True))
        LOCAL_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_SETTINGS_PATH.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        apply_local_settings(settings)
        if prediction_db:
            prediction_db.reload_connection_params()
        initialize_services()
        ai = get_ai_settings(settings, include_environment=False)
        ai_configured = is_ai_configured(settings, include_environment=False)
        return jsonify({
            'success': True,
            'message': '设置已保存',
            'database_configured': is_database_configured(settings, include_environment=False),
            'ai_configured': ai_configured,
            'ai_provider': ai['provider'],
            'ai_base_url': ai['base_url'],
            'ai_model': ai['model'],
            'gemini_configured': ai_configured,
            'gemini_model': ai['model']
        })
    except Exception as e:
        app.logger.error(f"保存本机设置失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'保存设置失败: {e}'}), 500

@app.route('/api/local-settings/test-db', methods=['POST'])
def test_local_settings_db():
    """测试前台提交或已保存的数据库配置。"""
    try:
        submitted = request.get_json(silent=True)
        settings = normalize_local_settings_payload(submitted) if submitted else load_local_settings()
        params = get_db_params_from_settings(settings)
        conn = psycopg2.connect(**params)
        conn.close()
        return jsonify({'success': True, 'message': '数据库连接成功'})
    except Exception as e:
        app.logger.warning(f"数据库连接测试失败: {e}")
        return jsonify({
            'success': False,
            'message': f'数据库连接失败：{e}'
        }), 200

@app.route('/api/local-settings/test-ai', methods=['POST'])
def test_local_settings_ai():
    """测试前台提交或已保存的 AI 配置。"""
    try:
        submitted = request.get_json(silent=True)
        settings = normalize_local_settings_payload(submitted) if submitted else load_local_settings()
        ai = get_ai_settings(settings, include_environment=False)
        if not ai.get('api_key') or not ai.get('model'):
            return jsonify({'success': False, 'message': '请先填写 AI Key 和模型名称'}), 200
        if not AIFootballPredictor:
            return jsonify({'success': False, 'message': 'AI 模块未加载'}), 200

        predictor = AIFootballPredictor(
            api_key=ai['api_key'],
            model_name=ai['model'],
            provider=ai['provider'],
            base_url=ai['base_url']
        )
        success, message = predictor.test_connection()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        app.logger.warning(f"AI 连接测试失败: {e}")
        return jsonify({'success': False, 'message': f'AI 连接失败：{e}'}), 200

@app.route('/api/session/debug')
def session_debug():
    """调试用：查看当前会话是否存在。上线可移除。"""
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })

@app.route('/')
def index():
    try:
        settings = load_local_settings()
        ai = get_ai_settings(settings, include_environment=True)
        current_user = get_current_user()

        return render_template('index.html',
                             ai_model=ai['model'],
                             ai_provider=ai['provider'],
                             ai_base_url=ai['base_url'],
                             gemini_model=ai['model'],
                             current_user=current_user,
                             local_free_mode=LOCAL_FREE_MODE)
    except Exception as e:
        app.logger.error(f"渲染主页失败: {e}")
        return f"页面加载错误: {str(e)}", 500


@app.route('/api/worldcup/fixtures', methods=['GET'])
def worldcup_fixtures():
    """返回本地世界杯赛程；不依赖数据库或 AI。"""
    predictor = get_worldcup_predictor()
    if not predictor:
        return jsonify({'success': False, 'message': '世界杯模块暂不可用'}), 500
    group_filter = (request.args.get('group') or '').strip().upper()
    status_filter = (request.args.get('status') or '').strip().lower()
    fixtures = []
    for fixture in predictor.data.fixtures:
        if group_filter and str(fixture.get('group', '')).upper() != group_filter:
            continue
        if status_filter and str(fixture.get('status', '')).lower() != status_filter:
            continue
        fixtures.append(public_fixture_payload(fixture, predictor))
    return jsonify({
        'success': True,
        'fixtures': fixtures,
        'count': len(fixtures),
        'data_cutoff_at': predictor.data.data_cutoff_at,
        'base_data_cutoff_at': predictor.data.base_data_cutoff_at,
        'effective_data_cutoff_at': predictor.data.data_cutoff_at,
        'local_patch_applied': predictor.data.local_patch_applied,
        'local_patch_matches_count': predictor.data.local_patch_matches_count,
        'update_source_mode': predictor.data.update_source_mode,
        'model_version': predictor.data.model_version,
        'message': '世界杯赛程加载成功'
    })


@app.route('/api/worldcup/meta', methods=['GET'])
def worldcup_meta():
    """返回世界杯本地数据概况；不依赖数据库或 AI。"""
    predictor = get_worldcup_predictor()
    if not predictor or not build_worldcup_meta:
        return jsonify({'success': False, 'message': '世界杯模块暂不可用'}), 500
    return jsonify(build_worldcup_meta(predictor.data))


@app.route('/api/worldcup/groups', methods=['GET'])
def worldcup_groups():
    """返回小组当前积分榜；可选附带小组赛模拟。"""
    predictor = get_worldcup_predictor()
    if not predictor or not build_group_standings:
        return jsonify({'success': False, 'message': '世界杯小组模块暂不可用'}), 500
    standings = build_group_standings(predictor.data)
    standings['simulation'] = None
    simulate = str(request.args.get('simulate') or '').lower() in ('1', 'true', 'yes', 'on')
    if simulate:
        if not simulate_group_stage:
            return jsonify({'success': False, 'message': '世界杯小组模拟模块暂不可用'}), 500
        trials = request.args.get('trials', 2000)
        seed_value = request.args.get('seed')
        try:
            seed = int(seed_value) if seed_value not in (None, '') else None
        except ValueError:
            return jsonify({'success': False, 'message': 'seed 必须是数字'}), 400
        standings['simulation'] = simulate_group_stage(predictor.data, trials=trials, seed=seed)
    return jsonify(standings)


@app.route('/api/worldcup/bracket-rules', methods=['GET'])
def worldcup_bracket_rules():
    """返回 2026 世界杯淘汰赛规则基线；不计算冠军概率。"""
    if not load_bracket_rules or not validate_bracket_rules:
        return jsonify({'success': False, 'message': '世界杯淘汰赛规则模块暂不可用'}), 500
    try:
        rules = load_bracket_rules(WORLD_CUP_DATA_DIR)
        summary = validate_bracket_rules(rules)
    except Exception as exc:
        if BracketRuleError and isinstance(exc, BracketRuleError):
            return jsonify({'success': False, 'message': str(exc)}), 400
        logging.getLogger(__name__).exception("世界杯淘汰赛规则读取失败")
        return jsonify({'success': False, 'message': '世界杯淘汰赛规则读取失败'}), 500
    return jsonify(summary)


@app.route('/api/worldcup/tournament', methods=['GET'])
def worldcup_tournament():
    """返回世界杯淘汰赛路径模拟；不依赖数据库或 AI。"""
    predictor = get_worldcup_predictor()
    if not predictor or not simulate_tournament:
        return jsonify({'success': False, 'message': '世界杯冠军路径模拟模块暂不可用'}), 500

    trials = request.args.get('trials', 1000)
    seed_value = request.args.get('seed', 2026)
    try:
        seed = int(seed_value) if seed_value not in (None, '') else None
    except ValueError:
        return jsonify({'success': False, 'message': 'seed 必须是数字'}), 400

    try:
        result = simulate_tournament(predictor.data, WORLD_CUP_DATA_DIR, trials=trials, seed=seed)
    except Exception as exc:
        if BracketRuleError and isinstance(exc, BracketRuleError):
            return jsonify({'success': False, 'message': str(exc)}), 400
        logging.getLogger(__name__).exception("世界杯冠军路径模拟失败")
        return jsonify({'success': False, 'message': '世界杯冠军路径模拟失败'}), 500
    return jsonify(result)


@app.route('/api/worldcup/predict', methods=['POST'])
def worldcup_predict():
    """返回世界杯单场基础预测；AI 不参与概率计算。"""
    predictor = get_worldcup_predictor()
    if not predictor:
        return jsonify({'success': False, 'message': '世界杯模块暂不可用'}), 500
    data = request.get_json(silent=True) or {}
    odds = data.get('odds')
    if data.get('match_id'):
        result = predictor.predict_fixture(str(data.get('match_id')), odds=odds)
    else:
        result = predictor.predict_match(str(data.get('home_team') or ''), str(data.get('away_team') or ''), odds=odds)
    status = 200 if result.get('success') else 400
    return jsonify(result), status




@app.route('/startup-check', strict_slashes=False)
def startup_check():
    """绿色版启动自检页。"""
    return render_template(
        'startup_check.html',
        local_free_mode=os.environ.get('LOCAL_FREE_MODE', 'true').lower() in ('1', 'true', 'yes', 'on'),
        launcher_log_path='logs/launcher.log',
        default_port=os.environ.get('PORT', '8000'),
    )


@app.route('/api/worldcup/evaluation/report', methods=['GET'])
def worldcup_evaluation_report():
    """Return local worldcup evaluation report without database, AI, or network."""
    if not load_evaluation_report:
        return jsonify({'success': False, 'message': 'WorldCup evaluation module is unavailable'}), 500
    report = load_evaluation_report(WORLD_CUP_DATA_DIR)
    report.setdefault('success', True)
    return jsonify(report)

@app.route('/api/worldcup/explain', methods=['POST'])
def worldcup_explain():
    """用 AI 或本地兜底解释预测 JSON；不改写概率。"""
    data = request.get_json(silent=True) or {}
    prediction = data.get('prediction') or data
    settings = load_local_settings()
    ai = get_ai_settings(settings, include_environment=True)
    predictor_client = None
    if AIFootballPredictor and ai.get('api_key') and ai.get('model'):
        predictor_client = AIFootballPredictor(
            api_key=ai['api_key'],
            model_name=ai['model'],
            provider=ai['provider'],
            base_url=ai['base_url']
        )
    explainer = WorldCupExplainer(predictor_client) if WorldCupExplainer else None
    if not explainer:
        return jsonify({'success': False, 'message': '世界杯解释模块暂不可用'}), 500
    return jsonify(explainer.explain(prediction))


@app.route('/api/teams')
def get_teams():
    """获取球队数据"""
    try:
        # 返回简化的球队数据
        teams = {
            "PL": ["Arsenal FC", "Manchester City FC", "Liverpool FC", "Manchester United FC",
                   "Chelsea FC", "Tottenham Hotspur FC", "Newcastle United FC", "Brighton & Hove Albion FC"],
            "PD": ["Real Madrid CF", "FC Barcelona", "Atlético de Madrid", "Sevilla FC",
                   "Valencia CF", "Real Betis Balompié", "Real Sociedad", "Athletic Bilbao"],
            "SA": ["FC Internazionale Milano", "AC Milan", "Juventus FC", "SSC Napoli",
                   "AS Roma", "SS Lazio", "Atalanta BC", "ACF Fiorentina"],
            "BL1": ["FC Bayern München", "Borussia Dortmund", "RB Leipzig", "Bayer 04 Leverkusen",
                    "VfB Stuttgart", "Eintracht Frankfurt", "Borussia Mönchengladbach", "VfL Wolfsburg"],
            "FL1": ["Paris Saint-Germain FC", "Olympique de Marseille", "AS Monaco FC", "Olympique Lyonnais",
                    "OGC Nice", "Stade Rennais FC", "RC Lens", "RC Strasbourg Alsace"]
        }

        return jsonify({
            'success': True,
            'teams': teams,
            'message': '球队数据获取成功'
        })

    except Exception as e:
        app.logger.error(f"获取球队数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取球队数据失败'
        }), 500

@app.route('/api/lottery/matches')
def get_lottery_matches():
    """获取中国体育彩票比赛数据 - 仅从数据库获取"""
    try:
        days = request.args.get('days', 3, type=int)
        days = min(max(days, 1), 7)  # 限制在1-7天之间

        app.logger.info(f"从数据库获取体彩数据 - 天数: {days}")

        if not prediction_db:
            app.logger.error("数据库未初始化")
            return jsonify({
                'success': False,
                'error': '数据库未配置',
                'message': '数据库连接失败，请联系管理员'
            }), 500

        try:
            # 仅从数据库获取
            db_matches = prediction_db.get_daily_matches(days_ahead=days)

            if db_matches and len(db_matches) > 0:
                app.logger.info(f"从数据库获取到 {len(db_matches)} 场比赛")

                return jsonify({
                    'success': True,
                    'matches': db_matches,
                    'count': len(db_matches),
                    'message': f'从数据库获取 {len(db_matches)} 场比赛',
                    'source': 'database'
                })
            else:
                app.logger.warning("数据库中没有找到比赛数据")

                return jsonify({
                    'success': False,
                    'error': '暂无比赛数据',
                    'message': '数据库中暂无比赛数据，请运行同步脚本更新数据：python scripts/sync_daily_matches.py --days 7'
                }), 404

        except Exception as db_error:
            app.logger.error(f"数据库获取失败: {db_error}")

            return jsonify({
                'success': False,
                'error': str(db_error),
                'message': '数据库查询失败，请稍后重试'
            }), 500

    except Exception as e:
        app.logger.error(f"获取体彩数据失败: {e}")

        return jsonify({
            'success': False,
            'error': str(e),
            'message': '系统错误，暂时无法获取数据'
        }), 500

@app.route('/api/save-prediction', methods=['POST'])
def save_prediction():
    """保存预测结果到数据库"""
    try:
        if not prediction_db:
            return jsonify({
                'success': False,
                'message': '数据库未配置'
            }), 500

        # 检查用户登录状态；本机免费模式允许匿名使用
        current_user = get_current_user()
        is_local_guest = LOCAL_FREE_MODE and not current_user
        if is_local_guest:
            current_user = get_local_guest_user()
        elif not current_user:
            return jsonify({
                'success': False,
                'message': '请先登录再进行预测'
            }), 401

        if not is_local_guest:
            # 检查用户预测权限
            can_predict = prediction_db.can_user_predict(
                current_user['id'],
                current_user['user_type'],
                current_user['daily_predictions_used']
            )

            if not can_predict:
                return jsonify({
                    'success': False,
                    'message': '今日免费预测次数已用完，请升级会员'
                }), 403

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            }), 400

        prediction_mode = data.get('mode', '').lower()
        match_data = data.get('match_data', {})
        prediction_result = data.get('prediction_result', '')
        confidence = data.get('confidence', 0)
        ai_analysis = data.get('ai_analysis', '')
        user_ip = request.remote_addr

        success = False

        if prediction_mode == 'ai':
            success = prediction_db.save_ai_prediction(
                match_data=match_data,
                prediction_result=prediction_result,
                confidence=confidence,
                ai_analysis=ai_analysis,
                user_ip=user_ip,
                user_id=current_user['id'],
                username=current_user['username']
            )
        elif prediction_mode == 'classic':
            success = prediction_db.save_classic_prediction(
                match_data=match_data,
                prediction_result=prediction_result,
                confidence=confidence,
                user_ip=user_ip,
                user_id=current_user['id'],
                username=current_user['username']
            )
        elif prediction_mode == 'lottery':
            success = prediction_db.save_lottery_prediction(
                match_data=match_data,
                prediction_result=prediction_result,
                confidence=confidence,
                ai_analysis=ai_analysis,
                user_ip=user_ip,
                user_id=current_user['id'],
                username=current_user['username']
            )
        else:
            return jsonify({
                'success': False,
                'message': '未知的预测模式'
            }), 400

        if success:
            if is_local_guest:
                return jsonify({
                    'success': True,
                    'message': '预测结果已匿名保存',
                    'user': {
                        'username': current_user['username'],
                        'user_type': current_user['user_type'],
                        'daily_predictions_used': 0,
                        'total_predictions': 0,
                        'membership_expires': None
                    }
                })

            # 增加用户预测次数
            prediction_db.increment_user_predictions(current_user['id'])

            # 重新从数据库获取最新用户数据，包括更新后的预测次数
            updated_user = prediction_db.get_user_by_username(current_user['username'])

            # 如果成功获取到更新的用户数据，则更新session并返回
            if updated_user:
                session['user_id'] = updated_user['id']
                session['username'] = updated_user['username']
                session.permanent = True
                app.logger.info(f"用户 {updated_user['username']} 预测次数已更新: {updated_user['daily_predictions_used']}")
                return jsonify({
                    'success': True,
                    'message': '预测结果保存成功',
                    'user': {
                        'username': updated_user['username'],
                        'user_type': updated_user['user_type'],
                        'daily_predictions_used': updated_user['daily_predictions_used'],
                        'total_predictions': updated_user['total_predictions'],
                        'membership_expires': updated_user['membership_expires'].isoformat() if updated_user['membership_expires'] else None
                    }
                })
            else:
                app.logger.error(f"保存预测后无法获取更新后的用户数据: {current_user['username']}", exc_info=True)
                return jsonify({'success': False, 'message': '预测成功，但获取用户状态失败'}), 500
        else:
            return jsonify({
                'success': False,
                'message': '预测结果保存失败'
            }), 500

    except Exception as e:
        app.logger.error(f"保存预测结果失败: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/prediction-stats', methods=['GET'])
def get_prediction_stats():
    """获取预测统计信息"""
    try:
        if not prediction_db:
            return jsonify({
                'success': False,
                'message': '数据库未配置'
            }), 500

        stats = prediction_db.get_prediction_stats()
        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        app.logger.error(f"获取统计信息失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取统计信息失败: {str(e)}'
        }), 500

@app.route('/api/ai/predict', methods=['POST'])
def ai_predict():
    """AI智能预测接口"""
    try:
        data = request.get_json() or {}
        matches = data.get('matches', [])

        if not matches:
            return jsonify({
                'success': False,
                'error': '没有提供比赛数据'
            }), 400

        app.logger.info(f"收到AI预测请求，比赛数量: {len(matches)}")

        settings = load_local_settings()
        ai = get_ai_settings(settings, include_environment=True)
        if not ai.get('api_key') or not ai.get('model'):
            return jsonify({
                'success': False,
                'error': '请先在右上角“设置”中填写 AI Key 和模型名称'
            }), 400
        if not AIFootballPredictor:
            return jsonify({
                'success': False,
                'error': 'AI预测器模块未加载'
            }), 500

        current_predictor = AIFootballPredictor(
            api_key=ai['api_key'],
            model_name=ai['model'],
            provider=ai['provider'],
            base_url=ai['base_url']
        )
        analyses = current_predictor.analyze_matches(matches)

        results = []
        for analysis in analyses:
            results.append({
                'match_id': analysis.match_id,
                'home_team': analysis.home_team,
                'away_team': analysis.away_team,
                'league_name': analysis.league_name,
                'ai_analysis': analysis.ai_analysis,
                'odds': {
                    'home': analysis.home_odds,
                    'draw': analysis.draw_odds,
                    'away': analysis.away_odds
                }
            })

        return jsonify({
            'success': True,
            'predictions': results,
            'count': len(results)
        })

    except Exception as e:
        app.logger.error(f"AI预测失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai/analyze-text', methods=['POST'])
def ai_analyze_text():
    """通用 AI 文本分析接口，用于串关推荐等文本场景。"""
    try:
        data = request.get_json() or {}
        prompt = (data.get('prompt') or '').strip()
        if not prompt:
            return jsonify({'success': False, 'error': '没有提供分析内容'}), 400

        settings = load_local_settings()
        ai = get_ai_settings(settings, include_environment=True)
        if not ai.get('api_key') or not ai.get('model'):
            return jsonify({
                'success': False,
                'error': '请先在右上角“设置”中填写 AI Key 和模型名称'
            }), 400
        if not AIFootballPredictor:
            return jsonify({'success': False, 'error': 'AI预测器模块未加载'}), 500

        predictor = AIFootballPredictor(
            api_key=ai['api_key'],
            model_name=ai['model'],
            provider=ai['provider'],
            base_url=ai['base_url']
        )
        analysis = predictor._call_ai_model(prompt)
        if not analysis:
            return jsonify({'success': False, 'error': 'AI 没有返回有效内容'}), 500
        return jsonify({'success': True, 'analysis': analysis})
    except Exception as e:
        app.logger.error(f"AI文本分析失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/predict', methods=['POST'])
def predict():
    """简化版预测接口"""
    try:
        data = request.json
        matches = data.get('matches', [])

        if not matches:
            return jsonify({
                'success': False,
                'message': '未提供比赛数据'
            })

        # 记录用户输入
        log_user_prediction(matches)

        # 简化预测逻辑
        individual_predictions = []
        for match in matches:
            prediction = simple_predict_match(match)
            individual_predictions.append(prediction)

        return jsonify({
            'success': True,
            'individual_predictions': individual_predictions,
            'message': '简化预测模式，推荐使用AI智能预测获得更准确结果'
        })

    except Exception as e:
        app.logger.error(f"预测错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'预测过程中发生错误: {str(e)}'
        })

def simple_predict_match(match):
    """简化的比赛预测"""
    home_odds = float(match.get('home_odds', 2.0))
    draw_odds = float(match.get('draw_odds', 3.0))
    away_odds = float(match.get('away_odds', 2.5))

    # 基于赔率的简单概率计算
    home_prob = 1 / home_odds
    draw_prob = 1 / draw_odds
    away_prob = 1 / away_odds

    total_prob = home_prob + draw_prob + away_prob

    # 归一化概率
    home_prob /= total_prob
    draw_prob /= total_prob
    away_prob /= total_prob

    return {
        'match': f"{match['home_team']} vs {match['away_team']}",
        'home_team': match['home_team'],
        'away_team': match['away_team'],
        'probabilities': {
            'home': round(home_prob, 3),
            'draw': round(draw_prob, 3),
            'away': round(away_prob, 3)
        },
        'odds': {
            'home': home_odds,
            'draw': draw_odds,
            'away': away_odds
        },
        'recommendation': '主胜' if home_prob > max(draw_prob, away_prob) else ('平局' if draw_prob > away_prob else '客胜')
    }

def generate_ai_combinations(ai_analyses):
    """基于AI分析生成组合预测"""
    combinations = []

    # 胜平负最佳组合
    best_wdl_combo = []
    total_confidence = 1.0

    for analysis in ai_analyses:
        wdl = analysis['win_draw_loss']
        best_outcome = max(wdl, key=wdl.get)

        best_wdl_combo.append({
            'match': f"{analysis['home_team']} vs {analysis['away_team']}",
            'prediction': best_outcome,
            'probability': wdl[best_outcome],
            'confidence': analysis['confidence_level']
        })

        total_confidence *= analysis['confidence_level']

    combinations.append({
        'type': '胜平负最佳组合',
        'selections': best_wdl_combo,
        'total_confidence': total_confidence,
        'description': '基于AI分析的最高概率胜平负组合'
    })

    return combinations

def log_user_prediction(matches):
    """记录用户预测请求"""
    try:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'matches_count': len(matches),
            'matches': matches
        }

        # 简单的文件日志
        with open('user_predictions.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    except Exception as e:
        app.logger.error(f"记录用户预测失败: {str(e)}")

@app.route('/api/lottery/refresh', methods=['POST'])
def refresh_lottery_data():
    """刷新彩票数据"""
    try:
        data = request.json
        days = data.get('days', 3)

        if not lottery_spider:
            return jsonify({
                'success': False,
                'message': '彩票API未初始化'
            })

        matches = lottery_spider.get_formatted_matches(days)

        return jsonify({
            'success': True,
            'matches': matches,
            'count': len(matches)
        })

    except Exception as e:
        app.logger.error(f"刷新彩票数据失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'刷新数据失败: {str(e)}'
        })

@app.route('/api/ai/batch-predict', methods=['POST'])
def ai_batch_predict():
    """AI批量预测"""
    try:
        data = request.json
        matches = data.get('matches', [])

        if not matches:
            return jsonify({
                'success': False,
                'message': '未提供比赛数据'
            })

        # 调用AI预测
        return ai_predict()

    except Exception as e:
        app.logger.error(f"AI批量预测错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量预测失败: {str(e)}'
        })

@app.route('/test')
def test():
    """测试路由"""
    return jsonify({
        'status': 'ok',
        'message': '服务正常运行',
        'lottery_spider': lottery_spider is not None,
        'ai_predictor': ai_predictor is not None,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    """健康检查"""
    return "OK", 200

@app.route('/data/<filename>')
def serve_data_files(filename):
    """提供数据文件访问"""
    try:
        from flask import send_from_directory
        return send_from_directory(RESOURCE_DIR / 'data', filename)
    except Exception as e:
        app.logger.error(f"提供数据文件失败: {e}")
        return jsonify({'error': '文件未找到'}), 404

# 用户认证路由
@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    """用户注册"""
    app.logger.info(f"收到注册请求：{request.json}")
    try:
        if not prediction_db:
            app.logger.error("注册失败: 数据库未配置或初始化失败", exc_info=True)
            return jsonify({'success': False, 'message': '注册失败：数据库服务不可用'}), 500

        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        # 验证输入
        if not username or len(username) < 3:
            app.logger.warning(f"注册失败: 用户名不符合要求 - {username}")
            return jsonify({'success': False, 'message': '用户名长度至少3个字符'}), 400
        if not email or '@' not in email:
            app.logger.warning(f"注册失败: 邮箱格式无效 - {email}")
            return jsonify({'success': False, 'message': '请输入有效的邮箱地址'}), 400
        if not password or len(password) < 6:
            app.logger.warning(f"注册失败: 密码不符合要求 - {password}")
            return jsonify({'success': False, 'message': '密码长度至少6个字符'}), 400

        # 哈希密码
        password_hash = hash_password(password)

        # 创建用户
        success = prediction_db.create_user(username, email, password_hash)

        if success:
            app.logger.info(f"用户注册成功: {username}")
            resp = jsonify({'success': True, 'message': '注册成功，请登录'})
            # 调试用：设置一个临时测试 Cookie，帮助判断浏览器是否接受 SameSite=None; Secure
            try:
                pass # 移除调试Cookie设置
            except Exception as e:
                app.logger.warning(f"设置测试Cookie失败: {e}", exc_info=True)
                # 忽略设置 Cookie 时的任何异常
                pass
            return resp
        else:
            # create_user 内部已处理 UniqueViolation，这里捕获通用失败
            app.logger.warning(f"用户注册失败: 用户名或邮箱已存在或数据库操作失败 - {username}, {email}")
            return jsonify({'success': False, 'message': '注册失败：用户名或邮箱已存在，或数据库写入失败'}), 409

    except Exception as e:
        app.logger.error(f"用户注册失败（捕获到异常）: {e}", exc_info=True) # 打印完整堆栈
        return jsonify({'success': False, 'message': '注册失败，请稍后重试'}), 500

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    """用户登录"""
    app.logger.info(f"收到登录请求: {request.json}")
    try:
        if not prediction_db:
            app.logger.error("登录失败: 数据库未配置或初始化失败", exc_info=True)
            return jsonify({'success': False, 'message': '登录失败：数据库服务不可用'}), 500

        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            app.logger.warning("登录失败: 缺少用户名或密码")
            return jsonify({'success': False, 'message': '请输入用户名和密码'}), 400

        # 哈希密码
        password_hash = hash_password(password)

        # 验证用户
        user = prediction_db.authenticate_user(username, password_hash)

        if user:
            # 设置session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True

            app.logger.info(f"用户登录成功，设置会话: {username}")
            resp = jsonify({
                'success': True,
                'message': '登录成功',
                'user': {
                    'username': user['username'],
                    'user_type': user['user_type'],
                    'daily_predictions_used': user['daily_predictions_used'],
                    'total_predictions': user['total_predictions']
                }
            })
            # 显式设置 Flask session cookie 值，确保 Set-Cookie 在响应头中可见
            try:
                serializer = app.session_interface.get_signing_serializer(app)
                if serializer:
                    session_cookie_val = serializer.dumps(dict(session))
                    resp.set_cookie(app.config.get('SESSION_COOKIE_NAME', 'mp_session'),
                                    session_cookie_val,
                                    samesite=os.environ.get('SESSION_COOKIE_SAMESITE', 'None'),
                                    secure=True,
                                    httponly=True,
                                    domain=app.config.get('SESSION_COOKIE_DOMAIN'))
                # 额外设置一个非 HttpOnly 的测试 Cookie 便于调试（可见于 DevTools -> Cookies）
                pass # 移除调试Cookie设置
            except Exception as e:
                app.logger.warning(f"设置Cookie失败: {e}", exc_info=True)
                pass
            return resp
        else:
            app.logger.warning(f"用户登录失败: 用户名或密码错误 - {username}")
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

    except Exception as e:
        app.logger.error(f"用户登录失败（捕获到异常）: {e}", exc_info=True) # 打印完整堆栈
        return jsonify({'success': False, 'message': '登录失败，请稍后重试'}), 500

@app.route('/api/logout', methods=['POST', 'OPTIONS'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'success': True, 'message': '已安全退出'})

@app.route('/api/user/info', methods=['GET'])
def get_user_info():
    """获取用户信息"""
    app.logger.info("收到获取用户信息请求")
    try:
        if LOCAL_FREE_MODE:
            local_user = get_local_guest_user()
            return jsonify({
                'success': True,
                'local_free_mode': True,
                'user': {
                    'username': local_user['username'],
                    'email': local_user['email'],
                    'user_type': local_user['user_type'],
                    'daily_predictions_used': local_user['daily_predictions_used'],
                    'total_predictions': local_user['total_predictions'],
                    'membership_expires': None
                }
            })

        current_user = get_current_user()
        if not current_user:
            app.logger.warning("获取用户信息失败: 用户未登录")
            return jsonify({'success': False, 'message': '未登录'}), 401

        # 确保 prediction_db 可用，get_current_user 已经做了初步检查
        if not prediction_db:
            app.logger.error("获取用户信息失败: 数据库未配置或初始化失败", exc_info=True)
            return jsonify({'success': False, 'message': '获取用户信息失败：数据库服务不可用'}), 500

        # 刷新用户数据以获取最新状态，特别是每日预测次数可能已重置
        user_data_from_db = prediction_db.get_user_by_username(current_user['username'])
        if not user_data_from_db:
            app.logger.error(f"获取用户信息失败: 数据库中未找到用户 {current_user['username']}", exc_info=True)
            # 用户可能已被删除，清理session
            session.clear()
            return jsonify({'success': False, 'message': '用户数据异常，请重新登录'}), 401

        app.logger.info(f"成功获取用户 {user_data_from_db['username']} 信息")
        return jsonify({
            'success': True,
            'user': {
                'username': user_data_from_db['username'],
                'email': user_data_from_db['email'],
                'user_type': user_data_from_db['user_type'],
                'daily_predictions_used': user_data_from_db['daily_predictions_used'],
                'total_predictions': user_data_from_db['total_predictions'],
                'membership_expires': user_data_from_db['membership_expires'].isoformat() if user_data_from_db['membership_expires'] else None
            }
        })

    except Exception as e:
        app.logger.error(f"获取用户信息失败（捕获到异常）: {e}", exc_info=True)
        return jsonify({'success': False, 'message': '获取用户信息失败'}), 500

@app.route('/api/user/can-predict', methods=['GET'])
def can_user_predict_api():
    """检查用户是否可以预测"""
    app.logger.info("收到检查用户预测权限请求")
    try:
        if LOCAL_FREE_MODE:
            return jsonify({
                'success': True,
                'local_free_mode': True,
                'can_predict': True,
                'user_type': 'local_free',
                'daily_used': 0,
                'remaining': 'unlimited'
            })

        current_user = get_current_user()
        if not current_user:
            app.logger.warning("检查预测权限失败: 用户未登录")
            return jsonify({'success': False, 'message': '未登录', 'can_predict': False}), 401

        if not prediction_db:
            app.logger.error("检查预测权限失败: 数据库未配置或初始化失败", exc_info=True)
            return jsonify({'success': False, 'message': '检查失败：数据库服务不可用'}), 500

        # 刷新用户数据以获取最新状态，特别是每日预测次数可能已重置
        user_data_from_db = prediction_db.get_user_by_username(current_user['username'])
        if not user_data_from_db:
            app.logger.error(f"检查预测权限失败: 数据库中未找到用户 {current_user['username']}", exc_info=True)
            session.clear()
            return jsonify({'success': False, 'message': '用户数据异常，请重新登录', 'can_predict': False}), 401

        can_predict = prediction_db.can_user_predict(
            user_data_from_db['id'],
            user_data_from_db['user_type'],
            user_data_from_db['daily_predictions_used']
        )

        remaining = 0
        if user_data_from_db['user_type'] == 'free':
            remaining = max(0, 3 - user_data_from_db['daily_predictions_used'])

        app.logger.info(f"用户 {user_data_from_db['username']} 预测权限检查结果: can_predict={can_predict}, remaining={remaining}")
        return jsonify({
            'success': True,
            'can_predict': can_predict,
            'user_type': user_data_from_db['user_type'],
            'daily_used': user_data_from_db['daily_predictions_used'],
            'remaining': remaining
        })

    except Exception as e:
        app.logger.error(f"检查预测权限失败（捕获到异常）: {e}", exc_info=True)
        return jsonify({'success': False, 'message': '检查失败'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes', 'on')
    app.run(debug=debug, host='0.0.0.0', port=port)
