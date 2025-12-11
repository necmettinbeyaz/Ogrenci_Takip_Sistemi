import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import hashlib
import uuid
import random

# ===================== VERİTABANI KATMANI =====================

DB_FILE = "student_tracking.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL,
            unique_id TEXT UNIQUE,
            is_admin INTEGER DEFAULT 0,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            course_name TEXT NOT NULL,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY,
            course_id INTEGER,
            unit_name TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            repeat_count INTEGER DEFAULT 0,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_entries (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            entry_date DATE,
            course_id INTEGER,
            unit_id INTEGER,
            questions_solved INTEGER DEFAULT 0,
            wrong_answers INTEGER DEFAULT 0,
            empty_answers INTEGER DEFAULT 0,
            duration_minutes INTEGER DEFAULT 0,
            repeated INTEGER DEFAULT 0,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY(unit_id) REFERENCES units(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS exam_entries (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            exam_date DATE,
            course_id INTEGER,
            questions_solved INTEGER DEFAULT 0,
            wrong_answers INTEGER DEFAULT 0,
            empty_answers INTEGER DEFAULT 0,
            duration_minutes INTEGER DEFAULT 0,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_students (
            id INTEGER PRIMARY KEY,
            teacher_id INTEGER,
            student_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(teacher_id, student_id),
            FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS parent_students (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER,
            student_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(parent_id, student_id),
            FOREIGN KEY(parent_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def generate_unique_id():
    return str(uuid.uuid4())[:6].upper()

def generate_reset_token():
    return str(uuid.uuid4())

def add_user(name, email, phone, password, user_type, is_demo=False):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """INSERT INTO users (name,email,phone,password,user_type,unique_id,is_demo)
               VALUES (?,?,?,?,?,?,?)""",
            (name, email, phone, hash_password(password), user_type, generate_unique_id(), int(is_demo)),
        )
        conn.commit()
        uid = c.lastrowid
        conn.close()
        return uid
    except sqlite3.IntegrityError:
        return None

def verify_user(email, password):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id,name,email,user_type,unique_id,is_admin FROM users WHERE email=? AND password=?",
        (email, hash_password(password)),
    )
    u = c.fetchone()
    conn.close()
    if u:
        return {
            "id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "user_type": u["user_type"],
            "unique_id": u["unique_id"],
            "is_admin": u["is_admin"],
        }
    return None

def get_user_by_email(email):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    r = c.fetchone()
    conn.close()
    return r

def get_teacher_id(email):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT unique_id FROM users WHERE email=? AND user_type='ÖĞRETMEN'", (email,))
    r = c.fetchone()
    conn.close()
    return r["unique_id"] if r else None

def get_student_id(email):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT unique_id FROM users WHERE email=? AND user_type='ÖĞRENCİ'", (email,))
    r = c.fetchone()
    conn.close()
    return r["unique_id"] if r else None

def create_password_reset_token(email):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email=?", (email,))
    u = c.fetchone()
    if not u:
        conn.close()
        return None
    token = generate_reset_token()
    expires = datetime.now() + timedelta(hours=24)
    c.execute(
        "INSERT INTO password_reset_tokens (user_id,token,expires_at) VALUES (?,?,?)",
        (u["id"], token, expires),
    )
    conn.commit()
    conn.close()
    return token

def reset_password_with_token(token, new_password):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT user_id FROM password_reset_tokens WHERE token=? AND expires_at>datetime('now')",
        (token,),
    )
    r = c.fetchone()
    if not r:
        conn.close()
        return False
    c.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), r["user_id"]),
    )
    c.execute("DELETE FROM password_reset_tokens WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return True

def add_course(student_id, course_name, is_demo=False):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO courses (student_id,course_name,is_demo) VALUES (?,?,?)",
        (student_id, course_name, int(is_demo)),
    )
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return cid

def get_student_courses(student_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM courses WHERE student_id=? ORDER BY created_at DESC",
        (student_id,),
    )
    r = c.fetchall()
    conn.close()
    return r

def add_unit(course_id, unit_name, is_demo=False):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO units (course_id,unit_name,is_demo) VALUES (?,?,?)",
        (course_id, unit_name, int(is_demo)),
    )
    conn.commit()
    uid = c.lastrowid
    conn.close()
    return uid

