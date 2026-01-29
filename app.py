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
CREDS_FILE = os.path.join(BASE_DIR, 'credentials.json')
SHEET_NAME = "RepairData"

# --- ฟังก์ชันจัดการรูปภาพ (บีบอัดให้เบาหวิว) ---
def get_logo_image():
    possible_names = ['Logo_ss2.jpg', 'logo.png', 'logo.jpg']
    for name in possible_names:
        path = os.path.join(BASE_DIR, name)
        if os.path.exists(path): return path
    return None

def process_image(image_file):
    """บีบอัดรูปให้เล็กพอที่จะเก็บใน Google Sheet"""
    if image_file is None: return ""
    try:
        img = Image.open(image_file)
        img.thumbnail((400, 400)) # ย่อรูป
        if img.mode != 'RGB': img = img.convert('RGB')
            
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=50) # ลดคุณภาพ
        
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # ถ้ายังใหญ่เกิน 50k ตัวอักษร ให้บีบอีก
        if len(img_str) > 50000:
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=30)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
        return img_str
    except: return ""

def base64_to_image(base64_string):
    try:
        if not base64_string or len(base64_string) < 100: return None
        img_data = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(img_data))
    except: return None

# ================= เชื่อมต่อ Google Sheets =================

def connect_google_sheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    try:
        creds = None
        # 1. อ่านจาก Secrets
        if 'google_credentials' in st.secrets:
            secret_value = st.secrets['google_credentials']
            if isinstance(secret_value, str):
                creds_dict = json.loads(secret_value)
            else:
                creds_dict = dict(secret_value)

            if 'private_key' in creds_dict:
                creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        # 2. อ่านจากไฟล์ในเครื่อง
        if creds is None and os.path.exists(CREDS_FILE):
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)

        if creds is None:
            st.error("❌ ไม่พบกุญแจเชื่อมต่อ")
            return None

        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# ================= จัดการข้อมูล =================

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
            # เพิ่ม Row ใหม่ (Column I ไว้เก็บรูปหลังซ่อม)
            sheet.append_row([new_id, timestamp, name, department, issue, 'รอคิว (Pending)', '', img_str, ''])
            return True
        except Exception as e:
            st.error(f"Error: {e}")
            return False
    return False

def update_status(req_id, new_status, repair_note, after_repair_img_str=None):
    sheet = connect_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(req_id))
            if cell:
                # อัปเดตสถานะ (Col F)
                sheet.update_cell(cell.row, 6, new_status)
                # อัปเดตบันทึก (Col G)
                sheet.update_cell(cell.row, 7, repair_note)
                
                # ถ้ามีรูปหลังซ่อมส่งมา ให้บันทึกใน Col I (ช่องที่ 9)
                if after_repair_img_str:
                    sheet.update_cell(cell.row, 9, after_repair_img_str)
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

# ================= หน้าจอ UI =================
st.set_page_config(page_title="ระบบแจ้งซ่อม - ร.น.ส.๒", layout="wide", page_icon="🛠️")

col_logo, col_title = st.columns([1, 5])
with col_logo:
    logo_path = get_logo_image()
    if logo_path: st.image(logo_path, width=120)

with col_title:
    st.title("ระบบแจ้งซ่อมงานอาคาร")
    st.subheader("โรงเรียนราชนันทาจารย์ สามเสนวิทยาลัย ๒")

st.divider()

tab1, tab2, tab3 = st.tabs(["📝 แจ้งซ่อม", "📊 ดูคิวงาน", "🔧 Admin"])

