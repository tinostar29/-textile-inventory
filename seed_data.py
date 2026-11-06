import os
from database import get_db, init_db
from auth import generate_salt, hash_password
from stock_service import record_yarn_purchase, record_production, record_sale

def seed_all():
    init_db()
    conn = get_db()
    cur = conn.cursor()

    # Clear existing data for fresh seed
    cur.execute("DELETE FROM activity_logs")
    cur.execute("DELETE FROM stock_ledger")
    cur.execute("DELETE FROM sales")
    cur.execute("DELETE FROM production_items")
    cur.execute("DELETE FROM productions")
    cur.execute("DELETE FROM yarn_purchases")
    cur.execute("DELETE FROM customers")
    cur.execute("DELETE FROM suppliers")
    cur.execute("DELETE FROM system_settings")
    cur.execute("DELETE FROM machines")
    cur.execute("DELETE FROM yarn_masters")
    cur.execute("DELETE FROM colour_masters")
    cur.execute("DELETE FROM users")
    try:
        cur.execute("DELETE FROM sqlite_sequence")
    except Exception:
        pass
    conn.commit()

    # 1. Seed Users
    users_data = [
        ("admin", "admin123", "Factory Owner / Admin", "admin"),
        ("manager", "manager123", "Production Manager", "manager"),
        ("staff", "staff123", "Floor Supervisor", "staff")
    ]
    user_ids = {}
    for uname, pwd, fname, role in users_data:
        salt = generate_salt()
        phash = hash_password(pwd, salt)
        cur.execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role) VALUES (?, ?, ?, ?, ?)",
            (uname, phash, salt, fname, role)
        )
        user_ids[uname] = cur.lastrowid

    # 2. Company & System Settings
    settings = [
        ("company_name", "Sri Krishna Textile Mills & Twisting Works"),
        ("company_address", "Plot No. 42-45, Textile Industrial Complex, Tirupur, Tamil Nadu - 641604"),
        ("company_phone", "+91 98420 12345 / 0421-224455"),
        ("company_email", "accounts@krishnatextiles.in"),
        ("company_gstin", "33AABCT9988Q1ZA"),
        ("company_bank_details", "HDFC Bank, Tirupur Main Branch | A/C: 50200012345678 | IFSC: HDFC0001234"),
        ("raw_yarn_threshold", "25.0"),
        ("finished_goods_threshold", "15.0"),
        ("invoice_prefix", "SKT-INV-")
    ]
    cur.executemany("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", settings)

    # 3. Machines
    machines = [
        ("Twisting Machine T-01", "T01", "Twisting"),
        ("Twisting Machine T-02", "T02", "Twisting"),
        ("Braiding Machine B-01 (Tape)", "B01", "Tape Braiding"),
        ("Rope Twister R-01", "R01", "Rope Twisting"),
        ("Tipping Machine TP-01", "TP01", "Tipping Application")
    ]
    cur.executemany("INSERT INTO machines (name, code, machine_type) VALUES (?, ?, ?)", machines)

    # 4. Yarn Types & Colours
    yarns = [
        ("Cotton 2/20s", "Cotton", "2/20s"),
        ("Cotton 2/30s", "Cotton", "2/30s"),
        ("Cotton 2/40s", "Cotton", "2/40s"),
        ("Polyester 150D", "Polyester", "150D"),
        ("Polyester 300D", "Polyester", "300D"),
        ("Poly-Cotton 80/20", "Poly-Cotton", "80/20")
    ]
    cur.executemany("INSERT INTO yarn_masters (name, category, standard_count) VALUES (?, ?, ?)", yarns)

    colours = [
        ("Bleached White", "#FFFFFF"),
        ("Jet Black", "#111111"),
        ("Navy Blue", "#001F3F"),
        ("Deep Red", "#8B0000"),
        ("Olive Green", "#556B2F"),
        ("Charcoal Grey", "#333333"),
        ("Royal Blue", "#4169E1")
    ]
    cur.executemany("INSERT INTO colour_masters (name, hex_code) VALUES (?, ?)", colours)

    # 5. Suppliers
    suppliers = [
        ("Vardhman Spinning Mills Ltd", "Prakash Jain", "+91 94431 11222", "sales@vardhman.com", "Coimbatore Main Road, Coimbatore", "33AAACV1234F1Z1", "Primary cotton supplier"),
        ("Super Spinning Mills", "K. Natarajan", "+91 98432 22333", "orders@superspinning.com", "Erode Ring Road, Erode", "33AABCS5678G1Z2", "Quality 2/30s and 2/40s yarn"),
        ("KPR Mill Yarns Division", "S. Murugesan", "+91 97500 33444", "yarns@kprmill.com", "Avinashi Road, Tirupur", "33AACCK9012H1Z3", "Immediate delivery for combed yarn"),
        ("Reliance Synthetics Hub", "Anand Verma", "+91 98200 44555", "yarn@relsynthetics.com", "Salem Bypass, Salem", "33AABCR3456J1Z4", "High-tenacity polyester supplier")
    ]
    supplier_ids = []
    for s in suppliers:
        cur.execute(
            "INSERT INTO suppliers (name, contact_person, phone, email, address, gstin, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            s
        )
        supplier_ids.append(cur.lastrowid)

    # 6. Customers (Clothes & Garment Makers: Nighties, Track pants, T-shirts)
    customers = [
        ("Classic Nighties & Loungewear Ltd", "Mr. R. Karthik", "+91 98430 77889", "procurement@classicnighties.in", "SIDCO Garment Complex, Tirupur", "33AABCC1122D1ZA", 100000, "Manufactures cotton & poly nighties - large tape buyer"),
        ("FitMax Activewear & Track Pants Mfg", "V. Balachander", "+91 97890 88990", "purchase@fitmaxsports.com", "Textile City Phase 2, Coimbatore", "33AABCF3344E1ZB", 150000, "Uses cord & rope for track pants waistbands"),
        ("Apex Knitwear & T-Shirts Export", "M. Shanmugam", "+91 94422 99001", "merchandising@apexknit.com", "Ring Road Industrial Estate, Tirupur", "33AABCA5566F1ZC", 200000, "Uses tape & tipping for branded neck tape & hoodies"),
        ("Royal Comforts Garments", "Mrs. L. Vani", "+91 98944 11223", "vani@royalcomforts.com", "Kangeyam Road, Tirupur", "33AABCR7788G1ZD", 75000, "Nighty laces and drawstring cords buyer")
    ]
    customer_ids = []
    for c in customers:
        cur.execute(
            "INSERT INTO customers (name, contact_person, phone, email, address, gstin, credit_limit, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            c
        )
        customer_ids.append(cur.lastrowid)

    conn.commit()
    conn.close()

    admin_id = user_ids['admin']

    # 7. Record Yarn Purchases
    purchases = [
        {
            'purchase_date': '2026-10-15',
            'supplier_id': supplier_ids[0],
            'yarn_type': 'Cotton 2/20s',
            'yarn_colour': 'Bleached White',
            'bags_cones': 20,
            'weight_kg': 500.000,
            'price_per_kg': 285.00,
            'invoice_number': 'VARD-2026-1089',
            'notes': 'Grade A combed cotton bags'
        },
        {
            'purchase_date': '2026-10-18',
            'supplier_id': supplier_ids[3],
            'yarn_type': 'Polyester 150D',
            'yarn_colour': 'Navy Blue',
            'bags_cones': 15,
            'weight_kg': 350.000,
            'price_per_kg': 195.00,
            'invoice_number': 'REL-7782',
            'notes': 'High tenacity textured polyester'
        },
        {
            'purchase_date': '2026-10-22',
            'supplier_id': supplier_ids[1],
            'yarn_type': 'Cotton 2/30s',
            'yarn_colour': 'Jet Black',
            'bags_cones': 12,
            'weight_kg': 300.000,
            'price_per_kg': 310.00,
            'invoice_number': 'SSM-5521',
            'notes': 'Reactive dyed jet black cones'
        },
        {
            'purchase_date': '2026-10-28',
            'supplier_id': supplier_ids[2],
            'yarn_type': 'Poly-Cotton 80/20',
            'yarn_colour': 'Deep Red',
            'bags_cones': 8,
            'weight_kg': 200.000,
            'price_per_kg': 240.00,
            'invoice_number': 'KPR-9045',
            'notes': 'Blended yarn for drawstrings and tipping'
        },
        {
            'purchase_date': '2026-11-01',
            'supplier_id': supplier_ids[0],
            'yarn_type': 'Cotton 2/20s',
            'yarn_colour': 'Bleached White',
            'bags_cones': 10,
            'weight_kg': 250.000,
            'price_per_kg': 288.00,
            'invoice_number': 'VARD-2026-1142',
            'notes': 'Additional raw stock replenishment'
        }
    ]

    for p in purchases:
        record_yarn_purchase(p, user_id=admin_id, username="admin")

    # 8. Record Production Batches
    # Batch 1: Cotton 2/20s White (50 KG Input -> 47 KG Tape + 3 KG Wastage)
    prod_1 = {
        'batch_number': 'BATCH-202610-0001',
        'production_date': '2026-10-25',
        'machine_name': 'Braiding Machine B-01 (Tape)',
        'operator_name': 'Raju Ramanathan',
        'input_yarn_type': 'Cotton 2/20s',
        'input_yarn_colour': 'Bleached White',
        'input_weight_kg': 50.000,
        'items': [
            {'product_type': 'Tape', 'colour': 'Bleached White', 'weight_kg': 47.000}
        ],
        'wastage_weight_kg': 3.000,
        'notes': 'Narrow twill tape production for nighties neck binding'
    }
    record_production(prod_1, user_id=admin_id, username="admin")

    # Batch 2: Multi-item batch from prompt!
    # 80 KG Input Polyester 150D Navy Blue -> 45 KG Tape + 30 KG Rope + 3 KG Tipping + 2 KG Wastage
    prod_2 = {
        'batch_number': 'BATCH-202610-0002',
        'production_date': '2026-10-29',
        'machine_name': 'Twisting Machine T-01',
        'operator_name': 'Suresh Kumar',
        'input_yarn_type': 'Polyester 150D',
        'input_yarn_colour': 'Navy Blue',
        'input_weight_kg': 80.000,
        'items': [
            {'product_type': 'Tape', 'colour': 'Navy Blue', 'weight_kg': 45.000},
            {'product_type': 'Rope', 'colour': 'Navy Blue', 'weight_kg': 30.000},
            {'product_type': 'Tipping', 'colour': 'Navy Blue', 'weight_kg': 3.000}
        ],
        'wastage_weight_kg': 2.000,
        'notes': 'Composite twisting run creating tape, waistband rope & tipped cords'
    }
    record_production(prod_2, user_id=admin_id, username="admin")

    # Batch 3: Cotton 2/30s Black (60 KG Input -> 56 KG Rope + 4 KG Wastage)
    prod_3 = {
        'batch_number': 'BATCH-202611-0003',
        'production_date': '2026-11-02',
        'machine_name': 'Rope Twister R-01',
        'operator_name': 'Maheshwaran',
        'input_yarn_type': 'Cotton 2/30s',
        'input_yarn_colour': 'Jet Black',
        'input_weight_kg': 60.000,
        'items': [
            {'product_type': 'Rope', 'colour': 'Jet Black', 'weight_kg': 56.000}
        ],
        'wastage_weight_kg': 4.000,
        'notes': 'Heavy gauge track pant drawstring rope'
    }
    record_production(prod_3, user_id=admin_id, username="admin")

    # Batch 4: Poly-Cotton 80/20 Red (40 KG Input -> 37 KG Tipping + 3 KG Wastage)
    prod_4 = {
        'batch_number': 'BATCH-202611-0004',
        'production_date': '2026-11-04',
        'machine_name': 'Tipping Machine TP-01',
        'operator_name': 'Ramesh Babu',
        'input_yarn_type': 'Poly-Cotton 80/20',
        'input_yarn_colour': 'Deep Red',
        'input_weight_kg': 40.000,
        'items': [
            {'product_type': 'Tipping', 'colour': 'Deep Red', 'weight_kg': 37.000}
        ],
        'wastage_weight_kg': 3.000,
        'notes': 'High-finish tipping for hoodie drawstrings'
    }
    record_production(prod_4, user_id=admin_id, username="admin")

    # 9. Record Sales of Finished Goods
    # Sale 1: 20 KG Tape Bleached White to Classic Nighties
    sale_1 = {
        'sale_date': '2026-10-27',
        'customer_id': customer_ids[0],
        'product_type': 'Tape',
        'product_colour': 'Bleached White',
        'quantity_kg': 20.000,
        'price_per_kg': 420.00,
        'total_amount': 8400.00,
        'invoice_number': 'SKT-INV-202610-0001',
        'payment_status': 'Paid',
        'paid_amount': 8400.00,
        'notes': 'Tape supplied for nighties manufacturing'
    }
    record_sale(sale_1, user_id=admin_id, username="admin")

    # Sale 2: 15 KG Rope Navy Blue to FitMax Track Pants
    sale_2 = {
        'sale_date': '2026-10-31',
        'customer_id': customer_ids[1],
        'product_type': 'Rope',
        'product_colour': 'Navy Blue',
        'quantity_kg': 15.000,
        'price_per_kg': 340.00,
        'total_amount': 5100.00,
        'invoice_number': 'SKT-INV-202610-0002',
        'payment_status': 'Partial',
        'paid_amount': 3000.00,
        'notes': 'Drawstring rope for sports track pants batch'
    }
    record_sale(sale_2, user_id=admin_id, username="admin")

    # Sale 3: 10 KG Tipping Deep Red to Apex Knitwear
    sale_3 = {
        'sale_date': '2026-11-05',
        'customer_id': customer_ids[2],
        'product_type': 'Tipping',
        'product_colour': 'Deep Red',
        'quantity_kg': 10.000,
        'price_per_kg': 480.00,
        'total_amount': 4800.00,
        'invoice_number': 'SKT-INV-202611-0003',
        'payment_status': 'Paid',
        'paid_amount': 4800.00,
        'notes': 'Tipping supplied for export hoodie strings'
    }
    record_sale(sale_3, user_id=admin_id, username="admin")

    print("Comprehensive textile factory sample data seeded successfully!")

if __name__ == "__main__":
    seed_all()
