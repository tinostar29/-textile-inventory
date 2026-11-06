import unittest
from app import app
from seed_data import seed_all

class TextileAppE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_all()

    def setUp(self):
        self.client = app.test_client()
        self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})

    def test_01_static_index(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TEXMANAGE', res.data)
        print("[PASS] Static Index HTML served successfully")

    def test_02_auth_workflow(self):
        # Failed login
        res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrongpassword'})
        self.assertEqual(res.status_code, 401)

        # Successful login
        res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['role'], 'admin')

        # Check me
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['authenticated'])
        print("[PASS] Authentication & Role-Based Session Verified")

    def test_03_dashboard_api(self):
        res = self.client.get('/api/dashboard')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']
        self.assertIn('cards', data)
        self.assertIn('recent_purchases', data)
        self.assertIn('recent_productions', data)
        self.assertIn('recent_sales', data)
        self.assertIn('monthly_overview', data)
        self.assertIn('low_stock_alerts', data)
        print("[PASS] Dashboard API and Structure Verified")

    def test_04_yarn_purchase_and_raw_stock_increase(self):
        # Check initial raw stock for Polyester 300D
        res = self.client.get('/api/raw-stock?search=Polyester+300D')
        self.assertEqual(res.status_code, 200)
        initial_stock = 0.0
        for item in res.get_json()['data']:
            if item['yarn_type'] == 'Polyester 300D' and item['yarn_colour'] == 'Jet Black':
                initial_stock = item['remaining_kg']

        # Get first supplier
        supp_res = self.client.get('/api/suppliers')
        supplier_id = supp_res.get_json()['data'][0]['id']

        # Record new yarn purchase of 100 KG
        purchase_payload = {
            'purchase_date': '2026-11-06',
            'supplier_id': supplier_id,
            'yarn_type': 'Polyester 300D',
            'yarn_colour': 'Jet Black',
            'bags_cones': 4,
            'weight_kg': 100.000,
            'price_per_kg': 210.00,
            'total_amount': 21000.00,
            'invoice_number': 'TEST-INV-100',
            'notes': 'Test automated stock addition'
        }
        res = self.client.post('/api/purchases', json=purchase_payload)
        if res.status_code != 200:
            print("TEST 4 FAILURE:", res.status_code, res.get_json())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify raw stock increased by exactly 100 KG
        res = self.client.get('/api/raw-stock?search=Polyester+300D')
        new_stock = 0.0
        for item in res.get_json()['data']:
            if item['yarn_type'] == 'Polyester 300D' and item['yarn_colour'] == 'Jet Black':
                new_stock = item['remaining_kg']
        self.assertEqual(new_stock, initial_stock + 100.000)
        print("[PASS] Yarn Purchase automatically increased Raw Yarn Stock by 100.000 KG")

    def test_05_production_deducts_raw_and_adds_finished_stock(self):
        # Produce from the 100 KG Polyester 300D Jet Black:
        # Input = 50 KG -> Output: 30 KG Tape + 18 KG Rope + 2 KG Wastage
        prod_payload = {
            'production_date': '2026-11-06',
            'machine_name': 'Braiding Machine B-01 (Tape)',
            'operator_name': 'Murugan',
            'input_yarn_type': 'Polyester 300D',
            'input_yarn_colour': 'Jet Black',
            'input_weight_kg': 50.000,
            'items': [
                {'product_type': 'Tape', 'colour': 'Jet Black', 'weight_kg': 30.000},
                {'product_type': 'Rope', 'colour': 'Jet Black', 'weight_kg': 18.000}
            ],
            'wastage_weight_kg': 2.000,
            'notes': 'Twisting run producing tape and rope'
        }
        res = self.client.post('/api/productions', json=prod_payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify Raw Yarn stock decreased by 50 KG
        res = self.client.get('/api/raw-stock?search=Polyester+300D')
        for item in res.get_json()['data']:
            if item['yarn_type'] == 'Polyester 300D' and item['yarn_colour'] == 'Jet Black':
                self.assertEqual(item['remaining_kg'], 50.000)

        # Verify Finished Goods Stock increased
        res = self.client.get('/api/finished-stock?product_type=Tape')
        tape_item = next(f for f in res.get_json()['data'] if f['colour'] == 'Jet Black')
        self.assertEqual(tape_item['available_kg'], 30.000)

        res = self.client.get('/api/finished-stock?product_type=Rope')
        rope_item = next(f for f in res.get_json()['data'] if f['colour'] == 'Jet Black')
        self.assertGreaterEqual(rope_item['available_kg'], 18.000)
        print("[PASS] Production deducted Raw Yarn, created multiple Finished Goods, and tracked Wastage")

    def test_06_sales_deducts_finished_stock_and_prevents_oversell(self):
        cust_res = self.client.get('/api/customers')
        customer_id = cust_res.get_json()['data'][0]['id']

        # Attempt to sell 35 KG of Tape Jet Black (only 30 KG available) -> must fail!
        oversell_payload = {
            'sale_date': '2026-11-06',
            'customer_id': customer_id,
            'product_type': 'Tape',
            'product_colour': 'Jet Black',
            'quantity_kg': 35.000,
            'price_per_kg': 400.00
        }
        res = self.client.post('/api/sales', json=oversell_payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Insufficient finished stock", res.get_json()['message'])

        # Valid sale of 10 KG
        valid_sale = {
            'sale_date': '2026-11-06',
            'customer_id': customer_id,
            'product_type': 'Tape',
            'product_colour': 'Jet Black',
            'quantity_kg': 10.000,
            'price_per_kg': 400.00,
            'payment_status': 'Paid',
            'paid_amount': 4000.00
        }
        res = self.client.post('/api/sales', json=valid_sale)
        self.assertEqual(res.status_code, 200)
        sale_id = res.get_json()['id']

        # Verify finished Tape stock is now 20 KG (30 - 10)
        res = self.client.get('/api/finished-stock?product_type=Tape')
        tape_item = next(f for f in res.get_json()['data'] if f['colour'] == 'Jet Black')
        self.assertEqual(tape_item['available_kg'], 20.000)

        # Verify invoice generation
        res = self.client.get(f'/api/sales/{sale_id}/invoice')
        self.assertEqual(res.status_code, 200)
        inv_data = res.get_json()
        self.assertEqual(inv_data['invoice']['quantity_kg'], 10.000)
        self.assertEqual(inv_data['invoice']['total_amount'], 4000.00)
        print("[PASS] Sales validation, over-sell prevention, stock deduction & invoice generation verified")

    def test_07_export_endpoints(self):
        res = self.client.get('/api/reports/export/excel?type=raw_stock')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        res = self.client.get('/api/reports/export/pdf?type=finished_stock')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/pdf')
        print("[PASS] Excel and PDF export HTTP endpoints verified")

if __name__ == '__main__':
    unittest.main()
