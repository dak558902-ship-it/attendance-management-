# AttendX – Enhanced Attendance Management System

## What's New in This Version

### 🔐 Dual Login System
- **Staff Login** → `/login` — Username + Password (default: admin / admin123)
- **Student Login** → `/student/login` — Registration Number + Date of Birth (YYYY-MM-DD)

### 🤖 AI/ML Features (No external model needed)
- **Safe Leave Days** — Calculates exactly how many more days a student can miss and stay ≥75%
- **Days to Recover** — If below 75%, shows consecutive days needed to recover
- **Risk Levels** — Safe / Good / Warning / Critical per student
- **Staff AI Reports** — Full class overview with all predictions, filterable

### 📊 Student Portal
- Personal attendance dashboard with circular progress ring
- Attendance trend chart (last 30 days)
- Clear advice: "You can take X more leaves safely" or "Attend next N days to reach 75%"
- Attendance log history

### 👨‍🏫 Staff Portal
- Dashboard with stats: total, avg attendance, below 75%, critical count
- AI Reports page with risk filter, class filter, searchable
- Analytics with bar + doughnut charts
- Export to Excel with all ML columns

---

## Setup Instructions

### 1. Install Dependencies
```bash
pip install flask pandas openpyxl werkzeug numpy
```

### 2. Run the App
```bash
python app.py
```

### 3. Access
- Staff Login: http://localhost:5000/login
  - Username: `admin`, Password: `admin123`
- Student Login: http://localhost:5000/student/login
  - Reg No: (from CSV), DOB: (from CSV, format YYYY-MM-DD)

---

## CSV Upload Format

Upload at `/upload` with these columns:

| Column | Description |
|--------|-------------|
| `reg_no` | Unique registration number |
| `name` | Full student name |
| `class` | Class/section |
| `dob` | Date of birth — YYYY-MM-DD (student's password) |
| `parent_email` | Email address |

**Sample file: `sample_students.csv`**

---

## ML Prediction Logic

### Safe Leave Days
```
safe_leaves = floor(days_present / 0.75) - total_days
```
This gives the number of additional days a student can miss while staying ≥75%.

### Days Needed to Reach 75%
```
days_needed = ceil((0.75 × total_days - days_present) / 0.25)
```
Consecutive days of attendance needed to hit exactly 75%.

### Risk Levels
| Level | Condition |
|-------|-----------|
| Safe | ≥ 85% |
| Good | 75–85% |
| Warning | 60–75% |
| Critical | < 60% |

---

## File Structure
```
attendx/
├── app.py                  # Main Flask app
├── database.db             # Auto-created SQLite DB
├── sample_students.csv     # Test data
└── templates/
    ├── base.html           # Staff layout
    ├── login.html          # Staff login
    ├── student_login.html  # Student login
    ├── student_dashboard.html  # Student view
    ├── dashboard.html      # Staff dashboard
    ├── students.html       # Students list
    ├── attendance.html     # Mark attendance
    ├── analytics.html      # Charts
    ├── reports.html        # AI reports
    └── upload.html         # CSV upload
```
