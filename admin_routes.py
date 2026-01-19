"""
Admin Panel Routes for Soul AI Bot
Веб-админка для управления ботом через Telegram WebApp
"""

import os
import asyncio
import psutil
import hashlib
import hmac
import json
import urllib.parse
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, abort

from database import postgres_db as db
from database.postgres_db import init_pool, init_db
from config import ADMIN_IDS, BOT_TOKEN

# Configure logging
logger = logging.getLogger(__name__)

# TEMPORARY: Test mode to bypass Telegram auth
TEST_MODE = os.getenv('ADMIN_TEST_MODE', 'false').lower() == 'true'

# Admin password (hash stored in env, plain password checked once)
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', '')  # SHA256 hash of password

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Test route
@admin_bp.route('/test')
def test_auth():
    """Test authentication"""
    init_data = get_init_data()
    user = verify_telegram_auth(init_data) if init_data else None
    is_admin = check_admin(init_data) if init_data else False
    
    return jsonify({
        'init_data_present': bool(init_data),
        'init_data_length': len(init_data) if init_data else 0,
        'user': user,
        'is_admin': is_admin,
        'ADMIN_IDS': ADMIN_IDS,
        'headers': dict(request.headers),
        'args': dict(request.args)
    })


# Global event loop and pool state
_admin_loop = None
_pool_initialized = False


def get_admin_loop():
    """Get or create event loop for admin operations"""
    global _admin_loop
    if _admin_loop is None or _admin_loop.is_closed():
        _admin_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_admin_loop)
    return _admin_loop


def ensure_pool_initialized():
    """Ensure PostgreSQL pool is initialized"""
    global _pool_initialized
    if _pool_initialized:
        return
    
    try:
        loop = get_admin_loop()
        loop.run_until_complete(init_pool())
        loop.run_until_complete(init_db())
        _pool_initialized = True
    except Exception as e:
        print(f"Admin pool init error: {e}")


def run_async(coro):
    """Run async function in sync context with automatic reconnection"""
    try:
        ensure_pool_initialized()
        loop = get_admin_loop()
        return loop.run_until_complete(coro)
    except (RuntimeError, Exception) as e:
        error_str = str(e)
        # Проверяем различные типы ошибок подключения
        if any(x in error_str for x in ["different loop", "attached to a different loop", "connection was closed", "ConnectionDoesNotExistError"]):
            # Pool привязан к другому loop или соединение закрыто - пересоздаём
            logger.warning(f"Admin connection/loop error detected, reinitializing: {e}")
            global _pool_initialized, _admin_loop
            _pool_initialized = False
            
            # Пересоздаём loop и pool
            if _admin_loop and not _admin_loop.is_closed():
                try:
                    _admin_loop.close()
                except:
                    pass
            _admin_loop = None
            
            ensure_pool_initialized()
            loop = get_admin_loop()
            return loop.run_until_complete(coro)
        raise


# ============================================================================
# TELEGRAM WEBAPP AUTH
# ============================================================================

