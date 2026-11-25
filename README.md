# MediTrack – Professional Academic Project

A local Flask + SQLite medicine routine organizer for a BCA project. It demonstrates database CRUD, authentication, browser reminders, dose logs, reporting and prompt engineering.

## Run on Windows / VS Code
1. Install Python 3.10+ and VS Code.
2. Extract the ZIP and open this folder in VS Code.
3. Open Terminal (PowerShell) in this folder.
4. Run:
   ```powershell
   py -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   py app.py
   ```
5. Visit http://127.0.0.1:5000 and register your own account.

SQLite database is created automatically at `instance/meditrack.db`.

## Optional Gemini integration
The AI assistant page works as a prompt-engineering demonstration without an API key. To enable a live Gemini response:
1. Copy `.env.example` to `.env`.
2. Set `GEMINI_API_KEY` to your own key and optionally set `GEMINI_MODEL`.
3. Install python-dotenv (`pip install python-dotenv`) and add `from dotenv import load_dotenv; load_dotenv()` near the imports in app.py, or set environment variables in the terminal before running.
4. Restart the app. Never publish your API key or include it in your report screenshots.

## Main modules
- Account registration and login with hashed passwords
- Medicine add, edit, delete and date range
- Dashboard and daily schedule
- Browser reminders (dashboard must remain open; notifications permission required)
- Taken/Missed dose log
- History and 30-day adherence report
- Prompt-engineering assistant with optional Gemini API

## Safety and limitations
This is an academic organizer, not a medical device. Enter only information supplied by a healthcare professional. The AI assistant only formats user-provided text; verify all output against the original prescription. It does not diagnose, prescribe or change dosage. Browser reminders are not guaranteed if the browser/device is closed or notifications are disabled.
