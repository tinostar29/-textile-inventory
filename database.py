import sqlite3
import os
import shutil

IS_SERVERLESS = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

if IS_SERVERLESS:
    DB_PATH = "/tmp/textile_inventory.db"
    bundled_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textile_inventory.db")
    if not os.path.exists(DB_PATH) and os.path.exists(bundled_db):
        try:
            shutil.copy2(bundled_db, DB_PATH)
        except Exception as e:
            print(f"Error copying bundled db: {e}")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textile_inventory.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL mode may fail on some read-only/tmp mounts; use standard journal mode if WAL fails
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
    -- Users and Authentication
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'staff')),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Suppliers (Yarn Spinners & Dealers)
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        gstin TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Customers (Garment & Clothes Manufacturers)
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        gstin TEXT,
        credit_limit REAL DEFAULT 0,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Yarn Purchases
    CREATE TABLE IF NOT EXISTS yarn_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_date DATE NOT NULL,
        supplier_id INTEGER NOT NULL,
        yarn_type TEXT NOT NULL,
        yarn_colour TEXT NOT NULL,
        bags_cones INTEGER DEFAULT 0,
        weight_kg REAL NOT NULL CHECK(weight_kg > 0),
        price_per_kg REAL NOT NULL CHECK(price_per_kg >= 0),
        total_amount REAL NOT NULL,
        invoice_number TEXT,
        notes TEXT,
        created_by INTEGER,
        status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'CANCELLED')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    -- Production Runs (Twisting / Narrow Weaving)
    CREATE TABLE IF NOT EXISTS productions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT UNIQUE NOT NULL,
        production_date DATE NOT NULL,
        machine_name TEXT NOT NULL,
        operator_name TEXT,
        input_yarn_type TEXT NOT NULL,
        input_yarn_colour TEXT NOT NULL,
        input_weight_kg REAL NOT NULL CHECK(input_weight_kg > 0),
        total_finished_weight_kg REAL NOT NULL DEFAULT 0,
        wastage_weight_kg REAL NOT NULL DEFAULT 0,
        notes TEXT,
        created_by INTEGER,
        status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'CANCELLED')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    -- Production Finished Items (Tape / Rope / Tipping)
    CREATE TABLE IF NOT EXISTS production_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        production_id INTEGER NOT NULL,
        product_type TEXT NOT NULL CHECK(product_type IN ('Tape', 'Rope', 'Tipping')),
        colour TEXT NOT NULL,
        weight_kg REAL NOT NULL CHECK(weight_kg > 0),
        FOREIGN KEY (production_id) REFERENCES productions(id) ON DELETE CASCADE
    );

    -- Finished Goods Sales
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_date DATE NOT NULL,
        customer_id INTEGER NOT NULL,
        product_type TEXT NOT NULL CHECK(product_type IN ('Tape', 'Rope', 'Tipping')),
        product_colour TEXT NOT NULL,
        quantity_kg REAL NOT NULL CHECK(quantity_kg > 0),
        price_per_kg REAL NOT NULL CHECK(price_per_kg >= 0),
        total_amount REAL NOT NULL,
        invoice_number TEXT UNIQUE NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'Unpaid' CHECK(payment_status IN ('Paid', 'Unpaid', 'Partial')),
        paid_amount REAL NOT NULL DEFAULT 0,
        balance_amount REAL NOT NULL DEFAULT 0,
        notes TEXT,
        created_by INTEGER,
        status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'CANCELLED')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    -- Comprehensive Stock Movement Ledger (Audit Log of all weight changes)
    CREATE TABLE IF NOT EXISTS stock_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date DATE NOT NULL,
        transaction_type TEXT NOT NULL, 
        category TEXT NOT NULL CHECK(category IN ('RAW_YARN', 'FINISHED_TAPE', 'FINISHED_ROPE', 'FINISHED_TIPPING', 'WASTAGE')),
        item_name TEXT NOT NULL,
        colour TEXT NOT NULL,
        batch_number TEXT,
        reference_id INTEGER,
        reference_type TEXT,
        qty_in_kg REAL NOT NULL DEFAULT 0,
        qty_out_kg REAL NOT NULL DEFAULT 0,
        balance_kg REAL,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- System & Activity Audit Logs
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        action TEXT NOT NULL,
        module TEXT NOT NULL,
        record_id TEXT,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- System Configuration Settings
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    -- Master Setup Tables
    CREATE TABLE IF NOT EXISTS machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT,
        machine_type TEXT,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS yarn_masters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT,
        standard_count TEXT
    );

    CREATE TABLE IF NOT EXISTS colour_masters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        hex_code TEXT
    );

    -- Indexes for high-speed stock calculation and filtering
    CREATE INDEX IF NOT EXISTS idx_yarn_purchases_type_colour ON yarn_purchases(yarn_type, yarn_colour, status);
    CREATE INDEX IF NOT EXISTS idx_productions_type_colour ON productions(input_yarn_type, input_yarn_colour, status);
    CREATE INDEX IF NOT EXISTS idx_production_items_type_colour ON production_items(product_type, colour);
    CREATE INDEX IF NOT EXISTS idx_sales_type_colour ON sales(product_type, product_colour, status);
    CREATE INDEX IF NOT EXISTS idx_ledger_category_item ON stock_ledger(category, item_name, colour);
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
