from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os, sqlite3
from functools import wraps
from datetime import date

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sms_super_secret_key_2024_xK9mP2qL!')

DATABASE_URL = os.environ.get('DATABASE_URL')
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB    = os.path.join(BASE_DIR, 'database.db')
USE_PG       = bool(DATABASE_URL)

# ── DB connection ───────────────────────────────────────────
def get_db():
    if USE_PG:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def db_fetchall(conn, sql, params=()):
    c = conn.cursor()
    c.execute(sql.replace('?','%s') if USE_PG else sql, params)
    return [dict(r) for r in c.fetchall()]

def db_fetchone(conn, sql, params=()):
    c = conn.cursor()
    c.execute(sql.replace('?','%s') if USE_PG else sql, params)
    r = c.fetchone()
    return dict(r) if r else None

def db_exec(conn, sql, params=()):
    c = conn.cursor()
    c.execute(sql.replace('?','%s') if USE_PG else sql, params)
    return c

# ── init_db ─────────────────────────────────────────────────
def init_db():
    conn = get_db()
    c = conn.cursor()
    if USE_PG:
        for stmt in [
            '''CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, roll_no TEXT UNIQUE NOT NULL,
                email TEXT, phone TEXT, course TEXT NOT NULL, year INTEGER NOT NULL,
                section TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, course TEXT NOT NULL, year INTEGER NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
                date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'present',
                UNIQUE(student_id, subject_id, date))''',
            '''CREATE TABLE IF NOT EXISTS marks (
                id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
                internal INTEGER DEFAULT 0, external INTEGER DEFAULT 0,
                max_internal INTEGER DEFAULT 40, max_external INTEGER DEFAULT 60,
                UNIQUE(student_id, subject_id))''',
        ]:
            c.execute(stmt)
        conn.commit()
        try:
            c.execute("INSERT INTO admins(username,password) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                      ('admin', generate_password_hash('admin123')))
            conn.commit()
        except Exception: conn.rollback()
        for s in [
            ('Mathematics','B.Tech',1),('Physics','B.Tech',1),('Chemistry','B.Tech',1),
            ('English','B.Tech',1),('Programming','B.Tech',1),('Data Structures','B.Tech',2),
            ('Algorithms','B.Tech',2),('DBMS','B.Tech',2),('Networks','B.Tech',3),('OS','B.Tech',3),
            ('Mathematics','BCA',1),('Programming','BCA',1),('Web Dev','BCA',2),('Database','BCA',2),
            ('Statistics','MCA',1),('Advanced Algorithms','MCA',1),
        ]:
            try:
                c.execute("INSERT INTO subjects(name,course,year) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING", s)
                conn.commit()
            except Exception: conn.rollback()
    else:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, roll_no TEXT UNIQUE NOT NULL, email TEXT, phone TEXT,
                course TEXT NOT NULL, year INTEGER NOT NULL, section TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, course TEXT NOT NULL, year INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
                date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'present',
                UNIQUE(student_id, subject_id, date));
            CREATE TABLE IF NOT EXISTS marks (id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
                internal INTEGER DEFAULT 0, external INTEGER DEFAULT 0,
                max_internal INTEGER DEFAULT 40, max_external INTEGER DEFAULT 60,
                UNIQUE(student_id, subject_id));
        ''')
        try:
            c.execute("INSERT INTO admins(username,password) VALUES(?,?)",
                      ('admin', generate_password_hash('admin123')))
        except Exception: pass
        for s in [
            ('Mathematics','B.Tech',1),('Physics','B.Tech',1),('Chemistry','B.Tech',1),
            ('English','B.Tech',1),('Programming','B.Tech',1),('Data Structures','B.Tech',2),
            ('Algorithms','B.Tech',2),('DBMS','B.Tech',2),('Networks','B.Tech',3),('OS','B.Tech',3),
            ('Mathematics','BCA',1),('Programming','BCA',1),('Web Dev','BCA',2),('Database','BCA',2),
            ('Statistics','MCA',1),('Advanced Algorithms','MCA',1),
        ]:
            try: c.execute("INSERT INTO subjects(name,course,year) VALUES(?,?,?)", s)
            except Exception: pass
        conn.commit()
    conn.close()

# ── Auth ─────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_grade(pct):
    if pct>=90: return 'O'
    if pct>=80: return 'A+'
    if pct>=70: return 'A'
    if pct>=60: return 'B+'
    if pct>=50: return 'B'
    if pct>=40: return 'C'
    return 'F'

# ══════════════════════════════════════════════════════════════
# LOGIN / LOGOUT
# ══════════════════════════════════════════════════════════════
@app.route('/', methods=['GET','POST'])
@app.route('/login', methods=['GET','POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn  = get_db()
        admin = db_fetchone(conn, "SELECT * FROM admins WHERE username=?", (username,))
        conn.close()
        if admin and check_password_hash(admin['password'], password):
            session['admin_id']   = admin['id']
            session['admin_name'] = admin['username']
            return redirect(url_for('dashboard'))
        error = 'Invalid credentials. Try admin / admin123'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    total_students = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM students")['cnt']
    courses   = db_fetchall(conn, "SELECT course, COUNT(*) as cnt FROM students GROUP BY course")
    year_dist = db_fetchall(conn, "SELECT year, COUNT(*) as cnt FROM students GROUP BY year")

    if USE_PG:
        top = db_fetchall(conn, '''
            SELECT s.name, s.roll_no, s.course,
                   ROUND(AVG(CAST(m.internal+m.external AS numeric)
                         /(m.max_internal+m.max_external)*100)::numeric,1) as avg_pct
            FROM students s JOIN marks m ON s.id=m.student_id
            GROUP BY s.id, s.name, s.roll_no, s.course
            ORDER BY avg_pct DESC LIMIT 5''')
        pass_fail = db_fetchone(conn, '''
            SELECT SUM(CASE WHEN avg_pct>=40 THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN avg_pct<40  THEN 1 ELSE 0 END) as failed
            FROM (SELECT s.id, AVG(CAST(m.internal+m.external AS numeric)
                         /(m.max_internal+m.max_external)*100) as avg_pct
                  FROM students s JOIN marks m ON s.id=m.student_id GROUP BY s.id) sub''')
        monthly_att = db_fetchall(conn, '''
            SELECT TO_CHAR(date::date,'YYYY-MM') as month,
                   ROUND(100.0*SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)/COUNT(*),1) as pct
            FROM attendance GROUP BY month ORDER BY month DESC LIMIT 6''')
    else:
        top = db_fetchall(conn, '''
            SELECT s.name, s.roll_no, s.course,
                   ROUND(AVG(CAST(m.internal+m.external AS REAL)/(m.max_internal+m.max_external)*100),1) as avg_pct
            FROM students s JOIN marks m ON s.id=m.student_id
            GROUP BY s.id ORDER BY avg_pct DESC LIMIT 5''')
        pass_fail = db_fetchone(conn, '''
            SELECT SUM(CASE WHEN avg_pct>=40 THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN avg_pct<40  THEN 1 ELSE 0 END) as failed
            FROM (SELECT s.id, AVG(CAST(m.internal+m.external AS REAL)
                         /(m.max_internal+m.max_external)*100) as avg_pct
                  FROM students s JOIN marks m ON s.id=m.student_id GROUP BY s.id)''')
        monthly_att = db_fetchall(conn, '''
            SELECT strftime('%Y-%m', date) as month,
                   ROUND(100.0*SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)/COUNT(*),1) as pct
            FROM attendance GROUP BY month ORDER BY month DESC LIMIT 6''')

    conn.close()
    return render_template('dashboard.html',
        total_students=total_students, courses=courses, year_dist=year_dist,
        top_performers=top, pass_fail=pass_fail or {'passed':0,'failed':0},
        monthly_att=list(reversed(monthly_att)))

# ══════════════════════════════════════════════════════════════
# STUDENTS
# ══════════════════════════════════════════════════════════════
@app.route('/students')
@login_required
def students():
    q       = request.args.get('q','').strip()
    course  = request.args.get('course','')
    year    = request.args.get('year','')
    section = request.args.get('section','')
    sql, params = "SELECT * FROM students WHERE 1=1", []
    if q:       sql += " AND (name LIKE ? OR roll_no LIKE ?)"; params += [f'%{q}%',f'%{q}%']
    if course:  sql += " AND course=?";  params.append(course)
    if year:    sql += " AND year=?";    params.append(year)
    if section: sql += " AND section=?"; params.append(section)
    sql += " ORDER BY name"
    conn    = get_db()
    rows    = db_fetchall(conn, sql, params)
    courses = db_fetchall(conn, "SELECT DISTINCT course FROM students ORDER BY course")
    conn.close()
    return render_template('students.html', students=rows,
        courses=[r['course'] for r in courses],
        q=q, filter_course=course, filter_year=year, filter_section=section)

@app.route('/students/add', methods=['GET','POST'])
@login_required
def add_student():
    conn    = get_db()
    courses = db_fetchall(conn, "SELECT DISTINCT course FROM subjects ORDER BY course")
    if request.method == 'POST':
        try:
            db_exec(conn,
                "INSERT INTO students(name,roll_no,email,phone,course,year,section) VALUES(?,?,?,?,?,?,?)",
                (request.form['name'].strip(), request.form['roll_no'].strip().upper(),
                 request.form['email'].strip(), request.form['phone'].strip(),
                 request.form['course'], int(request.form['year']),
                 request.form['section'].strip().upper()))
            conn.commit(); flash('Student added successfully!', 'success')
            conn.close(); return redirect(url_for('students'))
        except Exception:
            if USE_PG: conn.rollback()
            flash('Roll number already exists.', 'error')
    conn.close()
    return render_template('add_student.html', courses=[r['course'] for r in courses])

@app.route('/students/edit/<int:sid>', methods=['GET','POST'])
@login_required
def edit_student(sid):
    conn    = get_db()
    student = db_fetchone(conn, "SELECT * FROM students WHERE id=?", (sid,))
    courses = db_fetchall(conn, "SELECT DISTINCT course FROM subjects ORDER BY course")
    if not student:
        conn.close(); return redirect(url_for('students'))
    if request.method == 'POST':
        try:
            db_exec(conn,
                "UPDATE students SET name=?,roll_no=?,email=?,phone=?,course=?,year=?,section=? WHERE id=?",
                (request.form['name'].strip(), request.form['roll_no'].strip().upper(),
                 request.form['email'].strip(), request.form['phone'].strip(),
                 request.form['course'], int(request.form['year']),
                 request.form['section'].strip().upper(), sid))
            conn.commit(); flash('Student updated.', 'success')
            conn.close(); return redirect(url_for('students'))
        except Exception:
            if USE_PG: conn.rollback()
            flash('Roll number conflict.', 'error')
    conn.close()
    return render_template('edit_student.html', student=student,
        courses=[r['course'] for r in courses])

@app.route('/students/delete/<int:sid>', methods=['POST'])
@login_required
def delete_student(sid):
    conn = get_db()
    db_exec(conn, "DELETE FROM attendance WHERE student_id=?", (sid,))
    db_exec(conn, "DELETE FROM marks WHERE student_id=?", (sid,))
    db_exec(conn, "DELETE FROM students WHERE id=?", (sid,))
    conn.commit(); conn.close()
    flash('Student deleted.', 'success')
    return redirect(url_for('students'))

# ══════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════
@app.route('/attendance', methods=['GET','POST'])
@login_required
def attendance():
    conn    = get_db()
    courses = db_fetchall(conn, "SELECT DISTINCT course FROM subjects ORDER BY course")
    selected_course  = request.args.get('course') or (courses[0]['course'] if courses else '')
    selected_year    = request.args.get('year','1')
    selected_date    = request.args.get('date', date.today().isoformat())
    subjects         = db_fetchall(conn,
        "SELECT * FROM subjects WHERE course=? AND year=?", (selected_course, selected_year))
    selected_subject = request.args.get('subject_id', str(subjects[0]['id']) if subjects else '')

    students_list, existing = [], {}
    if selected_subject:
        students_list = db_fetchall(conn,
            "SELECT * FROM students WHERE course=? AND year=? ORDER BY roll_no",
            (selected_course, selected_year))
        existing = {str(r['student_id']): r['status']
                    for r in db_fetchall(conn,
                        "SELECT student_id, status FROM attendance WHERE subject_id=? AND date=?",
                        (selected_subject, selected_date))}

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        att_date   = request.form.get('att_date')
        for s in students_list:
            status = request.form.get(f'status_{s["id"]}', 'absent')
            if USE_PG:
                db_exec(conn,
                    '''INSERT INTO attendance(student_id,subject_id,date,status) VALUES(%s,%s,%s,%s)
                       ON CONFLICT(student_id,subject_id,date) DO UPDATE SET status=EXCLUDED.status''',
                    (s['id'], subject_id, att_date, status))
            else:
                db_exec(conn,
                    '''INSERT INTO attendance(student_id,subject_id,date,status) VALUES(?,?,?,?)
                       ON CONFLICT(student_id,subject_id,date) DO UPDATE SET status=excluded.status''',
                    (s['id'], subject_id, att_date, status))
        conn.commit(); flash('Attendance saved!', 'success'); conn.close()
        return redirect(url_for('attendance', course=selected_course,
                                year=selected_year, subject_id=subject_id, date=att_date))

    monthly = []
    if selected_subject:
        grp = "s.id, s.name, s.roll_no" if USE_PG else "s.id"
        monthly = db_fetchall(conn, f'''
            SELECT s.name, s.roll_no, COUNT(*) as total,
                   SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) as present,
                   ROUND(100.0*SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)/COUNT(*),1) as pct
            FROM students s JOIN attendance a ON s.id=a.student_id
            WHERE a.subject_id=? GROUP BY {grp} ORDER BY pct DESC''', (selected_subject,))

    conn.close()
    return render_template('attendance.html',
        courses=[r['course'] for r in courses], subjects=subjects,
        students=students_list, existing=existing, monthly=monthly,
        selected_course=selected_course, selected_year=selected_year,
        selected_date=selected_date, selected_subject=selected_subject)

# ══════════════════════════════════════════════════════════════
# MARKS
# ══════════════════════════════════════════════════════════════
@app.route('/marks', methods=['GET','POST'])
@login_required
def marks():
    conn    = get_db()
    courses = db_fetchall(conn, "SELECT DISTINCT course FROM subjects ORDER BY course")
    selected_course  = request.args.get('course') or (courses[0]['course'] if courses else '')
    selected_year    = request.args.get('year','1')
    subjects         = db_fetchall(conn,
        "SELECT * FROM subjects WHERE course=? AND year=?", (selected_course, selected_year))
    selected_subject = request.args.get('subject_id', str(subjects[0]['id']) if subjects else '')

    if request.method == 'POST':
        subject_id  = request.form.get('subject_id')
        student_ids = request.form.getlist('student_id')
        for sid in student_ids:
            internal = int(request.form.get(f'internal_{sid}', 0))
            external = int(request.form.get(f'external_{sid}', 0))
            if USE_PG:
                db_exec(conn,
                    '''INSERT INTO marks(student_id,subject_id,internal,external) VALUES(%s,%s,%s,%s)
                       ON CONFLICT(student_id,subject_id)
                       DO UPDATE SET internal=EXCLUDED.internal, external=EXCLUDED.external''',
                    (sid, subject_id, internal, external))
            else:
                db_exec(conn,
                    '''INSERT INTO marks(student_id,subject_id,internal,external) VALUES(?,?,?,?)
                       ON CONFLICT(student_id,subject_id)
                       DO UPDATE SET internal=excluded.internal, external=excluded.external''',
                    (sid, subject_id, internal, external))
        conn.commit(); flash('Marks saved!', 'success'); conn.close()
        return redirect(url_for('marks', course=selected_course,
                                year=selected_year, subject_id=subject_id))

    rows = []
    if selected_subject:
        rows = db_fetchall(conn, '''
            SELECT s.id, s.name, s.roll_no,
                   COALESCE(m.internal,0) as internal, COALESCE(m.external,0) as external,
                   COALESCE(m.max_internal,40) as max_internal, COALESCE(m.max_external,60) as max_external
            FROM students s
            LEFT JOIN marks m ON s.id=m.student_id AND m.subject_id=?
            WHERE s.course=? AND s.year=? ORDER BY s.roll_no''',
            (selected_subject, selected_course, selected_year))

    def enrich(r):
        total = r['internal'] + r['external']
        max_t = r['max_internal'] + r['max_external']
        r['total'] = total; r['max_total'] = max_t
        r['pct']   = round(total/max_t*100, 1) if max_t else 0
        r['grade'] = get_grade(r['pct'])
        return r

    conn.close()
    return render_template('marks.html',
        courses=[r['course'] for r in courses], subjects=subjects,
        rows=[enrich(r) for r in rows],
        selected_course=selected_course, selected_year=selected_year,
        selected_subject=selected_subject)

# ── API ──────────────────────────────────────────────────────
@app.route('/api/subjects')
@login_required
def api_subjects():
    conn = get_db()
    rows = db_fetchall(conn, "SELECT * FROM subjects WHERE course=? AND year=?",
        (request.args.get('course',''), request.args.get('year','1')))
    conn.close()
    return jsonify(rows)

# ── Startup ──────────────────────────────────────────────────
init_db()

if __name__ == '__main__':
    app.run(debug=True)