import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
from streamlit_calendar import calendar  


# 구글 시트 인증
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1rDlVNsJrPHB5cjLsAJpqTRH_WEsUBVrqU61CtQVMZas"
worksheet = client.open_by_url(SHEET_URL).sheet1

def load_data():
    data = worksheet.get_all_values() 
    if not data: 
        st.error("구글 시트에서 데이터를 불러올 수 없습니다.")
        return pd.DataFrame()
    data = [row for row in data if any(cell.strip() for cell in row)]  
    headers = data[0]  
    rows = data[1:]    
    df = pd.DataFrame(rows, columns=headers)
    # st.write(df)  # 데이터 확인
    return df

patient_db = load_data()

DATA_PATH = "patients.csv"
DONE_PATH = "completed.csv"
AUDIO_LINKS_PATH = "audio_links.csv"

# Google Drive 음성 파일 링크 생성 함수
def get_audio_file_link(patient_id, date, df):
    try:
        audio_df = pd.read_csv(AUDIO_LINKS_PATH)

        # 날짜 형식 통일: '2025.3.5'
        audio_df["검사 날짜"] = pd.to_datetime(audio_df["검사 날짜"], errors="coerce").dt.strftime("%Y.%-m.%-d")

        if isinstance(date, (datetime, pd.Timestamp)):
            date_str = date.strftime("%Y.%-m.%-d")
        else:
            date_str = pd.to_datetime(date).strftime("%Y.%-m.%-d")

        row = audio_df[
            (audio_df['환자번호'] == patient_id) & (audio_df['검사 날짜'] == date_str)
        ]

        if not row.empty:
            return row.iloc[0]['파일 링크']  
    except Exception as e:
        st.error(f"음성 파일 로딩 오류: {e}")

    return None

if os.path.exists(DONE_PATH):
    completed_db = pd.read_csv(DONE_PATH)
else:
    completed_db = pd.DataFrame(columns=["환자번호", "날짜", "항목"])

# 기능 선택
menu = st.sidebar.radio("기능 선택", [
    "📁 전체 환자 관리",
    "📋 새 환자 등록",
    "📂 환자 목록 보기",
    "✅ 오늘 해야 할 검사",
    "📌 내일 예정된 검사",
    "🗓️ 달력 뷰어",
    "🗂️ 외래 일정 관리",
    "📊 월별 검사 통계"
], key="menu_select")

def mark_completed_tests():
    today = datetime.today().date()
    
    for _, row in patient_db.iterrows():
        for 항목 in ["음성", "증상", "환경", "웨어러블"]:
            if row[항목] == "●":
                if today > row["날짜"]:
                    if completed_db[(completed_db["환자번호"] == row["환자번호"]) &
                                    (completed_db["항목"] == 항목)].empty:
                        completed_db = pd.concat([completed_db, pd.DataFrame([{
                            "환자번호": row["환자번호"], 
                            "날짜": row["날짜"],
                            "항목": 항목
                        }])])
    
    completed_db.to_csv(DONE_PATH, index=False)

    # 환자 일정 생성 함수
