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

# --- เชื่อมต่อ Google Sheets (ฉบับอัปเกรดล่าสุด) ---
def connect_google_sheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    try:
        # 1. เช็คว่ามี Secrets บนเว็บไหม (แบบใหม่: เช็ค key โดยตรง)
        if 'type' in st.secrets and 'private_key' in st.secrets:
            # แปลง st.secrets ให้เป็น Dictionary ปกติ
            creds_dict = dict(st.secrets)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            
        # 2. ถ้าไม่มี Secrets ให้หาไฟล์ในเครื่อง (สำหรับรันในคอมตัวเอง)
        elif os.path.exists(CREDS_PATH):
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_PATH, scope)
            
        else:
            st.error("❌ ไม่พบกุญแจเชื่อมต่อ (Credentials not found)")
            return None

        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
        
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Sheets ไม่ได้: {e}")
        return None

# --- โหลดข้อมูล ---
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

# --- บันทึกงานใหม่ ---
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

# --- อัปเดตสถานะ ---
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

# --- ลบงาน ---
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

# ================= หน้าจอโปรแกรมหลัก =================
st.set_page_config(page_title="ระบบแจ้งซ่อม - ร.น.ส.๒", layout="wide", page_icon="🛠️")

col_logo, col_title = st.columns([1, 5])
with col_logo:
    # พยายามโหลดโลโก้ ถ้าไม่เจอก็ข้ามไป
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    else:
        st.write("") 

with col_title:
    st.title("ระบบแจ้งซ่อมงานอาคาร")
    st.subheader("โรงเรียนราชนันทาจารย์ สามเสนวิทยาลัย ๒")

st.divider()

tab1, tab2, tab3 = st.tabs(["📝 แจ้งซ่อม (สำหรับผู้ใช้)", "📊 ตารางคิวงาน (Real-time)", "🔧 จัดการงาน (สำหรับแอดมิน)"])

# TAB 1: แจ้งซ่อม
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
                    st.error("❌ บันทึกไม่สำเร็จ")
            else:
                st.warning("⚠️ กรุณากรอกข้อมูลให้ครบ")

# TAB 2: ดูคิวงาน
with tab2:
    col_head, col_ref = st.columns([4,1])
    with col_head: st.header("รายการแจ้งซ่อมล่าสุด")
    with col_ref: 
        if st.button("🔄 รีเฟรช", use_container_width=True): st.rerun()

    df = load_data()
    if not df.empty and 'ID' in df.columns:
        df = df.sort_values(by='ID', ascending=False)
        for index, row in df.iterrows():
            status = row.get('Status', 'รอคิว (Pending)')
            s_color = "red" if "รอคิว" in status else "green" if "เสร็จ" in status else "#FF8C00"
            s_icon = "🔴" if "รอคิว" in status else "🟢" if "เสร็จ" in status else "🟠"
            
            with st.expander(f"{s_icon} ID: {row.get('ID','-')} | {row.get('Issue','-')} [สถานะ: :{s_color}[{status}]]"):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.write(f"👤 **ผู้:** {row.get('Name','-')} | 🏢 **ห้อง:** {row.get('Department','-')}")
                    st.write(f"🕒 {row.get('Timestamp','-')}")
                with c2:
                    st.info(f"**อาการ:** {row.get('Issue','-')}")
                    if row.get('RepairNote'): st.success(f"**ช่าง:** {row.get('RepairNote')}")
                with c3:
                    img = base64_to_image(row.get('Image', ''))
                    if img: st.image(img, use_column_width=True)
    else:
        st.info("ยังไม่มีรายการแจ้งซ่อม")

# TAB 3: Admin
with tab3:
    st.header("🔧 Admin Only")
    pwd = st.text_input("🔑 รหัสผ่าน", type="password")
    
    if pwd == "1234":
        st.success("Login OK!")
        if st.button("🔄 โหลดงาน"): st.rerun()
        df_admin = load_data()
        
        if not df_admin.empty and 'ID' in df_admin.columns:
            df_admin = df_admin.sort_values(by='ID', ascending=False)
            for i, row in df_admin.iterrows():
                task_id = row['ID']
                with st.container(border=True):
                    st.markdown(f"**ID {task_id}: {row.get('Issue','-')}**")
                    ac1, ac2 = st.columns([3, 1])
                    with ac1:
                        with st.form(key=f"form_{task_id}"):
                            c_stat, c_note = st.columns(2)
                            with c_stat:
                                status_options = ["รอคิว (Pending)", "กำลังดำเนินการ", "รออะไหล่", "ซ่อมเสร็จสิ้น"]
                                try: dx = status_options.index(row.get('Status'))
                                except: dx = 0
                                new_status = st.selectbox("สถานะ", status_options, index=dx, key=f"st_{task_id}")
                            with c_note:
                                new_note = st.text_input("บันทึกช่าง", value=str(row.get('RepairNote','')), key=f"nt_{task_id}")
                            
                            if st.form_submit_button("💾 บันทึก"):
                                update_status(task_id, new_status, new_note)
                                st.rerun()
                    with ac2:
                         with st.popover("🗑️ ลบ"):
                            if st.button("ยืนยัน", key=f"del_{task_id}", type="primary"):
                                delete_request(task_id)
                                st.rerun()