def get_course_units(course_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM units WHERE course_id=? ORDER BY created_at", (course_id,))
    r = c.fetchall()
    conn.close()
    return r

def update_unit_completion(unit_id, is_completed):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE units SET is_completed=? WHERE id=?",
        (int(is_completed), unit_id),
    )
    conn.commit()
    conn.close()

def delete_course(course_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM units WHERE course_id=?", (course_id,))
    c.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()

def delete_unit(unit_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM units WHERE id=?", (unit_id,))
    conn.commit()
    conn.close()

def add_daily_entry(student_id, entry_date, course_id, unit_id,
                    questions_solved, wrong_answers, empty_answers,
                    duration_minutes, repeated, is_demo=False):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO daily_entries
           (student_id,entry_date,course_id,unit_id,questions_solved,
            wrong_answers,empty_answers,duration_minutes,repeated,is_demo)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            student_id,
            entry_date,
            course_id,
            unit_id,
            questions_solved,
            wrong_answers,
            empty_answers,
            duration_minutes,
            int(repeated),
            int(is_demo),
        ),
    )
    conn.commit()
    conn.close()

def get_daily_entries(student_id, entry_date=None):
    conn = get_db()
    c = conn.cursor()
    q = """SELECT d.*,c.course_name,u.unit_name
           FROM daily_entries d
           JOIN courses c ON d.course_id=c.id
           LEFT JOIN units u ON d.unit_id=u.id
           WHERE d.student_id=?"""
    params = [student_id]
    if entry_date:
        q += " AND d.entry_date=?"
        params.append(entry_date)
    q += " ORDER BY d.entry_date DESC,d.created_at DESC"
    c.execute(q, params)
    r = c.fetchall()
    conn.close()
    return r

def delete_daily_entry(entry_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM daily_entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

def add_exam_entry(student_id, exam_date, course_id,
                   questions_solved, wrong_answers,
                   empty_answers, duration_minutes, is_demo=False):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO exam_entries
           (student_id,exam_date,course_id,questions_solved,
            wrong_answers,empty_answers,duration_minutes,is_demo)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            student_id,
            exam_date,
            course_id,
            questions_solved,
            wrong_answers,
            empty_answers,
            duration_minutes,
            int(is_demo),
        ),
    )
    conn.commit()
    conn.close()

def get_exam_entries(student_id, exam_date=None):
    conn = get_db()
    c = conn.cursor()
    q = """SELECT e.*,c.course_name
           FROM exam_entries e
           JOIN courses c ON e.course_id=c.id
           WHERE e.student_id=?"""
    params = [student_id]
    if exam_date:
        q += " AND e.exam_date=?"
        params.append(exam_date)
    q += " ORDER BY e.exam_date DESC,e.created_at DESC"
    c.execute(q, params)
    r = c.fetchall()
    conn.close()
    return r

def delete_exam_entry(entry_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM exam_entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

def link_teacher_student(teacher_id, student_unique_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM users WHERE unique_id=? AND user_type='ÖĞRENCİ'",
        (student_unique_id,),
    )
    s = c.fetchone()
    if not s:
        conn.close()
        return False
    c.execute(
        "INSERT OR IGNORE INTO teacher_students (teacher_id,student_id) VALUES (?,?)",
        (teacher_id, s["id"]),
    )
    conn.commit()
    conn.close()
    return True

def get_teacher_students(teacher_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT u.* FROM users u
           JOIN teacher_students ts ON u.id=ts.student_id
           WHERE ts.teacher_id=?""",
        (teacher_id,),
    )
    r = c.fetchall()
    conn.close()
    return r

def link_parent_student(parent_id, student_unique_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM users WHERE unique_id=? AND user_type='ÖĞRENCİ'",
        (student_unique_id,),
    )
    s = c.fetchone()
    if not s:
        conn.close()
        return False
    c.execute(
        "INSERT OR IGNORE INTO parent_students (parent_id,student_id) VALUES (?,?)",
        (parent_id, s["id"]),
    )
    conn.commit()
    conn.close()
    return True

def get_parent_students(parent_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT u.* FROM users u
           JOIN parent_students ps ON u.id=ps.student_id
           WHERE ps.parent_id=?""",
        (parent_id,),
    )
    r = c.fetchall()
    conn.close()
    return r

def get_all_users(user_type=None):
    conn = get_db()
    c = conn.cursor()
    if user_type:
        c.execute(
            "SELECT * FROM users WHERE user_type=? ORDER BY created_at DESC",
            (user_type,),
        )
    else:
        c.execute("SELECT * FROM users ORDER BY created_at DESC")
    r = c.fetchall()
    conn.close()
    return r

def delete_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def make_user_admin(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def set_user_password(user_id, new_password):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), user_id),
    )
    conn.commit()
    conn.close()

