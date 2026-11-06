# Deploying Textile Inventory System to Vercel 🚀

The project is already **100% pre-configured and optimized for Vercel deployment** with:
- `vercel.json` (Vercel serverless routing)
- `api/index.py` (Serverless WSGI entry point)
- `requirements.txt` (Python runtime dependencies)
- `database.py` (Configured for Vercel's serverless `/tmp` filesystem)

---

## ⚡ Option 1: Deploy in 2 Clicks via GitHub (Recommended)

1. **Push this folder to a GitHub repository**:
   - Create a new repository on [GitHub](https://github.com/new) (e.g., `textile-inventory`).
   - Push your code to GitHub:
     ```bash
     git init
     git add .
     git commit -m "Initial textile management system"
     git branch -M main
     git remote add origin https://github.com/YOUR_USERNAME/textile-inventory.git
     git push -u origin main
     ```

2. **Deploy on Vercel**:
   - Go to **[vercel.com/new](https://vercel.com/new)**.
   - Click **"Import"** next to your `textile-inventory` repository.
   - Click **"Deploy"** (no custom build settings needed; `vercel.json` handles everything).
   - In ~30 seconds, Vercel will give you a live production URL:
     👉 **`https://your-project.vercel.app`**

---

## 💻 Option 2: Deploy using Vercel CLI

If you have Node/npm installed on your machine:
```bash
# 1. Log in to your Vercel account
npx vercel login

# 2. Deploy to production
npx vercel --prod
```
The CLI will output your live URL directly in your terminal.

---

## 🗄️ Notes on Database Persistence on Vercel

> [!NOTE]
> Vercel is a **serverless** environment with an ephemeral `/tmp` filesystem. The system automatically initializes and copies the SQLite database into `/tmp` so all reads, writes, purchases, production batches, and sales work seamlessly out of the box.
> For long-term permanent storage on cloud serverless deployments, you can download a **1-click database backup** from **Settings** anytime, or connect to a cloud database (such as Supabase, Turso SQLite, or Vercel Postgres).