def verify_telegram_auth(init_data: str) -> dict:
    """
    Проверка подписи Telegram WebApp initData.
    Возвращает данные пользователя или None при неудаче.
    """
    if not init_data:
        logger.warning("❌ [Admin Auth] No initData provided")
        return None
    
    try:
        # Парсим initData (URL-encoded string)
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        hash_str = parsed.pop('hash', '')
        
        if not hash_str:
            logger.warning("❌ [Admin Auth] No hash in initData")
            return None
        
        # Формируем строку для проверки
        data_check_string = '\n'.join(
            f'{k}={v}' for k, v in sorted(parsed.items())
        )
        
        # Создаём ключ и хэш
        secret_key = hmac.new(
            b'WebAppData', 
            BOT_TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != hash_str:
            logger.warning(f"❌ [Admin Auth] Hash mismatch: expected {hash_str[:20]}..., got {calculated_hash[:20]}...")
            return None
        
        # Парсим данные пользователя
        user_str = parsed.get('user', '{}')
        user_data = json.loads(urllib.parse.unquote(user_str))
        logger.info(f"✅ [Admin Auth] User authenticated: {user_data.get('id')} (@{user_data.get('username')})")
        return user_data
        
    except Exception as e:
        logger.error(f"❌ [Admin Auth] Exception: {e}", exc_info=True)
        return None


def check_admin(init_data: str) -> bool:
    """Проверить что пользователь админ"""
    user = verify_telegram_auth(init_data)
    if not user:
        logger.warning("❌ [Admin Auth] No user after verification")
        return False
    
    user_id = user.get('id')
    is_admin = user_id in ADMIN_IDS
    
    if is_admin:
        logger.info(f"✅ [Admin Auth] User {user_id} is admin")
    else:
        logger.warning(f"❌ [Admin Auth] User {user_id} NOT in ADMIN_IDS {ADMIN_IDS}")
    
    return is_admin


def check_password_session(user_id: int) -> bool:
    """Проверка, введён ли пароль в текущей сессии"""
    session_key = f'admin_password_verified:{user_id}'
    try:
        from database.redis_db import redis_client
        if redis_client:
            return redis_client.get(session_key) == 'true'
        return False
    except Exception as e:
        logger.error(f"❌ Redis error checking password session: {e}")
        return False


def set_password_session(user_id: int, expires_hours: int = 24):
    """Сохранить сессию после успешного ввода пароля"""
    session_key = f'admin_password_verified:{user_id}'
    try:
        from database.redis_db import redis_client
        if redis_client:
            redis_client.setex(session_key, expires_hours * 3600, 'true')
            logger.info(f"✅ Password session set for user {user_id} (expires in {expires_hours}h)")
    except Exception as e:
        logger.error(f"❌ Redis error setting password session: {e}")


def verify_password(password: str) -> bool:
    """Проверка пароля"""
    if not ADMIN_PASSWORD_HASH:
        logger.warning("⚠️ ADMIN_PASSWORD_HASH not set, password check disabled")
        return True
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return password_hash == ADMIN_PASSWORD_HASH


def get_init_data():
    """Получить initData из запроса (header или query param)"""
    init_data = request.headers.get('X-Telegram-Init-Data')
    source = 'header'
    if not init_data:
        init_data = request.args.get('initData')
        source = 'query'
    if not init_data:
        init_data = request.form.get('initData')
        source = 'form'
    if not init_data:
        source = 'NONE'
    
    logger.info(f"🔍 [Admin Auth] initData source: {source}")
    if init_data:
        logger.info(f"🔍 [Admin Auth] initData length: {len(init_data)}, first 50 chars: {init_data[:50]}...")
    
    return init_data


def admin_required(f):
    """Decorator to require admin authentication via Telegram WebApp + password"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TEMPORARY: Test mode bypass
        if TEST_MODE:
            logger.warning("⚠️ [Admin Auth] TEST MODE ENABLED - Skipping auth")
            return f(*args, **kwargs)
        
        init_data = get_init_data()
        
        # Шаг 1: Проверка Telegram ID
        if not check_admin(init_data):
            if request.path.startswith('/admin/api/'):
                return jsonify({'error': 'Forbidden', 'message': 'Доступ запрещён'}), 403
            return render_template('admin/error.html', 
                error="Доступ запрещён", 
                message="Только администраторы могут использовать эту панель."
            ), 403
        
        # Шаг 2: Проверка пароля (если задан)
        user = verify_telegram_auth(init_data)
        user_id = user.get('id')
        
        # Пропускаем проверку пароля для страницы ввода пароля
        if request.path == '/admin/password':
            return f(*args, **kwargs)
        
        # Если пароль не задан в .env, пропускаем проверку
        if not ADMIN_PASSWORD_HASH:
            logger.info(f"✅ [Admin Auth] Password not required, user {user_id} granted access")
            return f(*args, **kwargs)
        
        # Проверяем сессию пароля
        if not check_password_session(user_id):
            logger.warning(f"⚠️ [Admin Auth] User {user_id} needs to enter password")
            if request.path.startswith('/admin/api/'):
                return jsonify({'error': 'Password required', 'message': 'Требуется ввод пароля'}), 401
            return redirect(url_for('admin.password_page'))
        
        logger.info(f"✅ [Admin Auth] User {user_id} fully authenticated")
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Получить текущего пользователя из initData"""
    init_data = get_init_data()
    return verify_telegram_auth(init_data)


def get_template_context(**kwargs):
    """Базовый контекст для всех шаблонов"""
    init_data = get_init_data()
    user = verify_telegram_auth(init_data)
    return {
        'init_data': init_data or '',
        'admin_user': user,
        **kwargs
    }


# ============================================================================
# PAGES
# ============================================================================

@admin_bp.route('/password', methods=['GET', 'POST'])
def password_page():
    """Страница ввода пароля"""
    init_data = get_init_data()
    
    # Проверяем что пользователь - админ по ID
    if not check_admin(init_data):
        return render_template('admin/error.html',
            error="Доступ запрещён",
            message="Только администраторы могут использовать эту панель."
        ), 403
    
    user = verify_telegram_auth(init_data)
    user_id = user.get('id')
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        if verify_password(password):
            set_password_session(user_id, expires_hours=24)
            logger.info(f"✅ User {user_id} entered correct password")
            return redirect(url_for('admin.dashboard'))
        else:
            logger.warning(f"❌ User {user_id} entered wrong password")
            return render_template('admin/password.html', 
                error="Неверный пароль",
                **get_template_context()
            )
    
    return render_template('admin/password.html', **get_template_context())


@admin_bp.route('/')
def dashboard():
    """Main dashboard - initial load without auth check"""
    # На первой загрузке просто отдаём HTML с JavaScript
    # JavaScript сам проверит initData и перенаправит если нужно
    period = request.args.get('period', 30, type=int)
    
    # Get stats
    total_users = run_async(db.count_users())
    blocked = run_async(db.get_blocked_count())
    mini_count = run_async(db.count_subscribers_by_type('mini'))
    standard_count = run_async(db.count_subscribers_by_type('standard'))
    premium_count = run_async(db.count_subscribers_by_type('premium'))
    stars_used = run_async(db.get_total_stars_used())
    
    # Server load
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Get chart data
    stars_by_day = run_async(get_stars_by_period(period))
    stars_by_function = run_async(get_stars_by_function())
    users_by_day = run_async(get_users_by_period(period))
    payments_by_day = run_async(get_payments_by_period(period))
    
    # Calculate revenue
    revenue = run_async(get_month_revenue())
    
    return render_template('admin/dashboard.html',
        **get_template_context(
            active_page='dashboard',
            stats={
                'total_users': total_users,
                'subscribers': mini_count + standard_count + premium_count,
                'blocked': blocked,
                'stars_used': stars_used,
                'mini_count': mini_count,
                'standard_count': standard_count,
                'premium_count': premium_count,
                'revenue': revenue
            },
            server={
                'cpu': cpu,
                'ram': mem.percent,
                'disk': disk.percent
            },
            stars_by_day=stars_by_day,
            stars_by_function=stars_by_function,
            users_by_day=users_by_day,
            payments_by_day=payments_by_day
        )
    )


@admin_bp.route('/users')
def users():
    """Users list and search - auth checked by JavaScript"""
    """Users list and search"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    per_page = 20
    
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'success')
    
    user_detail = None
    
    if search:
        # Search by ID or username
        try:
            uid = int(search)
            user_detail = run_async(db.get_user(uid))
            if user_detail:
                sub = run_async(db.get_subscription(uid))
                user_detail['subscription'] = sub
        except ValueError:
            # Search by username
            all_users = run_async(db.get_all_users())
            for u in all_users:
                if u.get('username') and search.lower() in u['username'].lower():
                    user_detail = u
                    sub = run_async(db.get_subscription(u['user_id']))
                    user_detail['subscription'] = sub
                    break
    
    # Get users with pagination
    all_users = run_async(db.get_all_users())
    total_users = len(all_users)
    total_pages = max(1, (total_users + per_page - 1) // per_page)
    
    start = (page - 1) * per_page
    end = start + per_page
    users_page = all_users[start:end]
    
    # Add subscription info
    for u in users_page:
        u['subscription'] = run_async(db.get_subscription(u['user_id']))
    
    return render_template('admin/users.html',
        **get_template_context(
            active_page='users',
            users=users_page,
            user_detail=user_detail,
            total_users=total_users,
            page=page,
            total_pages=total_pages,
            search=search,
            message=message,
            message_type=message_type
        )
    )


@admin_bp.route('/subscriptions')
def subscriptions():
    """Subscriptions management - auth checked by JavaScript"""
    """Subscriptions management"""
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    per_page = 20
    
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'success')
    
    # Get stats
    mini = run_async(db.count_subscribers_by_type('mini'))
    standard = run_async(db.count_subscribers_by_type('standard'))
    premium = run_async(db.count_subscribers_by_type('premium'))
    
    # Get subscriptions
    if filter_type == 'all':
        subs = run_async(db.get_active_subscriptions())
    else:
        subs = run_async(get_subscribers_by_type_with_user(filter_type))
    
    total = len(subs)
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    start = (page - 1) * per_page
    end = start + per_page
    subs_page = subs[start:end]
    
    # Add usernames
    for s in subs_page:
        user = run_async(db.get_user(s['user_id']))
        s['username'] = user.get('username') if user else None
    
    return render_template('admin/subscriptions.html',
        **get_template_context(
            active_page='subscriptions',
            stats={'mini': mini, 'standard': standard, 'premium': premium},
            subscriptions=subs_page,
            filter=filter_type,
            page=page,
            total_pages=total_pages,
            message=message,
            message_type=message_type
        )
    )


@admin_bp.route('/tokens')
def tokens():
    """Tokens management - auth checked by JavaScript"""
    """Star management"""
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'success')
    
    total_users = run_async(db.count_users())
    users_without_sub = run_async(count_users_without_subscription())
    
    history = []
    
    return render_template('admin/tokens.html',
        **get_template_context(
            active_page='tokens',
            total_users=total_users,
            users_without_sub=users_without_sub,
            history=history,
            message=message,
            message_type=message_type
        )
    )


@admin_bp.route('/broadcast')
def broadcast():
    """Broadcast page - auth checked by JavaScript"""
    """Broadcast page"""
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'success')
    
    # Get counts for each filter
    total = run_async(db.count_users())
    subs = run_async(db.get_active_subscriptions())
    subs_count = len(subs)
    nosub_count = total - subs_count
    
    mini = run_async(db.count_subscribers_by_type('mini'))
    standard = run_async(db.count_subscribers_by_type('standard'))
    premium = run_async(db.count_subscribers_by_type('premium'))
    
    counts = {
        'all': total,
        'sub': subs_count,
        'nosub': nosub_count,
        'mini': mini,
        'standard': standard,
        'premium': premium
    }
    
    history = []
    
    return render_template('admin/broadcast.html',
        **get_template_context(
            active_page='broadcast',
            counts=counts,
            history=history,
            message=message,
            message_type=message_type
        )
    )


@admin_bp.route('/memory')
def memory():
    """Memory management - auth checked by JavaScript"""
    """Memory management"""
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id', type=int)
    per_page = 20
    
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'success')
    
    user_memory = None
    
    if user_id:
        # Get user's memory for all bots
        user_memory = {}
        for bot_name in ['luca', 'silas', 'titus', 'voice']:
            facts = run_async(db.get_memory(user_id, bot_name))
            if facts:
                user_memory[bot_name] = facts
    
    # Get users with memory
    users_with_memory = run_async(get_users_with_memory_counts(per_page, (page - 1) * per_page))
    total_with_memory = run_async(db.count_users_with_memory())
    total_pages = max(1, (total_with_memory + per_page - 1) // per_page)
    
    return render_template('admin/memory.html',
        **get_template_context(
            active_page='memory',
            user_memory=user_memory,
            user_id=user_id,
            users_with_memory=users_with_memory,
            total_with_memory=total_with_memory,
            page=page,
            total_pages=total_pages,
            message=message,
            message_type=message_type
        )
    )


@admin_bp.route('/finance')
def finance():
    """Finance page - auth checked by JavaScript"""
    """Finance and payments"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    period = request.args.get('period', 30, type=int)
    per_page = 20
    
    # Get stats
    stats = run_async(get_finance_stats())
    
    # Get payments
    payments = run_async(get_payment_transactions(per_page, (page - 1) * per_page, status_filter))
    total_payments = run_async(count_payment_transactions(status_filter))
    total_pages = max(1, (total_payments + per_page - 1) // per_page)
    
    # Revenue by day for chart
    revenue_by_day = run_async(get_payments_by_period(period))
    
    return render_template('admin/finance.html',
        **get_template_context(
            active_page='finance',
            stats=stats,
            payments=payments,
            page=page,
            total_pages=total_pages,
            status_filter=status_filter,
            period=period,
            revenue_by_day=revenue_by_day
        )
    )


@admin_bp.route('/settings')
def settings():
    """Settings page - auth checked by JavaScript"""
    """Settings page"""
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'success')
    
    # Get current settings
    settings_data = run_async(get_all_settings())
    
    return render_template('admin/settings.html',
        **get_template_context(
            active_page='settings',
            settings=settings_data,
            system={'python_version': '3.12', 'uptime': get_uptime()},
            message=message,
            message_type=message_type
        )
    )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@admin_bp.route('/api/auth/check', methods=['POST'])
def check_auth():
    """Проверка авторизации через initData"""
    try:
        init_data = get_init_data()
        
        if not init_data:
            return jsonify({'authorized': False, 'error': 'no_init_data'}), 401
        
        # Проверяем Telegram ID
        if not check_admin(init_data):
            return jsonify({'authorized': False, 'error': 'not_admin'}), 403
        
        user = verify_telegram_auth(init_data)
        user_id = user.get('id')
        
        # Если пароль не задан, авторизация успешна
        if not ADMIN_PASSWORD_HASH:
            return jsonify({
                'authorized': True,
                'password_required': False,
                'user_id': user_id
            })
        
        # Проверяем сессию пароля
        if check_password_session(user_id):
            return jsonify({
                'authorized': True,
                'password_required': False,
                'user_id': user_id
            })
        
        # Нужен ввод пароля
        return jsonify({
            'authorized': True,
            'password_required': True,
            'user_id': user_id
        })
        
    except Exception as e:
        logger.error(f"❌ Auth check error: {e}")
        return jsonify({'authorized': False, 'error': str(e)}), 500


@admin_bp.route('/api/auth/password', methods=['POST'])
def verify_password_api():
    """Проверка пароля"""
    try:
        init_data = get_init_data()
        
        if not check_admin(init_data):
            return jsonify({'success': False, 'error': 'not_admin'}), 403
        
        data = request.get_json()
        password = data.get('password', '').strip()
        
        if not password:
            return jsonify({'success': False, 'error': 'password_required'}), 400
        
        if verify_password(password):
            user = verify_telegram_auth(init_data)
            user_id = user.get('id')
            set_password_session(user_id, expires_hours=24)
            return jsonify({'success': True, 'message': 'Пароль верный'})
        else:
            return jsonify({'success': False, 'error': 'wrong_password', 'message': 'Неверный пароль'}), 401
            
    except Exception as e:
        logger.error(f"❌ Password verify error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """API: Get dashboard stats"""
    total_users = run_async(db.count_users())
    blocked = run_async(db.get_blocked_count())
    mini_count = run_async(db.count_subscribers_by_type('mini'))
    standard_count = run_async(db.count_subscribers_by_type('standard'))
    premium_count = run_async(db.count_subscribers_by_type('premium'))
    stars_used = run_async(db.get_total_stars_used())
    
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return jsonify({
        'total_users': total_users,
        'subscribers': mini_count + standard_count + premium_count,
        'blocked': blocked,
        'stars_used': stars_used,
        'mini_count': mini_count,
        'standard_count': standard_count,
        'premium_count': premium_count,
        'server': {
            'cpu': cpu,
            'ram': mem.percent,
            'disk': disk.percent
        }
    })


@admin_bp.route('/api/users/<int:user_id>/block', methods=['POST'])
@admin_required
def api_block_user(user_id):
    """API: Block user"""
    run_async(db.block_user(user_id))
    return jsonify({'success': True, 'message': 'Пользователь заблокирован'})


@admin_bp.route('/api/users/<int:user_id>/unblock', methods=['POST'])
@admin_required
def api_unblock_user(user_id):
    """API: Unblock user"""
    run_async(db.unblock_user(user_id))
    return jsonify({'success': True, 'message': 'Пользователь разблокирован'})


@admin_bp.route('/api/users/<int:user_id>/give-stars', methods=['POST'])
@admin_required
def api_give_stars(user_id):
    """API: Give stars to user"""
    data = request.get_json() or {}
    amount = data.get('amount', 0)
    
    if amount > 0:
        run_async(db.add_stars(user_id, amount))
        run_async(notify_user_stars(user_id, amount))
        return jsonify({'success': True, 'message': f'Выдано {amount} звёзд'})
    
    return jsonify({'success': False, 'message': 'Укажите количество'}), 400


@admin_bp.route('/api/users/<int:user_id>/give-subscription', methods=['POST'])
@admin_required
def api_give_subscription(user_id):
    """API: Give subscription to user"""
    data = request.get_json() or {}
    sub_type = data.get('sub_type', 'mini')
    days = data.get('days', 30)
    
    stars_limits = {'mini': 4000, 'standard': 9000, 'premium': 20000}
    stars = stars_limits.get(sub_type, 4000)
    
    run_async(db.create_subscription(user_id, sub_type, stars, days))
    run_async(notify_user_subscription(user_id, sub_type, days))
    
    return jsonify({'success': True, 'message': f'Выдана подписка {sub_type} на {days} дней'})


@admin_bp.route('/api/tokens/give', methods=['POST'])
@admin_required
def api_give_tokens():
    """API: Give tokens to single user"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 0)
    amount = data.get('amount', 0)
    
    if user_id and amount > 0:
        run_async(db.add_stars(user_id, amount))
        run_async(notify_user_stars(user_id, amount))
        return jsonify({'success': True, 'message': f'Выдано {amount} звёзд пользователю {user_id}'})
    
    return jsonify({'success': False, 'message': 'Проверьте данные'}), 400


@admin_bp.route('/api/tokens/mass', methods=['POST'])
@admin_required
def api_give_tokens_mass():
    """API: Give tokens to all users"""
    data = request.get_json() or {}
    amount = data.get('amount', 0)
    
    if amount > 0:
        users = run_async(db.get_all_users())
        count = 0
        for u in users:
            run_async(db.add_stars(u['user_id'], amount))
            count += 1
        
        return jsonify({'success': True, 'message': f'Выдано {amount} звёзд {count} пользователям'})
    
    return jsonify({'success': False, 'message': 'Ошибка'}), 400


@admin_bp.route('/api/tokens/no-sub', methods=['POST'])
@admin_required
def api_give_tokens_no_sub():
    """API: Give tokens to users without subscription"""
    data = request.get_json() or {}
    amount = data.get('amount', 0)
    
    if amount > 0:
        users = run_async(get_users_without_subscription())
        count = 0
        for u in users:
            run_async(db.add_stars(u['user_id'], amount))
            count += 1
        
        return jsonify({'success': True, 'message': f'Выдано {amount} звёзд {count} пользователям без подписки'})
    
    return jsonify({'success': False, 'message': 'Ошибка'}), 400


@admin_bp.route('/api/broadcast/send', methods=['POST'])
@admin_required
def api_broadcast_send():
    """API: Send broadcast"""
    data = request.get_json() or {}
    filter_type = data.get('filter', 'all')
    text = data.get('text', '')
    
    if not text:
        return jsonify({'success': False, 'message': 'Введите текст рассылки'}), 400
    
    # Get recipients
    if filter_type == 'all':
        users = run_async(db.get_all_users())
    elif filter_type == 'sub':
        users = run_async(db.get_active_subscriptions())
    elif filter_type == 'nosub':
        users = run_async(get_users_without_subscription())
    elif filter_type == 'mini':
        users = run_async(get_subscribers_by_type_with_user('mini'))
    elif filter_type == 'standard':
        users = run_async(get_subscribers_by_type_with_user('standard'))
    elif filter_type == 'premium':
        users = run_async(get_subscribers_by_type_with_user('premium'))
    else:
        users = []
    
    # Send messages
    success, errors = run_async(send_broadcast(users, text))
    
    return jsonify({
        'success': True, 
        'sent': success, 
        'errors': errors,
        'message': f'Отправлено: {success}, ошибок: {errors}'
    })


@admin_bp.route('/api/memory/<int:user_id>/clear/<bot_name>', methods=['POST'])
@admin_required
def api_clear_memory_bot(user_id, bot_name):
    """API: Clear memory for specific bot"""
    run_async(db.save_memory(user_id, bot_name, []))
    return jsonify({'success': True, 'message': f'Память {bot_name} очищена'})


@admin_bp.route('/api/memory/<int:user_id>/clear-all', methods=['POST'])
@admin_required
def api_clear_memory_all(user_id):
    """API: Clear all memory for user"""
    for bot_name in ['luca', 'silas', 'titus', 'voice']:
        run_async(db.save_memory(user_id, bot_name, []))
    return jsonify({'success': True, 'message': f'Вся память пользователя {user_id} очищена'})


@admin_bp.route('/api/memory/<int:user_id>/delete/<bot_name>/<int:fact_idx>', methods=['POST'])
@admin_required
def api_delete_memory_fact(user_id, bot_name, fact_idx):
    """API: Delete single fact"""
    facts = run_async(db.get_memory(user_id, bot_name))
    if 0 <= fact_idx < len(facts):
        facts.pop(fact_idx)
        run_async(db.save_memory(user_id, bot_name, facts))
    return jsonify({'success': True, 'message': 'Факт удалён'})


@admin_bp.route('/api/memory/<int:user_id>/add/<bot_name>', methods=['POST'])
@admin_required
def api_add_memory_fact(user_id, bot_name):
    """API: Add new fact"""
    data = request.get_json() or {}
    fact = data.get('fact', '').strip()
    if fact:
        facts = run_async(db.get_memory(user_id, bot_name))
        facts.append(fact)
        run_async(db.save_memory(user_id, bot_name, facts))
        return jsonify({'success': True, 'message': 'Факт добавлен'})
    return jsonify({'success': False, 'message': 'Введите факт'}), 400


@admin_bp.route('/api/settings/save', methods=['POST'])
@admin_required
def api_save_settings():
    """API: Save all settings"""
    data = request.get_json() or {}
    
    settings_map = {
        'mini_price': '490', 'mini_stars': '4000',
        'standard_price': '990', 'standard_stars': '9000',
        'premium_price': '1990', 'premium_stars': '20000',
        'pack1_stars': '1000', 'pack1_price': '149',
        'pack2_stars': '2000', 'pack2_price': '249',
        'pack3_stars': '10000', 'pack3_price': '1190',
        'pack4_stars': '25000', 'pack4_price': '2790',
        'spam_interval': '2', 'spam_max_rpm': '8',
        'new_user_bonus': '250',
        'ref_mini': '1000', 'ref_standard': '2000', 'ref_premium': '4000'
    }
    
    for key, default in settings_map.items():
        if key in data:
            run_async(db.set_setting(key, str(data[key])))
    
    # Boolean settings
    if 'notify_new_sub' in data:
        run_async(db.set_setting('notify_new_sub', '1' if data['notify_new_sub'] else '0'))
    if 'notify_payments' in data:
        run_async(db.set_setting('notify_payments', '1' if data['notify_payments'] else '0'))
    
    return jsonify({'success': True, 'message': 'Настройки сохранены'})


# ============================================================================
# FORM ENDPOINTS (для форм без JS)
# ============================================================================

@admin_bp.route('/users/<int:user_id>/block', methods=['POST'])
@admin_required
def block_user(user_id):
    """Block user"""
    run_async(db.block_user(user_id))
    init_data = get_init_data()
    return redirect(url_for('admin.users', search=user_id, message='Пользователь заблокирован', initData=init_data))


@admin_bp.route('/users/<int:user_id>/unblock', methods=['POST'])
@admin_required
def unblock_user(user_id):
    """Unblock user"""
    run_async(db.unblock_user(user_id))
    init_data = get_init_data()
    return redirect(url_for('admin.users', search=user_id, message='Пользователь разблокирован', initData=init_data))


@admin_bp.route('/users/<int:user_id>/give-stars', methods=['POST'])
@admin_required
def give_stars_to_user(user_id):
    """Give stars to user"""
    amount = request.form.get('amount', 0, type=int)
    init_data = get_init_data()
    if amount > 0:
        run_async(db.add_stars(user_id, amount))
        run_async(notify_user_stars(user_id, amount))
    return redirect(url_for('admin.users', search=user_id, message=f'Выдано {amount} звёзд', initData=init_data))


@admin_bp.route('/users/<int:user_id>/give-subscription', methods=['POST'])
@admin_required
def give_subscription_to_user(user_id):
    """Give subscription to user"""
    sub_type = request.form.get('sub_type', 'mini')
    days = request.form.get('days', 30, type=int)
    init_data = get_init_data()
    
    stars_limits = {'mini': 4000, 'standard': 9000, 'premium': 20000}
    stars = stars_limits.get(sub_type, 4000)
    
    run_async(db.create_subscription(user_id, sub_type, stars, days))
    run_async(notify_user_subscription(user_id, sub_type, days))
    
    return redirect(url_for('admin.users', search=user_id, message=f'Выдана подписка {sub_type}', initData=init_data))


@admin_bp.route('/subscriptions/give', methods=['POST'])
@admin_required
def give_subscription():
    """Give subscription to user"""
    user_id = request.form.get('user_id', 0, type=int)
    sub_type = request.form.get('sub_type', 'mini')
    days = request.form.get('days', 30, type=int)
    init_data = get_init_data()
    
    if user_id:
        stars_limits = {'mini': 4000, 'standard': 9000, 'premium': 20000}
        stars = stars_limits.get(sub_type, 4000)
        
        run_async(db.create_subscription(user_id, sub_type, stars, days))
        run_async(notify_user_subscription(user_id, sub_type, days))
        
        return redirect(url_for('admin.subscriptions', message=f'Подписка выдана', initData=init_data))
    
    return redirect(url_for('admin.subscriptions', message='Ошибка', message_type='error', initData=init_data))


@admin_bp.route('/tokens/give', methods=['POST'])
@admin_required
def give_tokens():
    """Give tokens to single user"""
    user_id = request.form.get('user_id', 0, type=int)
    amount = request.form.get('amount', 0, type=int)
    init_data = get_init_data()
    
    if user_id and amount > 0:
        run_async(db.add_stars(user_id, amount))
        run_async(notify_user_stars(user_id, amount))
        return redirect(url_for('admin.tokens', message=f'Выдано {amount} звёзд', initData=init_data))
    
    return redirect(url_for('admin.tokens', message='Ошибка', message_type='error', initData=init_data))


@admin_bp.route('/tokens/mass', methods=['POST'])
@admin_required
def give_tokens_mass():
    """Give tokens to all users"""
    amount = request.form.get('amount', 0, type=int)
    init_data = get_init_data()
    
    if amount > 0:
        users = run_async(db.get_all_users())
        for u in users:
            run_async(db.add_stars(u['user_id'], amount))
        
        return redirect(url_for('admin.tokens', message=f'Выдано {amount} звёзд {len(users)} пользователям', initData=init_data))
    
    return redirect(url_for('admin.tokens', message='Ошибка', message_type='error', initData=init_data))


@admin_bp.route('/tokens/no-sub', methods=['POST'])
@admin_required
def give_tokens_no_sub():
    """Give tokens to users without subscription"""
    amount = request.form.get('amount', 0, type=int)
    init_data = get_init_data()
    
    if amount > 0:
        users = run_async(get_users_without_subscription())
        for u in users:
            run_async(db.add_stars(u['user_id'], amount))
        
        return redirect(url_for('admin.tokens', message=f'Выдано {amount} звёзд {len(users)} пользователям', initData=init_data))
    
    return redirect(url_for('admin.tokens', message='Ошибка', message_type='error', initData=init_data))


@admin_bp.route('/tokens/subscribers', methods=['POST'])
@admin_required
def give_tokens_subscribers():
    """Give tokens to subscribers"""
    amount = request.form.get('amount', 0, type=int)
    sub_type = request.form.get('sub_type', 'all')
    init_data = get_init_data()
    
    if amount > 0:
        subs = run_async(db.get_active_subscriptions())
        count = 0
        for s in subs:
            if sub_type == 'all' or s.get('type') == sub_type:
                run_async(db.add_stars(s['user_id'], amount))
                count += 1
        
        return redirect(url_for('admin.tokens', message=f'Выдано {amount} звёзд {count} подписчикам', initData=init_data))
    
    return redirect(url_for('admin.tokens', message='Ошибка', message_type='error', initData=init_data))


@admin_bp.route('/broadcast/send', methods=['POST'])
@admin_required
def broadcast_send():
    """Send broadcast"""
    filter_type = request.form.get('filter', 'all')
    text = request.form.get('text', '')
    init_data = get_init_data()
    
    if not text:
        return redirect(url_for('admin.broadcast', message='Введите текст', message_type='error', initData=init_data))
    
    # Get recipients
    if filter_type == 'all':
        users = run_async(db.get_all_users())
    elif filter_type == 'sub':
        users = run_async(db.get_active_subscriptions())
    elif filter_type == 'nosub':
        users = run_async(get_users_without_subscription())
    else:
        users = run_async(get_subscribers_by_type_with_user(filter_type))
    
    success, errors = run_async(send_broadcast(users, text))
    
    return redirect(url_for('admin.broadcast', message=f'Отправлено: {success}, ошибок: {errors}', initData=init_data))


@admin_bp.route('/memory/<int:user_id>/clear/<bot_name>', methods=['POST'])
@admin_required
def clear_memory_bot(user_id, bot_name):
    """Clear memory for specific bot"""
    run_async(db.save_memory(user_id, bot_name, []))
    init_data = get_init_data()
    return redirect(url_for('admin.memory', user_id=user_id, message=f'Память {bot_name} очищена', initData=init_data))


@admin_bp.route('/memory/<int:user_id>/clear-all', methods=['POST'])
@admin_required
def clear_memory_all(user_id):
    """Clear all memory for user"""
    for bot_name in ['luca', 'silas', 'titus', 'voice']:
        run_async(db.save_memory(user_id, bot_name, []))
    init_data = get_init_data()
    return redirect(url_for('admin.memory', message='Вся память очищена', initData=init_data))


@admin_bp.route('/memory/<int:user_id>/delete/<bot_name>/<int:fact_idx>', methods=['POST'])
@admin_required
def delete_memory_fact(user_id, bot_name, fact_idx):
    """Delete single fact"""
    facts = run_async(db.get_memory(user_id, bot_name))
    if 0 <= fact_idx < len(facts):
        facts.pop(fact_idx)
        run_async(db.save_memory(user_id, bot_name, facts))
    init_data = get_init_data()
    return redirect(url_for('admin.memory', user_id=user_id, message='Факт удалён', initData=init_data))


@admin_bp.route('/memory/<int:user_id>/add/<bot_name>', methods=['POST'])
@admin_required
def add_memory_fact(user_id, bot_name):
    """Add new fact"""
    fact = request.form.get('fact', '').strip()
    init_data = get_init_data()
    if fact:
        facts = run_async(db.get_memory(user_id, bot_name))
        facts.append(fact)
        run_async(db.save_memory(user_id, bot_name, facts))
    return redirect(url_for('admin.memory', user_id=user_id, message='Факт добавлен', initData=init_data))


@admin_bp.route('/settings/subscriptions', methods=['POST'])
@admin_required
def save_subscriptions():
    """Save subscription pricing"""
    run_async(db.set_setting('mini_price', request.form.get('mini_price', '490')))
    run_async(db.set_setting('mini_stars', request.form.get('mini_stars', '4000')))
    run_async(db.set_setting('standard_price', request.form.get('standard_price', '990')))
    run_async(db.set_setting('standard_stars', request.form.get('standard_stars', '9000')))
    run_async(db.set_setting('premium_price', request.form.get('premium_price', '1990')))
    run_async(db.set_setting('premium_stars', request.form.get('premium_stars', '20000')))
    init_data = get_init_data()
    return redirect(url_for('admin.settings', message='Тарифы сохранены', initData=init_data))


@admin_bp.route('/settings/packages', methods=['POST'])
@admin_required
def save_packages():
    """Save star packages"""
    run_async(db.set_setting('pack1_stars', request.form.get('pack1_stars', '1000')))
    run_async(db.set_setting('pack1_price', request.form.get('pack1_price', '149')))
    run_async(db.set_setting('pack2_stars', request.form.get('pack2_stars', '2000')))
    run_async(db.set_setting('pack2_price', request.form.get('pack2_price', '249')))
    run_async(db.set_setting('pack3_stars', request.form.get('pack3_stars', '10000')))
    run_async(db.set_setting('pack3_price', request.form.get('pack3_price', '1190')))
    run_async(db.set_setting('pack4_stars', request.form.get('pack4_stars', '25000')))
    run_async(db.set_setting('pack4_price', request.form.get('pack4_price', '2790')))
    init_data = get_init_data()
    return redirect(url_for('admin.settings', message='Пакеты сохранены', initData=init_data))


@admin_bp.route('/settings/antiflood', methods=['POST'])
@admin_required
def save_antiflood():
    """Save anti-flood settings"""
    run_async(db.set_setting('spam_interval', request.form.get('spam_interval', '2')))
    run_async(db.set_setting('spam_max_rpm', request.form.get('spam_max_rpm', '8')))
    init_data = get_init_data()
    return redirect(url_for('admin.settings', message='Настройки сохранены', initData=init_data))


@admin_bp.route('/settings/notifications', methods=['POST'])
@admin_required
def save_notifications():
    """Save notification settings"""
    notify_new_sub = '1' if request.form.get('notify_new_sub') else '0'
    notify_payments = '1' if request.form.get('notify_payments') else '0'
    run_async(db.set_setting('notify_new_sub', notify_new_sub))
    run_async(db.set_setting('notify_payments', notify_payments))
    init_data = get_init_data()
    return redirect(url_for('admin.settings', message='Настройки сохранены', initData=init_data))


@admin_bp.route('/settings/bonus', methods=['POST'])
@admin_required
def save_bonus():
    """Save new user bonus"""
    run_async(db.set_setting('new_user_bonus', request.form.get('new_user_bonus', '250')))
    init_data = get_init_data()
    return redirect(url_for('admin.settings', message='Бонус сохранён', initData=init_data))


@admin_bp.route('/settings/referrals', methods=['POST'])
@admin_required
def save_referrals():
    """Save referral rewards"""
    run_async(db.set_setting('ref_mini', request.form.get('ref_mini', '1000')))
    run_async(db.set_setting('ref_standard', request.form.get('ref_standard', '2000')))
    run_async(db.set_setting('ref_premium', request.form.get('ref_premium', '4000')))
    init_data = get_init_data()
    return redirect(url_for('admin.settings', message='Награды сохранены', initData=init_data))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_stars_by_period(days: int):
    """Get star usage by day for charts"""
    result = []
    today = datetime.now().date()
    
    for i in range(days - 1, -1, -1):
        date = today - timedelta(days=i)
        result.append({
            'date': date.strftime('%d.%m'),
            'total': 0
        })
    
    return result


async def get_stars_by_function():
    """Get star usage by bot/function"""
    return {
        'Luca': 0,
        'Silas': 0,
        'Titus': 0,
        'Images': 0,
        'Voice': 0
    }


async def get_users_by_period(days: int):
    """Get new users by day"""
    result = []
    today = datetime.now().date()
    
    for i in range(days - 1, -1, -1):
        date = today - timedelta(days=i)
        result.append({
            'date': date.strftime('%d.%m'),
            'count': 0
        })
    
    return result


async def get_payments_by_period(days: int):
    """Get payments by day"""
    result = []
    today = datetime.now().date()
    
    for i in range(days - 1, -1, -1):
        date = today - timedelta(days=i)
        result.append({
            'date': date.strftime('%d.%m'),
            'amount': 0
        })
    
    return result


async def get_month_revenue():
    """Get total revenue for current month"""
    return 0


async def get_subscribers_by_type_with_user(sub_type: str):
    """Get subscribers with user info"""
    subs = await db.get_active_subscriptions()
    return [s for s in subs if s.get('type') == sub_type]


async def count_users_without_subscription():
    """Count users without active subscription"""
    total = await db.count_users()
    subs = await db.get_active_subscriptions()
    return total - len(subs)


async def get_users_without_subscription():
    """Get users without subscription"""
    all_users = await db.get_all_users()
    subs = await db.get_active_subscriptions()
    sub_ids = {s['user_id'] for s in subs}
    return [u for u in all_users if u['user_id'] not in sub_ids]


async def get_users_with_memory_counts(limit: int, offset: int):
    """Get users with memory and their counts"""
    users = await db.get_all_users()
    result = []
    
    for u in users:
        memory_counts = {}
        for bot in ['luca', 'silas', 'titus', 'voice']:
            facts = await db.get_memory(u['user_id'], bot)
            if facts:
                memory_counts[bot] = len(facts)
        
        if memory_counts:
            result.append({
                'user_id': u['user_id'],
                'username': u.get('username'),
                'memory_counts': memory_counts
            })
    
    return result[offset:offset + limit]


async def get_finance_stats():
    """Get finance statistics"""
    async with db.get_connection() as conn:
        # Total revenue (all completed payments)
        total_revenue = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM payment_transactions WHERE status = 'completed'"
        ) or 0
        
        # Month revenue (last 30 days)
        month_revenue = await conn.fetchval(
            """SELECT COALESCE(SUM(amount), 0) FROM payment_transactions 
               WHERE status = 'completed' AND created_at >= NOW() - INTERVAL '30 days'"""
        ) or 0
        
        # Week revenue (last 7 days)
        week_revenue = await conn.fetchval(
            """SELECT COALESCE(SUM(amount), 0) FROM payment_transactions 
               WHERE status = 'completed' AND created_at >= NOW() - INTERVAL '7 days'"""
        ) or 0
        
        # Total payments count
        total_payments = await conn.fetchval(
            "SELECT COUNT(*) FROM payment_transactions WHERE status = 'completed'"
        ) or 0
        
        # Subscriptions by type (assuming type contains subscription name: 'subscription_mini', etc.)
        mini_data = await conn.fetchrow(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as revenue 
               FROM payment_transactions 
               WHERE status = 'completed' AND type LIKE '%mini%'"""
        )
        mini_count = mini_data['cnt'] or 0
        mini_revenue = mini_data['revenue'] or 0
        
        standard_data = await conn.fetchrow(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as revenue 
               FROM payment_transactions 
               WHERE status = 'completed' AND type LIKE '%standard%'"""
        )
        standard_count = standard_data['cnt'] or 0
        standard_revenue = standard_data['revenue'] or 0
        
        premium_data = await conn.fetchrow(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as revenue 
               FROM payment_transactions 
               WHERE status = 'completed' AND type LIKE '%premium%'"""
        )
        premium_count = premium_data['cnt'] or 0
        premium_revenue = premium_data['revenue'] or 0
        
        # Stars packages
        stars_data = await conn.fetchrow(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as revenue 
               FROM payment_transactions 
               WHERE status = 'completed' AND type LIKE '%stars%'"""
        )
        stars_count = stars_data['cnt'] or 0
        stars_revenue = stars_data['revenue'] or 0
        
        return {
            'total_revenue': float(total_revenue),
            'month_revenue': float(month_revenue),
            'week_revenue': float(week_revenue),
            'total_payments': int(total_payments),
            'mini_revenue': float(mini_revenue),
            'mini_count': int(mini_count),
            'standard_revenue': float(standard_revenue),
            'standard_count': int(standard_count),
            'premium_revenue': float(premium_revenue),
            'premium_count': int(premium_count),
            'stars_revenue': float(stars_revenue),
            'stars_count': int(stars_count)
        }


async def get_payment_transactions(limit: int, offset: int, status: str):
    """Get payment transactions"""
    async with db.get_connection() as conn:
        if status == 'all':
            rows = await conn.fetch(
                "SELECT * FROM payment_transactions ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM payment_transactions WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                status, limit, offset
            )
        return [dict(r) for r in rows]


async def count_payment_transactions(status: str):
    """Count payment transactions"""
    async with db.get_connection() as conn:
        if status == 'all':
            return await conn.fetchval("SELECT COUNT(*) FROM payment_transactions")
        else:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM payment_transactions WHERE status = $1",
                status
            )


