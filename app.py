import os
from datetime import datetime
from flask import Flask, request, jsonify, session, send_from_directory, send_file
from database import get_db, init_db, DB_PATH
from auth import (
    hash_password, verify_password, generate_salt,
    login_required, role_required, log_activity
)
import stock_service as ss
import reports_service as rs
from seed_data import seed_all

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'textile-secret-key-prod-2026')

# Initialize DB on start
try:
    init_db()
except Exception as e:
    print(f"Warning initializing DB: {e}")

# --- Serve Static UI ---
@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

# --- Authentication APIs ---

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required.'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
    user = cur.fetchone()
    conn.close()

    if not user or not verify_password(password, user['salt'], user['password_hash']):
        return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['full_name'] = user['full_name']

    log_activity(user['id'], user['username'], 'LOGIN', 'auth', user['id'], f"User '{username}' logged in.")

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'full_name': user['full_name'],
            'role': user['role']
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    user_id = session.get('user_id')
    username = session.get('username')
    if user_id:
        log_activity(user_id, username, 'LOGOUT', 'auth', user_id, f"User '{username}' logged out.")
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 200
    return jsonify({
        'authenticated': True,
        'user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role')
        }
    })

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.get_json() or {}
    current_password = (data.get('current_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()
    confirm_password = (data.get('confirm_password') or '').strip()

    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Current password and new password are required.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New password and confirmation do not match.'}), 400

    if len(new_password) < 4:
        return jsonify({'success': False, 'message': 'New password must be at least 4 characters long.'}), 400

    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    if not user or not verify_password(current_password, user['salt'], user['password_hash']):
        conn.close()
        return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 400

    new_salt = generate_salt()
    new_hash = hash_password(new_password, new_salt)
    cur.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
    conn.commit()
    conn.close()

    log_activity(user_id, session.get('username'), 'PASSWORD_CHANGE', 'auth', user_id, 'User changed their password.')
    return jsonify({'success': True, 'message': 'Password changed successfully!'})

# --- Dashboard APIs ---

@app.route('/api/dashboard', methods=['GET'])
@login_required
def api_dashboard():
    try:
        data = ss.get_dashboard_summary()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Yarn Purchases APIs ---

@app.route('/api/purchases', methods=['GET'])
@login_required
def api_get_purchases():
    conn = get_db()
    cur = conn.cursor()
    search = request.args.get('search')
    supplier_id = request.args.get('supplier_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = """
        SELECT p.*, s.name as supplier_name, u.full_name as created_by_name
        FROM yarn_purchases p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        LEFT JOIN users u ON p.created_by = u.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.yarn_type LIKE ? OR p.yarn_colour LIKE ? OR p.invoice_number LIKE ? OR s.name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    if supplier_id:
        query += " AND p.supplier_id = ?"
        params.append(supplier_id)
    if start_date:
        query += " AND p.purchase_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.purchase_date <= ?"
        params.append(end_date)

    query += " ORDER BY p.purchase_date DESC, p.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': rows})

@app.route('/api/purchases', methods=['POST'])
@login_required
def api_add_purchase():
    data = request.get_json() or {}
    try:
        pid = ss.record_yarn_purchase(
            data,
            user_id=session.get('user_id'),
            username=session.get('username')
        )
        log_activity(session.get('user_id'), session.get('username'), 'CREATE', 'purchases', pid, 
                     f"Recorded yarn purchase: {data.get('weight_kg')} KG of {data.get('yarn_type')} ({data.get('yarn_colour')})")
        return jsonify({'success': True, 'message': 'Yarn purchase recorded and raw stock updated successfully!', 'id': pid})
    except (ss.ValidationError, ss.InsufficientStockError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"Internal error: {str(e)}"}), 500

@app.route('/api/purchases/<int:pid>', methods=['DELETE'])
@login_required
def api_cancel_purchase(pid):
    try:
        ss.cancel_yarn_purchase(pid, user_id=session.get('user_id'), username=session.get('username'))
        log_activity(session.get('user_id'), session.get('username'), 'CANCEL', 'purchases', pid, f"Cancelled yarn purchase #{pid}")
        return jsonify({'success': True, 'message': 'Purchase cancelled and raw yarn stock adjusted successfully!'})
    except (ss.ValidationError, ss.InsufficientStockError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Raw Yarn Stock APIs ---

@app.route('/api/raw-stock', methods=['GET'])
@login_required
def api_get_raw_stock():
    search = request.args.get('search')
    data = ss.get_raw_yarn_stock_summary(search=search)
    return jsonify({'success': True, 'data': data})

# --- Production APIs ---

@app.route('/api/productions', methods=['GET'])
@login_required
def api_get_productions():
    conn = get_db()
    cur = conn.cursor()
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = """
        SELECT p.*, u.full_name as created_by_name
        FROM productions p
        LEFT JOIN users u ON p.created_by = u.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.batch_number LIKE ? OR p.machine_name LIKE ? OR p.operator_name LIKE ? OR p.input_yarn_type LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    if start_date:
        query += " AND p.production_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.production_date <= ?"
        params.append(end_date)

    query += " ORDER BY p.production_date DESC, p.id DESC"
    cur.execute(query, params)
    prods = [dict(r) for r in cur.fetchall()]

    # Fetch items for each production
    for p in prods:
        cur.execute("SELECT * FROM production_items WHERE production_id = ?", (p['id'],))
        p['items'] = [dict(it) for it in cur.fetchall()]

    conn.close()
    return jsonify({'success': True, 'data': prods})

@app.route('/api/productions', methods=['POST'])
@login_required
def api_add_production():
    data = request.get_json() or {}
    try:
        pid, batch_no = ss.record_production(
            data,
            user_id=session.get('user_id'),
            username=session.get('username')
        )
        log_activity(session.get('user_id'), session.get('username'), 'CREATE', 'production', pid, 
                     f"Recorded production batch {batch_no}: Input {data.get('input_weight_kg')} KG, Output {data.get('total_finished_weight_kg')} KG, Wastage {data.get('wastage_weight_kg')} KG")
        return jsonify({'success': True, 'message': f'Production batch {batch_no} recorded! Raw yarn deducted and finished goods added.', 'id': pid, 'batch_number': batch_no})
    except (ss.ValidationError, ss.InsufficientStockError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"Error: {str(e)}"}), 500

@app.route('/api/productions/<int:pid>', methods=['DELETE'])
@login_required
def api_cancel_production(pid):
    try:
        ss.cancel_production(pid, user_id=session.get('user_id'), username=session.get('username'))
        log_activity(session.get('user_id'), session.get('username'), 'CANCEL', 'production', pid, f"Cancelled production batch #{pid}")
        return jsonify({'success': True, 'message': 'Production batch cancelled. Raw yarn returned and finished stock deducted!'})
    except (ss.ValidationError, ss.InsufficientStockError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Finished Goods Stock APIs ---

@app.route('/api/finished-stock', methods=['GET'])
@login_required
def api_get_finished_stock():
    product_type = request.args.get('product_type') # 'Tape', 'Rope', 'Tipping'
    search = request.args.get('search')
    data = ss.get_finished_goods_summary(product_type=product_type, search=search)
    return jsonify({'success': True, 'data': data})

@app.route('/api/finished-stock/batches', methods=['GET'])
@login_required
def api_get_finished_stock_batches():
    conn = get_db()
    cur = conn.cursor()
    product_type = request.args.get('product_type')
    
    query = """
        SELECT pi.id, pi.product_type, pi.colour, pi.weight_kg as produced_kg,
               p.batch_number, p.production_date, p.machine_name, p.operator_name,
               p.status
        FROM production_items pi
        JOIN productions p ON pi.production_id = p.id
        WHERE p.status = 'ACTIVE'
    """
    params = []
    if product_type:
        query += " AND pi.product_type = ?"
        params.append(product_type)
    query += " ORDER BY p.production_date DESC, pi.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': rows})

# --- Sales APIs ---

@app.route('/api/sales', methods=['GET'])
@login_required
def api_get_sales():
    conn = get_db()
    cur = conn.cursor()
    search = request.args.get('search')
    customer_id = request.args.get('customer_id')
    product_type = request.args.get('product_type')
    payment_status = request.args.get('payment_status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = """
        SELECT s.*, c.name as customer_name, c.phone as customer_phone, u.full_name as created_by_name
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        LEFT JOIN users u ON s.created_by = u.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (s.invoice_number LIKE ? OR s.product_colour LIKE ? OR c.name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if customer_id:
        query += " AND s.customer_id = ?"
        params.append(customer_id)
    if product_type:
        query += " AND s.product_type = ?"
        params.append(product_type)
    if payment_status:
        query += " AND s.payment_status = ?"
        params.append(payment_status)
    if start_date:
        query += " AND s.sale_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.sale_date <= ?"
        params.append(end_date)

    query += " ORDER BY s.sale_date DESC, s.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': rows})

@app.route('/api/sales', methods=['POST'])
@login_required
def api_add_sale():
    data = request.get_json() or {}
    try:
        sid, inv_no = ss.record_sale(
            data,
            user_id=session.get('user_id'),
            username=session.get('username')
        )
        log_activity(session.get('user_id'), session.get('username'), 'CREATE', 'sales', sid,
                     f"Recorded sale {inv_no}: {data.get('quantity_kg')} KG of {data.get('product_type')} ({data.get('product_colour')}) for ₹{data.get('total_amount')}")
        return jsonify({'success': True, 'message': f'Sale recorded with Invoice {inv_no}! Finished goods stock updated.', 'id': sid, 'invoice_number': inv_no})
    except (ss.ValidationError, ss.InsufficientStockError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"Error: {str(e)}"}), 500

@app.route('/api/sales/<int:sid>', methods=['DELETE'])
@login_required
def api_cancel_sale(sid):
    try:
        ss.cancel_sale(sid, user_id=session.get('user_id'), username=session.get('username'))
        log_activity(session.get('user_id'), session.get('username'), 'CANCEL', 'sales', sid, f"Cancelled sale #{sid}")
        return jsonify({'success': True, 'message': 'Sale cancelled. Finished goods stock restored!'})
    except (ss.ValidationError, ss.InsufficientStockError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sales/<int:sid>/payment', methods=['POST'])
@login_required
def api_update_sale_payment(sid):
    data = request.get_json() or {}
    payment_status = data.get('payment_status')
    paid_amount = float(data.get('paid_amount') or 0.0)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT total_amount FROM sales WHERE id = ?", (sid,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'Sale not found.'}), 404

    total_amount = row['total_amount']
    if payment_status == 'Paid':
        paid_amount = total_amount
    balance_amount = max(0.0, total_amount - paid_amount)

    cur.execute(
        "UPDATE sales SET payment_status = ?, paid_amount = ?, balance_amount = ? WHERE id = ?",
        (payment_status, paid_amount, balance_amount, sid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Payment status updated successfully.'})

@app.route('/api/sales/<int:sid>/invoice', methods=['GET'])
@login_required
def api_get_invoice(sid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, c.name as customer_name, c.contact_person, c.phone as customer_phone,
               c.email as customer_email, c.address as customer_address, c.gstin as customer_gstin
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.id = ?
    """, (sid,))
    sale = cur.fetchone()
    if not sale:
        conn.close()
        return jsonify({'success': False, 'message': 'Invoice not found.'}), 404

    # Settings
    cur.execute("SELECT key, value FROM system_settings")
    settings = {r['key']: r['value'] for r in cur.fetchall()}
    conn.close()

    return jsonify({
        'success': True,
        'invoice': dict(sale),
        'company': settings
    })

# --- Customers & Suppliers APIs ---

@app.route('/api/customers', methods=['GET'])
@login_required
def api_get_customers():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*,
               COALESCE((SELECT SUM(quantity_kg) FROM sales WHERE customer_id = c.id AND status = 'ACTIVE'), 0.0) as total_bought_kg,
               COALESCE((SELECT SUM(total_amount) FROM sales WHERE customer_id = c.id AND status = 'ACTIVE'), 0.0) as total_sales_val,
               COALESCE((SELECT SUM(balance_amount) FROM sales WHERE customer_id = c.id AND status = 'ACTIVE'), 0.0) as outstanding_balance
        FROM customers c
        ORDER BY c.name ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': rows})

@app.route('/api/customers', methods=['POST'])
@login_required
def api_add_customer():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Customer name is required.'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO customers (name, contact_person, phone, email, address, gstin, credit_limit, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, data.get('contact_person'), data.get('phone'), data.get('email'),
         data.get('address'), data.get('gstin'), data.get('credit_limit', 0), data.get('notes'))
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Customer added successfully.', 'id': cid})

@app.route('/api/customers/<int:cid>', methods=['PUT'])
@login_required
def api_edit_customer(cid):
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """UPDATE customers SET name=?, contact_person=?, phone=?, email=?, address=?, gstin=?, credit_limit=?, notes=?
           WHERE id = ?""",
        (data.get('name'), data.get('contact_person'), data.get('phone'), data.get('email'),
         data.get('address'), data.get('gstin'), data.get('credit_limit', 0), data.get('notes'), cid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Customer updated.'})

@app.route('/api/suppliers', methods=['GET'])
@login_required
def api_get_suppliers():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*,
               COALESCE((SELECT SUM(weight_kg) FROM yarn_purchases WHERE supplier_id = s.id AND status = 'ACTIVE'), 0.0) as total_supplied_kg,
               COALESCE((SELECT SUM(total_amount) FROM yarn_purchases WHERE supplier_id = s.id AND status = 'ACTIVE'), 0.0) as total_purchase_val
        FROM suppliers s
        ORDER BY s.name ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': rows})

@app.route('/api/suppliers', methods=['POST'])
@login_required
def api_add_supplier():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Supplier name is required.'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO suppliers (name, contact_person, phone, email, address, gstin, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, data.get('contact_person'), data.get('phone'), data.get('email'),
         data.get('address'), data.get('gstin'), data.get('notes'))
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Supplier added successfully.', 'id': sid})

@app.route('/api/suppliers/<int:sid>', methods=['PUT'])
@login_required
def api_edit_supplier(sid):
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """UPDATE suppliers SET name=?, contact_person=?, phone=?, email=?, address=?, gstin=?, notes=?
           WHERE id = ?""",
        (data.get('name'), data.get('contact_person'), data.get('phone'), data.get('email'),
         data.get('address'), data.get('gstin'), data.get('notes'), sid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Supplier updated.'})

# --- Masters & System Config APIs ---

@app.route('/api/masters', methods=['GET'])
@login_required
def api_get_masters():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM machines WHERE is_active = 1 ORDER BY name ASC")
    machines = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM yarn_masters ORDER BY name ASC")
    yarns = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM colour_masters ORDER BY name ASC")
    colours = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT key, value FROM system_settings")
    settings = {r['key']: r['value'] for r in cur.fetchall()}

    conn.close()
    return jsonify({
        'success': True,
        'machines': machines,
        'yarns': yarns,
        'colours': colours,
        'settings': settings
    })

@app.route('/api/masters/<category>', methods=['POST'])
@login_required
@role_required(['admin', 'manager'])
def api_add_master(category):
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Name is required.'}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        if category == 'machine':
            cur.execute("INSERT INTO machines (name, code, machine_type) VALUES (?, ?, ?)",
                        (name, data.get('code'), data.get('machine_type')))
        elif category == 'yarn':
            cur.execute("INSERT INTO yarn_masters (name, category, standard_count) VALUES (?, ?, ?)",
                        (name, data.get('category'), data.get('standard_count')))
        elif category == 'colour':
            cur.execute("INSERT INTO colour_masters (name, hex_code) VALUES (?, ?)",
                        (name, data.get('hex_code') or '#000000'))
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid category.'}), 400

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'{category.capitalize()} added successfully.'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/settings', methods=['POST'])
@login_required
@role_required(['admin'])
def api_update_settings():
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    for k, v in data.items():
        cur.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Settings saved successfully.'})

# --- User Management APIs ---

@app.route('/api/users', methods=['GET'])
@login_required
@role_required(['admin'])
def api_get_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id ASC")
    users = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': users})

@app.route('/api/users', methods=['POST'])
@login_required
@role_required(['admin'])
def api_add_user():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    role = data.get('role', 'staff')

    if not username or not password or not full_name:
        return jsonify({'success': False, 'message': 'Username, password and full name are required.'}), 400

    salt = generate_salt()
    phash = hash_password(password, salt)

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role) VALUES (?, ?, ?, ?, ?)",
            (username, phash, salt, full_name, role)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f"User '{username}' created."})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f"Username already exists or error: {str(e)}"}), 400

@app.route('/api/users/<int:uid>', methods=['PUT'])
@login_required
@role_required(['admin'])
def api_edit_user(uid):
    data = request.get_json() or {}
    full_name = data.get('full_name')
    role = data.get('role')
    is_active = data.get('is_active', 1)
    new_password = data.get('new_password')

    conn = get_db()
    cur = conn.cursor()
    if new_password:
        salt = generate_salt()
        phash = hash_password(new_password, salt)
        cur.execute("UPDATE users SET full_name=?, role=?, is_active=?, password_hash=?, salt=? WHERE id=?",
                    (full_name, role, is_active, phash, salt, uid))
    else:
        cur.execute("UPDATE users SET full_name=?, role=?, is_active=? WHERE id=?",
                    (full_name, role, is_active, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'User updated.'})

# --- Activity Log API ---

@app.route('/api/activity-logs', methods=['GET'])
@login_required
def api_get_activity_logs():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 50")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': rows})

# --- System Reset & Backup APIs ---

@app.route('/api/system/clear-all-data', methods=['POST'])
@login_required
@role_required(['admin'])
def api_clear_all_data():
    conn = get_db()
    cur = conn.cursor()
    try:
        # Clear all transactional data and ledgers
        cur.execute("DELETE FROM stock_ledger")
        cur.execute("DELETE FROM sales")
        cur.execute("DELETE FROM production_items")
        cur.execute("DELETE FROM productions")
        cur.execute("DELETE FROM yarn_purchases")
        cur.execute("DELETE FROM activity_logs")

        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('stock_ledger', 'sales', 'production_items', 'productions', 'yarn_purchases', 'activity_logs')")
        except Exception:
            pass

        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), session.get('username'), 'CLEAR_DATA', 'system', None, 'Admin cleared all transactions and reset stock to zero.')
        return jsonify({'success': True, 'message': 'All inventory transactions, purchases, production batches, and sales have been cleared. All stock balances are now reset to 0.000 KG.'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Error clearing data: {str(e)}'}), 500

@app.route('/api/system/reset-demo', methods=['POST'])
@login_required
@role_required(['admin'])
def api_reset_demo():
    try:
        seed_all()
        log_activity(session.get('user_id'), session.get('username'), 'RESET', 'system', None, 'Reset system with realistic sample demo data')
        return jsonify({'success': True, 'message': 'Database re-seeded with realistic textile factory data!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/system/backup', methods=['GET'])
@login_required
@role_required(['admin'])
def api_download_backup():
    if os.path.exists(DB_PATH):
        return send_file(DB_PATH, as_attachment=True, download_name=f"textile_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    return jsonify({'success': False, 'message': 'Database file not found.'}), 404

# --- Reports & Export APIs ---

@app.route('/api/reports/export/excel', methods=['GET'])
@login_required
def api_export_excel():
    report_type = request.args.get('type', 'raw_stock')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if report_type == 'raw_stock':
        stream = rs.export_raw_yarn_stock_excel()
        filename = f"Raw_Yarn_Stock_{datetime.now().strftime('%Y%m%d')}.xlsx"
    elif report_type == 'finished_stock':
        ptype = request.args.get('product_type')
        stream = rs.export_finished_goods_excel(product_type=ptype)
        filename = f"Finished_{ptype or 'Goods'}_Stock_{datetime.now().strftime('%Y%m%d')}.xlsx"
    elif report_type == 'purchases':
        stream = rs.export_purchases_excel(start_date, end_date)
        filename = f"Yarn_Purchases_{datetime.now().strftime('%Y%m%d')}.xlsx"
    elif report_type == 'production':
        stream = rs.export_production_excel(start_date, end_date)
        filename = f"Production_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    elif report_type == 'sales':
        stream = rs.export_sales_excel(start_date, end_date)
        filename = f"Sales_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    else:
        return jsonify({'success': False, 'message': 'Invalid report type.'}), 400

    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/reports/export/pdf', methods=['GET'])
@login_required
def api_export_pdf():
    report_type = request.args.get('type', 'raw_stock')
    
    if report_type == 'raw_stock':
        stocks = ss.get_raw_yarn_stock_summary()
        headers = ["Yarn Type", "Colour", "Purchased (KG)", "Used (KG)", "Remaining (KG)", "Avg ₹/KG", "Status"]
        data = [[s['yarn_type'], s['yarn_colour'], f"{s['purchased_kg']:.3f}", f"{s['used_kg']:.3f}", f"{s['remaining_kg']:.3f}", f"₹{s['avg_price_per_kg']:.2f}", s['status']] for s in stocks]
        stream = rs.export_generic_pdf("Raw Yarn Inventory Report", "Live Raw Material Stock Balance", headers, data)
        filename = "Raw_Yarn_Stock_Report.pdf"

    elif report_type == 'finished_stock':
        stocks = ss.get_finished_goods_summary()
        headers = ["Product", "Colour", "Batches", "Produced (KG)", "Sold (KG)", "Available (KG)", "Status"]
        data = [[s['product_type'], s['colour'], str(s['batch_count']), f"{s['produced_kg']:.3f}", f"{s['sold_kg']:.3f}", f"{s['available_kg']:.3f}", s['status']] for s in stocks]
        stream = rs.export_generic_pdf("Finished Goods Stock Report", "Tape, Rope & Tipping Stock Balance", headers, data)
        filename = "Finished_Goods_Stock_Report.pdf"

    elif report_type == 'purchases':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT p.*, s.name as supplier FROM yarn_purchases p LEFT JOIN suppliers s ON p.supplier_id = s.id WHERE p.status='ACTIVE' ORDER BY purchase_date DESC LIMIT 50")
        rows = cur.fetchall()
        conn.close()
        headers = ["Date", "Invoice #", "Supplier", "Yarn Type", "Colour", "KG", "Price/KG", "Total (₹)"]
        data = [[r['purchase_date'], r['invoice_number'] or '-', r['supplier'] or '-', r['yarn_type'], r['yarn_colour'], f"{r['weight_kg']:.3f}", f"₹{r['price_per_kg']:.2f}", f"₹{r['total_amount']:.2f}"] for r in rows]
        stream = rs.export_generic_pdf("Yarn Purchases Report", "Recent Yarn Purchases", headers, data)
        filename = "Yarn_Purchases_Report.pdf"

    elif report_type == 'sales':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT s.*, c.name as customer FROM sales s LEFT JOIN customers c ON s.customer_id = c.id WHERE s.status='ACTIVE' ORDER BY sale_date DESC LIMIT 50")
        rows = cur.fetchall()
        conn.close()
        headers = ["Date", "Invoice #", "Customer", "Product", "Colour", "KG", "Price/KG", "Total (₹)", "Status"]
        data = [[r['sale_date'], r['invoice_number'], r['customer'] or '-', r['product_type'], r['product_colour'], f"{r['quantity_kg']:.3f}", f"₹{r['price_per_kg']:.2f}", f"₹{r['total_amount']:.2f}", r['payment_status']] for r in rows]
        stream = rs.export_generic_pdf("Finished Goods Sales Report", "Recent Sales Invoices", headers, data)
        filename = "Sales_Report.pdf"

    elif report_type == 'production':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM productions WHERE status='ACTIVE' ORDER BY production_date DESC LIMIT 50")
        rows = cur.fetchall()
        conn.close()
        headers = ["Batch #", "Date", "Machine", "Input Yarn", "Colour", "Input (KG)", "Finished (KG)", "Wastage (KG)"]
        data = [[r['batch_number'], r['production_date'], r['machine_name'], r['input_yarn_type'], r['input_yarn_colour'], f"{r['input_weight_kg']:.3f}", f"{r['total_finished_weight_kg']:.3f}", f"{r['wastage_weight_kg']:.3f}"] for r in rows]
        stream = rs.export_generic_pdf("Production & Twisting Report", "Recent Production Batches & Wastage", headers, data)
        filename = "Production_Report.pdf"

    else:
        return jsonify({'success': False, 'message': 'Unknown report type.'}), 400

    return send_file(stream, mimetype="application/pdf", as_attachment=True, download_name=filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Textile Manufacturing Inventory System running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