def generate_schedule(patient):
    baseline = datetime.strptime(patient["Baseline"], "%Y-%m-%d").date()
    start_date = datetime.strptime(patient["Start_date"], "%Y-%m-%d").date()
    음성_주기 = patient["음성_주기"]
    증상_주기 = patient["증상_주기"]
    환경_사용 = patient["환경_사용"]
    웨어러블_사용 = patient["웨어러블_사용"]
    외래일 = [datetime.strptime(d.strip(), "%Y-%m-%d").date() for d in patient["외래일"].split("|") if d.strip()]

    dates = [baseline + timedelta(days=i) for i in range(365)]
  
    def is_voice(date):
        gap = {"1w": 7, "2w": 14, "1m": 30}[음성_주기]
        return date == baseline or date == start_date or (date > start_date and (date - start_date).days % gap == 0)

    def is_symptom(date):
        return True if 증상_주기 == "daily" else date.weekday() in [0, 2, 4, 5]

    def is_environment(date):
        if 환경_사용 == "비착용":
            return False
        # 환경: baseline 기준 0일부터 4주, 이후 3,6,9,12개월의 앞단 4주
        if baseline <= date <= baseline + timedelta(days=27):
            return True
        for m in [3, 6, 9, 12]:
            check_day = baseline + relativedelta(months=+m)
            start = check_day - timedelta(days=27)
            if start <= date <= check_day:
                return True
        return False

    def is_wearable(date):
        if 웨어러블_사용 == "비착용":
            return False
        # 웨어러블: baseline 기준 0일부터 2주, 이후 3,6,9,12개월의 앞단 2주
        if baseline <= date <= baseline + timedelta(days=13):
            return True
        for m in [3, 6, 9, 12]:
            check_day = baseline + relativedelta(months=+m)
            start = check_day - timedelta(days=13)
            if start <= date <= check_day:
                return True
        return False

    # 일정 데이터 프레임 생성
    df = pd.DataFrame({
        "환자번호": patient["환자번호"],
        "날짜": dates,
        "음성": ["●" if is_voice(d) else "" for d in dates],
        "증상": ["●" if is_symptom(d) else "" for d in dates],
        "환경": ["●" if is_environment(d) else "" for d in dates],
        "웨어러블": ["●" if is_wearable(d) else "" for d in dates],
        "음성_담당자": patient["음성_담당자"],
        "증상_담당자": patient["증상_담당자"],
        "환경_담당자": patient["환경_담당자"],
        "웨어러블_담당자": patient["웨어러블_담당자"]
    })

    return df


if menu == "📁 전체 환자 관리":
    st.subheader("📁 전체 환자 점오표 확인")

    st.markdown("### 📊 등록 환자 기본 통계")
    total_patients = patient_db["환자번호"].nunique()
    st.write(f"**총 등록 환자 수:** {total_patients}명")

    st.write("**각 항목별 검사 진행 환자 수**")
    def count_active(dataframe, column_name):
        return dataframe[dataframe[column_name] != "비착용"].shape[0]

    voice_count = patient_db[patient_db["음성_주기"].notnull()].shape[0]
    symptom_count = patient_db[patient_db["증상_주기"].notnull()].shape[0]
    environment_count = count_active(patient_db, "환경_사용")
    wearable_count = count_active(patient_db, "웨어러블_사용")

    st.markdown("### 🕒 검사 진행률 (오늘 기준)")

    def get_progress_stats(item):
        today = datetime.today().date()
        all_sched = []
        for _, row in patient_db.iterrows():
            schedule = generate_schedule(row)
            sch = schedule[schedule[item] == "●"].copy()
            sch = sch[sch["날짜"] <= today]  # 오늘 이전 날짜만 필터링
            sch["환자번호"] = row["환자번호"]
            all_sched.append(sch)

        if not all_sched:
            return 0, 0, 0, 0, 0

        df_all = pd.concat(all_sched)
        total_cnt = len(df_all)

        done_cnt = completed_db[completed_db["항목"] == item].shape[0]
        undone_cnt = total_cnt - done_cnt
        progress = (done_cnt / total_cnt * 100) if total_cnt > 0 else 0
        drop = (undone_cnt / total_cnt * 100) if total_cnt > 0 else 0

        return total_cnt, done_cnt, undone_cnt, progress, drop

    progress_data = []
    for 항목 in ["음성", "증상", "환경", "웨어러블"]:
        total_cnt, done_cnt, undone_cnt, progress, drop = get_progress_stats(항목)
        progress_data.append({
            "검사 항목": 항목,
            "예정건수": total_cnt,
            "완료건수": done_cnt,
            "미완료건수": undone_cnt,
            "진행률(%)": f"{progress:.1f}",
            "Drop률(%)": f"{drop:.1f}"
        })

    col1, col2 = st.columns(2)
    with col1:
        st.metric("음성 검사 시행 환자 수", voice_count)
        st.metric("환경 착용 환자 수", environment_count)
    with col2:
        st.metric("증상 검사 시행 환자 수", symptom_count)
        st.metric("웨어러블 착용 환자 수", wearable_count)

    if patient_db.empty:
        st.warning("등록된 환자가 없습니다.")
        st.stop()

    # 점오표
    full_schedule = pd.concat([generate_schedule(row) for _, row in patient_db.iterrows()])
    full_schedule["날짜"] = pd.to_datetime(full_schedule["날짜"])

    melted = full_schedule.melt(
        id_vars=["환자번호", "날짜"],
        value_vars=["음성", "증상", "환경", "웨어러블"],
        var_name="항목",
        value_name="검사"
    )

    melted["날짜"] = pd.to_datetime(melted["날짜"]).dt.date

    # 완료된 검사 이력
    if os.path.exists("completed.csv"):
        completed = pd.read_csv("completed.csv")
        completed["날짜"] = pd.to_datetime(completed["날짜"]).dt.date
        if "결과" in completed.columns:
            merged = pd.merge(melted, completed, on=["환자번호", "항목", "날짜"], how="left")
            merged["표시"] = merged.apply(lambda row: row["결과"] if pd.notna(row["결과"]) else row["검사"], axis=1)
        else:
            merged = melted.copy()
            merged["표시"] = merged["검사"]
    else:
        merged = melted.copy()
        merged["표시"] = merged["검사"]

    # 점오표 출력
    점오표 = merged.pivot_table(
        index=["환자번호", "항목"],
        columns="날짜",
        values="표시",
        aggfunc="first",
        fill_value=""
    )

    st.dataframe(점오표, use_container_width=True)

    progress_df = pd.DataFrame(progress_data)
    st.dataframe(progress_df, use_container_width=True)









