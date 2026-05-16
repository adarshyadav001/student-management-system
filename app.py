from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, json
from functools import wraps
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sms_super_secret_key_2024_xK9mP2qL!')

# Always resolve DB path relative to this file, works on local & Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, 'database.db')

# ── DB helpers ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            email TEXT,
            phone TEXT,
            course TEXT NOT NULL,
            year INTEGER NOT NULL,
            section TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            course TEXT NOT NULL,
            year INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'present',
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            UNIQUE(student_id, subject_id, date)
        );
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            internal INTEGER DEFAULT 0,
            external INTEGER DEFAULT 0,
            max_internal INTEGER DEFAULT 40,
            max_external INTEGER DEFAULT 60,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            UNIQUE(student_id, subject_id)
        );
    ''')
    # Seed admin
    try:
        c.execute("INSERT INTO admins(username, password) VALUES(?,?)",
                  ('admin', generate_password_hash('admin123')))
    except Exception:
        pass
    # Seed subjects
    subjects = [
        ('Mathematics', 'B.Tech', 1), ('Physics', 'B.Tech', 1),
        ('Chemistry', 'B.Tech', 1), ('English', 'B.Tech', 1),
        ('Programming', 'B.Tech', 1), ('Data Structures', 'B.Tech', 2),
        ('Algorithms', 'B.Tech', 2), ('DBMS', 'B.Tech', 2),
        ('Networks', 'B.Tech', 3), ('OS', 'B.Tech', 3),
        ('Mathematics', 'BCA', 1), ('Programming', 'BCA', 1),
        ('Web Dev', 'BCA', 2), ('Database', 'BCA', 2),
        ('Statistics', 'MCA', 1), ('Advanced Algorithms', 'MCA', 1),
    ]
    for s in subjects:
        try:
            c.execute("INSERT INTO subjects(name,course,year) VALUES(?,?,?)", s)
        except Exception:
            pass
    conn.commit()
    conn.close()

# ── Auth decorator ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── Grade logic ─────────────────────────────────────────────────────────────────
def get_grade(pct):
    if pct >= 90: return 'O'
    if pct >= 80: return 'A+'
    if pct >= 70: return 'A'
    if pct >= 60: return 'B+'
    if pct >= 50: return 'B'
    if pct >= 40: return 'C'
    return 'F'

# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], password):
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['username']
            return redirect(url_for('dashboard'))
        error = 'Invalid credentials. Try admin / admin123'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    courses = conn.execute("SELECT course, COUNT(*) as cnt FROM students GROUP BY course").fetchall()
    year_dist = conn.execute("SELECT year, COUNT(*) as cnt FROM students GROUP BY year").fetchall()

    # Top performers by average marks %
    top = conn.execute('''
        SELECT s.name, s.roll_no, s.course,
               ROUND(AVG(CAST(m.internal+m.external AS REAL)/(m.max_internal+m.max_external)*100),1) as avg_pct
        FROM students s JOIN marks m ON s.id=m.student_id
        GROUP BY s.id ORDER BY avg_pct DESC LIMIT 5
    ''').fetchall()

    # Pass/fail
    pass_fail = conn.execute('''
        SELECT
          SUM(CASE WHEN avg_pct >= 40 THEN 1 ELSE 0 END) as passed,
          SUM(CASE WHEN avg_pct < 40 THEN 1 ELSE 0 END) as failed
        FROM (
          SELECT s.id,
                 ROUND(AVG(CAST(m.internal+m.external AS REAL)/(m.max_internal+m.max_external)*100),1) as avg_pct
          FROM students s JOIN marks m ON s.id=m.student_id
          GROUP BY s.id
        )
    ''').fetchone()

    # Monthly attendance (last 6 months)
    monthly_att = conn.execute('''
        SELECT strftime('%Y-%m', date) as month,
               ROUND(100.0*SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)/COUNT(*),1) as pct
        FROM attendance GROUP BY month ORDER BY month DESC LIMIT 6
    ''').fetchall()

    conn.close()
    return render_template('dashboard.html',
        total_students=total_students,
        courses=[dict(r) for r in courses],
        year_dist=[dict(r) for r in year_dist],
        top_performers=[dict(r) for r in top],
        pass_fail=dict(pass_fail) if pass_fail else {'passed':0,'failed':0},
        monthly_att=list(reversed([dict(r) for r in monthly_att])))

# ══════════════════════════════════════════════════════════════════════════════
# STUDENTS
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/students')
@login_required
def students():
    q = request.args.get('q','').strip()
    course = request.args.get('course','')
    year = request.args.get('year','')
    section = request.args.get('section','')

    sql = "SELECT * FROM students WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR roll_no LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if course:
        sql += " AND course=?"
        params.append(course)
    if year:
        sql += " AND year=?"
        params.append(year)
    if section:
        sql += " AND section=?"
        params.append(section)
    sql += " ORDER BY name"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    courses = conn.execute("SELECT DISTINCT course FROM students ORDER BY course").fetchall()
    conn.close()
    return render_template('students.html', students=rows,
        courses=[r['course'] for r in courses],
        q=q, filter_course=course, filter_year=year, filter_section=section)

@app.route('/students/add', methods=['GET','POST'])
@login_required
def add_student():
    conn = get_db()
    courses = conn.execute("SELECT DISTINCT course FROM subjects ORDER BY course").fetchall()
    if request.method == 'POST':
        try:
            conn.execute('''INSERT INTO students(name,roll_no,email,phone,course,year,section)
                            VALUES(?,?,?,?,?,?,?)''', (
                request.form['name'].strip(),
                request.form['roll_no'].strip().upper(),
                request.form['email'].strip(),
                request.form['phone'].strip(),
                request.form['course'],
                int(request.form['year']),
                request.form['section'].strip().upper(),
            ))
            conn.commit()
            flash('Student added successfully!', 'success')
            conn.close()
            return redirect(url_for('students'))
        except sqlite3.IntegrityError:
            flash('Roll number already exists.', 'error')
    conn.close()
    return render_template('add_student.html',
        courses=[r['course'] for r in courses])

@app.route('/students/edit/<int:sid>', methods=['GET','POST'])
@login_required
def edit_student(sid):
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    courses = conn.execute("SELECT DISTINCT course FROM subjects ORDER BY course").fetchall()
    if not student:
        conn.close()
        return redirect(url_for('students'))
    if request.method == 'POST':
        try:
            conn.execute('''UPDATE students SET name=?,roll_no=?,email=?,phone=?,course=?,year=?,section=?
                            WHERE id=?''', (
                request.form['name'].strip(),
                request.form['roll_no'].strip().upper(),
                request.form['email'].strip(),
                request.form['phone'].strip(),
                request.form['course'],
                int(request.form['year']),
                request.form['section'].strip().upper(),
                sid,
            ))
            conn.commit()
            flash('Student updated.', 'success')
            conn.close()
            return redirect(url_for('students'))
        except sqlite3.IntegrityError:
            flash('Roll number conflict.', 'error')
    conn.close()
    return render_template('edit_student.html', student=student,
        courses=[r['course'] for r in courses])

@app.route('/students/delete/<int:sid>', methods=['POST'])
@login_required
def delete_student(sid):
    conn = get_db()
    conn.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM marks WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM students WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    flash('Student deleted.', 'success')
    return redirect(url_for('students'))

# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/attendance', methods=['GET','POST'])
@login_required
def attendance():
    conn = get_db()
    courses = conn.execute("SELECT DISTINCT course FROM subjects ORDER BY course").fetchall()
    selected_course = request.args.get('course') or (courses[0]['course'] if courses else '')
    selected_year   = request.args.get('year','1')
    selected_date   = request.args.get('date', date.today().isoformat())

    subjects = conn.execute("SELECT * FROM subjects WHERE course=? AND year=?",
                            (selected_course, selected_year)).fetchall()
    selected_subject = request.args.get('subject_id', str(subjects[0]['id']) if subjects else '')

    students_list = []
    if selected_subject:
        students_list = conn.execute(
            "SELECT * FROM students WHERE course=? AND year=? ORDER BY roll_no",
            (selected_course, selected_year)).fetchall()
        existing = {str(r['student_id']): r['status']
                    for r in conn.execute(
                        "SELECT student_id, status FROM attendance WHERE subject_id=? AND date=?",
                        (selected_subject, selected_date)).fetchall()}
    else:
        existing = {}

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        att_date   = request.form.get('att_date')
        for s in students_list:
            status = request.form.get(f'status_{s["id"]}', 'absent')
            conn.execute('''INSERT INTO attendance(student_id,subject_id,date,status)
                            VALUES(?,?,?,?)
                            ON CONFLICT(student_id,subject_id,date) DO UPDATE SET status=excluded.status''',
                         (s['id'], subject_id, att_date, status))
        conn.commit()
        flash('Attendance saved!', 'success')
        conn.close()
        return redirect(url_for('attendance', course=selected_course,
                                year=selected_year, subject_id=subject_id, date=att_date))

    # Monthly report for selected subject
    monthly = []
    if selected_subject:
        monthly = conn.execute('''
            SELECT s.name, s.roll_no,
                   COUNT(*) as total,
                   SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) as present,
                   ROUND(100.0*SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)/COUNT(*),1) as pct
            FROM students s JOIN attendance a ON s.id=a.student_id
            WHERE a.subject_id=?
            GROUP BY s.id ORDER BY pct DESC
        ''', (selected_subject,)).fetchall()

    conn.close()
    return render_template('attendance.html',
        courses=[r['course'] for r in courses],
        subjects=subjects, students=students_list,
        existing=existing, monthly=monthly,
        selected_course=selected_course, selected_year=selected_year,
        selected_date=selected_date, selected_subject=selected_subject)

# ══════════════════════════════════════════════════════════════════════════════
# MARKS
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/marks', methods=['GET','POST'])
@login_required
def marks():
    conn = get_db()
    courses = conn.execute("SELECT DISTINCT course FROM subjects ORDER BY course").fetchall()
    selected_course = request.args.get('course') or (courses[0]['course'] if courses else '')
    selected_year   = request.args.get('year','1')

    subjects = conn.execute("SELECT * FROM subjects WHERE course=? AND year=?",
                            (selected_course, selected_year)).fetchall()
    selected_subject = request.args.get('subject_id', str(subjects[0]['id']) if subjects else '')

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        students_ids = request.form.getlist('student_id')
        for sid in students_ids:
            internal = int(request.form.get(f'internal_{sid}', 0))
            external = int(request.form.get(f'external_{sid}', 0))
            conn.execute('''INSERT INTO marks(student_id,subject_id,internal,external)
                            VALUES(?,?,?,?)
                            ON CONFLICT(student_id,subject_id)
                            DO UPDATE SET internal=excluded.internal, external=excluded.external''',
                         (sid, subject_id, internal, external))
        conn.commit()
        flash('Marks saved!', 'success')
        conn.close()
        return redirect(url_for('marks', course=selected_course,
                                year=selected_year, subject_id=subject_id))

    rows = []
    if selected_subject:
        rows = conn.execute('''
            SELECT s.id, s.name, s.roll_no,
                   COALESCE(m.internal,0) as internal,
                   COALESCE(m.external,0) as external,
                   COALESCE(m.max_internal,40) as max_internal,
                   COALESCE(m.max_external,60) as max_external
            FROM students s
            LEFT JOIN marks m ON s.id=m.student_id AND m.subject_id=?
            WHERE s.course=? AND s.year=?
            ORDER BY s.roll_no
        ''', (selected_subject, selected_course, selected_year)).fetchall()

    def enrich(r):
        d = dict(r)
        total = d['internal'] + d['external']
        max_t = d['max_internal'] + d['max_external']
        d['total'] = total
        d['max_total'] = max_t
        d['pct'] = round(total / max_t * 100, 1) if max_t else 0
        d['grade'] = get_grade(d['pct'])
        return d

    conn.close()
    return render_template('marks.html',
        courses=[r['course'] for r in courses],
        subjects=subjects, rows=[enrich(r) for r in rows],
        selected_course=selected_course, selected_year=selected_year,
        selected_subject=selected_subject)

# ── API: subjects by course+year ────────────────────────────────────────────
@app.route('/api/subjects')
@login_required
def api_subjects():
    course = request.args.get('course','')
    year   = request.args.get('year','1')
    conn   = get_db()
    rows   = conn.execute("SELECT * FROM subjects WHERE course=? AND year=?", (course, year)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# Always initialize DB on startup — works for both local and Render
init_db()

if __name__ == '__main__':
    app.run(debug=True)