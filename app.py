import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os


def filter_by_user(df, user):
    if user == "전체 관리자":
        return df
    return df[
        (df["음성_담당자"] == user) |
        (df["증상_담당자"] == user) |
        (df["환경_담당자"] == user) |
        (df["웨어러블_담당자"] == user)
    ]



# 파일 경로
DATA_PATH = "patients.csv"
DONE_PATH = "completed.csv"
AUDIO_LINKS_PATH = "audio_links.csv"

# Google Drive 음성 파일 링크 생성 함수

def get_audio_file_link(patient_id, date, df):
    import pandas as pd
    from datetime import datetime

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
            return row.iloc[0]['파일 링크']  # 변환 없이 원본 링크 그대로 반환
    except Exception as e:
        st.error(f"음성 파일 로딩 오류: {e}")

    return None




# CSV 파일 로드
if os.path.exists(DATA_PATH):
    patient_db = pd.read_csv(DATA_PATH)
    patient_db["외래일"] = patient_db["외래일"].fillna("").astype(str)
else:
    patient_db = pd.DataFrame(columns=[
        "환자번호", "Baseline", "Start_date", "음성_주기", "증상_주기",
        "환경_사용", "웨어러블_사용", "외래일",
        "음성_담당자", "증상_담당자", "환경_담당자", "웨어러블_담당자"
    ])

if os.path.exists(DONE_PATH):
    completed_db = pd.read_csv(DONE_PATH)
else:
    completed_db = pd.DataFrame(columns=["환자번호", "날짜", "항목"])

# 사용자 목록 및 로그인
user_list = ["전체 관리자", "김은선", "최민지"]
current_user = st.sidebar.selectbox("사용자 선택", user_list, key="user_select")

# 기능 선택
menu = st.sidebar.radio("기능 선택", [
    "📋 새 환자 등록",
    "📂 환자 목록 보기",
    "✅ 오늘 해야 할 검사",
    "📌 내일 예정된 검사",
    "🗓️ 달력 뷰어",
    "🗂️ 외래 일정 관리",
    "📊 월별 검사 통계"
], key="menu_select")

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
        return any(0 <= (date - d).days <= 30 for d in 외래일)

    def is_wearable(date):
        if 웨어러블_사용 == "비착용":
            return False
        return any(0 <= (date - d).days <= 13 for d in 외래일)

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

# 📋 새 환자 등록
if menu == "📋 새 환자 등록":
    st.subheader("📋 새 환자 등록")

    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            환자번호 = st.text_input("환자 번호")
            baseline = st.date_input("Baseline 날짜")
            start_date = st.date_input("Start_date")
            음성_주기 = st.selectbox("음성 검사 주기", ["1w", "2w", "1m"], key="voice_cycle")
            증상_주기 = st.selectbox("증상 검사 주기", ["daily", "weekly"], key="symptom_cycle")
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
            st.success(f"{환자번호} 등록 완료")

