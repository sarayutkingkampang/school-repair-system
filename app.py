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

# --- ตั้งค่า ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH = os.path.join(BASE_DIR, 'credentials.json')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
SHEET_NAME = "RepairData"

# --- ฟังก์ชันจัดการรูปภาพ ---
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

# --- เชื่อมต่อ Google Sheets (ฉบับนักสืบ 🕵️‍♂️) ---
def connect_google_sheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    try:
        # 1. เช็ค Secrets บนเว็บ
        if 'type' in st.secrets and 'private_key' in st.secrets:
            creds_dict = dict(st.secrets)
            
            # 🔥 ดึงกุญแจออกมาตรวจ
            pk = creds_dict['private_key']
            
            # --- ส่วนแสดงผลตรวจสอบ (Diagnostic) ---
            with st.expander("🕵️‍♂️ ตรวจสอบกุญแจ (Debug Info)", expanded=True):
                st.write(f"🔑 **ความยาวกุญแจ:** {len(pk)} ตัวอักษร")
                st.write(f"✅ **ขึ้นต้นด้วย:** `{pk[:20]}...` (ต้องเป็น `-----BEGIN PRIVATE...`)")
                st.write(f"✅ **ลงท้ายด้วย:** `...{pk[-20:]}` (ต้องเป็น `...END PRIVATE KEY-----`)")
                
                if '\\n' in pk:
                    st.warning("⚠️ พบตัวอักษร \\n (ระบบกำลังแก้ไขให้อัตโนมัติ...)")
                else:
                    st.success("✅ ไม่พบตัวอักษร \\n (กุญแจดูปกติ)")

            # 🔥 แก้ไขกุญแจอัตโนมัติ (ล้างขยะ + แปลงบรรทัด)
            pk_fixed = pk.replace('\\n', '\n').strip('"').strip("'").strip()
            creds_dict['private_key'] = pk_fixed
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            
        # 2. เช็คไฟล์ในเครื่อง
        elif os.path.exists(CREDS_PATH):
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_PATH, scope)
            
        else:
            st.error("❌ ไม่พบกุญแจเชื่อมต่อ")
            return None

        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
        
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Sheets ไม่ได้: {e}")
        return None

# --- ฟังก์ชันจัดการข้อมูล ---
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

# ================= UI หลัก =================
st.set_page_config(page_title="ระบบแจ้งซ่อม - ร.น.ส.๒", layout="wide", page_icon="🛠️")

col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    else:
        st.write("") 

with col_title:
    st.title("ระบบแจ้งซ่อมงานอาคาร")
    st.subheader("โรงเรียนราชนันทาจารย์ สามเสนวิทยาลัย ๒")

st.divider()

tab1, tab2, tab3 = st.tabs(["📝 แจ้งซ่อม", "📊 ตารางงาน", "🔧 Admin"])

with tab1:
    with st.form("repair_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("ชื่อ-นามสกุล")
            dept = st.text_input("แผนก/ห้อง") 
        with c2:
            issue = st.text_area("อาการเสีย")
            uploaded_file = st.file_uploader("รูปภาพ (ถ้ามี)", type=['jpg', 'png', 'jpeg'])
        
        if st.form_submit_button("ส่งข้อมูล", type="primary"):
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
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("ไม่พบข้อมูล")

with tab3:
    pwd = st.text_input("รหัสผ่าน Admin", type="password")
    if pwd == "1234":
        st.success("Login OK")
        df_admin = load_data()
        if not df_admin.empty:
            for i, row in df_admin.iterrows():
                with st.container(border=True):
                    st.write(f"**ID {row['ID']}: {row['Issue']}**")
                    with st.popover("ลบงาน"):
                        if st.button("ยืนยันลบ", key=f"del_{row['ID']}"):
                            delete_request(row['ID'])
                            st.rerun()