# --- TAB 1: แจ้งซ่อม ---
with tab1:
    with st.form("repair_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("ชื่อ-นามสกุล ผู้แจ้ง")
            # เปลี่ยนกลับเป็นช่องพิมพ์เอง (Text Input)
            dept = st.text_input("กลุ่มสาระ / แผนกงาน / ห้อง") 
        with c2:
            issue = st.text_area("อาการเสีย / รายละเอียด")
            uploaded_file = st.file_uploader("รูปภาพจุดที่เสีย (ถ้ามี)", type=['jpg', 'png', 'jpeg'])
        
        submitted = st.form_submit_button("🚀 ส่งแจ้งซ่อม", type="primary")
        
        if submitted:
            if name and issue:
                with st.spinner("กำลังส่งข้อมูล..."):
                    img_str = process_image(uploaded_file)
                    if add_request(name, dept, issue, img_str):
                        st.success("✅ บันทึกสำเร็จ!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("⚠️ กรุณากรอกชื่อและรายละเอียดอาการเสีย")

# --- TAB 2: ดูคิวงาน ---
with tab2:
    if st.button("🔄 รีเฟรช"): st.rerun()
    df = load_data()
    if not df.empty and 'ID' in df.columns:
        df = df.sort_values(by='ID', ascending=False)
        for index, row in df.iterrows():
            status = row.get('Status', 'รอคิว (Pending)')
            s_color = "red" if "รอคิว" in status else "green" if "เสร็จ" in status else "orange"
            
            # หัวข้อ Expander
            with st.expander(f"ID: {row.get('ID')} | {row.get('Issue')} [:{s_color}[{status}]]"):
                c1, c2 = st.columns([1, 1])
                
                with c1:
                    st.markdown("#### 📋 รายละเอียด")
                    st.write(f"**ผู้แจ้ง:** {row.get('Name')}")
                    st.write(f"**หน่วยงาน:** {row.get('Department')}")
                    st.write(f"**เวลา:** {row.get('Timestamp')}")
                    st.info(f"**อาการ:** {row.get('Issue')}")
                    
                    if row.get('RepairNote'): 
                        st.success(f"**👨‍🔧 ช่างบันทึก:** {row.get('RepairNote')}")

                with c2:
                    st.markdown("#### 🖼️ รูปภาพ")
                    # แสดงรูป ก่อนซ่อม vs หลังซ่อม
                    img_before = base64_to_image(row.get('Image', ''))
                    # ลองดึงรูปหลังซ่อม (Column I ซึ่งใน DataFrame อาจชื่อไม่มี header หรือเป็น index)
                    try:
                        # ใน pandas ถ้าอ่าน sheet มา คอลัมน์ที่ 9 อาจจะชื่อว่างๆ หรือ 'Unnamed: 8'
                        # เราจะลองหา key ที่เป็นค่า img string
                        cols = df.columns.tolist()
                        img_after_str = row.iloc[8] if len(row) > 8 else ""
                    except: img_after_str = ""

                    img_after = base64_to_image(str(img_after_str))

                    ic1, ic2 = st.columns(2)
                    with ic1:
                        if img_before: 
                            st.image(img_before, caption="ก่อนซ่อม", use_column_width=True)
                        else:
                            st.write("*(ไม่มีรูปก่อนซ่อม)*")
                    with ic2:
                        if img_after:
                            st.image(img_after, caption="✅ หลังซ่อม", use_column_width=True)
                        elif "เสร็จ" in status:
                            st.write("*(ไม่มีรูปหลังซ่อม)*")

    else:
        st.info("ไม่พบข้อมูล")

# --- TAB 3: Admin ---
with tab3:
    pwd = st.text_input("🔑 รหัสผ่าน Admin", type="password")
    if pwd == "1234":
        st.success("Login OK")
        df_admin = load_data()
        if not df_admin.empty:
            for i, row in df_admin.iterrows():
                task_id = row['ID']
                with st.container(border=True):
                    st.write(f"**ID {task_id}: {row.get('Issue')}** ({row.get('Department')})")
                    
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        with st.form(key=f"f_{task_id}"):
                            col_s, col_n = st.columns(2)
                            with col_s:
                                st_opts = ["รอคิว (Pending)", "กำลังดำเนินการ", "รออะไหล่", "ซ่อมเสร็จสิ้น"]
                                try: idx = st_opts.index(row.get('Status'))
                                except: idx = 0
                                new_st = st.selectbox("สถานะ", st_opts, index=idx, key=f"s_{task_id}")
                            with col_n:
                                new_nt = st.text_input("บันทึกการซ่อม", value=str(row.get('RepairNote','')), key=f"n_{task_id}")
                            
                            # เพิ่มช่องอัปโหลดรูปหลังซ่อม
                            st.write("📸 **อัปโหลดรูปงานที่เสร็จแล้ว (ถ้ามี):**")
                            admin_file = st.file_uploader("", type=['jpg','png'], key=f"u_{task_id}")
                            
                            if st.form_submit_button("💾 บันทึกการเปลี่ยนแปลง"):
                                with st.spinner("กำลังบันทึก..."):
                                    # แปลงรูปหลังซ่อม (ถ้ามี)
                                    after_img_str = process_image(admin_file) if admin_file else None
                                    
                                    update_status(task_id, new_st, new_nt, after_img_str)
                                    st.success("เรียบร้อย!")
                                    time.sleep(1)
                                    st.rerun()
                    with c2:
                        st.write("")
                        st.write("")
                        st.write("")
                        with st.popover("🗑️ ลบ"):
                            if st.button("ยืนยัน", key=f"d_{task_id}", type="primary"):
                                delete_request(task_id)
                                st.rerun()