elif menu == "📂 환자 목록 보기":
    st.subheader("📂 환자 목록 보기")

    if patient_db.empty:
        st.warning("등록된 환자가 없습니다.")
        st.stop()

    선택 = st.selectbox("환자 선택", sorted(patient_db["환자번호"].unique()), key="patient_select")
    patient = patient_db[patient_db["환자번호"] == 선택].iloc[0]

    st.markdown("#### 📝 기본 정보")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"- **환자번호:** {patient['환자번호']}")
        st.markdown(f"- **Baseline:** {patient['Baseline']}")
        st.markdown(f"- **Start_date:** {patient['Start_date']}")
        st.markdown(f"- **외래일:** {patient['외래일']}")
    with col2:
        st.markdown(f"- **음성 주기:** {patient['음성_주기']} (담당자: {patient['음성_담당자']})")
        st.markdown(f"- **증상 주기:** {patient['증상_주기']} (담당자: {patient['증상_담당자']})")
        st.markdown(f"- **환경 착용:** {patient['환경_사용']} (담당자: {patient['환경_담당자']})")
        st.markdown(f"- **웨어러블 착용:** {patient['웨어러블_사용']} (담당자: {patient['웨어러블_담당자']})")

    schedule = generate_schedule(patient)
    schedule["날짜"] = pd.to_datetime(schedule["날짜"]).dt.date

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

    # 완료 여부 판별
    completed = completed_db[completed_db["환자번호"] == 선택]
    completed["날짜"] = pd.to_datetime(completed["날짜"]).dt.date

    melted["표시"] = melted.apply(
        lambda row: "🔴" if ((completed["날짜"] == row["날짜"]) & (completed["항목"] == row["항목"])).any()
        else ("⚫" if row["표시"] == "●" else ""), axis=1
    )

    # 타임라인 점오표
    st.markdown("#### 🗓️ 환자 검사 타임라인")
    pivot = melted.pivot(index="항목", columns="날짜", values="표시").fillna("")
    st.dataframe(pivot, use_container_width=True)

    # 완료/수동 처리
    st.markdown("#### ✅ 완료된 검사 이력 / 수동 처리")
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


# ✅ 오늘 해야 할 검사
elif menu == "✅ 오늘 해야 할 검사":
    st.subheader("✅ 오늘 해야 할 검사")
    today = datetime.today().date()

    full = pd.concat([generate_schedule(row) for _, row in patient_db.iterrows()])
    today_df = full[full["날짜"] == today]

    melted = today_df.melt(
        id_vars=["환자번호", "날짜"],
        value_vars=["음성", "증상", "환경", "웨어러블"],
        var_name="항목",
        value_name="검사"
    )

    검사_필요 = melted[melted["검사"] == "●"].copy()
    검사_필요["완료여부"] = 검사_필요.apply(
        lambda row: "✅ 완료됨" if (
            (completed_db["환자번호"] == row["환자번호"]) &
            (completed_db["날짜"] == str(row["날짜"])) &
            (completed_db["항목"] == row["항목"])
        ).any() else "", axis=1
    )

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

# 📌 내일 예정된 검사
elif menu == "📌 내일 예정된 검사":
    st.subheader("📌 내일 예정된 검사")
    tomorrow = datetime.today().date() + timedelta(days=1)

    full = pd.concat([generate_schedule(row) for _, row in patient_db.iterrows()])
    tomorrow_df = full[full["날짜"] == tomorrow]

    melted = tomorrow_df.melt(
        id_vars=["환자번호", "날짜"],
        value_vars=["음성", "증상", "환경", "웨어러블"],
        var_name="항목",
        value_name="검사"
    )

    검사예정 = melted[melted["검사"] == "●"]
    if 검사예정.empty:
        st.info("내일 예정된 검사가 없습니다.")
    else:
        st.dataframe(검사예정[["환자번호", "항목", "날짜"]], use_container_width=True)


elif menu == "🗓️ 달력 뷰어":
    from streamlit_calendar import calendar

    st.subheader("🗓️ 달력 형태로 검사 일정 보기")

    full = pd.concat([generate_schedule(r) for _, r in patient_db.iterrows()])
    full = filter_by_user(full, current_user)

    events = []
    for _, row in full.iterrows():
        for 항목 in ["음성", "증상", "환경", "웨어러블"]:
            if row[항목] == "●":
                events.append({
                    "title": f"{항목}",
                    "start": str(row["날짜"]),
                    "end": str(row["날짜"]),
                    "allDay": True
                })

    calendar_options = {"initialView": "dayGridMonth"}
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

    # 검사 완료된 것만 추출
    df = melted[melted["검사"] == "●"].copy()
    df["월"] = pd.to_datetime(df["날짜"]).dt.to_period("M").astype(str)

    pivot = df.pivot_table(index="월", columns="항목", values="환자번호", aggfunc="count", fill_value=0)
    pivot = pivot.reset_index()

    st.dataframe(pivot, use_container_width=True)

    # 차트 시각화
    st.bar_chart(pivot.set_index("월"))