# user_list = ["전체 관리자", "김은선", "최민지"]  
if menu == "📋 새 환자 등록":
    st.subheader("📋 새 환자 등록")

    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            환자번호 = st.text_input("환자번호")
            baseline = st.date_input("Baseline 날짜")
            start_date = st.date_input("Start_date")
            음성_주기 = st.selectbox("음성_주기", ["1w", "2w", "1m"], key="voice_cycle")
            증상_주기 = st.selectbox("증상_주기", ["daily", "weekly"], key="symptom_cycle")
        with col2:
            환경_사용 = st.radio("환경 착용 여부", ["착용", "비착용"], horizontal=True, key="env_use")
            웨어러블_사용 = st.radio("웨어러블 착용 여부", ["착용", "비착용"], horizontal=True, key="wear_use")
            외래1차 = st.date_input("첫 외래 일정")

        st.markdown("#### 담당자 지정")
        col3, col4 = st.columns(2)
        with col3:
            음성_담당자 = st.selectbox("음성 담당자", user_list[1:], key="staff_voice")
            증상_담당자 = st.selectbox("증상 담당자", user_list[1:], key="staff_symptom")
        with col4:
            환경_담당자 = st.selectbox("환경 담당자", user_list[1:], key="staff_env")
            웨어러블_담당자 = st.selectbox("웨어러블 담당자", user_list[1:], key="staff_wear")

        제출 = st.form_submit_button("등록 완료")
        if 제출:
            new_data = {
                "환자번호": 환자번호,
                "Baseline": baseline.strftime("%Y-%m-%d"),
                "Start_date": start_date.strftime("%Y-%m-%d"),
                "음성_주기": 음성_주기,
                "증상_주기": 증상_주기,
                "환경_사용": 환경_사용,
                "웨어러블_사용": 웨어러블_사용,
                "외래일": 외래1차.strftime("%Y-%m-%d"),
                "음성_담당자": 음성_담당자,
                "증상_담당자": 증상_담당자,
                "환경_담당자": 환경_담당자,
                "웨어러블_담당자": 웨어러블_담당자
            }
   
            patient_db.loc[len(patient_db)] = new_data
            patient_db.to_csv(DATA_PATH, index=False)
    
            worksheet.append_row([
                환자번호,
                baseline.strftime("%Y-%m-%d"),
                start_date.strftime("%Y-%m-%d"),
                외래1차.strftime("%Y-%m-%d"),
                음성_주기,
                증상_주기,
                환경_사용,
                웨어러블_사용,
                음성_담당자,
                증상_담당자,
                환경_담당자,
                웨어러블_담당자
            ])

            st.success(f"{환자번호} 등록 완료")



if os.path.exists(DONE_PATH):
    completed_db = pd.read_csv(DONE_PATH)
else:
    completed_db = pd.DataFrame(columns=["환자번호", "날짜", "항목"])




