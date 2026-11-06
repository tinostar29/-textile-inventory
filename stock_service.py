import sqlite3
from datetime import datetime
from database import get_db

class InsufficientStockError(Exception):
    pass

class ValidationError(Exception):
    pass

def round_kg(val):
    return round(float(val or 0.0), 3)

def round_curr(val):
    return round(float(val or 0.0), 2)

# --- Raw Yarn Stock Calculation ---

def get_raw_yarn_stock_for_type_colour(conn, yarn_type, yarn_colour):
    """Returns (purchased_kg, used_kg, remaining_kg) for a specific yarn type & colour."""
    cur = conn.cursor()
    # Total purchased
    cur.execute(
        """SELECT COALESCE(SUM(weight_kg), 0.0) FROM yarn_purchases
           WHERE yarn_type = ? AND yarn_colour = ? AND status = 'ACTIVE'""",
        (yarn_type, yarn_colour)
    )
    purchased = round_kg(cur.fetchone()[0])

    # Total used in production
    cur.execute(
        """SELECT COALESCE(SUM(input_weight_kg), 0.0) FROM productions
           WHERE input_yarn_type = ? AND input_yarn_colour = ? AND status = 'ACTIVE'""",
        (yarn_type, yarn_colour)
    )
    used = round_kg(cur.fetchone()[0])

    remaining = round_kg(purchased - used)
    return purchased, used, remaining

def get_raw_yarn_stock_summary(search=None):
    """Returns grouped list of all raw yarn stocks with current status."""
    conn = get_db()
    cur = conn.cursor()

    query = """
    WITH purchases_summary AS (
        SELECT yarn_type, yarn_colour, 
               COUNT(id) as purchase_count,
               SUM(weight_kg) as total_purchased_kg,
               SUM(total_amount) as total_spent,
               MAX(purchase_date) as last_purchase_date
        FROM yarn_purchases
        WHERE status = 'ACTIVE'
        GROUP BY yarn_type, yarn_colour
    ),
    production_summary AS (
        SELECT input_yarn_type as yarn_type, input_yarn_colour as yarn_colour,
               SUM(input_weight_kg) as total_used_kg,
               COUNT(id) as batch_count,
               MAX(production_date) as last_used_date
        FROM productions
        WHERE status = 'ACTIVE'
        GROUP BY input_yarn_type, input_yarn_colour
    )
    SELECT 
        p.yarn_type,
        p.yarn_colour,
        p.purchase_count,
        ROUND(p.total_purchased_kg, 3) as purchased_kg,
        ROUND(COALESCE(pr.total_used_kg, 0.0), 3) as used_kg,
        ROUND(p.total_purchased_kg - COALESCE(pr.total_used_kg, 0.0), 3) as remaining_kg,
        ROUND(p.total_spent / NULLIF(p.total_purchased_kg, 0), 2) as avg_price_per_kg,
        p.last_purchase_date,
        pr.last_used_date
    FROM purchases_summary p
    LEFT JOIN production_summary pr 
        ON p.yarn_type = pr.yarn_type AND p.yarn_colour = pr.yarn_colour
    """

    params = []
    if search:
        query += " WHERE p.yarn_type LIKE ? OR p.yarn_colour LIKE ?"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY p.yarn_type, p.yarn_colour"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        remaining = round_kg(r['remaining_kg'])
        status = 'Normal'
        if remaining <= 0:
            status = 'Out of Stock'
        elif remaining < 25.0: # threshold
            status = 'Low Stock'

        result.append({
            'yarn_type': r['yarn_type'],
            'yarn_colour': r['yarn_colour'],
            'purchase_count': r['purchase_count'],
            'purchased_kg': round_kg(r['purchased_kg']),
            'used_kg': round_kg(r['used_kg']),
            'remaining_kg': remaining,
            'avg_price_per_kg': round_curr(r['avg_price_per_kg']),
            'last_purchase_date': r['last_purchase_date'],
            'last_used_date': r['last_used_date'],
            'status': status
        })
    return result

# --- Finished Goods Stock Calculation ---

