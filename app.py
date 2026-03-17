from flask import Flask, render_template, request, redirect, session, flash, send_file, jsonify
import sqlite3
import pandas as pd
import io
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
from datetime import datetime, date
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
DATABASE     = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = "attendx_secret_2024"

# ── EMAIL CONFIG ── update before use ──────────────────────────────────────
SMTP_HOST   = "smtp.gmail.com"
SMTP_PORT   = 587
SMTP_USER   = "your_email@gmail.com"    # ← your Gmail address
SMTP_PASS   = "your_app_password"       # ← Gmail App Password (not login password)
SENDER_NAME = "AttendX System"

# ═══════════════════════════ DATABASE ══════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, password TEXT, full_name TEXT DEFAULT 'Staff'
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg_no TEXT UNIQUE, name TEXT, class TEXT, dob TEXT,
        parent_email TEXT,
        total_days INTEGER DEFAULT 0, days_present INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS attendance_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg_no TEXT, date TEXT, status TEXT
    )""")
    conn.commit(); conn.close()


def create_admin():
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO admin(username,password,full_name) VALUES (?,?,?)",
                 ("admin", generate_password_hash("admin123"), "Admin Staff"))
    conn.commit(); conn.close()


init_db()
create_admin()

# ═══════════════════════════ ML PREDICTION ═════════════════════════════════
def predict_attendance(current_percent, total_days, days_present):
    remaining = max(0, 180 - total_days)
    safe_leaves = max(0, int((days_present / 0.75) - total_days)) if total_days > 0 else 0
    safe_leaves = min(safe_leaves, remaining)

    days_needed = 0
    if current_percent < 75 and total_days > 0:
        num = 0.75 * total_days - days_present
        if num > 0:
            days_needed = int(np.ceil(num / 0.25))

    if   current_percent >= 85: risk, risk_color = "Safe",     "success"
    elif current_percent >= 75: risk, risk_color = "Good",     "info"
    elif current_percent >= 60: risk, risk_color = "Warning",  "warning"
    else:                       risk, risk_color = "Critical", "danger"

    return {"current_percent": round(current_percent, 2),
            "safe_leaves": safe_leaves, "days_needed": days_needed,
            "risk": risk, "risk_color": risk_color}

# ═══════════════════════════ EMAIL HELPER ══════════════════════════════════
def send_absence_email(to_email, student_name, reg_no, absent_date, attendance_percent):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Absence Alert – {student_name} ({reg_no})"
        msg["From"]    = f"{SENDER_NAME} <{SMTP_USER}>"
        msg["To"]      = to_email

        status_text = "Your attendance is below 75%! Please attend regularly." \
                      if float(attendance_percent) < 75 else \
                      "Keep maintaining your attendance."

        html = f"""<html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
<div style="max-width:560px;margin:auto;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
  <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;">
    <h1 style="color:white;margin:0;font-size:22px;">📋 Absence Notification</h1>
    <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:14px;">AttendX Attendance Management System</p>
  </div>
  <div style="padding:28px 32px;">
    <p style="color:#374151;font-size:15px;">Dear <strong>{student_name}</strong>,</p>
    <p style="color:#6b7280;font-size:14px;line-height:1.6;">
      You were marked <strong style="color:#ef4444;">Absent</strong> on <strong>{absent_date}</strong>.
    </p>
    <div style="background:#fef3c7;border-left:4px solid #f59e0b;border-radius:6px;padding:14px 18px;margin:20px 0;">
      <p style="margin:0;color:#92400e;font-size:14px;">
        ⚠️ Current Attendance: <strong>{attendance_percent}%</strong> — {status_text}
      </p>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr style="background:#f9fafb;"><td style="padding:10px 14px;color:#6b7280;border:1px solid #e5e7eb;">Reg No</td>
        <td style="padding:10px 14px;font-weight:600;border:1px solid #e5e7eb;">{reg_no}</td></tr>
      <tr><td style="padding:10px 14px;color:#6b7280;border:1px solid #e5e7eb;">Absent Date</td>
        <td style="padding:10px 14px;color:#ef4444;font-weight:600;border:1px solid #e5e7eb;">{absent_date}</td></tr>
      <tr style="background:#f9fafb;"><td style="padding:10px 14px;color:#6b7280;border:1px solid #e5e7eb;">Attendance %</td>
        <td style="padding:10px 14px;font-weight:600;border:1px solid #e5e7eb;">{attendance_percent}%</td></tr>
    </table>
    <p style="color:#9ca3af;font-size:12px;margin-top:24px;">Automated message from AttendX. Contact your teacher if this is an error.</p>
  </div>
