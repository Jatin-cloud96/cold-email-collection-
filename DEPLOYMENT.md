# Free Cloud Deployment Guide

This document explains how to deploy the **India Professional Email Lead Finder** web frontend to a **100% permanently free platform** with your own live public URL (HTTPS enabled).

---

## Option 1: Streamlit Community Cloud (Recommended - Free Forever)

**Streamlit Community Cloud** is the official, completely free hosting platform for Streamlit applications. It gives you a custom URL (`https://<your-app>.streamlit.app`), automatic SSL, and redeploys every time you push to GitHub.

### Step-by-Step Instructions:
1. **Initialize Git & Push to GitHub**:
   In your project directory (`C:\Users\jatin\.gemini\antigravity\scratch\india_email_lead_finder`):
   ```bash
   git init
   git add .
   git commit -m "Initial commit of India Email Lead Finder"
   ```
   Create a new repository on [GitHub](https://github.com/new) (can be Public or Private) and push:
   ```bash
   git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
   git branch -M main
   git push -u origin main
   ```

2. **Deploy on Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and click **Sign In** (with GitHub).
   - Click **"Create app"** &rarr; **"I already have an app"**.
   - Select your GitHub repository, set Branch to `main`, and Main file path to `app.py`.
   - Under **Advanced settings &rarr; Secrets**, paste any environment variables (e.g., `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, `HUNTER_API_KEY`, or `LINKEDIN_LI_AT`).
   - Click **"Deploy!"**.

Your web dashboard will be live on the web in about 60 seconds!

---

## Option 2: Render.com (Free Web Service)

Render offers free web service hosting with custom domains and SSL.

### Step-by-Step Instructions:
1. Sign up at [Render.com](https://render.com/).
2. Click **"New +"** &rarr; **"Web Service"** &rarr; connect your GitHub repo.
3. Configure the settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port 10000 --server.address 0.0.0.0`
4. Under **Environment Variables**, add any keys from your `.env`.
5. Select the **Free instance type** and click **"Deploy Web Service"**.

---

## Option 3: Hugging Face Spaces (Free 16GB RAM)

1. Sign up at [Hugging Face](https://huggingface.co/).
2. Click **"New Space"**.
3. Choose **Space SDK: Streamlit**.
4. Set visibility to **Public** or **Private** (both are free).
5. Push your files to the repository provided by Hugging Face:
   ```bash
   git remote add space https://huggingface.co/spaces/<YOUR_USERNAME>/<SPACE_NAME>
   git push --force space main
   ```
Hugging Face will automatically build and launch your Streamlit dashboard.

---

## Running Locally on Your Machine

To launch the dashboard anytime on your local computer:
```powershell
cd C:\Users\jatin\.gemini\antigravity\scratch\india_email_lead_finder
.\start_gui.bat
```
*(Or run `python -m streamlit run app.py`)*

The dashboard will open automatically in your browser at `http://localhost:8501`.