def get_finished_stock_for_item(conn, product_type, colour):
    """Returns (produced_kg, sold_kg, available_kg) for a finished product & colour."""
    cur = conn.cursor()
    # Total produced
    cur.execute(
        """SELECT COALESCE(SUM(pi.weight_kg), 0.0) 
           FROM production_items pi
           JOIN productions p ON pi.production_id = p.id
           WHERE pi.product_type = ? AND pi.colour = ? AND p.status = 'ACTIVE'""",
        (product_type, colour)
    )
    produced = round_kg(cur.fetchone()[0])

    # Total sold
    cur.execute(
        """SELECT COALESCE(SUM(quantity_kg), 0.0) 
           FROM sales
           WHERE product_type = ? AND product_colour = ? AND status = 'ACTIVE'""",
        (product_type, colour)
    )
    sold = round_kg(cur.fetchone()[0])

    available = round_kg(produced - sold)
    return produced, sold, available

def get_finished_goods_summary(product_type=None, search=None):
    """Returns grouped list of finished goods stocks."""
    conn = get_db()
    cur = conn.cursor()

    query = """
    WITH prod_summary AS (
        SELECT pi.product_type, pi.colour,
               COUNT(DISTINCT p.id) as batch_count,
               SUM(pi.weight_kg) as total_produced_kg,
               MAX(p.production_date) as last_produced_date
        FROM production_items pi
        JOIN productions p ON pi.production_id = p.id
        WHERE p.status = 'ACTIVE'
        GROUP BY pi.product_type, pi.colour
    ),
    sale_summary AS (
        SELECT product_type, product_colour as colour,
               COUNT(id) as sale_count,
               SUM(quantity_kg) as total_sold_kg,
               SUM(total_amount) as total_sales_val,
               MAX(sale_date) as last_sale_date
        FROM sales
        WHERE status = 'ACTIVE'
        GROUP BY product_type, product_colour
    )
    SELECT 
        p.product_type,
        p.colour,
        p.batch_count,
        ROUND(p.total_produced_kg, 3) as produced_kg,
        ROUND(COALESCE(s.total_sold_kg, 0.0), 3) as sold_kg,
        ROUND(p.total_produced_kg - COALESCE(s.total_sold_kg, 0.0), 3) as available_kg,
        p.last_produced_date,
        s.last_sale_date
    FROM prod_summary p
    LEFT JOIN sale_summary s 
        ON p.product_type = s.product_type AND p.colour = s.colour
    WHERE 1=1
    """
    params = []
    if product_type:
        query += " AND p.product_type = ?"
        params.append(product_type)

    if search:
        query += " AND (p.colour LIKE ? OR p.product_type LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY p.product_type, p.colour"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        available = round_kg(r['available_kg'])
        status = 'Normal'
        if available <= 0:
            status = 'Out of Stock'
        elif available < 15.0: # threshold
            status = 'Low Stock'

        result.append({
            'product_type': r['product_type'],
            'colour': r['colour'],
            'batch_count': r['batch_count'],
            'produced_kg': round_kg(r['produced_kg']),
            'sold_kg': round_kg(r['sold_kg']),
            'available_kg': available,
            'last_produced_date': r['last_produced_date'],
            'last_sale_date': r['last_sale_date'],
            'status': status
        })
    return result

# --- Recording Purchases ---

