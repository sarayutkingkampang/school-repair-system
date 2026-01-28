import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from PIL import Image
import io
import base64
import time
import json

# --- ตั้งค่า Path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(BASE_DIR, 'credentials.json')
SHEET_NAME = "RepairData"

# ================= ฟังก์ชันจัดการรูปภาพ =================

def get_logo_image():
    """ค้นหาไฟล์โลโก้ (รองรับหลายชื่อ)"""
    possible_names = ['Logo_ss2.jpg', 'logo.png', 'logo.jpg', 'Logo.png']
    for name in possible_names:
        path = os.path.join(BASE_DIR, name)
        if os.path.exists(path):
            return path
    return None

def process_image(image_file):
    if image_file is None: return ""
    try:
        img = Image.open(image_file)
        img.thumbnail((600, 600))
        buffered = io.BytesIO()
        img.convert('RGB').save(buffered, format="JPEG", quality=60)
        return base64.b64encode(buffered.getvalue()).decode()
    except: return ""

def base64_to_image(base64_string):
    try:
        if not base64_string or len(base64_string) < 100: return None
        img_data = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(img_data))
    except: return None

# ================= ฟังก์ชันเชื่อมต่อ (ฉบับไม้ตาย 🔫) =================

def connect_google_sheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    try:
        # 1. วิธีใหม่: อ่านจากก้อน JSON ใน Secrets (ชัวร์ที่สุด)
        if 'google_credentials' in st.secrets:
            # แปลงข้อความ JSON ให้กลายเป็น Dictionary (ระบบจะจัดการ \n ให้เอง)
            creds_dict = json.loads(st.secrets['google_credentials'])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            
        # 2. วิธีสำรอง: อ่านจากไฟล์ในเครื่อง (สำหรับรัน Local)
        elif os.path.exists(CREDS_FILE):
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
            
        else:
            st.error("❌ ไม่พบกุญแจเชื่อมต่อ (กรุณาเช็ค Secrets หรือไฟล์ credentials.json)")
            return None

        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
        
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Sheets ไม่ได้: {e}")
        return None

# ================= ฟังก์ชันจัดการข้อมูล =================

def load_data():
    sheet = connect_google_sheet()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if 'ID' in df.columns:
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce')
            return df
        except: pass
    return pd.DataFrame()

def add_request(name, department, issue, img_str):
    sheet = connect_google_sheet()
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            all_records = sheet.get_all_values()
            new_id = len(all_records)
        except: new_id = 1
        try:
            sheet.append_row([new_id, timestamp, name, department, issue, 'รอคิว (Pending)', '', img_str])
            return True
        except: pass
    return False

def update_status(req_id, new_status, repair_note):
    sheet = connect_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(req_id))
            if cell:
                sheet.update_cell(cell.row, 6, new_status)
                sheet.update_cell(cell.row, 7, repair_note)
                return True
        except: pass
    return False

def delete_request(req_id):
    sheet = connect_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(req_id))
            if cell:
                sheet.delete_rows(cell.row)
                return True
        except: pass
    return False

# ================= หน้าจอโปรแกรม =================

st.set_page_config(page_title="ระบบแจ้งซ่อม - ร.น.ส.๒", layout="wide", page_icon="🛠️")

# --- ส่วนหัว ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    logo_path = get_logo_image()
    if logo_path:
        st.image(logo_path, width=120)
    else:
        st.write("*(Logo)*") 

with col_title:
    st.title("ระบบแจ้งซ่อมงานอาคาร")
    st.subheader("โรงเรียนราชนันทาจารย์ สามเสนวิทยาลัย ๒")

st.divider()

# --- เมนูแท็บ ---
tab1, tab2, tab3 = st.tabs(["📝 แจ้งซ่อม", "📊 ดูคิวงาน", "🔧 Admin"])

with tab1:
    with st.form("repair_form", clear_on_submit=True):
        st.subheader("กรอกข้อมูลแจ้งซ่อม")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("ชื่อ-นามสกุล")
            dept = st.text_input("แผนก/ห้อง") 
        with c2:
            issue = st.text_area("อาการเสีย")
            uploaded_file = st.file_uploader("แนบรูป (ถ้ามี)", type=['jpg', 'png', 'jpeg'])
        
        if st.form_submit_button("ส่งแจ้งซ่อม", type="primary"):
            if name and issue:
                with st.spinner("กำลังบันทึก..."):
                    img_str = process_image(uploaded_file)
                    if add_request(name, dept, issue, img_str):
                        st.success("บันทึกสำเร็จ!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("กรุณากรอกข้อมูลให้ครบ")

with tab2:
    if st.button("รีเฟรช"): st.rerun()
    df = load_data()
    if not df.empty and 'ID' in df.columns:
        df = df.sort_values(by='ID', ascending=False)
        
        for index, row in df.iterrows():
            status = row.get('Status', 'รอคิว (Pending)')
            s_color = "red" if "รอคิว" in status else "green" if "เสร็จ" in status else "orange"
            
            with st.expander(f"ID: {row.get('ID','-')} | {row.get('Issue','-')} [:{s_color}[{status}]]"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.write(f"**ผู้แจ้ง:** {row.get('Name')} | **เวลา:** {row.get('Timestamp')}")
                    st.info(f"อาการ: {row.get('Issue')}")
                    if row.get('RepairNote'): st.success(f"ช่างตอบ: {row.get('RepairNote')}")
                with c2:
                    img = base64_to_image(row.get('Image', ''))
                    if img: st.image(img, use_column_width=True)
    else:
        st.info("ไม่พบข้อมูล")

with tab3:
    pwd = st.text_input("รหัสผ่าน Admin", type="password")
    if pwd == "1234":
        st.success("Login OK")
        df_admin = load_data()
        if not df_admin.empty:
            for i, row in df_admin.iterrows():
                task_id = row['ID']
                with st.container(border=True):
                    st.markdown(f"**ID {task_id}: {row.get('Issue','-')}**")
                    ac1, ac2 = st.columns([3, 1])
                    with ac1:
                        with st.form(key=f"f_{task_id}"):
                            new_status = st.selectbox("สถานะ", ["รอคิว (Pending)", "กำลังดำเนินการ", "รออะไหล่", "ซ่อมเสร็จสิ้น"], key=f"s_{task_id}")
                            new_note = st.text_input("บันทึก", value=str(row.get('RepairNote','')), key=f"n_{task_id}")
                            if st.form_submit_button("บันทึก"):
                                update_status(task_id, new_status, new_note)
                                st.rerun()
                    with ac2:
                        with st.popover("ลบ"):
                            if st.button("ยืนยัน", key=f"d_{task_id}", type="primary"):
                                delete_request(task_id)
                                st.rerun()