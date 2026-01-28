import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from PIL import Image
import io
import base64
import time # เพิ่มมาเพื่อหน่วงเวลาตอนบันทึกนิดหน่อย

# --- ตั้งค่า Path และชื่อไฟล์ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH = os.path.join(BASE_DIR, 'credentials.json')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png') # Path ของไฟล์โลโก้
SHEET_NAME = "RepairData"

# ================= ฟังก์ชันช่วยเหลือต่างๆ =================

# --- แปลงรูปภาพเป็น Base64 (สำหรับเก็บใน Sheets) ---
def process_image(image_file):
    if image_file is None: return ""
    try:
        img = Image.open(image_file)
        img.thumbnail((600, 600)) # ย่อรูป
        buffered = io.BytesIO()
        # แปลงเป็น RGB ก่อนเซฟเป็น JPEG เพื่อป้องกันปัญหารูป PNG พื้นใส
        img.convert('RGB').save(buffered, format="JPEG", quality=60)
        return base64.b64encode(buffered.getvalue()).decode()
    except: return ""

# --- แปลง Base64 กลับเป็นรูปภาพ (สำหรับโชว์) ---
def base64_to_image(base64_string):
    try:
        if not base64_string or len(base64_string) < 100: return None
        img_data = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(img_data))
    except: return None

# --- เชื่อมต่อ Google Sheets ---
def connect_google_sheet():
    if not os.path.exists(CREDS_PATH):
        st.error(f"❌ ไม่พบไฟล์กุญแจ: {CREDS_PATH}")
        return None
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_PATH, scope)
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

# --- อัปเดตสถานะ (Admin) ---
def update_status(req_id, new_status, repair_note):
    sheet = connect_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(req_id))
            if cell:
                sheet.update_cell(cell.row, 6, new_status) # Col F
                sheet.update_cell(cell.row, 7, repair_note) # Col G
                return True
        except: pass
    return False

# --- ลบงาน (Admin) ---
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

# --- ส่วนหัวของเว็บ (Header & Logo) ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120) # แสดงโลโก้
    else:
        st.warning("ไม่พบไฟล์ logo.png")
with col_title:
    st.title("ระบบแจ้งซ่อมงานอาคาร")
    st.subheader("โรงเรียนราชนันทาจารย์ สามเสนวิทยาลัย ๒")

st.divider()

# --- แบ่งแท็บการทำงาน ---
tab1, tab2, tab3 = st.tabs(["📝 แจ้งซ่อม (สำหรับผู้ใช้)", "📊 ตารางคิวงาน (Real-time)", "🔧 จัดการงาน (สำหรับแอดมิน)"])