if menu == "📂 환자 목록 보기":
    st.subheader("📂 환자 목록 보기")

    if patient_db.empty:
        st.warning("등록된 환자가 없습니다.")
        st.stop()

    선택 = st.selectbox("환자 선택", sorted(patient_db["환자번호"].unique()), key=f"patient_select_{len(patient_db)}")


    if st.button("🗑️ 선택 환자 삭제", key=f"delete_{선택}"):
        patient_db.drop(patient_db[patient_db["환자번호"] == 선택].index, inplace=True)
        patient_db.to_csv(DATA_PATH, index=False)
        st.success(f"{선택} 환자 정보가 삭제되었습니다.")
        st.experimental_rerun()

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    col_title, col_button = st.columns([6, 1])
    with col_title:
        st.markdown("### 📝 기본 정보")
    with col_button:
        if st.button("✏️ 수정", key=f"edit_toggle_{선택}"):
            st.session_state.edit_mode = not st.session_state.edit_mode


    patient = patient_db[patient_db["환자번호"] == 선택].iloc[0]
    schedule = generate_schedule(patient)

    if not st.session_state.edit_mode:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"- **Baseline:** {patient['Baseline']}")
            st.markdown(f"- **Start_date:** {patient['Start_date']}")
            st.markdown(f"- **외래일:** {patient['외래일']}")
        with col2:
            st.markdown(f"- **음성 주기:** {patient['음성_주기']}")
            st.markdown(f"- **증상 주기:** {patient['증상_주기']}")
            st.markdown(f"- **환경 착용:** {patient['환경_사용']}")
            st.markdown(f"- **웨어러블 착용:** {patient['웨어러블_사용']}")

        st.markdown("#### 담당자")
        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f"- 음성 담당자: {patient['음성_담당자']}")
            st.markdown(f"- 증상 담당자: {patient['증상_담당자']}")
        with col4:
            st.markdown(f"- 환경 담당자: {patient['환경_담당자']}")
            st.markdown(f"- 웨어러블 담당자: {patient['웨어러블_담당자']}")

    else:
        col1, col2 = st.columns(2)
        with col1:
            edit_baseline = st.date_input("Baseline", value=pd.to_datetime(patient['Baseline']).date(), key="edit_baseline")
            edit_start = st.date_input("Start_date", value=pd.to_datetime(patient['Start_date']).date(), key="edit_start")
            edit_outpatient = st.text_input("외래일 (|로 구분)", value=patient["외래일"], key="edit_outpatient")
        with col2:
            edit_voice = st.selectbox("음성 주기", ["1w", "2w", "1m"], index=["1w", "2w", "1m"].index(patient["음성_주기"]))
            edit_symptom = st.selectbox("증상 주기", ["daily", "weekly"], index=["daily", "weekly"].index(patient["증상_주기"]))
            edit_env = st.radio("환경 착용", ["착용", "비착용"], index=["착용", "비착용"].index(patient["환경_사용"]))
            edit_wear = st.radio("웨어러블 착용", ["착용", "비착용"], index=["착용", "비착용"].index(patient["웨어러블_사용"]))

        st.markdown("#### 담당자 수정")
        col3, col4 = st.columns(2)
        with col3:
            edit_voice_staff = st.selectbox("음성 담당자", user_list[1:], index=user_list[1:].index(patient["음성_담당자"]))
            edit_symptom_staff = st.selectbox("증상 담당자", user_list[1:], index=user_list[1:].index(patient["증상_담당자"]))
        with col4:
            edit_env_staff = st.selectbox("환경 담당자", user_list[1:], index=user_list[1:].index(patient["환경_담당자"]))
            edit_wear_staff = st.selectbox("웨어러블 담당자", user_list[1:], index=user_list[1:].index(patient["웨어러블_담당자"]))

        if st.button("💾 수정 내용 저장"):
            idx = patient_db[patient_db["환자번호"] == 선택].index[0]

            patient_db.at[idx, "Baseline"] = edit_baseline.strftime("%Y-%m-%d")
            patient_db.at[idx, "Start_date"] = edit_start.strftime("%Y-%m-%d")
            patient_db.at[idx, "외래일"] = edit_outpatient
            patient_db.at[idx, "음성_주기"] = edit_voice
            patient_db.at[idx, "증상_주기"] = edit_symptom
            patient_db.at[idx, "환경_사용"] = edit_env
            patient_db.at[idx, "웨어러블_사용"] = edit_wear
            patient_db.at[idx, "음성_담당자"] = edit_voice_staff
            patient_db.at[idx, "증상_담당자"] = edit_symptom_staff
            patient_db.at[idx, "환경_담당자"] = edit_env_staff
            patient_db.at[idx, "웨어러블_담당자"] = edit_wear_staff

            patient_db.to_csv(DATA_PATH, index=False)  # 수정된 데이터를 저장
            st.success("기본 정보가 수정되었습니다.")
            st.session_state.edit_mode = False
            st.experimental_rerun()  # 수정 후 페이지 새로고침


    st.markdown("#### 🔍 검사 상태 필터링")
    검사_기간 = st.date_input("날짜 범위 선택", [datetime.today() - timedelta(days=14), datetime.today()], key="filter_date")
    항목_필터 = st.multiselect("항목 선택", ["음성", "증상", "환경", "웨어러블"], default=["음성", "증상", "환경", "웨어러블"], key="filter_item")

    filtered_schedule = schedule[
        (schedule["날짜"] >= 검사_기간[0]) &
        (schedule["날짜"] <= 검사_기간[1])
    ]

    melted = filtered_schedule.melt(
        id_vars=["날짜"],
        value_vars=항목_필터,
        var_name="항목",
        value_name="표시"
    )

    completed = completed_db[completed_db["환자번호"] == 선택]
    completed["날짜"] = pd.to_datetime(completed["날짜"]).dt.date

    melted["표시"] = melted.apply(
        lambda row: "🔴" if ((completed["날짜"] == row["날짜"]) & (completed["항목"] == row["항목"])).any()
        else ("⚫" if row["표시"] == "●" else ""), axis=1
    )

    st.markdown("#### 🗓️ 환자 검사 타임라인")
    pivot = melted.pivot(index="항목", columns="날짜", values="표시").fillna("")
    st.dataframe(pivot, use_container_width=True)

    st.markdown("#### ⏳ 미완료 검사 이력 / 수동 처리")
    검사필터 = st.selectbox("항목 필터", ["전체"] + 항목_필터, key="이력항목")
    날짜필터 = st.date_input("날짜 선택 (필터용)", value=datetime.today(), key="이력날짜")

    이력대상 = melted[
        ((melted["표시"] == "⚫") | (melted["표시"] == "🔴")) &
        ((melted["항목"] == 검사필터) if 검사필터 != "전체" else True) &
        (melted["날짜"] == 날짜필터)
    ]

    for _, row in 이력대상.iterrows():
        is_done = row["표시"] == "🔴"
        cols = st.columns([3, 2, 3])
        cols[0].write(row["날짜"])
        cols[1].write(row["항목"])

        if is_done:
            if row["항목"] == "음성":
                link = get_audio_file_link(선택, row["날짜"], patient_db)
                if link:
                    cols[2].markdown(f"[🎧 재생하기]({link})", unsafe_allow_html=True)
                else:
                    cols[2].write("🔇 음성 없음")
            if cols[2].button("❌ 완료 취소", key=f"cancel_{row['날짜']}_{row['항목']}"):
                completed_db = completed_db[~(
                    (completed_db["환자번호"] == 선택) &
                    (completed_db["날짜"] == str(row["날짜"])) &
                    (completed_db["항목"] == row["항목"])
                )]
                completed_db.to_csv(DONE_PATH, index=False)
                st.rerun()
        else:
            if cols[2].button("✅ 완료 처리", key=f"manual_done_{row['날짜']}_{row['항목']}"):
                completed_db.loc[len(completed_db)] = {
                    "환자번호": 선택,
                    "날짜": row["날짜"],
                    "항목": row["항목"]
                }
                completed_db.to_csv(DONE_PATH, index=False)
                st.rerun()

    today = datetime.today().date()
    past_uncompleted = melted[
        (melted["표시"] == "⚫") & 
        (melted["날짜"] < today)
    ]
    if past_uncompleted.empty:
        st.info("오늘 이전에 완료되지 않은 검사가 없습니다.")
    else:
        for _, row in past_uncompleted.iterrows():
            cols = st.columns([3, 2, 3])
            cols[0].write(row["날짜"])
            cols[1].write(row["항목"])
            completed_db.loc[len(completed_db)] = {
                "환자번호": 선택,
                "날짜": row["날짜"],
                "항목": row["항목"]
            }
            completed_db.to_csv(DONE_PATH, index=False)
            st.rerun()







