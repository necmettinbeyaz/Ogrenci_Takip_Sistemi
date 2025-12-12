import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import random
import string
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import io

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Öğrenci Takip Sistemi", layout="wide", page_icon="📚")

# --- VERİTABANI BAĞLANTISI VE KURULUMU ---
def get_db_connection():
    conn = sqlite3.connect('ogrenci_takip.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Kullanıcılar Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    role TEXT,
                    email TEXT UNIQUE,
                    phone TEXT,
                    password TEXT,
                    unique_id TEXT UNIQUE
                )''')
    
    # İlişkiler (Öğretmen-Öğrenci, Veli-Öğrenci)
    c.execute('''CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supervisor_id INTEGER, -- Öğretmen veya Veli ID
                    student_id INTEGER,    -- Öğrenci ID
                    type TEXT              -- 'ogretmen' veya 'veli'
                )''')

    # Dersler
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    subject_name TEXT
                )''')

    # Üniteler
    c.execute('''CREATE TABLE IF NOT EXISTS units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER,
                    unit_name TEXT,
                    is_completed INTEGER DEFAULT 0
                )''')

    # Günlük Çalışma Kayıtları
    c.execute('''CREATE TABLE IF NOT EXISTS study_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    subject_id INTEGER,
                    unit_id INTEGER,
                    date TEXT,
                    q_solved INTEGER,
                    q_wrong INTEGER,
                    q_empty INTEGER,
                    duration INTEGER,
                    is_repeated INTEGER DEFAULT 0
                )''')

    # Deneme Sınavı Kayıtları
    c.execute('''CREATE TABLE IF NOT EXISTS exam_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    subject_id INTEGER, -- Ders bazlı deneme
                    date TEXT,
                    q_solved INTEGER,
                    q_wrong INTEGER,
                    q_empty INTEGER,
                    duration INTEGER
                )''')
    
    # Admin02 Varsayılan Kullanıcı
    c.execute("SELECT * FROM users WHERE email='admin02'")
    if not c.fetchone():
        # Şifre: admin02
        hashed_pw = hashlib.sha256("admin02".encode()).hexdigest()
        c.execute("INSERT INTO users (name, role, email, phone, password, unique_id) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Sistem Yöneticisi", "Yönetici", "admin02", "000", hashed_pw, "ADMIN1"))
        
    conn.commit()
    conn.close()

# --- YARDIMCI FONKSİYONLAR ---

def generate_unique_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, hashed):
    return hash_password(password) == hashed

def export_to_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Rapor')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- OTURUM YÖNETİMİ ---

def login_page():
    st.header("Giriş Yap")
    email = st.text_input("E-Mail Adresi")
    password = st.text_input("Şifre", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Giriş Yap"):
            conn = get_db_connection()
            c = conn.cursor()
            hashed_pw = hash_password(password)
            c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hashed_pw))
            user = c.fetchone()
            conn.close()
            
            if user:
                st.session_state['user_id'] = user[0]
                st.session_state['name'] = user[1]
                st.session_state['role'] = user[2]
                st.session_state['unique_id'] = user[6]
                st.success(f"Hoşgeldiniz {user[1]} ({user[2]})")
                st.rerun()
            else:
                st.error("Hatalı E-Mail veya Şifre")
    
    with col2:
        if st.button("Şifremi Unuttum"):
            st.session_state['page'] = 'forgot_password'
            st.rerun()

    st.markdown("---")
    st.subheader("Hesabınız yok mu?")
    if st.button("Yeni Üyelik Oluştur"):
        st.session_state['page'] = 'register'
        st.rerun()