async def get_all_settings():
    """Get all settings as dict"""
    settings = {}
    keys = [
        'mini_price', 'mini_stars', 'standard_price', 'standard_stars',
        'premium_price', 'premium_stars', 'pack1_stars', 'pack1_price',
        'pack2_stars', 'pack2_price', 'pack3_stars', 'pack3_price',
        'pack4_stars', 'pack4_price', 'spam_interval', 'spam_max_rpm',
        'notify_new_sub', 'notify_payments', 'new_user_bonus',
        'ref_mini', 'ref_standard', 'ref_premium'
    ]
    
    for key in keys:
        value = await db.get_setting(key)
        if value:
            if key in ['notify_new_sub', 'notify_payments']:
                settings[key] = value == '1'
            else:
                try:
                    settings[key] = int(value)
                except:
                    settings[key] = value
    
    return settings


async def notify_user_stars(user_id: int, amount: int):
    """Notify user about received stars"""
    try:
        from loader import bot
        await bot.send_message(
            user_id,
            f"🎉 <b>Вам начислены звёзды!</b>\n\n"
            f"💰 Количество: <b>{amount:,}</b> ⭐\n\n"
            f"Спасибо за использование бота! 🙏"
        )
    except:
        pass


async def notify_user_subscription(user_id: int, sub_type: str, days: int):
    """Notify user about subscription"""
    try:
        from loader import bot
        type_names = {'mini': '💎 Mini', 'standard': '👑 Standard', 'premium': '✨ Premium'}
        await bot.send_message(
            user_id,
            f"🎉 <b>Вам выдана подписка!</b>\n\n"
            f"⭐ Тариф: {type_names.get(sub_type, sub_type)}\n"
            f"📅 Срок: {days} дней\n\n"
            f"Приятного использования! 🙏"
        )
    except:
        pass