elif menu == "✅ 오늘 해야 할 검사":
    st.subheader("✅ 오늘 해야 할 검사")
    today = datetime.today().date()

    항목_필터 = st.multiselect("검사 항목 선택", ["음성", "환경", "웨어러블"], default=["음성", "환경", "웨어러블"], key="test_filter")
    환자_필터 = st.selectbox("환자 선택", ["전체 보기"] + patient_db["환자번호"].unique().tolist(), key="patient_filter")

    # 전체 환자 스케줄 생성
    full = pd.concat([generate_schedule(row) for _, row in patient_db.iterrows()])
    today_df = full[full["날짜"] == today]

    melted = today_df.melt(
        id_vars=["환자번호", "날짜"],
        value_vars=항목_필터,  
        var_name="항목",
        value_name="검사"
    )
    if 환자_필터 != "전체 보기":
        melted = melted[melted["환자번호"] == 환자_필터]

    검사_필요 = melted[melted["검사"] == "●"].copy()
    검사_필요["완료여부"] = 검사_필요.apply(
        lambda row: "✅ 완료됨" if (
            (completed_db["환자번호"] == row["환자번호"]) &
            (completed_db["날짜"] == str(row["날짜"])) &
            (completed_db["항목"] == row["항목"])
        ).any() else "", axis=1
    )

    if 검사_필요.empty:
        st.info("오늘 해야 할 검사 항목이 없습니다.")
    else:
        for idx, row in 검사_필요.iterrows():
            cols = st.columns([2, 2, 2, 2])
            cols[0].write(f"{row['환자번호']}")
            cols[1].write(f"{row['항목']}")
            cols[2].write(f"{row['완료여부']}")

            if row["완료여부"]:
                if cols[3].button("❌ 취소", key=f"today_cancel_{idx}"):
                    completed_db = completed_db[~(
                        (completed_db["환자번호"] == row["환자번호"]) &
                        (completed_db["날짜"] == str(row["날짜"])) &
                        (completed_db["항목"] == row["항목"])
                    )]
                    completed_db.to_csv(DONE_PATH, index=False)
                    st.rerun()
            else:
                if cols[3].button("✅ 완료", key=f"today_done_{idx}"):
                    completed_db.loc[len(completed_db)] = {
                        "환자번호": row["환자번호"],
                        "날짜": row["날짜"],
                        "항목": row["항목"]
                    }
                    completed_db.to_csv(DONE_PATH, index=False)
                    st.rerun()




