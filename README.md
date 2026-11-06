# Textile Manufacturing Inventory & Sales Management System

A modern, professional, production-grade **Textile Yarn, Production, Inventory and Sales Management System** designed for yarn twisting and narrow-fabric textile manufacturers.

---

## 🏭 Business Workflow

The system manages the complete lifecycle of materials in the factory:

$$\text{Yarn Purchase} \longrightarrow \text{Raw Yarn Stock} \longrightarrow \text{Production / Twisting} \longrightarrow \text{Finished Goods Stock} \longrightarrow \text{Sales Invoicing} \longrightarrow \text{Remaining Stock}$$

### Finished Products Produced:
1. **Tape** (Twill tape, binding tape for nighties & T-shirts)
2. **Rope** (Drawstring cord for track pants & sportswear)
3. **Tipping** (Lace tipping & hood cords)

---

## 🚀 Key Features

### 1. Automated Stock Calculation Engine (Zero Manual Math)
- **Yarn Purchase**: Automatically increments raw yarn stock for the specified yarn count and colour.
- **Production Entry**: Automatically deducts input yarn weight from raw stock, increments finished goods stocks (**Tape**, **Rope**, **Tipping**), and records production wastage.
- **Formula Enforced**:
  $$\text{Input Yarn Weight (KG)} = \sum \text{Finished Products Weight (Tape + Rope + Tipping)} + \text{Wastage Weight (KG)}$$
- **Sales Invoicing**: Automatically deducts sold weight from finished goods stock and prevents selling more weight than available.
- **Full Reversibility**: Cancelling any purchase, production batch, or sale safely and atomically reverses its stock effects (with negative-stock prevention checks).
- **Decimal Precision**: All material weights tracked accurately to 3 decimal places (e.g. `12.500 KG`).
- **Currency**: Indian Rupees (₹) formatted with Indian numbering format.

### 2. Comprehensive Dashboard
- **8 Primary KPI Cards**:
  1. Total Yarn Purchased (KG)
  2. Available Raw Yarn Stock (KG)
  3. Total Yarn Used in Production (KG)
  4. Total Tape Stock (KG)
  5. Total Rope Stock (KG)
  6. Total Tipping Stock (KG)
  7. Total Finished Goods Sold (KG)
  8. Total Production Waste (KG)
- **Financial Cards**: Total Yarn Purchases (₹), Total Sales Revenue (₹), Outstanding Receivables (₹), Wastage %.
- **Real-time Low Stock Warning Banner & Notification Bell**.
- **Interactive Charts**: Monthly Purchase vs Sales Trends (KG & ₹) and Stock Weight Distribution Donut.
- **Recent Activities Feed**: Latest purchases, production runs, and sales.

### 3. Dedicated Modules
- **Yarn Purchase Management**: Supplier dropdown, count/type, colour, cones/bags, weight, rate/KG, auto total, invoice #.
- **Raw Material Stock**: Grouped by yarn type and colour, batch tracking, health indicators.
- **Production Management**: Multi-item finished product creator, machine & operator tracking, live balance indicator.
- **Finished Goods Stock**: Dedicated tabbed sections for **Tape Stock**, **Rope Stock**, and **Tipping Stock**.
- **Sales & Invoicing**: Customer selection, real-time available stock preview, payment tracking (Paid/Unpaid/Partial), and printable GST/Tax Invoice generator.
- **Customer & Supplier CRM**: Contact details, GSTIN, and transaction ledgers.
- **Reports & Exporting**: 1-click **Excel (.xlsx)** and **PDF** downloads for raw stock, finished stock, purchases, productions, and sales.
- **Role-Based Authentication**: Secure login supporting `Admin`, `Manager`, and `Staff` roles.
- **Change Password**: Any user can change their password securely by verifying their current password.
- **Clear All Data Option**: 1-click administrative reset in Settings that wipes all transactions and sets all stock balances to `0.000 KG` for a clean fresh start.
- **System Utilities**: 1-click Database Backup and optional Sample Data Seeder.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.13, Flask REST API, SQLite 3 (WAL mode with ACID transactions)
- **Excel & PDF**: `openpyxl` (styled spreadsheets with formulas), `reportlab` (PDF generation)
- **Frontend**: Responsive Single-Page App (SPA), Tailwind CSS, Lucide Icons, Chart.js, SweetAlert2

---

## 🏃 Quick Start Guide

### 1. Start the Application Server
Run in PowerShell or Command Prompt:
```bash
python app.py
```
Or double-click `run.bat`.

### 2. Open in Browser
Visit:
```
http://localhost:5000
```

### 3. Demo Login Credentials
| Role | Username | Password | Access Level |
|---|---|---|---|
| **Admin** | `admin` | `admin123` | Full access, settings, user management, backup/seed |
| **Manager** | `manager` | `manager123` | Purchases, production, stocks, sales, reports |
| **Staff** | `staff` | `staff123` | Production & purchase entry, stock viewing |

*(Or click any of the 1-click demo login buttons on the login screen)*

---

## 🧪 Running Automated Tests

Run the unit tests:
```bash
python test_system.py
```

Run the complete end-to-end HTTP integration tests:
```bash
python test_e2e.py
```