def get_student_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS c FROM users WHERE user_type='ÖĞRENCİ'")
    r = c.fetchone()
    conn.close()
    return r["c"] if r else 0

def get_teacher_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS c FROM users WHERE user_type='ÖĞRETMEN'")
    r = c.fetchone()
    conn.close()
    return r["c"] if r else 0

def get_parent_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS c FROM users WHERE user_type='VELİ'")
    r = c.fetchone()
    conn.close()
    return r["c"] if r else 0

def delete_all_demo_data():
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM daily_entries WHERE is_demo=1")
    c.execute("DELETE FROM exam_entries WHERE is_demo=1")
    c.execute("DELETE FROM units WHERE is_demo=1")
    c.execute("DELETE FROM courses WHERE is_demo=1")
    conn.commit()
    conn.close()

def calculate_success_rate(q, w):
    if not q:
        return 0.0
    return (q - w) / q * 100.0

def get_student_stats(student_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT SUM(questions_solved) AS tq, SUM(wrong_answers) AS tw FROM daily_entries WHERE student_id=?",
        (student_id,),
    )
    r1 = c.fetchone() or {"tq": 0, "tw": 0}
    c.execute(
        """SELECT COUNT(*) AS total_units,
                  SUM(CASE WHEN is_completed=1 THEN 1 ELSE 0 END) AS comp
           FROM units u
           JOIN courses c2 ON u.course_id=c2.id
           WHERE c2.student_id=?""",
        (student_id,),
    )
    r2 = c.fetchone() or {"total_units": 0, "comp": 0}
    conn.close()
    tq = r1["tq"] or 0
    tw = r1["tw"] or 0
    sr = calculate_success_rate(tq, tw)
    return {
        "total_questions": tq,
        "total_wrong": tw,
        "completed_units": r2["comp"] or 0,
        "total_units": r2["total_units"] or 0,
        "success_rate": round(sr, 2),
    }

def get_daily_summary(student_id, date):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT d.course_id,d.unit_id,c.course_name,u.unit_name,
                  SUM(d.questions_solved) AS daily_q,
                  SUM(d.wrong_answers) AS daily_w,
                  SUM(d.empty_answers) AS daily_e,
                  SUM(d.duration_minutes) AS daily_time
           FROM daily_entries d
           JOIN courses c ON d.course_id=c.id
           LEFT JOIN units u ON d.unit_id=u.id
           WHERE d.student_id=? AND d.entry_date=?
           GROUP BY d.course_id,d.unit_id""",
        (student_id, date),
    )
    r = c.fetchall()
    conn.close()
    return r

def get_weekly_summary(student_id, start_date, end_date):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT d.course_id,c.course_name,
                  COUNT(DISTINCT d.entry_date) AS study_days,
                  SUM(d.questions_solved) AS weekly_q,
                  SUM(d.wrong_answers) AS weekly_w,
                  SUM(d.empty_answers) AS weekly_e
           FROM daily_entries d
           JOIN courses c ON d.course_id=c.id
           WHERE d.student_id=? AND d.entry_date BETWEEN ? AND ?
           GROUP BY d.course_id""",
        (student_id, start_date, end_date),
    )
    r = c.fetchall()
    conn.close()
    return r

