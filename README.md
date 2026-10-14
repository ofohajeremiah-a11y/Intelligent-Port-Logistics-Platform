# Intelligent Port Logistics Optimization Platform

A student prototype for the Queen Elizabeth II Quay / Freetown Port. It is a decision-support application: it records port logistics information and recommends schedules/allocations; it does **not** control vessels, cranes, trucks, or official port systems.

## Current prototype features

- Login and role-based access (Administrator, Port Operations Officer, Terminal/Logistics Officer, Cargo/Container Officer, Truck/Transport Officer, Management). All private pages, including the dashboard, redirect to the login page until a user signs in. The top bar and sidebar both provide sign-out links.
- Dashboard summaries and operational alerts.
- Vessel and berth records.
- Container and cargo records, status tracking, and movement history.
- Yard locations and capacity-aware allocation recommendations.
- Truck records and appointment scheduling.
- Basic rule-based berth scheduling recommendations.
- Simple container-flow forecast from recorded movement data (uses a transparent baseline; not validated against actual port data).
- CSV export for containers and vessels.
- Seeded demo data for a classroom demonstration.

## Technology

Python + Flask, Flask-SQLAlchemy, HTML/CSS/Bootstrap, JavaScript, SQLite for a quick local start, and MySQL support through `DATABASE_URL`. Pandas, NumPy, and scikit-learn are included for future analytics work.

### Why SQLite locally?

It makes the first run easy without installing a database server. The application is configured to use MySQL when you supply a MySQL `DATABASE_URL`. For a public deployment, use a managed database and set `DATABASE_URL` in Render. Do not commit passwords or `.env`.

## Run on Windows / VS Code

1. Install Python 3.11 or 3.12 and Git.
2. Extract this project folder.
3. Open the folder in VS Code (`File > Open Folder`).
4. Open Terminal > New Terminal and run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   Copy-Item .env.example .env
   python seed_demo.py
   python app.py
   ```

5. Open `http://127.0.0.1:5000`.
6. The login page appears before the dashboard. Demo login: `admin` / `PortDemo2026!`
7. Use the **Logout** button in the top bar (or **Sign out** in the sidebar) to end the session. After logging out, private pages redirect back to login.

Change the demo password before any public use. Demo data is fictional.

If PowerShell blocks activation, run this once in the same terminal:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
Then activate the environment again.

## Database setup

Local default: SQLite database file `instance/port_logistics.db`.

To use MySQL, create a database and set `.env` like:

```env
DATABASE_URL=mysql+pymysql://USERNAME:PASSWORD@HOST:3306/DATABASE_NAME
```

URL-encode special characters in the password. The database account should have permission to create tables. Restart the app after changing `.env`.

## Push to GitHub

1. Create an empty public or private repository on GitHub.
2. In VS Code terminal, from this folder:

   ```powershell
   git init
   git add .
   git commit -m "Initial port logistics platform"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
   git push -u origin main
   ```

Replace the remote URL with your own repository URL. Never upload `.env`.

## Deploy on Render

1. Push the project to GitHub.
2. In Render, choose **New + > Web Service**, connect the repository, and select Python.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `SECRET_KEY` with a long random value.
6. Add `DATABASE_URL` for a persistent managed database.
7. Deploy and open the service URL.

**Important persistence note:** Render's local filesystem is not a safe permanent database location for a production deployment. Do not rely on the SQLite file on an ephemeral web-service disk for lasting data. Configure a managed MySQL database (or another supported managed SQL database) before relying on online data. For an educational demo, resettable seed data is acceptable.

## Prototype limitations

- Sample records are fictional and must not be presented as actual Freetown Port operational data.
- The berth and yard recommendations are rule-based prototype recommendations, not a certified port scheduling system.
- Forecast quality depends on adequate, reliable historical data.
- No integration with customs, shipping-line systems, or proprietary terminal operating systems is included.
- The demo administrator account must be changed before public use.
