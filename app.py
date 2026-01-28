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
CREDS_PATH = os.path.join(BASE_DIR, 'credentials.json')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
SHEET_NAME = "RepairData"

# ================= ฟังก์ชันจัดการรูปภาพ =================

def process_image(image_file):
    """แปลงรูปภาพที่อัปโหลดเป็น Base64 String เพื่อเก็บใน Sheets"""
    if image_file is None: return ""
    try:
        img = Image.open(image_file)
        img.thumbnail((600, 600)) # ย่อรูปไม่ให้เกิน 600px
        buffered = io.BytesIO()
        img.convert('RGB').save(buffered, format="JPEG", quality=60)
        return base64.b64encode(buffered.getvalue()).decode()
    except: return ""

def base64_to_image(base64_string):
    """แปลง Base64 String กลับเป็นรูปภาพเพื่อแสดงผล"""
    try:
        if not base64_string or len(base64_string) < 100: return None
        img_data = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(img_data))
    except: return None

# ================= ฟังก์ชัน Google Sheets (ฉบับแก้บั๊ก 100%) =================

def connect_google_sheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    try:
        # 1. กรณีรันบนเว็บ (Streamlit Cloud) -> ใช้ Secrets
        if 'type' in st.secrets and 'private_key' in st.secrets:
            # สร้าง Dictionary จาก Secrets
            creds_dict = dict(st.secrets)
            
            # 🔥 แก้บั๊กสำคัญ: แปลงตัวอักษร \n ให้เป็น Newline จริงๆ
            if 'private_key' in creds_dict:
                creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            
        # 2. กรณีรันในเครื่องตัวเอง -> ใช้ไฟล์ credentials.json
        elif os.path.exists(CREDS_PATH):
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_PATH, scope)
            
        else:
            st.error("❌ ไม่พบกุญแจเชื่อมต่อ (ทั้ง Secrets และ credentials.json)")
            return None

        # เชื่อมต่อ
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
        
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Sheets ไม่ได้: {e}")
        return None

# ================= ฟังก์ชันจัดการข้อมูล =================

def load_data():
    """ดึงข้อมูลทั้งหมดมาแสดง"""
    sheet = connect_google_sheet()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            # แปลง ID เป็นตัวเลขเพื่อการเรียงลำดับ
            if 'ID' in df.columns:
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce')
            return df
        except: pass
    return pd.DataFrame()

def add_request(name, department, issue, img_str):
    """บันทึกงานใหม่"""
    sheet = connect_google_sheet()
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            all_records = sheet.get_all_values()
            new_id = len(all_records) # นับรวมหัวข้อแล้วรัน ID ต่อเลย
        except: new_id = 1
        
        try:
            sheet.append_row([new_id, timestamp, name, department, issue, 'รอคิว (Pending)', '', img_str])
            return True
        except: pass
    return False

def update_status(req_id, new_status, repair_note):
    """อัปเดตสถานะงาน (Admin)"""
    sheet = connect_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(req_id))
            if cell:
                sheet.update_cell(cell.row, 6, new_status) # คอลัมน์ F (Status)
                sheet.update_cell(cell.row, 7, repair_note) # คอลัมน์ G (Note)
                return True
        except: pass
    return False

def delete_request(req_id):
    """ลบงาน (Admin)"""
    sheet = connect_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(req_id))
            if cell:
                sheet.delete_rows(cell.row)
                return True
        except: pass
    return False

# ================= หน้าจอโปรแกรมหลัก (UI) =================

st.set_page_config(page_title="ระบบแจ้งซ่อม - ร.น.ส.๒", layout="wide", page_icon="🛠️")

# --- ส่วนหัว (Header) ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    # แสดงโลโก้ (ถ้ามีไฟล์)
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    else:
        st.write("*(Logo)*") 

with col_title:
    st.title("ระบบแจ้งซ่อมงานอาคาร")
    st.subheader("โรงเรียนราชนันทาจารย์ สามเสนวิทยาลัย ๒")

st.divider()

# --- เมนูแท็บ ---
tab1, tab2, tab3 = st.tabs(["📝 แจ้งซ่อม (สำหรับผู้ใช้)", "📊 ตารางคิวงาน (Real-time)", "🔧 จัดการงาน (สำหรับแอดมิน)"])

# --- TAB 1: แจ้งซ่อม ---
with tab1:
    st.header("กรอกข้อมูลแจ้งซ่อม")
    with st.form("repair_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("ชื่อ-นามสกุล ผู้แจ้ง")
            dept = st.text_input("กลุ่มสาระฯ / แผนกงาน / ห้อง") 
        with c2:
            issue = st.text_area("อาการเสีย / ปัญหาที่พบ")
            uploaded_file = st.file_uploader("แนบรูปภาพ (ถ้ามี)", type=['jpg', 'png', 'jpeg'])
        
        submitted = st.form_submit_button("🚀 ส่งแจ้งซ่อม", type="primary", use_container_width=True)
        
        if submitted:
            if name and issue and dept:
                with st.spinner("กำลังบันทึกข้อมูล..."):
                    img_str = process_image(uploaded_file)
                    success = add_request(name, dept, issue, img_str)
                
                if success:
                    st.toast("✅ บันทึกข้อมูลสำเร็จ!", icon="🎉")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ บันทึกไม่สำเร็จ โปรดตรวจสอบการเชื่อมต่อ")