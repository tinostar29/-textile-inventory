import hashlib
import secrets
from functools import wraps
from flask import session, jsonify, request
from database import get_db

def generate_salt():
    return secrets.token_hex(16)

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

def verify_password(password: str, salt: str, password_hash: str) -> bool:
    return hash_password(password, salt) == password_hash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Authentication required. Please log in.'}), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Authentication required.'}), 401
            user_role = session.get('role', 'staff')
            if user_role not in allowed_roles:
                return jsonify({'success': False, 'message': f'Access denied. Required role: {", ".join(allowed_roles)}'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_activity(user_id, username, action, module, record_id, details):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO activity_logs (user_id, username, action, module, record_id, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, action, module, str(record_id) if record_id else None, details)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
    finally:
        conn.close()