</div></body></html>"""

        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(SMTP_USER, to_email, msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)

# ═══════════════════════════ ROUTES ════════════════════════════════════════

@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        conn  = get_db()
        admin = conn.execute("SELECT * FROM admin WHERE username=?",
                             (request.form["username"],)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password"], request.form["password"]):
            session["admin"] = admin["username"]
            session["admin_name"] = admin["full_name"]
            return redirect("/dashboard")
        flash("Invalid username or password")
    return render_template("login.html")


@app.route("/student/login", methods=["GET","POST"])
def student_login():
    if request.method == "POST":
        reg_no = request.form["reg_no"].strip()
        dob    = request.form["dob"].strip()
        conn   = get_db()
        s      = conn.execute("SELECT * FROM students WHERE reg_no=? AND dob=?",
                              (reg_no, dob)).fetchone()
        conn.close()
        if s:
            session["student_reg"]  = reg_no
            session["student_name"] = s["name"]
            return redirect("/student/dashboard")
        flash("Invalid Registration Number or Date of Birth")
    return render_template("student_login.html")


@app.route("/student/dashboard")
def student_dashboard():
    if "student_reg" not in session:
        return redirect("/student/login")
    conn = get_db()
    s    = conn.execute("SELECT * FROM students WHERE reg_no=?",
                        (session["student_reg"],)).fetchone()
    logs = conn.execute("SELECT * FROM attendance_log WHERE reg_no=? ORDER BY date DESC LIMIT 30",
                        (session["student_reg"],)).fetchall()
    conn.close()
    if not s: return redirect("/student/login")

    total   = s["total_days"]
    present = s["days_present"]
    percent = round(present / total * 100, 2) if total > 0 else 0
    pred    = predict_attendance(percent, total, present)

    chart_dates  = [l["date"]   for l in reversed(list(logs))]
    chart_status = [1 if l["status"]=="present" else 0 for l in reversed(list(logs))]

    return render_template("student_dashboard.html", student=dict(s), percent=percent,
                           prediction=pred, logs=logs,
                           chart_dates=chart_dates, chart_status=chart_status)


@app.route("/student/logout")
def student_logout():
    session.pop("student_reg", None); session.pop("student_name", None)
    return redirect("/student/login")


@app.route("/dashboard")
def dashboard():
    if "admin" not in session: return redirect("/login")
    conn     = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    total_students = len(students)
    total_att = below_75 = critical = 0
    for s in students:
        p = (s["days_present"]/s["total_days"]) if s["total_days"]>0 else 0
        total_att += p
        if p < 0.75: below_75 += 1
        if p < 0.60: critical += 1
    avg_att = round(total_att/total_students*100, 2) if total_students else 0
    return render_template("dashboard.html", students=students,
                           total_students=total_students, average_attendance=avg_att,
                           below_75_count=below_75, critical_count=critical)


# ── UPLOAD ─────────────────────────────────────────────────────────────────
@app.route("/upload", methods=["GET","POST"])
def upload():
    if "admin" not in session: return redirect("/login")

    if request.method == "POST":
        files = request.files.getlist("file")
        mode  = request.form.get("mode", "ignore")   # ignore | replace

        if not files or all(f.filename=="" for f in files):
            flash("No files selected"); return redirect("/upload")

        inserted = updated = skipped = 0
        errors   = []
        conn     = get_db()

        for file in files:
            if not file.filename: continue
            try:
                df = pd.read_csv(file)
            except Exception:
                errors.append(f"{file.filename}: invalid CSV"); continue

            needed = {"reg_no","name","class","dob","parent_email"}
            if not needed.issubset(set(df.columns)):
                errors.append(f"{file.filename}: missing {needed-set(df.columns)}"); continue

            for _, row in df.iterrows():
                reg = str(row.get("reg_no","")).strip()
                if not reg: continue
                exists = conn.execute("SELECT id FROM students WHERE reg_no=?", (reg,)).fetchone()
                if exists:
                    if mode == "replace":
                        conn.execute("""UPDATE students SET name=?,class=?,dob=?,parent_email=?
                                        WHERE reg_no=?""",
                                     (str(row["name"]),str(row["class"]),
                                      str(row["dob"]),str(row["parent_email"]),reg))
                        updated += 1
                    else:
                        skipped += 1
                else:
                    conn.execute("""INSERT INTO students(reg_no,name,class,dob,parent_email)
                                    VALUES(?,?,?,?,?)""",
                                 (reg,str(row["name"]),str(row["class"]),
                                  str(row["dob"]),str(row["parent_email"])))
                    inserted += 1

        conn.commit(); conn.close()
        parts = []
        if inserted: parts.append(f"{inserted} added")
        if updated:  parts.append(f"{updated} updated")
        if skipped:  parts.append(f"{skipped} skipped")
        if errors:   parts.append(f"{len(errors)} file error(s)")
        flash("Upload complete: " + (", ".join(parts) or "nothing imported"))
        return redirect("/students")

    return render_template("upload.html")


# ── STUDENTS ───────────────────────────────────────────────────────────────
@app.route("/students")
def students():
    if "admin" not in session: return redirect("/login")
    search = request.args.get("search","")
    cf     = request.args.get("class_filter","")
    conn   = get_db()
    q = "SELECT * FROM students WHERE 1=1"; p = []
    if search:
        q += " AND (name LIKE ? OR reg_no LIKE ?)"; p += [f"%{search}%",f"%{search}%"]
    if cf:
        q += " AND class=?"; p.append(cf)
    rows    = conn.execute(q, p).fetchall()
    classes = conn.execute("SELECT DISTINCT class FROM students ORDER BY class").fetchall()
    conn.close()
    return render_template("students.html", students=rows,
                           classes=[c["class"] for c in classes],
                           search=search, class_filter=cf)


# ── ATTENDANCE ─────────────────────────────────────────────────────────────
@app.route("/attendance", methods=["GET","POST"])
def attendance():
    if "admin" not in session: return redirect("/login")
    conn     = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
    today    = date.today().strftime("%Y-%m-%d")
    already  = conn.execute("SELECT COUNT(*) as c FROM attendance_log WHERE date=?",
                            (today,)).fetchone()["c"] > 0

    if request.method == "POST":
        raw_input = request.form.get("absent_serial","").strip()
        absent_sns = set()
        for part in raw_input.replace(","," ").split():
            part = part.strip()
            if "-" in part:
                try:
                    a,b = part.split("-"); absent_sns.update(range(int(a), int(b)+1))
                except: pass
            else:
                try: absent_sns.add(int(part))
                except: pass

        absent_reg = {s["reg_no"] for i,s in enumerate(students,1) if i in absent_sns}

        conn.execute("UPDATE students SET total_days=total_days+1")
        absent_details = []

        for s in students:
            status = "absent" if s["reg_no"] in absent_reg else "present"
            if status == "present":
                conn.execute("UPDATE students SET days_present=days_present+1 WHERE reg_no=?",
                             (s["reg_no"],))
            else:
                new_total   = s["total_days"] + 1
                new_present = s["days_present"]
                pct = round(new_present/new_total*100, 2) if new_total>0 else 0
                absent_details.append({"reg_no":s["reg_no"],"name":s["name"],
                                       "class":s["class"],"email":s["parent_email"],
                                       "percent":pct})
            conn.execute("INSERT INTO attendance_log(reg_no,date,status) VALUES(?,?,?)",
                         (s["reg_no"], today, status))

        conn.commit(); conn.close()
        session["last_absent_details"] = absent_details
        session["last_att_date"]       = today
        flash(f"Attendance saved for {today} — {len(absent_reg)} absent")
        return redirect("/attendance/absent_report")

    conn.close()
    return render_template("attendance.html", students=students,
                           today=today, already_marked=already)


# ── ABSENT REPORT ──────────────────────────────────────────────────────────
@app.route("/attendance/absent_report")
def absent_report():
    if "admin" not in session: return redirect("/login")
    return render_template("absent_report.html",
                           absent_details=session.get("last_absent_details",[]),
                           att_date=session.get("last_att_date",""),
                           email_results=None)


@app.route("/attendance/send_email", methods=["POST"])
def send_emails():
    if "admin" not in session: return redirect("/login")
    reg_nos  = request.form.getlist("send_to")
    details  = session.get("last_absent_details",[])
    att_date = session.get("last_att_date","")
    results  = []
    for d in details:
        if d["reg_no"] in reg_nos:
            ok, msg = send_absence_email(d["email"],d["name"],d["reg_no"],att_date,d["percent"])
            results.append({"name":d["name"],"email":d["email"],"success":ok,"msg":msg})
    sent = sum(1 for r in results if r["success"])
    flash(f"Emails: {sent} sent, {len(results)-sent} failed.")
    return render_template("absent_report.html",
                           absent_details=details, att_date=att_date, email_results=results)


@app.route("/attendance/export_absent")
def export_absent():
    if "admin" not in session: return redirect("/login")
    details  = session.get("last_absent_details",[])
    att_date = session.get("last_att_date","today")
    df       = pd.DataFrame(details)
    out      = io.BytesIO(); df.to_excel(out, index=False); out.seek(0)
    return send_file(out, download_name=f"absent_{att_date}.xlsx", as_attachment=True)


# ── ANALYTICS ──────────────────────────────────────────────────────────────
@app.route("/analytics")
def analytics():
    if "admin" not in session: return redirect("/login")
    conn     = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    labels=[]; attendance=[]; colors=[]
    for s in students:
        pct = round(s["days_present"]/s["total_days"]*100,2) if s["total_days"]>0 else 0
        labels.append(s["name"]); attendance.append(pct)
        colors.append("#22c55e" if pct>=85 else "#3b82f6" if pct>=75 else "#f59e0b" if pct>=60 else "#ef4444")
    return render_template("analytics.html", labels=labels, attendance=attendance, colors=colors)


# ── REPORTS ────────────────────────────────────────────────────────────────
@app.route("/reports")
def reports():
    if "admin" not in session: return redirect("/login")
    conn     = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    classes  = conn.execute("SELECT DISTINCT class FROM students ORDER BY class").fetchall()
    conn.close()
    data = []
    for s in students:
        pct  = round(s["days_present"]/s["total_days"]*100,2) if s["total_days"]>0 else 0
        pred = predict_attendance(pct, s["total_days"], s["days_present"])
        data.append({"reg_no":s["reg_no"],"name":s["name"],"class":s["class"],
                     "total_days":s["total_days"],"days_present":s["days_present"],
                     "percent":pct, **pred})
    data.sort(key=lambda x:x["percent"])
    return render_template("reports.html", report_data=data,
                           classes=[c["class"] for c in classes])


@app.route("/export_report")
def export_report():
    if "admin" not in session: return redirect("/login")
    cf   = request.args.get("class","")
    conn = get_db()
    rows = conn.execute("SELECT * FROM students WHERE class=?" if cf else "SELECT * FROM students",
                        (cf,) if cf else ()).fetchall()
    conn.close()
    data = []
    for s in rows:
        pct  = round(s["days_present"]/s["total_days"]*100,2) if s["total_days"]>0 else 0
        pred = predict_attendance(pct,s["total_days"],s["days_present"])
        data.append({"Reg No":s["reg_no"],"Name":s["name"],"Class":s["class"],
                     "Total Days":s["total_days"],"Days Present":s["days_present"],
                     "Attendance %":pct,"Safe Leave Days":pred["safe_leaves"],
                     "Days Needed to 75%":pred["days_needed"],"Risk Level":pred["risk"]})
    df  = pd.DataFrame(data); out = io.BytesIO()
    df.to_excel(out,index=False); out.seek(0)
    return send_file(out, download_name="attendance_report.xlsx", as_attachment=True)


@app.route("/logout")
def logout():
    session.pop("admin",None); session.pop("admin_name",None)
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