async def notify_admin_new_subscription(user_id: int, sub_type: str, amount: float):
    """Notify admin about new subscription"""
    try:
        notify = await db.get_setting('notify_new_sub')
        if notify != '1':
            return
        
        from loader import bot
        type_names = {'mini': '💎 Mini', 'standard': '👑 Standard', 'premium': '✨ Premium'}
        user = await db.get_user(user_id)
        username = f"@{user['username']}" if user and user.get('username') else str(user_id)
        
        await bot.send_message(
            ADMIN_IDS[0],
            f"🎉 <b>Новая подписка!</b>\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"⭐ Тариф: {type_names.get(sub_type, sub_type)}\n"
            f"💰 Сумма: {amount}₽"
        )
    except:
        pass


async def send_broadcast(users: list, text: str):
    """Send broadcast to users"""
    from loader import bot
    
    success = 0
    errors = 0
    
    for u in users:
        user_id = u.get('user_id', u) if isinstance(u, dict) else u
        try:
            await bot.send_message(user_id, text, parse_mode='HTML')
            success += 1
        except:
            errors += 1
    
    return success, errors


def get_uptime():
    """Get server uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}д {hours}ч {minutes}м"
        elif hours > 0:
            return f"{hours}ч {minutes}м"
        else:
            return f"{minutes}м"
    except:
        return "—"