elif menu == "📌 내일 예정된 검사":
    st.subheader("📌 내일 예정된 검사")
    tomorrow = datetime.today().date() + timedelta(days=1)

    항목_필터 = st.multiselect("검사 항목 선택", ["음성", "환경", "웨어러블"], default=["음성", "환경", "웨어러블"], key="test_filter_tomorrow")
    환자_필터 = st.selectbox("환자 선택", ["전체 보기"] + patient_db["환자번호"].unique().tolist(), key="patient_filter_tomorrow")

    full = pd.concat([generate_schedule(row) for _, row in patient_db.iterrows()])
    tomorrow_df = full[full["날짜"] == tomorrow]

    melted = tomorrow_df.melt(
        id_vars=["환자번호", "날짜"],
        value_vars=항목_필터, 
        var_name="항목",
        value_name="검사"
    )

    if 환자_필터 != "전체 보기":
        melted = melted[melted["환자번호"] == 환자_필터]

    검사예정 = melted[melted["검사"] == "●"]
    if 검사예정.empty:
        st.info("내일 예정된 검사가 없습니다.")
    else:
        st.dataframe(검사예정[["환자번호", "항목", "날짜"]], use_container_width=True)


if menu == "🗓️ 달력 뷰어":
    from streamlit_calendar import calendar

    st.subheader("🗓️ 달력 형태로 검사 일정 보기")

    검사_항목 = st.multiselect("검사 항목 선택", ["음성", "증상", "환경", "웨어러블"], default=["음성", "증상", "환경", "웨어러블"])
    patient_ids = patient_db["환자번호"].unique().tolist()
    selected_patient = st.selectbox("환자 선택", ["전체 보기"] + patient_ids)

    full = pd.concat([generate_schedule(r) for _, r in patient_db.iterrows()])

    if selected_patient != "전체 보기":
        full = full[full["환자번호"] == selected_patient]

    color_map = {
        "음성": "#FF6B6B",      # coral
        "증상": "#4D96FF",      # blue
        "환경": "#1DD1A1",      # mint
        "웨어러블": "#FDCB6E"   # yellow
    }

    events = []
    for _, row in full.iterrows():
        for 항목 in 검사_항목:
            if row[항목] == "●":  
                events.append({
                    "title": f"{row['환자번호']} - {항목}",
                    "start": str(row["날짜"]),
                    "end": str(row["날짜"]),
                    "allDay": True,
                    "color": color_map.get(항목, "gray")
                })

    calendar_options = {"initialView": "dayGridMonth"}  # 기본 달력 뷰
    calendar(events=events, options=calendar_options)