# ================= TAB 1: แจ้งซ่อม =================
with tab1:
    st.header("กรอกข้อมูลแจ้งซ่อม")
    with st.form("repair_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("ชื่อ-นามสกุล ผู้แจ้ง")
            dept = st.text_input("กลุ่มสาระฯ / แผนกงาน / ห้อง") 
        with c2:
            issue = st.text_area("อาการเสีย / ปัญหาที่พบ (ระบุให้ชัดเจน)")
            uploaded_file = st.file_uploader("แนบรูปภาพประกอบ (ถ้ามี)", type=['jpg', 'png', 'jpeg'])
        
        st.caption("*กรุณากรอกข้อมูลให้ครบถ้วนเพื่อความรวดเร็วในการบริการ")
        submitted = st.form_submit_button("🚀 ส่งแจ้งซ่อม", type="primary", use_container_width=True)
        
        if submitted:
            if name and issue and dept:
                with st.spinner("กำลังบันทึกข้อมูลเข้าสู่ระบบ..."):
                    img_str = process_image(uploaded_file)
                    success = add_request(name, dept, issue, img_str)
                
                if success:
                    st.toast("✅ บันทึกข้อมูลสำเร็จ!", icon="🎉")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ บันทึกไม่สำเร็จ โปรดลองใหม่อีกครั้ง")
            else:
                st.warning("⚠️ กรุณากรอก ชื่อ, แผนก และอาการเสียให้ครบ")

# ================= TAB 2: ดูคิวงาน =================
with tab2:
    col_head, col_ref = st.columns([4,1])
    with col_head: st.header("รายการแจ้งซ่อมล่าสุด")
    with col_ref: 
        if st.button("🔄 รีเฟรชข้อมูล", use_container_width=True): st.rerun()

    df = load_data()
    if not df.empty and 'ID' in df.columns:
        df = df.sort_values(by='ID', ascending=False) # เรียงงานใหม่สุดขึ้นก่อน
        
        for index, row in df.iterrows():
            status = row.get('Status', 'รอคิว (Pending)')
            # กำหนดสีตามสถานะ
            s_color = "red" if "รอคิว" in status else "green" if "เสร็จ" in status else "#FF8C00" # ส้ม
            s_icon = "🔴" if "รอคิว" in status else "🟢" if "เสร็จ" in status else "🟠"
            
            # แสดงเป็นการ์ด
            with st.expander(f"{s_icon} ID: {row.get('ID','-')} | {row.get('Issue','-')} [สถานะ: :{s_color}[{status}]]"):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.write(f"👤 **ผู้แจ้ง:** {row.get('Name','-')}")
                    st.write(f"🏢 **แผนก/ห้อง:** {row.get('Department','-')}")
                    st.write(f"🕒 **เวลาแจ้ง:** {row.get('Timestamp','-')}")
                with c2:
                    st.info(f"**📝 อาการ:** {row.get('Issue','-')}")
                    if row.get('RepairNote'):
                        st.success(f"**🛠️ บันทึกช่าง:** {row.get('RepairNote')}")
                with c3:
                    img = base64_to_image(row.get('Image', ''))
                    if img: st.image(img, caption="รูปภาพหน้างาน", use_column_width=True)
    else:
        st.info("ยังไม่มีรายการแจ้งซ่อมในระบบ")

# ================= TAB 3: Admin (ปรับปรุงใหม่) =================
with tab3:
    st.header("🔧 จัดการงานซ่อม (Admin)")
    pwd = st.text_input("🔑 รหัสผ่าน Admin", type="password")
    
    if pwd == "1234":
        st.success("เข้าสู่ระบบสำเร็จ!")
        st.divider()
        
        if st.button("🔄 โหลดข้อมูลล่าสุด"): st.rerun()
            
        df_admin = load_data()
        if not df_admin.empty and 'ID' in df_admin.columns:
            # เรียงเอา ID ล่าสุดขึ้นก่อน จะได้หาง่ายๆ
            df_admin = df_admin.sort_values(by='ID', ascending=False)
            
            st.write(f"📰 รายการงานทั้งหมด ({len(df_admin)} งาน)")
            
            # วนลูปสร้างรายการงานทีละงานแบบเรียงลงไปเลย (ใช้ง่ายกว่า Dropdown)
            for i, row in df_admin.iterrows():
                task_id = row['ID']
                status = row.get('Status', 'รอคิว (Pending)')
                s_color = "red" if "รอคิว" in status else "green" if "เสร็จ" in status else "orange"
                
                # กรอบแสดงงานแต่ละชิ้น
                with st.container(border=True):
                    # หัวข้องาน
                    st.markdown(f"### 🆔 {task_id} : {row.get('Issue','-')} (:{s_color}[{status}])")
                    
                    ac1, ac2 = st.columns([3, 1])
                    with ac1:
                        st.write(f"**ผู้แจ้ง:** {row.get('Name')} ({row.get('Department')}) | **เวลา:** {row.get('Timestamp')}")
                        # ฟอร์มสำหรับแก้ไข (ใช้ key เพื่อแยกฟอร์มแต่ละ ID ไม่ให้ตีกัน)
                        with st.form(key=f"form_{task_id}"):
                            st.write("🛠️ **อัปเดตสถานะงานนี้:**")
                            c_stat, c_note = st.columns(2)
                            with c_stat:
                                # ตั้งค่า Default ของ Dropdown ให้ตรงกับสถานะปัจจุบัน
                                status_options = ["รอคิว (Pending)", "กำลังดำเนินการ", "รออะไหล่", "ซ่อมเสร็จสิ้น"]
                                try: default_ix = status_options.index(status)
                                except: default_ix = 0
                                new_status = st.selectbox("สถานะ", status_options, index=default_ix, key=f"st_{task_id}")
                            with c_note:
                                new_note = st.text_input("บันทึกการซ่อม/หมายเหตุ", value=str(row.get('RepairNote','')), key=f"nt_{task_id}")
                            
                            # ปุ่มบันทึก
                            if st.form_submit_button("💾 บันทึกการแก้ไข", type="primary"):
                                update_status(task_id, new_status, new_note)
                                st.toast(f"อัปเดตงาน ID {task_id} เรียบร้อย!", icon="✅")
                                time.sleep(1) # รอให้ Toast ขึ้นก่อนรีเฟรช
                                st.rerun()

                    with ac2:
                        # แสดงรูป (ถ้ามี)
                        img = base64_to_image(row.get('Image', ''))
                        if img: st.image(img, caption="รูปงาน", use_column_width=True)
                        
                        st.divider()
                        # ปุ่มลบ (ใส่ Popover กันมือลั่น)
                        with st.popover("🗑️ ลบงานนี้", use_container_width=True):
                            st.write(f"⚠️ ยืนยันลบงาน ID {task_id}?")
                            if st.button("ยืนยันการลบ", type="primary", key=f"del_{task_id}"):
                                delete_request(task_id)
                                st.toast(f"ลบงาน ID {task_id} แล้ว!", icon="🗑️")
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("ไม่มีข้อมูลงานซ่อม")