def register_page():
    st.header("Üyelik Oluştur")
    name = st.text_input("Adı Soyadı")
    role = st.selectbox("Üyelik Statüsü", ["Öğrenci", "Öğretmen", "Veli"])
    email = st.text_input("E-Mail Adresi")
    phone = st.text_input("Telefon Numarası")
    p1 = st.text_input("Şifre", type="password")
    p2 = st.text_input("Şifre Doğrulama", type="password")
    
    if st.button("Üyelik Oluştur"):
        if p1 != p2:
            st.error("Şifreler uyuşmuyor!")
            return
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Email kontrolü
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        if c.fetchone():
            st.error("Bu E-Mail adresi zaten kullanılıyor.")
            conn.close()
            return
        
        unique_id = generate_unique_id()
        # Unique ID çakışma kontrolü (basit döngü)
        while True:
            c.execute("SELECT * FROM users WHERE unique_id=?", (unique_id,))
            if not c.fetchone():
                break
            unique_id = generate_unique_id()
            
        hashed_pw = hash_password(p1)
        c.execute("INSERT INTO users (name, role, email, phone, password, unique_id) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, role, email, phone, hashed_pw, unique_id))
        conn.commit()
        conn.close()
        st.success("Üyelik başarıyla oluşturuldu! Giriş ekranına yönlendiriliyorsunuz.")
        st.session_state['page'] = 'login'
        st.rerun()
        
    if st.button("Giriş Ekranına Dön"):
        st.session_state['page'] = 'login'
        st.rerun()

def forgot_password_page():
    st.header("Şifremi Unuttum")
    email = st.text_input("Kayıtlı E-Mail Adresinizi Girin")
    new_p1 = st.text_input("Yeni Şifre", type="password")
    new_p2 = st.text_input("Yeni Şifre Doğrulama", type="password")
    
    if st.button("Şifremi Güncelle"):
        if new_p1 != new_p2:
            st.error("Şifreler uyuşmuyor.")
            return
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()
        
        if user:
            hashed_pw = hash_password(new_p1)
            c.execute("UPDATE users SET password=? WHERE email=?", (hashed_pw, email))
            conn.commit()
            st.success("Şifreniz güncellendi. Giriş yapabilirsiniz.")
            # Normalde burada e-mail simülasyonu yapılır.
        else:
            st.error("Bu e-mail adresi sistemde kayıtlı değil.")
        conn.close()
        
    if st.button("Geri Dön"):
        st.session_state['page'] = 'login'
        st.rerun()

# --- ANALİZ VE RAPOR FONKSİYONLARI ---

def get_student_analysis(student_id):
    conn = get_db_connection()
    
    # Çalışma Verileri
    df_study = pd.read_sql(f"""
        SELECT s.subject_name, u.unit_name, l.date, l.q_solved, l.q_wrong, l.q_empty, l.duration, l.is_repeated
        FROM study_logs l
        JOIN units u ON l.unit_id = u.id
        JOIN subjects s ON l.subject_id = s.id
        WHERE l.student_id = {student_id}
    """, conn)
    
    # Deneme Verileri
    df_exam = pd.read_sql(f"""
        SELECT s.subject_name, e.date, e.q_solved, e.q_wrong, e.q_empty, e.duration
        FROM exam_logs e
        JOIN subjects s ON e.subject_id = s.id
        WHERE e.student_id = {student_id}
    """, conn)
    
    conn.close()
    return df_study, df_exam

def display_analysis_dashboard(df_study, df_exam):
    st.write("### 📊 Genel Analiz Paneli")
    
    tab1, tab2 = st.tabs(["Ders/Ünite Analizi", "Deneme Sınavı Analizi"])
    
    with tab1:
        if df_study.empty:
            st.info("Henüz çalışma verisi girilmemiş.")
        else:
            # Temel Metrikler
            total_q = df_study['q_solved'].sum()
            total_wrong = df_study['q_wrong'].sum()
            total_empty = df_study['q_empty'].sum()
            if total_q > 0:
                success_rate = ((total_q - total_wrong - total_empty) / total_q) * 100
                gap_to_100 = 100 - success_rate
            else:
                success_rate = 0
                gap_to_100 = 100
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Toplam Soru", total_q)
            col2.metric("Toplam Yanlış", total_wrong)
            col3.metric("Başarı Oranı", f"%{success_rate:.2f}")
            col4.metric("%100 Hedefine Kalan", f"%{gap_to_100:.2f}")
            
            # Grafikler
            st.subheader("Derslere Göre Soru Dağılımı")
            fig_pie = px.pie(df_study, values='q_solved', names='subject_name', title='Ders Bazlı Çözülen Soru')
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.subheader("Ünite Bazlı Başarı Analizi")
            # Ünite bazlı gruplama
            unit_grp = df_study.groupby(['subject_name', 'unit_name']).sum().reset_index()
            unit_grp['success_rate'] = ((unit_grp['q_solved'] - unit_grp['q_wrong'] - unit_grp['q_empty']) / unit_grp['q_solved'] * 100).fillna(0)
            
            fig_bar = px.bar(unit_grp, x='unit_name', y='success_rate', color='subject_name', title='Ünite Başarı Oranları (%)')
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Tarihsel Gelişim (Trend)
            st.subheader("Zaman İçinde Başarı Değişimi")
            df_study['date'] = pd.to_datetime(df_study['date'])
            daily_grp = df_study.groupby('date').sum().reset_index()
            daily_grp['daily_success'] = ((daily_grp['q_solved'] - daily_grp['q_wrong']) / daily_grp['q_solved'] * 100).fillna(0)
            fig_line = px.line(daily_grp, x='date', y='daily_success', title='Günlük Başarı Grafiği')
            st.plotly_chart(fig_line, use_container_width=True)
            
            # Excel İndir
            excel_file = export_to_excel(df_study)
            st.download_button(label="📥 Ünite Çalışma Raporunu İndir (Excel)", 
                               data=excel_file, file_name='unite_calisma_raporu.xlsx')

    with tab2:
        if df_exam.empty:
            st.info("Henüz deneme sınavı verisi girilmemiş.")
        else:
            st.subheader("Deneme Sınavı İstatistikleri")
            exam_grp = df_exam.groupby('subject_name').sum().reset_index()
            exam_grp['net'] = exam_grp['q_solved'] - exam_grp['q_wrong'] - (exam_grp['q_wrong'] / 4) # Klasik net hesabı (opsiyonel)
            
            st.dataframe(exam_grp)
            
            fig_exam = px.bar(exam_grp, x='subject_name', y=['q_solved', 'q_wrong', 'q_empty'], 
                              title="Ders Bazlı Deneme Analizi", barmode='group')
            st.plotly_chart(fig_exam, use_container_width=True)

            excel_exam = export_to_excel(df_exam)
            st.download_button(label="📥 Deneme Sınavı Raporunu İndir (Excel)", 
                               data=excel_exam, file_name='deneme_sinavi_raporu.xlsx')

# --- KULLANICI ARAYÜZLERİ ---

def student_interface():
    st.sidebar.title(f"Öğrenci: {st.session_state['name']}")
    st.sidebar.info(f"ÖĞRENCİ ID: **{st.session_state['unique_id']}**")
    
    menu = st.sidebar.radio("Menü", ["Öğrenci Bilgisi", "Ders ve Ünite Girişi", "Ünite Takip", "Günlük Giriş", "Deneme Sınavı", "Çalışma Takibi", "Çalışma Analizi"])
    conn = get_db_connection()
    c = conn.cursor()
    student_id = st.session_state['user_id']
    
    if menu == "Öğrenci Bilgisi":
        st.title("Öğrenci Bilgileri")
        # Öğretmen Ekleme
        st.subheader("Öğretmenini Ekle")
        teacher_code = st.text_input("Öğretmen ID'si (6 Haneli)")
        if st.button("Öğretmeni Kaydet"):
            c.execute("SELECT id FROM users WHERE unique_id=? AND role='Öğretmen'", (teacher_code,))
            res = c.fetchone()
            if res:
                # Daha önce ekli mi?
                c.execute("SELECT * FROM relationships WHERE student_id=? AND supervisor_id=?", (student_id, res[0]))
                if not c.fetchone():
                    c.execute("INSERT INTO relationships (supervisor_id, student_id, type) VALUES (?, ?, 'ogretmen')", (res[0], student_id))
                    conn.commit()
                    st.success("Öğretmen başarıyla eklendi.")
                else:
                    st.warning("Bu öğretmen zaten ekli.")
            else:
                st.error("Geçersiz Öğretmen ID")
        
        # Bilgileri Sil
        st.markdown("---")
        if st.button("TÜM BİLGİLERİMİ SİL (DEMO TEMİZLE)", type="primary"):
            c.execute("DELETE FROM study_logs WHERE student_id=?", (student_id,))
            c.execute("DELETE FROM exam_logs WHERE student_id=?", (student_id,))
            c.execute("DELETE FROM units WHERE subject_id IN (SELECT id FROM subjects WHERE student_id=?)", (student_id,))
            c.execute("DELETE FROM subjects WHERE student_id=?", (student_id,))
            conn.commit()
            st.warning("Tüm verileriniz silindi! Geri getirilemez.")

    elif menu == "Ders ve Ünite Girişi":
        st.title("Ders ve Ünite Yönetimi")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Ders Ekle")
            new_subject = st.text_input("Ders Adı Giriniz")
            if st.button("Dersi Ekle"):
                if new_subject:
                    c.execute("INSERT INTO subjects (student_id, subject_name) VALUES (?, ?)", (student_id, new_subject))
                    conn.commit()
                    st.success(f"{new_subject} eklendi.")
                    st.rerun()

        with col2:
            st.subheader("Ünite Ekle")
            # Mevcut dersleri çek
            df_subs = pd.read_sql(f"SELECT * FROM subjects WHERE student_id={student_id}", conn)
            if not df_subs.empty:
                selected_sub_id = st.selectbox("Ders Seç", df_subs['id'].tolist(), format_func=lambda x: df_subs[df_subs['id']==x]['subject_name'].values[0])
                new_unit = st.text_input("Ünite Adı Giriniz")
                if st.button("Üniteyi Ekle"):
                    if new_unit:
                        c.execute("INSERT INTO units (subject_id, unit_name) VALUES (?, ?)", (selected_sub_id, new_unit))
                        conn.commit()
                        st.success(f"{new_unit} eklendi.")
            else:
                st.warning("Önce ders eklemelisiniz.")

        # Listeleme ve Silme
        st.markdown("---")
        st.subheader("Mevcut Dersler ve Üniteler")
        df_all = pd.read_sql(f"""
            SELECT s.subject_name, u.unit_name, u.id as unit_id, s.id as subject_id 
            FROM subjects s LEFT JOIN units u ON s.id = u.subject_id 
            WHERE s.student_id={student_id}
        """, conn)
        st.dataframe(df_all)
        
        del_unit_id = st.number_input("Silinecek Ünite ID", min_value=0)
        if st.button("Üniteyi Sil"):
            c.execute("DELETE FROM units WHERE id=?", (del_unit_id,))
            conn.commit()
            st.rerun()
            
    elif menu == "Ünite Takip":
        st.title("Ünite Tamamlama Durumu")
        df_subs = pd.read_sql(f"SELECT * FROM subjects WHERE student_id={student_id}", conn)
        
        if not df_subs.empty:
            sel_sub = st.selectbox("Ders Seçiniz", df_subs['id'].tolist(), format_func=lambda x: df_subs[df_subs['id']==x]['subject_name'].values[0])
            
            # Üniteleri getir
            units = pd.read_sql(f"SELECT * FROM units WHERE subject_id={sel_sub}", conn)
            
            for index, row in units.iterrows():
                is_done = st.checkbox(f"{row['unit_name']}", value=bool(row['is_completed']), key=f"u_{row['id']}")
                if is_done != bool(row['is_completed']):
                    c.execute("UPDATE units SET is_completed=? WHERE id=?", (1 if is_done else 0, row['id']))
                    conn.commit()
            
            # Alt kısımda özet
            st.markdown("---")
            st.write("Ders Durumu:")
            st.dataframe(pd.read_sql(f"SELECT unit_name, CASE WHEN is_completed=1 THEN 'Bitti' ELSE 'Devam Ediyor' END as Durum FROM units WHERE subject_id={sel_sub}", conn))

    elif menu == "Günlük Giriş":
        st.title("Günlük Çalışma Girişi")
        date = st.date_input("Tarih", datetime.now())
        
        df_subs = pd.read_sql(f"SELECT * FROM subjects WHERE student_id={student_id}", conn)
        if not df_subs.empty:
            sel_sub = st.selectbox("Ders Seç", df_subs['id'].tolist(), format_func=lambda x: df_subs[df_subs['id']==x]['subject_name'].values[0])
            
            # Üniteler (Multi select)
            units = pd.read_sql(f"SELECT * FROM units WHERE subject_id={sel_sub}", conn)
            selected_unit_ids = st.multiselect("Ünite Seçimi (Birden fazla seçilebilir)", units['id'].tolist(), format_func=lambda x: units[units['id']==x]['unit_name'].values[0])
            
            col1, col2, col3, col4 = st.columns(4)
            q_solved = col1.number_input("Çözülen Soru", min_value=0)
            q_wrong = col2.number_input("Yanlış Sayısı", min_value=0)
            q_empty = col3.number_input("Boş Sayısı", min_value=0)
            duration = col4.number_input("Süre (dk)", min_value=0)
            is_repeated = st.checkbox("Tekrar Yapıldı mı?")
            
            if st.button("Kaydet"):
                for uid in selected_unit_ids:
                    c.execute("""INSERT INTO study_logs (student_id, subject_id, unit_id, date, q_solved, q_wrong, q_empty, duration, is_repeated) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                              (student_id, sel_sub, uid, date, q_solved, q_wrong, q_empty, duration, 1 if is_repeated else 0))
                conn.commit()
                st.success("Kayıt Başarılı!")
            
            st.subheader("Bugünün Kayıtları")
            today_logs = pd.read_sql(f"""
                SELECT s.subject_name, u.unit_name, l.q_solved, l.q_wrong, l.duration 
                FROM study_logs l JOIN subjects s ON l.subject_id=s.id JOIN units u ON l.unit_id=u.id 
                WHERE l.student_id={student_id} AND l.date='{date}'""", conn)
            st.dataframe(today_logs)

    elif menu == "Deneme Sınavı":
        st.title("Deneme Sınavı Girişi")
        date = st.date_input("Tarih", datetime.now())
        
        df_subs = pd.read_sql(f"SELECT * FROM subjects WHERE student_id={student_id}", conn)
        selected_subs = st.multiselect("Dersleri Seçiniz", df_subs['id'].tolist(), format_func=lambda x: df_subs[df_subs['id']==x]['subject_name'].values[0])
        
        for sub_id in selected_subs:
            st.markdown(f"**{df_subs[df_subs['id']==sub_id]['subject_name'].values[0]}**")
            c1, c2, c3, c4 = st.columns(4)
            qs = c1.number_input(f"Soru Sayısı ({sub_id})", min_value=0, key=f"ds_{sub_id}")
            qw = c2.number_input(f"Yanlış ({sub_id})", min_value=0, key=f"dw_{sub_id}")
            qe = c3.number_input(f"Boş ({sub_id})", min_value=0, key=f"de_{sub_id}")
            dur = c4.number_input(f"Süre ({sub_id})", min_value=0, key=f"dt_{sub_id}")
            
            if st.button(f"Kaydet ({sub_id})", key=f"btn_{sub_id}"):
                c.execute("""INSERT INTO exam_logs (student_id, subject_id, date, q_solved, q_wrong, q_empty, duration)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""", (student_id, sub_id, date, qs, qw, qe, dur))
                conn.commit()
                st.success("Ders notu kaydedildi.")

    elif menu in ["Çalışma Takibi", "Çalışma Analizi"]:
        df_study, df_exam = get_student_analysis(student_id)
        display_analysis_dashboard(df_study, df_exam)

    conn.close()

def teacher_interface():
    st.sidebar.title(f"Öğretmen: {st.session_state['name']}")
    st.sidebar.info(f"ÖĞRETMEN ID: **{st.session_state['unique_id']}**")
    
    menu = st.sidebar.radio("Menü", ["Öğrencilerim", "Öğrenci Çalışma Takibi", "Öğrenci Çalışma Analizi"])
    conn = get_db_connection()
    teacher_id = st.session_state['user_id']
    
    # Bu öğretmene kayıtlı öğrencileri bul
    students = pd.read_sql(f"""
        SELECT u.id, u.name, u.unique_id 
        FROM users u 
        JOIN relationships r ON u.id = r.student_id 
        WHERE r.supervisor_id = {teacher_id} AND r.type='ogretmen'
    """, conn)
    
    if menu == "Öğrencilerim":
        st.title("Öğrenci Listesi")
        if students.empty:
            st.warning("Henüz ID'nizi girerek size kayıt olan öğrenci yok.")
        else:
            st.dataframe(students)

    elif menu in ["Öğrenci Çalışma Takibi", "Öğrenci Çalışma Analizi"]:
        st.title("Öğrenci Analizleri")
        if not students.empty:
            selected_student_id = st.selectbox("Öğrenci Seçiniz", students['id'].tolist(), format_func=lambda x: students[students['id']==x]['name'].values[0])
            
            df_study, df_exam = get_student_analysis(selected_student_id)
            display_analysis_dashboard(df_study, df_exam)
        else:
            st.warning("Öğrenci bulunamadı.")
            
    conn.close()

def parent_interface():
    st.sidebar.title(f"Veli: {st.session_state['name']}")
    
    menu = st.sidebar.radio("Menü", ["Öğrencilerim", "Öğrenci Çalışma Takibi", "Öğrenci Çalışma Analizi"])
    conn = get_db_connection()
    c = conn.cursor()
    parent_id = st.session_state['user_id']
    
    if menu == "Öğrencilerim":
        st.title("Öğrenci Ekleme ve Listeleme")
        std_code = st.text_input("Öğrenci ID (6 Haneli)")
        if st.button("Öğrenciyi Getir ve Kaydet"):
            c.execute("SELECT id, name FROM users WHERE unique_id=? AND role='Öğrenci'", (std_code,))
            res = c.fetchone()
            if res:
                # İlişki kontrolü
                c.execute("SELECT * FROM relationships WHERE student_id=? AND supervisor_id=?", (res[0], parent_id))
                if not c.fetchone():
                    c.execute("INSERT INTO relationships (supervisor_id, student_id, type) VALUES (?, ?, 'veli')", (parent_id, res[0]))
                    conn.commit()
                    st.success(f"{res[1]} isimli öğrenci eklendi.")
                else:
                    st.warning("Bu öğrenci zaten ekli.")
            else:
                st.error("Öğrenci bulunamadı.")
        
        st.subheader("Kayıtlı Öğrenciler")
        students = pd.read_sql(f"""
            SELECT u.id, u.name, u.unique_id 
            FROM users u 
            JOIN relationships r ON u.id = r.student_id 
            WHERE r.supervisor_id = {parent_id} AND r.type='veli'
        """, conn)
        st.dataframe(students)

    elif menu in ["Öğrenci Çalışma Takibi", "Öğrenci Çalışma Analizi"]:
        students = pd.read_sql(f"""
            SELECT u.id, u.name 
            FROM users u 
            JOIN relationships r ON u.id = r.student_id 
            WHERE r.supervisor_id = {parent_id} AND r.type='veli'
        """, conn)
        
        if not students.empty:
            selected_student_id = st.selectbox("Öğrenci Seçiniz", students['id'].tolist(), format_func=lambda x: students[students['id']==x]['name'].values[0])
            df_study, df_exam = get_student_analysis(selected_student_id)
            display_analysis_dashboard(df_study, df_exam)
        else:
            st.warning("Önce öğrenci eklemelisiniz.")
            
    conn.close()

def admin_interface():
    st.sidebar.title("YÖNETİCİ PANELİ")
    menu = st.sidebar.radio("Menü", ["Yönetici Girişi", "Öğretmenler", "Veliler", "Tüm Öğrenciler", "Sistem Ayarları"])
    
    conn = get_db_connection()
    c = conn.cursor()
    
    if menu == "Yönetici Girişi":
        st.title("Yönetici Profil")
        st.info(f"Admin: {st.session_state['name']} - {st.session_state['unique_id']}")
        
        if st.button("Demo Verileri Sil (Veritabanını Sıfırla)"):
             # Tabloları drop edip yeniden oluşturmak daha temizdir ama sadece içeriği silelim
             c.execute("DELETE FROM study_logs")
             c.execute("DELETE FROM exam_logs")
             c.execute("DELETE FROM units")
             c.execute("DELETE FROM subjects")
             c.execute("DELETE FROM relationships")
             conn.commit()
             st.success("Sistem temizlendi.")

    elif menu == "Öğretmenler":
        st.title("Öğretmen Listesi")
        teachers = pd.read_sql("SELECT id, name, email, unique_id FROM users WHERE role='Öğretmen'", conn)
        st.dataframe(teachers)
        
        if st.button("Listeyi Excel İndir"):
             st.download_button("İndir", export_to_excel(teachers), "ogretmenler.xlsx")

    elif menu == "Veliler":
        st.title("Veli Listesi")
        parents = pd.read_sql("SELECT id, name, email FROM users WHERE role='Veli'", conn)
        st.dataframe(parents)

    elif menu == "Tüm Öğrenciler":
        st.title("Öğrenci Analiz (Admin Modu)")
        all_students = pd.read_sql("SELECT id, name, unique_id FROM users WHERE role='Öğrenci'", conn)
        
        if not all_students.empty:
            sel_std = st.selectbox("Analiz Edilecek Öğrenci", all_students['id'].tolist(), format_func=lambda x: all_students[all_students['id']==x]['name'].values[0])
            df_study, df_exam = get_student_analysis(sel_std)
            display_analysis_dashboard(df_study, df_exam)
    
    elif menu == "Sistem Ayarları":
        st.subheader("Yönetici Yetkisi Ver")
        users = pd.read_sql("SELECT id, name, email, role FROM users", conn)
        sel_user = st.selectbox("Kullanıcı Seç", users['id'].tolist(), format_func=lambda x: f"{users[users['id']==x]['name'].values[0]} ({users[users['id']==x]['role'].values[0]})")
        
        if st.button("Bu Kişiyi Yönetici Yap"):
            c.execute("UPDATE users SET role='Yönetici' WHERE id=?", (sel_user,))
            conn.commit()
            st.success("Yetki verildi.")
            
    conn.close()

# --- ANA UYGULAMA DÖNGÜSÜ ---

def main():
    init_db()
    
    if 'page' not in st.session_state:
        st.session_state['page'] = 'login'
    
    if 'user_id' in st.session_state:
        # GİRİŞ YAPILMIŞSA
        if st.sidebar.button("Güvenli Çıkış"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            
        role = st.session_state['role']
        if role == 'Öğrenci':
            student_interface()
        elif role == 'Öğretmen':
            teacher_interface()
        elif role == 'Veli':
            parent_interface()
        elif role == 'Yönetici':
            admin_interface()
    else:
        # GİRİŞ YAPILMAMIŞSA
        if st.session_state['page'] == 'login':
            login_page()
        elif st.session_state['page'] == 'register':
            register_page()
        elif st.session_state['page'] == 'forgot_password':
            forgot_password_page()

if __name__ == "__main__":
    main()
