import unittest
from stock_service import (
    get_dashboard_summary,
    get_raw_yarn_stock_summary,
    get_finished_goods_summary,
    record_yarn_purchase,
    record_production,
    record_sale,
    cancel_yarn_purchase,
    cancel_production,
    cancel_sale,
    InsufficientStockError,
    ValidationError
)
from reports_service import (
    export_raw_yarn_stock_excel,
    export_finished_goods_excel,
    export_purchases_excel,
    export_production_excel,
    export_sales_excel,
    export_generic_pdf
)

class TextileSystemTest(unittest.TestCase):

    def test_01_dashboard_summary_integrity(self):
        summary = get_dashboard_summary()
        cards = summary['cards']

        self.assertEqual(cards['total_yarn_purchased_kg'], 1600.000)
        self.assertEqual(cards['total_yarn_used_kg'], 230.000)
        self.assertEqual(cards['available_raw_yarn_stock_kg'], 1370.000)
        self.assertEqual(cards['total_production_waste_kg'], 12.000)
        
        # Tape: 92 produced - 20 sold = 72
        self.assertEqual(cards['total_tape_stock_kg'], 72.000)
        # Rope: 86 produced - 15 sold = 71
        self.assertEqual(cards['total_rope_stock_kg'], 71.000)
        # Tipping: 40 produced - 10 sold = 30
        self.assertEqual(cards['total_tipping_stock_kg'], 30.000)
        # Total sold: 20 + 15 + 10 = 45
        self.assertEqual(cards['total_finished_goods_sold_kg'], 45.000)

        # Financial assertions
        self.assertEqual(cards['total_sales_amount'], 18300.00)
        self.assertEqual(cards['total_paid_amount'], 16200.00)
        self.assertEqual(cards['total_outstanding_receivables'], 2100.00)
        print("[PASS] Dashboard Summary & Balance Integrity Verified!")
    def test_02_prevent_overconsumption_of_raw_yarn(self):
        # Attempt to produce with 5000 KG of Cotton 2/20s when available is far less
        invalid_prod = {
            'production_date': '2026-11-06',
            'machine_name': 'Twisting Machine T-01',
            'input_yarn_type': 'Cotton 2/20s',
            'input_yarn_colour': 'Bleached White',
            'input_weight_kg': 5000.000,
            'items': [{'product_type': 'Tape', 'colour': 'Bleached White', 'weight_kg': 4900.000}],
            'wastage_weight_kg': 100.000
        }
        with self.assertRaises(InsufficientStockError):
            record_production(invalid_prod)
        print("[PASS] Prevention of Raw Yarn Over-consumption Verified!")

    def test_03_prevent_production_balance_mismatch(self):
        # Input = 50, but finished (45) + wastage (2) = 47 != 50
        mismatch_prod = {
            'production_date': '2026-11-06',
            'machine_name': 'Twisting Machine T-01',
            'input_yarn_type': 'Cotton 2/20s',
            'input_yarn_colour': 'Bleached White',
            'input_weight_kg': 50.000,
            'items': [{'product_type': 'Tape', 'colour': 'Bleached White', 'weight_kg': 45.000}],
            'wastage_weight_kg': 2.000 # Missing 3 KG!
        }
        with self.assertRaises(ValidationError):
            record_production(mismatch_prod)
        print("[PASS] Production Balance Formula (Input = Finished + Wastage) Enforcement Verified!")

    def test_04_prevent_overselling_of_finished_goods(self):
        # Attempt to sell 500 KG of Tape Bleached White when only 72 KG available
        invalid_sale = {
            'sale_date': '2026-11-06',
            'customer_id': 1,
            'product_type': 'Tape',
            'product_colour': 'Bleached White',
            'quantity_kg': 500.000,
            'price_per_kg': 400.00
        }
        with self.assertRaises(InsufficientStockError):
            record_sale(invalid_sale)
        print("[PASS] Prevention of Finished Goods Over-selling Verified!")

    def test_05_excel_and_pdf_report_generation(self):
        # Excel streams
        raw_stream = export_raw_yarn_stock_excel()
        self.assertGreater(raw_stream.getbuffer().nbytes, 1000)

        fg_stream = export_finished_goods_excel()
        self.assertGreater(fg_stream.getbuffer().nbytes, 1000)

        sales_stream = export_sales_excel()
        self.assertGreater(sales_stream.getbuffer().nbytes, 1000)

        prod_stream = export_production_excel()
        self.assertGreater(prod_stream.getbuffer().nbytes, 1000)

        purch_stream = export_purchases_excel()
        self.assertGreater(purch_stream.getbuffer().nbytes, 1000)

        # PDF stream
        pdf_stream = export_generic_pdf("Test Report", "Sub", ["A", "B"], [["1", "2"]])
        self.assertGreater(pdf_stream.getbuffer().nbytes, 500)
        print("[PASS] Excel (.xlsx) and PDF Report Exports Verified!")

if __name__ == '__main__':
    unittest.main()