def get_monthly_summary(student_id, year, month):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT d.course_id,c.course_name,
                  COUNT(DISTINCT d.entry_date) AS study_days,
                  SUM(d.questions_solved) AS monthly_q
           FROM daily_entries d
           JOIN courses c ON d.course_id=c.id
           WHERE d.student_id=? AND strftime('%Y',d.entry_date)=? AND strftime('%m',d.entry_date)=?
           GROUP BY d.course_id""",
        (student_id, str(year), str(month).zfill(2)),
    )
    r = c.fetchall()
    conn.close()
    return r

# ===================== STREAMLIT ARAYÜZÜ =====================

st.set_page_config(
    page_title="🎓 Öğrenci Takip Sistemi v2.1",
    page_icon="📚",
    layout="wide",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700;800&display=swap');
* { font-family: 'Poppins', sans-serif; }
.motivasyon { background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); padding:20px; border-radius:15px; color:white; text-align:center; margin:10px 0; }
.info-box { background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%); padding:15px; border-radius:10px; color:white; margin:10px 0; }
.success-box { background:linear-gradient(135deg,#11998e 0%,#38ef7d 100%); padding:15px; border-radius:10px; color:white; margin:10px 0; }
.header-title { font-size:30px; font-weight:800; text-align:center; margin:20px 0;
    background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
</style>
""",
    unsafe_allow_html=True,
)

init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_type = None
    st.session_state.user_name = None
    st.session_state.user_email = None
    st.session_state.user_id = None
    st.session_state.is_admin = 0

motivasyon_mesajlari = [
    "🚀 Her gün biraz daha ileri git!",
    "💪 Zorluklar seni güçlendirir!",
    "🌟 Başarı sabır ve çalışkanlığın birleşimidir!",
    "📈 Küçük adımlar büyük sonuçlar getirir!",
]
motivasyon_mesaji = random.choice(motivasyon_mesajlari)

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            '<div class="header-title">🎓 Öğrenci Takip Sistemi v2.1</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="motivasyon">{motivasyon_mesaji}</div>',
            unsafe_allow_html=True,
        )

        tab1, tab2, tab3 = st.tabs(["🔐 Giriş", "📝 Üye Ol", "🔑 Şifremi Unuttum"])

        with tab1:
            email = st.text_input("📧 E-mail")
            pw = st.text_input("🔐 Şifre", type="password")
            if st.button("Giriş Yap", use_container_width=True):
                u = verify_user(email, pw)
                if u:
                    st.session_state.logged_in = True
                    st.session_state.user_type = u["user_type"]
                    st.session_state.user_name = u["name"]
                    st.session_state.user_email = u["email"]
                    st.session_state.user_id = u["id"]
                    st.session_state.is_admin = u["is_admin"]
                    st.success("✅ Giriş başarılı!")
                    st.rerun()
                else:
                    st.error("❌ E-mail veya şifre hatalı!")

        with tab2:
            name = st.text_input("👤 Ad Soyad", key="reg_name")
            remail = st.text_input("📧 E-mail", key="reg_email")
            phone = st.text_input("📱 Telefon", key="reg_phone")
            utype = st.selectbox("👥 Rol", ["ÖĞRENCİ", "ÖĞRETMEN", "VELİ"])
            rp1 = st.text_input("🔐 Şifre", type="password", key="reg_p1")
            rp2 = st.text_input("🔐 Şifre (Tekrar)", type="password", key="reg_p2")
            if st.button("Üyelik Oluştur", use_container_width=True):
                if not all([name, remail, phone, rp1, rp2]):
                    st.error("Tüm alanları doldurun.")
                elif rp1 != rp2:
                    st.error("Şifreler aynı olmalı.")
                else:
                    uid = add_user(name, remail, phone, rp1, utype, False)
                    if uid:
                        st.success("✅ Üyelik tamamlandı, giriş yapabilirsiniz.")
                    else:
                        st.error("Bu e-mail zaten kayıtlı.")

        with tab3:
            rem = st.text_input("📧 Kayıtlı e-mail", key="reset_email")
            if st.button("Şifre sıfırlama linki üret", use_container_width=True):
                if not rem:
                    st.error("E-mail girin.")
                elif not get_user_by_email(rem):
                    st.error("Bu e-mail ile kullanıcı yok.")
                else:
                    t = create_password_reset_token(rem)
                    st.success("✅ Teorik olarak link e-maile gönderildi.")
                    st.info(f"Test için token: {t}")