elif menu == "🗂️ 외래 일정 관리":
    st.subheader("📅 외래 일정 확인 및 수정")

    today = datetime.today().date()
    tomorrow = today + timedelta(days=1)

    today_visits = patient_db[patient_db["외래일"].str.contains(str(today))] if not patient_db.empty else []
    tomorrow_visits = patient_db[patient_db["외래일"].str.contains(str(tomorrow))] if not patient_db.empty else []

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📍 오늘 외래 일정")
        if not today_visits.empty:
            st.dataframe(today_visits[["환자번호", "외래일"]])
        else:
            st.info("오늘 외래 일정 없음")

    with col2:
        st.markdown("### 📍 내일 외래 일정")
        if not tomorrow_visits.empty:
            st.dataframe(tomorrow_visits[["환자번호", "외래일"]])
        else:
            st.info("내일 외래 일정 없음")

    st.markdown("### ✏️ 외래 일정 수정")
    환자선택 = st.selectbox("수정할 환자 선택", patient_db["환자번호"].unique(), key="outpatient_patient")
    현재_외래일 = patient_db[patient_db["환자번호"] == 환자선택]["외래일"].values[0]
    외래_리스트 = [d.strip() for d in 현재_외래일.split("|") if d.strip()]
    외래_리스트 = 외래_리스트[:4] + [""] * (4 - len(외래_리스트))  # 최대 4개까지만

    cols = st.columns(4)
    수정_리스트 = []
    for i, col in enumerate(cols):
        with col:
            date = st.date_input(f"{3*(i+1)}개월차", value=datetime.strptime(외래_리스트[i], "%Y-%m-%d").date()
                                 if 외래_리스트[i] else today, key=f"edit_out_{i}")
            수정_리스트.append(date.strftime("%Y-%m-%d"))

    if st.button("저장", key="save_outpatient"):
        new_string = "|".join([d for d in 수정_리스트 if d])
        patient_db.loc[patient_db["환자번호"] == 환자선택, "외래일"] = new_string
        patient_db.to_csv(DATA_PATH, index=False)
        st.success(f"{환자선택} 외래 일정 저장 완료!")

elif menu == "📊 월별 검사 통계":
    st.subheader("📊 항목별 월별 검사 횟수")

    full = pd.concat([generate_schedule(row) for _, row in patient_db.iterrows()])
    full = filter_by_user(full, current_user)

    melted = full.melt(id_vars=["환자번호", "날짜"], value_vars=["음성", "증상", "환경", "웨어러블"],
                       var_name="항목", value_name="검사")
                       
    df = melted[melted["검사"] == "●"].copy()
    df["월"] = pd.to_datetime(df["날짜"]).dt.to_period("M").astype(str)

    pivot = df.pivot_table(index="월", columns="항목", values="환자번호", aggfunc="count", fill_value=0)
    pivot = pivot.reset_index()

    st.dataframe(pivot, use_container_width=True)

    st.bar_chart(pivot.set_index("월"))


from datetime import datetime, date

def get_uncompleted_tests_before_today(test_data):
    today = datetime.today().date()
    return [test for test in test_data if test["date"] < today and not test["completed"]]

example_tests = [
    {"date": date(2025, 4, 20), "completed": False, "name": "혈액 검사"},
    {"date": date(2025, 4, 22), "completed": True, "name": "소변 검사"},
    {"date": date(2025, 4, 23), "completed": False, "name": "CT 촬영"},
]

uncompleted_tests = get_uncompleted_tests_before_today(example_tests)
print("⏳ 완료되지 않은 이전 검사 목록:")
for test in uncompleted_tests:
    print(f"- {test['name']} (날짜: {test['date']})")
