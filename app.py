import os, sqlite3, json, re
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.abspath(os.path.dirname(__file__))
DB = os.path.join(ROOT, "instance", "meditrack.db")
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-before-deployment")

def connect():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS medicines(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          name TEXT NOT NULL, dosage TEXT NOT NULL, medicine_time TEXT NOT NULL,
          instructions TEXT DEFAULT '', start_date TEXT NOT NULL, end_date TEXT DEFAULT '',
          frequency TEXT DEFAULT 'Daily', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS dose_logs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          medicine_id INTEGER NOT NULL, dose_date TEXT NOT NULL, dose_time TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('Taken','Missed')),
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(medicine_id,dose_date,dose_time),
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
          FOREIGN KEY(medicine_id) REFERENCES medicines(id) ON DELETE CASCADE);
        """)

def logged_in(fn):
    @wraps(fn)
    def inner(*a, **kw):
        if not session.get("uid"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return inner

def active_medicines(user_id, on_date=None):
    on_date = on_date or date.today().isoformat()
    with connect() as db:
        return db.execute("""SELECT * FROM medicines WHERE user_id=?
          AND start_date<=? AND (end_date='' OR end_date>=?)
          ORDER BY medicine_time""",(user_id,on_date,on_date)).fetchall()

@app.context_processor
def common():
    return {"today_label": date.today().strftime("%A, %d %B %Y")}

@app.route("/")
def index():
    return redirect(url_for("dashboard")) if session.get("uid") else render_template("landing.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or not email or len(password)<8:
            flash("Enter your name and email. Password must be at least 8 characters.", "error")
            return render_template("auth.html", mode="register")
        try:
            with connect() as db:
                db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                    (name,email,generate_password_hash(password)))
            flash("Account created successfully. Please sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "error")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        with connect() as db:
            user=db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password_hash"],password):
            session.clear()
            session["uid"],session["name"]=user["id"],user["name"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@logged_in
def dashboard():
    meds=active_medicines(session["uid"])
    today=date.today().isoformat()
    with connect() as db:
        logs=db.execute("SELECT medicine_id,status FROM dose_logs WHERE user_id=? AND dose_date=?",
                        (session["uid"],today)).fetchall()
        total=db.execute("SELECT COUNT(*) n FROM medicines WHERE user_id=?",(session["uid"],)).fetchone()["n"]
        week=db.execute("""SELECT status,COUNT(*) n FROM dose_logs WHERE user_id=?
          AND dose_date>=? GROUP BY status""",(session["uid"],(date.today()-timedelta(days=6)).isoformat())).fetchall()
    status={r["medicine_id"]:r["status"] for r in logs}
    counts={r["status"]:r["n"] for r in week}
    return render_template("dashboard.html",medicines=meds,status=status,total=total,
       taken=counts.get("Taken",0),missed=counts.get("Missed",0))

@app.route("/medicines")
@logged_in
def medicines():
    with connect() as db:
        rows=db.execute("SELECT * FROM medicines WHERE user_id=? ORDER BY medicine_time",(session["uid"],)).fetchall()
    return render_template("medicines.html",medicines=rows)

@app.route("/medicine/new",methods=["GET","POST"])
@app.route("/medicine/<int:mid>/edit",methods=["GET","POST"])
@logged_in
def medicine_form(mid=None):
    med=None
    if mid:
        with connect() as db: med=db.execute("SELECT * FROM medicines WHERE id=? AND user_id=?",(mid,session["uid"])).fetchone()
        if not med: flash("Medicine not found.","error"); return redirect(url_for("medicines"))
    if request.method=="POST":
        values=[request.form.get(k,"").strip() for k in ["name","dosage","medicine_time","instructions","start_date","end_date","frequency"]]
        name,dosage,tm,ins,start,end,freq=values
        if not name or not dosage or not tm or not start:
            flash("Medicine, prescribed dose, time and start date are required.","error")
        elif end and end<start:
            flash("End date cannot be earlier than start date.","error")
        else:
            with connect() as db:
                if mid:
                    db.execute("""UPDATE medicines SET name=?,dosage=?,medicine_time=?,instructions=?,
                      start_date=?,end_date=?,frequency=? WHERE id=? AND user_id=?""",
                      (*values,mid,session["uid"]))
                else:
                    db.execute("""INSERT INTO medicines(user_id,name,dosage,medicine_time,instructions,start_date,end_date,frequency)
                      VALUES(?,?,?,?,?,?,?,?)""",(session["uid"],*values))
            flash("Medicine details saved.","success")
            return redirect(url_for("medicines"))
    return render_template("medicine_form.html",medicine=med)

@app.route("/medicine/<int:mid>/delete",methods=["POST"])
@logged_in
def delete_medicine(mid):
    with connect() as db: db.execute("DELETE FROM medicines WHERE id=? AND user_id=?",(mid,session["uid"]))
    flash("Medicine removed.","success")
    return redirect(url_for("medicines"))

@app.route("/dose/<int:mid>/<status>",methods=["POST"])
@logged_in
def dose(mid,status):
    if status not in ("Taken","Missed"): return jsonify(ok=False),400
    today=date.today().isoformat()
    with connect() as db:
        med=db.execute("SELECT * FROM medicines WHERE id=? AND user_id=?",(mid,session["uid"])).fetchone()
        if not med: return jsonify(ok=False,message="Medicine not found"),404
        db.execute("""INSERT INTO dose_logs(user_id,medicine_id,dose_date,dose_time,status)
          VALUES(?,?,?,?,?) ON CONFLICT(medicine_id,dose_date,dose_time)
          DO UPDATE SET status=excluded.status,updated_at=CURRENT_TIMESTAMP""",
          (session["uid"],mid,today,med["medicine_time"],status))
    return jsonify(ok=True,message=f"Marked {status.lower()}.")

@app.route("/history")
@logged_in
def history():
    with connect() as db:
        rows=db.execute("""SELECT l.*,m.name,m.dosage FROM dose_logs l JOIN medicines m ON m.id=l.medicine_id
          WHERE l.user_id=? ORDER BY l.dose_date DESC,l.dose_time DESC LIMIT 200""",(session["uid"],)).fetchall()
    return render_template("history.html",rows=rows)

@app.route("/reports")
@logged_in
def reports():
    start=(date.today()-timedelta(days=29)).isoformat()
    with connect() as db:
        rows=db.execute("""SELECT status,COUNT(*) n FROM dose_logs WHERE user_id=? AND dose_date>=?
          GROUP BY status""",(session["uid"],start)).fetchall()
        daily=db.execute("""SELECT dose_date,status,COUNT(*) n FROM dose_logs WHERE user_id=? AND dose_date>=?
          GROUP BY dose_date,status ORDER BY dose_date""",(session["uid"],start)).fetchall()
    c={r["status"]:r["n"] for r in rows}; taken=c.get("Taken",0); missed=c.get("Missed",0)
    total=taken+missed; rate=round(taken*100/total) if total else 0
    return render_template("reports.html",taken=taken,missed=missed,total=total,rate=rate,daily=daily)

@app.route("/assistant",methods=["GET","POST"])
@logged_in
def assistant():
    result=None; raw=""
    if request.method=="POST":
        raw=request.form.get("schedule","").strip()
        if not raw:
            flash("Paste a schedule to organize.","error")
        else:
            prompt=("You are MediTrack, a careful schedule-formatting assistant. Extract only details explicitly "
            "present in the user's text. Return JSON array with medicine_name, prescribed_dose, time, instructions. "
            "For missing details write 'Not specified'. Never diagnose, recommend, infer, change dose, or invent a time. "
            "Tell the user to compare every field with the original clinician instruction before saving.\\n"
            "USER TEXT:\\n"+raw)
            key=os.getenv("GEMINI_API_KEY","")
            model=os.getenv("GEMINI_MODEL","gemini-2.0-flash")
            if key:
                try:
                    import urllib.request
                    endpoint=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    payload={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1}}
                    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
                    with urllib.request.urlopen(req,timeout=25) as resp: data=json.loads(resp.read().decode())
                    result=data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception as e:
                    result="AI service could not be reached. Check your API key, model setting and internet connection.\\n\\nPrompt prepared:\\n"+prompt
            else:
                result="AI mode is not connected yet because GEMINI_API_KEY is not configured.\\n\\nYour prompt is ready for the AI service:\\n"+prompt
            flash("Draft generated. Verify every detail against the original prescription before saving.", "info")
    return render_template("assistant.html",result=result,raw=raw)

@app.route("/api/reminders")
@logged_in
def reminders():
    today=date.today().isoformat()
    rows=active_medicines(session["uid"],today)
    return jsonify([{"id":r["id"],"name":r["name"],"time":r["medicine_time"],"dosage":r["dosage"]} for r in rows])

@app.errorhandler(404)
def not_found(e): return render_template("error.html",code=404,message="We couldn't find that page."),404

if __name__=="__main__":
    init_db()
    app.run(debug=True)