def student_dashboard():
    st.sidebar.markdown(
        f'<div class="motivasyon">Hoşgeldin {st.session_state.user_name}! 👋</div>',
        unsafe_allow_html=True,
    )
    sid = st.session_state.user_id
    menu = st.sidebar.radio(
        "📚 Menü",
        [
            "🏠 Anasayfa",
            "📖 Ders / Ünite",
            "✅ Ünite Takip",
            "📝 Günlük",
            "🧪 Deneme Sınavı",
            "📊 Çalışma Takibi",
            "🚪 Çıkış",
        ],
    )
    if menu == "🚪 Çıkış":
        st.session_state.logged_in = False
        st.rerun()

    elif menu == "🏠 Anasayfa":
        st.markdown(
            '<div class="header-title">📚 Öğrenci Paneli</div>',
            unsafe_allow_html=True,
        )
        stats = get_student_stats(sid)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("📖 Ders Sayısı", len(get_student_courses(sid)))
        with c2:
            st.metric(
                "✅ Tamamlanan Ünite",
                f"{stats['completed_units']}/{stats['total_units']}",
            )
        with c3:
            st.metric("📊 Başarı %", f"%{stats['success_rate']:.1f}")

    elif menu == "📖 Ders / Ünite":
        st.markdown("### 📖 Ders ve Ünite Girişi")
        col1, col2 = st.columns([3, 1])
        with col1:
            cname = st.text_input("📚 Ders Adı")
        with col2:
            if st.button("➕ Ders Ekle"):
                if cname:
                    add_course(sid, cname, False)
                    st.rerun()
                else:
                    st.error("Ders adı boş olamaz.")
        courses = get_student_courses(sid)
        if not courses:
            st.info("Henüz ders yok, yukarıdan ekleyin.")
        for c in courses:
            st.write(f"**📚 {c['course_name']}**")
            ucol1, ucol2, ucol3 = st.columns([2, 1, 1])
            with ucol1:
                uname = st.text_input("Ünite adı", key=f"u_{c['id']}")
            with ucol2:
                if st.button("➕ Ünite", key=f"uadd_{c['id']}"):
                    if uname:
                        add_unit(c["id"], uname, False)
                        st.rerun()
            with ucol3:
                if st.button("🗑️ Dersi Sil", key=f"cdel_{c['id']}"):
                    delete_course(c["id"])
                    st.rerun()
            units = get_course_units(c["id"])
            for u in units:
                st.write(f"• {u['unit_name']}")

    elif menu == "✅ Ünite Takip":
        st.markdown("### ✅ Ünite Takip")
        courses = get_student_courses(sid)
        if not courses:
            st.warning("Önce ders eklenmeli.")
            return
        cid = st.selectbox(
            "Ders seç",
            [c["id"] for c in courses],
            format_func=lambda x: next(
                c["course_name"] for c in courses if c["id"] == x
            ),
        )
        units = get_course_units(cid)
        for u in units:
            checked = st.checkbox(
                u["unit_name"], value=bool(u["is_completed"]), key=f"chk_{u['id']}"
            )
            if checked != bool(u["is_completed"]):
                update_unit_completion(u["id"], checked)
                st.rerun()

    elif menu == "📝 Günlük":
        st.markdown("### 📝 Günlük Giriş")
        courses = get_student_courses(sid)
        if not courses:
            st.warning("Ders ekleyin.")
            return
        dt = st.date_input("📅 Tarih", datetime.now())
        cid = st.selectbox(
            "Ders",
            [c["id"] for c in courses],
            format_func=lambda x: next(
                c["course_name"] for c in courses if c["id"] == x
            ),
        )
        units = get_course_units(cid)
        ulist = {u["id"]: u["unit_name"] for u in units}
        sel_units = st.multiselect(
            "Üniteler", list(ulist.keys()), format_func=lambda x: ulist[x]
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            q = st.number_input("❓ Soru", min_value=0, step=1)
        with c2:
            w = st.number_input("❌ Yanlış", min_value=0, step=1)
        with c3:
            e = st.number_input("⬜ Boş", min_value=0, step=1)
        dur = st.number_input("⏱ Süre (dk)", min_value=0, step=1)
        rep = st.checkbox("🔄 Tekrar")
        if st.button("💾 Kaydet"):
            if not sel_units:
                add_daily_entry(sid, dt, cid, None, q, w, e, dur, rep, False)
            for uid in sel_units:
                add_daily_entry(sid, dt, cid, uid, q, w, e, dur, rep, False)
            st.success("Günlük kayıt eklendi.")
            st.rerun()
        st.markdown("#### Bugünün Kayıtları")
        entries = get_daily_entries(sid, dt)
        for en in entries:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.write(
                    f"{en['course_name']} - {en['unit_name'] or 'Ünite yok'}"
                )
            with col2:
                st.write(f"❓ {en['questions_solved']} / ❌ {en['wrong_answers']}")
            with col3:
                st.write(f"⬜ {en['empty_answers']} | ⏱ {en['duration_minutes']} dk")
            with col4:
                if st.button("🗑️", key=f"del_d_{en['id']}"):
                    delete_daily_entry(en["id"])
                    st.rerun()

    elif menu == "🧪 Deneme Sınavı":
        st.markdown("### 🧪 Deneme Sınavı")
        courses = get_student_courses(sid)
        if not courses:
            st.warning("Ders ekleyin.")
            return
        dt = st.date_input("📅 Tarih", datetime.now(), key="exam_dt")
        cid = st.selectbox(
            "Ders",
            [c["id"] for c in courses],
            format_func=lambda x: next(
                c["course_name"] for c in courses if c["id"] == x
            ),
        )
        c1, c2 = st.columns(2)
        with c1:
            q = st.number_input("❓ Soru", min_value=0, step=1, key="eq")
        with c2:
            w = st.number_input("❌ Yanlış", min_value=0, step=1, key="ew")
        if q > 0:
            sr = calculate_success_rate(q, w)
            st.write(f"📊 Başarı: %{sr:.1f}")
        if st.button("💾 Sınavı Kaydet"):
            add_exam_entry(sid, dt, cid, q, w, 0, 0, False)
            st.success("Deneme kaydedildi.")
            st.rerun()
        st.markdown("#### Bugünkü Denemeler")
        exs = get_exam_entries(sid, dt)
        for ex in exs:
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                st.write(ex["course_name"])
            with col2:
                sr2 = calculate_success_rate(
                    ex["questions_solved"], ex["wrong_answers"]
                )
                st.write(
                    f"❓ {ex['questions_solved']} | ❌ {ex['wrong_answers']} | %{sr2:.1f}"
                )
            with col3:
                if st.button("🗑️", key=f"del_e_{ex['id']}"):
                    delete_exam_entry(ex["id"])
                    st.rerun()

    elif menu == "📊 Çalışma Takibi":
        st.markdown("### 📊 Çalışma Takibi")
        courses = get_student_courses(sid)
        if not courses:
            st.warning("Ders ekleyin.")
            return
        tab1, tab2, tab3, tab4 = st.tabs(
            ["📅 Günlük", "📆 Haftalık", "🗓 Aylık", "📊 Tüm Zamanlar"]
        )
        with tab1:
            d = st.date_input("Tarih", datetime.now(), key="trk_d")
            rows = get_daily_summary(sid, d)
            if rows:
                df = pd.DataFrame(
                    [
                        {
                            "Ders": r["course_name"],
                            "Ünite": r["unit_name"] or "",
                            "Soru": r["daily_q"],
                            "Yanlış": r["daily_w"],
                            "Boş": r["daily_e"],
                        }
                        for r in rows
                    ]
                )
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Bu tarihte veri yok.")
        with tab2:
            end = st.date_input("Hafta sonu", datetime.now(), key="trk_w")
            start = end - timedelta(days=7)
            rows = get_weekly_summary(sid, start, end)
            if rows:
                df = pd.DataFrame(
                    [
                        {
                            "Ders": r["course_name"],
                            "Çalışma Günü": r["study_days"],
                            "Soru": r["weekly_q"],
                        }
                        for r in rows
                    ]
                )
                st.dataframe(df, use_container_width=True)
        with tab3:
            year = st.number_input(
                "Yıl", min_value=2020, max_value=2100, value=datetime.now().year
            )
            month = st.number_input(
                "Ay", min_value=1, max_value=12, value=datetime.now().month
            )
            rows = get_monthly_summary(sid, year, month)
            if rows:
                df = pd.DataFrame(
                    [
                        {
                            "Ders": r["course_name"],
                            "Çalışma Günü": r["study_days"],
                            "Soru": r["monthly_q"],
                        }
                        for r in rows
                    ]
                )
                st.dataframe(df, use_container_width=True)
        with tab4:
            stats = get_student_stats(sid)
            st.metric("Toplam Soru", stats["total_questions"])
            st.metric("Genel Başarı %", f"%{stats['success_rate']:.1f}")

def teacher_dashboard():
    st.sidebar.markdown(
        f'<div class="motivasyon">Hoşgeldin Öğretmen {st.session_state.user_name}! 👋</div>',
        unsafe_allow_html=True,
    )
    tid = st.session_state.user_id
    menu = st.sidebar.radio(
        "📚 Menü",
        [
            "🏠 Anasayfa",
            "👨‍🎓 Öğrencilerim",
            "📊 Çalışma Takibi",
            "🚪 Çıkış",
        ],
    )
    if menu == "🚪 Çıkış":
        st.session_state.logged_in = False
        st.rerun()
    elif menu == "🏠 Anasayfa":
        st.markdown(
            '<div class="header-title">👨‍🏫 Öğretmen Paneli</div>',
            unsafe_allow_html=True,
        )
        students = get_teacher_students(tid)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("👨‍🎓 Öğrenci", len(students))
        with c2:
            if students:
                avg = sum(
                    get_student_stats(s["id"])["success_rate"] for s in students
                ) / len(students)
                st.metric("📊 Sınıf Ort.", f"%{avg:.1f}")
        with c3:
            st.metric(
                "📚 Toplam Ders",
                sum(len(get_student_courses(s["id"])) for s in students),
            )
        if st.checkbox("Öğrenci Ekle"):
            sid_code = st.text_input("Öğrenci ID (6 hane)")
            if st.button("Ekle"):
                if link_teacher_student(tid, sid_code):
                    st.success("Öğrenci eklendi.")
                    st.rerun()
                else:
                    st.error("Öğrenci bulunamadı.")
    elif menu == "👨‍🎓 Öğrencilerim":
        students = get_teacher_students(tid)
        if not students:
            st.info("Henüz öğrenci yok.")
            return
        df = pd.DataFrame(
            [
                {
                    "Adı": s["name"],
                    "E-mail": s["email"],
                    "Ders": len(get_student_courses(s["id"])),
                }
                for s in students
            ]
        )
        st.dataframe(df, use_container_width=True)
    elif menu == "📊 Çalışma Takibi":
        students = get_teacher_students(tid)
        if not students:
            st.info("Öğrenci ekleyin.")
            return
        sid = st.selectbox(
            "Öğrenci",
            [s["id"] for s in students],
            format_func=lambda x: next(
                s["name"] for s in students if s["id"] == x
            ),
        )
        stats = get_student_stats(sid)
        st.metric("Toplam Soru", stats["total_questions"])
        st.metric("Başarı %", f"%{stats['success_rate']:.1f}")

def parent_dashboard():
    st.sidebar.markdown(
        f'<div class="motivasyon">Hoşgeldin Veli {st.session_state.user_name}! 👋</div>',
        unsafe_allow_html=True,
    )
    pid = st.session_state.user_id
    menu = st.sidebar.radio(
        "📚 Menü",
        ["🏠 Anasayfa", "👨‍🎓 Çocuğum", "📊 Takip", "🚪 Çıkış"],
    )
    if menu == "🚪 Çıkış":
        st.session_state.logged_in = False
        st.rerun()
    elif menu == "🏠 Anasayfa":
        st.markdown(
            '<div class="header-title">👨‍👩‍👧 Veli Paneli</div>',
            unsafe_allow_html=True,
        )
        students = get_parent_students(pid)
        if not students:
            st.warning("Çocuk ekleyin.")
            if st.checkbox("Çocuk Ekle"):
                sid_code = st.text_input("Öğrenci ID (6 hane)")
                if st.button("Ekle"):
                    if link_parent_student(pid, sid_code):
                        st.success("Eklendi.")
                        st.rerun()
                    else:
                        st.error("Bulunamadı.")
        else:
            s = students[0]
            stats = get_student_stats(s["id"])
            st.metric("Çocuğum", s["name"])
            st.metric("Başarı %", f"%{stats['success_rate']:.1f}")
    elif menu == "👨‍🎓 Çocuğum":
        students = get_parent_students(pid)
        if not students:
            st.info("Çocuk yok.")
            return
        s = students[0]
        st.write(f"Adı: {s['name']}")
        st.write(f"E-mail: {s['email']}")
        st.write(f"ID: {s['unique_id']}")
    elif menu == "📊 Takip":
        students = get_parent_students(pid)
        if not students:
            st.info("Çocuk yok.")
            return
        s = students[0]
        stats = get_student_stats(s["id"])
        st.metric("Toplam Soru", stats["total_questions"])
        st.metric("Başarı %", f"%{stats['success_rate']:.1f}")

def admin_dashboard():
    st.sidebar.markdown(
        '<div class="motivasyon">Admin Paneli 🔐</div>', unsafe_allow_html=True
    )
    menu = st.sidebar.radio(
        "⚙️ Admin Menü",
        [
            "🏠 Anasayfa",
            "👨‍🎓 Öğrenciler",
            "👨‍🏫 Öğretmenler",
            "👨‍👩‍👧 Veliler",
            "🗑 Demo Veriler",
            "🚪 Çıkış",
        ],
    )
    if menu == "🚪 Çıkış":
        st.session_state.logged_in = False
        st.rerun()
    elif menu == "🏠 Anasayfa":
        st.markdown(
            '<div class="header-title">🔐 Admin Paneli</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Öğrenci", get_student_count())
        with c2:
            st.metric("Öğretmen", get_teacher_count())
        with c3:
            st.metric("Veli", get_parent_count())
        with c4:
            st.metric(
                "Toplam",
                get_student_count() + get_teacher_count() + get_parent_count(),
            )
    elif menu == "👨‍🎓 Öğrenciler":
        students = get_all_users("ÖĞRENCİ")
        if not students:
            st.info("Öğrenci yok.")
            return
        df = pd.DataFrame(
            [{"Adı": s["name"], "E-mail": s["email"]} for s in students]
        )
        st.dataframe(df, use_container_width=True)
    elif menu == "👨‍🏫 Öğretmenler":
        teachers = get_all_users("ÖĞRETMEN")
        if not teachers:
            st.info("Öğretmen yok.")
            return
        df = pd.DataFrame(
            [{"Adı": t["name"], "E-mail": t["email"]} for t in teachers]
        )
        st.dataframe(df, use_container_width=True)
    elif menu == "👨‍👩‍👧 Veliler":
        parents = get_all_users("VELİ")
        if not parents:
            st.info("Veli yok.")
            return
        df = pd.DataFrame(
            [{"Adı": p["name"], "E-mail": p["email"]} for p in parents]
        )
        st.dataframe(df, use_container_width=True)
    elif menu == "🗑 Demo Veriler":
        st.warning("Tüm demo verileri silinecek.")
        if st.button("Demo verileri sil"):
            delete_all_demo_data()
            st.success("Demo verileri silindi.")

def main():
    with st.sidebar.expander("🔐 Admin Girişi"):
        un = st.text_input("Kullanıcı", key="adm_u")
        pw = st.text_input("Şifre", type="password", key="adm_p")
        if st.button("Admin Giriş"):
            if un == "admin02" and pw == "admin02":
                st.session_state.logged_in = True
                st.session_state.user_type = "ADMIN"
                st.session_state.user_name = "Admin"
                st.session_state.user_email = "admin@example.com"
                st.session_state.user_id = 0
                st.session_state.is_admin = 1
                st.success("Admin girişi başarılı.")
                st.rerun()
            else:
                st.error("Admin bilgisi hatalı.")

    if not st.session_state.logged_in:
        login_page()
    else:
        if st.session_state.user_type == "ÖĞRENCİ":
            student_dashboard()
        elif st.session_state.user_type == "ÖĞRETMEN":
            teacher_dashboard()
        elif st.session_state.user_type == "VELİ":
            parent_dashboard()
        elif st.session_state.user_type == "ADMIN":
            admin_dashboard()
        else:
            login_page()

if __name__ == "__main__":
    main()