def record_yarn_purchase(data, user_id=None, username="System"):
    conn = get_db()
    cur = conn.cursor()
    try:
        purchase_date = data.get('purchase_date') or datetime.now().strftime('%Y-%m-%d')
        supplier_id = int(data['supplier_id'])
        yarn_type = data['yarn_type'].strip()
        yarn_colour = data['yarn_colour'].strip()
        bags_cones = int(data.get('bags_cones') or 0)
        weight_kg = round_kg(data['weight_kg'])
        price_per_kg = round_curr(data['price_per_kg'])
        total_amount = round_curr(data.get('total_amount') or (weight_kg * price_per_kg))
        invoice_number = (data.get('invoice_number') or '').strip()
        notes = (data.get('notes') or '').strip()

        if weight_kg <= 0:
            raise ValidationError("Weight must be greater than 0 KG.")
        if price_per_kg < 0:
            raise ValidationError("Price per KG cannot be negative.")

        cur.execute(
            """INSERT INTO yarn_purchases 
               (purchase_date, supplier_id, yarn_type, yarn_colour, bags_cones, weight_kg, price_per_kg, total_amount, invoice_number, notes, created_by, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')""",
            (purchase_date, supplier_id, yarn_type, yarn_colour, bags_cones, weight_kg, price_per_kg, total_amount, invoice_number, notes, user_id)
        )
        purchase_id = cur.lastrowid

        # Insert into stock ledger
        cur.execute(
            """INSERT INTO stock_ledger
               (entry_date, transaction_type, category, item_name, colour, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
               VALUES (?, 'PURCHASE', 'RAW_YARN', ?, ?, ?, 'yarn_purchases', ?, 0, ?)""",
            (purchase_date, yarn_type, yarn_colour, purchase_id, weight_kg, f"Yarn purchase from supplier #{supplier_id}, Inv: {invoice_number}")
        )

        conn.commit()
        return purchase_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def cancel_yarn_purchase(purchase_id, user_id=None, username="System"):
    """Cancels a yarn purchase. Blocks if cancelling would leave negative raw yarn stock."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM yarn_purchases WHERE id = ?", (purchase_id,))
        purchase = cur.fetchone()
        if not purchase:
            raise ValidationError("Purchase record not found.")
        if purchase['status'] == 'CANCELLED':
            raise ValidationError("Purchase record is already cancelled.")

        yarn_type = purchase['yarn_type']
        yarn_colour = purchase['yarn_colour']
        weight_kg = purchase['weight_kg']

        # Check current remaining stock
        _, _, remaining = get_raw_yarn_stock_for_type_colour(conn, yarn_type, yarn_colour)
        if remaining < weight_kg:
            raise InsufficientStockError(
                f"Cannot cancel purchase: {weight_kg:.3f} KG was purchased, but only {remaining:.3f} KG remains in raw stock (some was already used in production)."
            )

        # Mark cancelled
        cur.execute("UPDATE yarn_purchases SET status = 'CANCELLED' WHERE id = ?", (purchase_id,))

        # Add reversal entry in stock ledger
        cur.execute(
            """INSERT INTO stock_ledger
               (entry_date, transaction_type, category, item_name, colour, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
               VALUES (?, 'PURCHASE_CANCEL', 'RAW_YARN', ?, ?, ?, 'yarn_purchases', 0, ?, ?)""",
            (datetime.now().strftime('%Y-%m-%d'), yarn_type, yarn_colour, purchase_id, weight_kg, f"Cancelled Yarn Purchase #{purchase_id}")
        )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- Recording Production ---

def record_production(data, user_id=None, username="System"):
    """
    Records a production run.
    Validates:
      1. input_weight_kg <= available raw yarn
      2. input_weight_kg == total_finished_weight_kg + wastage_weight_kg (within 0.001 tolerance)
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        production_date = data.get('production_date') or datetime.now().strftime('%Y-%m-%d')
        machine_name = data.get('machine_name', 'Default Machine').strip()
        operator_name = (data.get('operator_name') or '').strip()
        input_yarn_type = data['input_yarn_type'].strip()
        input_yarn_colour = data['input_yarn_colour'].strip()
        input_weight_kg = round_kg(data['input_weight_kg'])
        items = data.get('items', [])  # list of {product_type: 'Tape'/'Rope'/'Tipping', colour: '', weight_kg: 0.0}
        wastage_weight_kg = round_kg(data.get('wastage_weight_kg', 0.0))
        notes = (data.get('notes') or '').strip()

        if input_weight_kg <= 0:
            raise ValidationError("Input yarn weight must be greater than 0 KG.")

        if not items:
            raise ValidationError("At least one finished product item must be specified.")

        total_finished = round_kg(sum(round_kg(item['weight_kg']) for item in items))
        expected_input = round_kg(total_finished + wastage_weight_kg)

        if abs(input_weight_kg - expected_input) > 0.002:
            raise ValidationError(
                f"Production balance error: Input ({input_weight_kg:.3f} KG) must equal Finished ({total_finished:.3f} KG) + Wastage ({wastage_weight_kg:.3f} KG). Difference: {abs(input_weight_kg - expected_input):.3f} KG."
            )

        # Check raw yarn availability
        _, _, remaining_raw = get_raw_yarn_stock_for_type_colour(conn, input_yarn_type, input_yarn_colour)
        if remaining_raw < input_weight_kg:
            raise InsufficientStockError(
                f"Insufficient raw yarn stock for '{input_yarn_type}' ({input_yarn_colour}): Available is {remaining_raw:.3f} KG, but {input_weight_kg:.3f} KG is required for this production batch."
            )

        # Generate unique batch number
        batch_number = data.get('batch_number')
        if not batch_number:
            cur.execute("SELECT COUNT(id) FROM productions")
            count = cur.fetchone()[0] + 1
            batch_number = f"BATCH-{datetime.now().strftime('%Y%m')}-{count:04d}"

        cur.execute(
            """INSERT INTO productions
               (batch_number, production_date, machine_name, operator_name, input_yarn_type, input_yarn_colour, 
                input_weight_kg, total_finished_weight_kg, wastage_weight_kg, notes, created_by, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')""",
            (batch_number, production_date, machine_name, operator_name, input_yarn_type, input_yarn_colour,
             input_weight_kg, total_finished, wastage_weight_kg, notes, user_id)
        )
        production_id = cur.lastrowid

        # Insert finished items
        for item in items:
            p_type = item['product_type']
            p_colour = item.get('colour', input_yarn_colour).strip()
            p_weight = round_kg(item['weight_kg'])
            if p_weight <= 0:
                continue

            cur.execute(
                """INSERT INTO production_items (production_id, product_type, colour, weight_kg)
                   VALUES (?, ?, ?, ?)""",
                (production_id, p_type, p_colour, p_weight)
            )

            # Finished goods ledger entry
            ledger_cat = f"FINISHED_{p_type.upper()}"
            cur.execute(
                """INSERT INTO stock_ledger
                   (entry_date, transaction_type, category, item_name, colour, batch_number, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
                   VALUES (?, 'PRODUCTION_IN', ?, ?, ?, ?, ?, 'productions', ?, 0, ?)""",
                (production_date, ledger_cat, p_type, p_colour, batch_number, production_id, p_weight, f"Produced {p_type} via batch {batch_number}")
            )

        # Raw yarn deduction in ledger
        cur.execute(
            """INSERT INTO stock_ledger
               (entry_date, transaction_type, category, item_name, colour, batch_number, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
               VALUES (?, 'PRODUCTION_OUT', 'RAW_YARN', ?, ?, ?, ?, 'productions', 0, ?, ?)""",
            (production_date, input_yarn_type, input_yarn_colour, batch_number, production_id, input_weight_kg, f"Consumed for batch {batch_number} on {machine_name}")
        )

        # Wastage in ledger
        if wastage_weight_kg > 0:
            cur.execute(
                """INSERT INTO stock_ledger
                   (entry_date, transaction_type, category, item_name, colour, batch_number, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
                   VALUES (?, 'WASTAGE', 'WASTAGE', ?, ?, ?, ?, 'productions', ?, 0, ?)""",
                (production_date, input_yarn_type, input_yarn_colour, batch_number, production_id, wastage_weight_kg, f"Wastage from batch {batch_number}")
            )

        conn.commit()
        return production_id, batch_number
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def cancel_production(production_id, user_id=None, username="System"):
    """Cancels a production run. Checks that finished goods were not already sold."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM productions WHERE id = ?", (production_id,))
        prod = cur.fetchone()
        if not prod:
            raise ValidationError("Production batch not found.")
        if prod['status'] == 'CANCELLED':
            raise ValidationError("Production batch is already cancelled.")

        # Check each finished item to ensure cancelling won't leave negative stock
        cur.execute("SELECT * FROM production_items WHERE production_id = ?", (production_id,))
        items = cur.fetchall()

        for item in items:
            p_type = item['product_type']
            colour = item['colour']
            weight = item['weight_kg']
            _, _, available = get_finished_stock_for_item(conn, p_type, colour)
            if available < weight:
                raise InsufficientStockError(
                    f"Cannot cancel production batch: {weight:.3f} KG of {p_type} ({colour}) was produced, but only {available:.3f} KG is available in finished stock (some items have already been sold)."
                )

        # Mark cancelled
        cur.execute("UPDATE productions SET status = 'CANCELLED' WHERE id = ?", (production_id,))

        # Add reversal ledger entries
        today = datetime.now().strftime('%Y-%m-%d')
        # Return raw yarn
        cur.execute(
            """INSERT INTO stock_ledger
               (entry_date, transaction_type, category, item_name, colour, batch_number, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
               VALUES (?, 'PROD_CANCEL_RAW_RETURN', 'RAW_YARN', ?, ?, ?, ?, 'productions', ?, 0, ?)""",
            (today, prod['input_yarn_type'], prod['input_yarn_colour'], prod['batch_number'], production_id, prod['input_weight_kg'], f"Returned raw yarn from cancelled batch {prod['batch_number']}")
        )

        # Deduct finished goods
        for item in items:
            cur.execute(
                """INSERT INTO stock_ledger
                   (entry_date, transaction_type, category, item_name, colour, batch_number, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
                   VALUES (?, 'PROD_CANCEL_FG_DEDUCT', ?, ?, ?, ?, ?, 'productions', 0, ?, ?)""",
                (today, f"FINISHED_{item['product_type'].upper()}", item['product_type'], item['colour'], prod['batch_number'], production_id, item['weight_kg'], f"Reversed finished goods from cancelled batch {prod['batch_number']}")
            )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- Recording Sales ---

def record_sale(data, user_id=None, username="System"):
    """
    Records a sale of finished goods.
    Validates:
      1. quantity_kg <= available finished stock of (product_type, product_colour)
      2. total_amount = quantity_kg * price_per_kg
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        sale_date = data.get('sale_date') or datetime.now().strftime('%Y-%m-%d')
        customer_id = int(data['customer_id'])
        product_type = data['product_type'].strip()
        product_colour = data['product_colour'].strip()
        quantity_kg = round_kg(data['quantity_kg'])
        price_per_kg = round_curr(data['price_per_kg'])
        total_amount = round_curr(data.get('total_amount') or (quantity_kg * price_per_kg))
        
        payment_status = data.get('payment_status', 'Unpaid')
        paid_amount = round_curr(data.get('paid_amount', 0.0))
        if payment_status == 'Paid':
            paid_amount = total_amount
        balance_amount = round_curr(total_amount - paid_amount)

        notes = (data.get('notes') or '').strip()

        if quantity_kg <= 0:
            raise ValidationError("Sold quantity must be greater than 0 KG.")
        if price_per_kg < 0:
            raise ValidationError("Price per KG cannot be negative.")

        # Check finished stock availability
        _, _, available = get_finished_stock_for_item(conn, product_type, product_colour)
        if available < quantity_kg:
            raise InsufficientStockError(
                f"Insufficient finished stock for {product_type} ({product_colour}): Available is {available:.3f} KG, but sale requires {quantity_kg:.3f} KG."
            )

        # Invoice number generation
        invoice_number = data.get('invoice_number')
        if not invoice_number:
            cur.execute("SELECT COUNT(id) FROM sales")
            count = cur.fetchone()[0] + 1
            invoice_number = f"INV-{datetime.now().strftime('%Y%m')}-{count:04d}"

        cur.execute(
            """INSERT INTO sales
               (sale_date, customer_id, product_type, product_colour, quantity_kg, price_per_kg, 
                total_amount, invoice_number, payment_status, paid_amount, balance_amount, notes, created_by, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')""",
            (sale_date, customer_id, product_type, product_colour, quantity_kg, price_per_kg,
             total_amount, invoice_number, payment_status, paid_amount, balance_amount, notes, user_id)
        )
        sale_id = cur.lastrowid

        # Deduct from finished stock ledger
        ledger_cat = f"FINISHED_{product_type.upper()}"
        cur.execute(
            """INSERT INTO stock_ledger
               (entry_date, transaction_type, category, item_name, colour, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
               VALUES (?, 'SALE', ?, ?, ?, ?, 'sales', 0, ?, ?)""",
            (sale_date, ledger_cat, product_type, product_colour, sale_id, quantity_kg, f"Sale to customer #{customer_id}, Invoice: {invoice_number}")
        )

        conn.commit()
        return sale_id, invoice_number
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def cancel_sale(sale_id, user_id=None, username="System"):
    """Cancels a sale and restores finished goods stock."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM sales WHERE id = ?", (sale_id,))
        sale = cur.fetchone()
        if not sale:
            raise ValidationError("Sale record not found.")
        if sale['status'] == 'CANCELLED':
            raise ValidationError("Sale record is already cancelled.")

        cur.execute("UPDATE sales SET status = 'CANCELLED' WHERE id = ?", (sale_id,))

        # Reversal entry in ledger
        ledger_cat = f"FINISHED_{sale['product_type'].upper()}"
        cur.execute(
            """INSERT INTO stock_ledger
               (entry_date, transaction_type, category, item_name, colour, reference_id, reference_type, qty_in_kg, qty_out_kg, notes)
               VALUES (?, 'SALE_CANCEL', ?, ?, ?, ?, 'sales', ?, 0, ?)""",
            (datetime.now().strftime('%Y-%m-%d'), ledger_cat, sale['product_type'], sale['product_colour'], sale_id, sale['quantity_kg'], f"Cancelled Sale #{sale_id}, Inv: {sale['invoice_number']}")
        )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- Dashboard Summary ---

def get_dashboard_summary():
    conn = get_db()
    cur = conn.cursor()

    # 1. Total Yarn Purchased (KG) & Total Spend
    cur.execute(
        """SELECT COALESCE(SUM(weight_kg), 0.0), COALESCE(SUM(total_amount), 0.0)
           FROM yarn_purchases WHERE status = 'ACTIVE'"""
    )
    r_purch = cur.fetchone()
    total_yarn_purchased_kg = round_kg(r_purch[0])
    total_purchase_amount = round_curr(r_purch[1])

    # 2. Total Yarn Used in Production (KG) & Total Wastage
    cur.execute(
        """SELECT COALESCE(SUM(input_weight_kg), 0.0), COALESCE(SUM(wastage_weight_kg), 0.0)
           FROM productions WHERE status = 'ACTIVE'"""
    )
    r_prod = cur.fetchone()
    total_yarn_used_kg = round_kg(r_prod[0])
    total_production_waste_kg = round_kg(r_prod[1])

    # 3. Available Raw Yarn Stock (KG)
    available_raw_yarn_stock_kg = round_kg(total_yarn_purchased_kg - total_yarn_used_kg)

    # 4. Total Tape, Rope, Tipping Produced
    cur.execute(
        """SELECT pi.product_type, COALESCE(SUM(pi.weight_kg), 0.0)
           FROM production_items pi
           JOIN productions p ON pi.production_id = p.id
           WHERE p.status = 'ACTIVE'
           GROUP BY pi.product_type"""
    )
    produced_by_type = {r[0]: round_kg(r[1]) for r in cur.fetchall()}
    total_tape_produced = produced_by_type.get('Tape', 0.0)
    total_rope_produced = produced_by_type.get('Rope', 0.0)
    total_tipping_produced = produced_by_type.get('Tipping', 0.0)

    # 5. Total Sold by Type, Total Sales Revenue, Receivables
    cur.execute(
        """SELECT product_type, COALESCE(SUM(quantity_kg), 0.0)
           FROM sales WHERE status = 'ACTIVE'
           GROUP BY product_type"""
    )
    sold_by_type = {r[0]: round_kg(r[1]) for r in cur.fetchall()}
    tape_sold = sold_by_type.get('Tape', 0.0)
    rope_sold = sold_by_type.get('Rope', 0.0)
    tipping_sold = sold_by_type.get('Tipping', 0.0)

    total_tape_stock_kg = round_kg(total_tape_produced - tape_sold)
    total_rope_stock_kg = round_kg(total_rope_produced - rope_sold)
    total_tipping_stock_kg = round_kg(total_tipping_produced - tipping_sold)
    total_finished_goods_sold_kg = round_kg(tape_sold + rope_sold + tipping_sold)

    cur.execute(
        """SELECT COALESCE(SUM(total_amount), 0.0), COALESCE(SUM(paid_amount), 0.0), COALESCE(SUM(balance_amount), 0.0)
           FROM sales WHERE status = 'ACTIVE'"""
    )
    r_sales = cur.fetchone()
    total_sales_amount = round_curr(r_sales[0])
    total_paid_amount = round_curr(r_sales[1])
    total_outstanding_receivables = round_curr(r_sales[2])

    # Recent Purchases (last 5)
    cur.execute(
        """SELECT p.*, s.name as supplier_name
           FROM yarn_purchases p
           LEFT JOIN suppliers s ON p.supplier_id = s.id
           WHERE p.status = 'ACTIVE'
           ORDER BY p.purchase_date DESC, p.id DESC LIMIT 5"""
    )
    recent_purchases = [dict(r) for r in cur.fetchall()]

    # Recent Productions (last 5)
    cur.execute(
        """SELECT p.*, 
                  (SELECT GROUP_CONCAT(product_type || ' (' || ROUND(weight_kg, 2) || ' KG)', ', ') 
                   FROM production_items WHERE production_id = p.id) as finished_summary
           FROM productions p
           WHERE p.status = 'ACTIVE'
           ORDER BY p.production_date DESC, p.id DESC LIMIT 5"""
    )
    recent_productions = [dict(r) for r in cur.fetchall()]

    # Recent Sales (last 5)
    cur.execute(
        """SELECT s.*, c.name as customer_name
           FROM sales s
           LEFT JOIN customers c ON s.customer_id = c.id
           WHERE s.status = 'ACTIVE'
           ORDER BY s.sale_date DESC, s.id DESC LIMIT 5"""
    )
    recent_sales = [dict(r) for r in cur.fetchall()]

    # Monthly Purchases & Sales (Last 6 Months)
    cur.execute(
        """WITH months AS (
               SELECT strftime('%Y-%m', purchase_date) as m FROM yarn_purchases WHERE status = 'ACTIVE'
               UNION
               SELECT strftime('%Y-%m', sale_date) as m FROM sales WHERE status = 'ACTIVE'
               ORDER BY m DESC LIMIT 6
           )
           SELECT m.m,
                  COALESCE((SELECT SUM(weight_kg) FROM yarn_purchases WHERE strftime('%Y-%m', purchase_date) = m.m AND status = 'ACTIVE'), 0.0) as purchase_kg,
                  COALESCE((SELECT SUM(total_amount) FROM yarn_purchases WHERE strftime('%Y-%m', purchase_date) = m.m AND status = 'ACTIVE'), 0.0) as purchase_val,
                  COALESCE((SELECT SUM(quantity_kg) FROM sales WHERE strftime('%Y-%m', sale_date) = m.m AND status = 'ACTIVE'), 0.0) as sales_kg,
                  COALESCE((SELECT SUM(total_amount) FROM sales WHERE strftime('%Y-%m', sale_date) = m.m AND status = 'ACTIVE'), 0.0) as sales_val
           FROM months m
           ORDER BY m.m ASC"""
    )
    monthly_overview = [dict(r) for r in cur.fetchall()]

    # Low stock alerts
    # Raw yarn < 25 KG
    raw_summary = get_raw_yarn_stock_summary()
    low_raw_yarn = [r for r in raw_summary if r['status'] in ('Low Stock', 'Out of Stock')]

    # Finished stock < 15 KG
    fg_summary = get_finished_goods_summary()
    low_finished_goods = [f for f in fg_summary if f['status'] in ('Low Stock', 'Out of Stock')]

    conn.close()

    return {
        'cards': {
            'total_yarn_purchased_kg': total_yarn_purchased_kg,
            'available_raw_yarn_stock_kg': available_raw_yarn_stock_kg,
            'total_yarn_used_kg': total_yarn_used_kg,
            'total_tape_stock_kg': total_tape_stock_kg,
            'total_rope_stock_kg': total_rope_stock_kg,
            'total_tipping_stock_kg': total_tipping_stock_kg,
            'total_finished_goods_sold_kg': total_finished_goods_sold_kg,
            'total_production_waste_kg': total_production_waste_kg,
            'total_purchase_amount': total_purchase_amount,
            'total_sales_amount': total_sales_amount,
            'total_paid_amount': total_paid_amount,
            'total_outstanding_receivables': total_outstanding_receivables,
            'wastage_percentage': round((total_production_waste_kg / total_yarn_used_kg * 100) if total_yarn_used_kg > 0 else 0.0, 2)
        },
        'recent_purchases': recent_purchases,
        'recent_productions': recent_productions,
        'recent_sales': recent_sales,
        'monthly_overview': monthly_overview,
        'low_stock_alerts': {
            'raw_yarn': low_raw_yarn,
            'finished_goods': low_finished_goods,
            'total_alert_count': len(low_raw_yarn) + len(low_finished_goods)
        }
    }
