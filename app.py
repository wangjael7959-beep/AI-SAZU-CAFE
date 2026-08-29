import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request, jsonify, session
from openai import OpenAI
from korean_lunar_calendar import KoreanLunarCalendar
from lunar_python import Solar
import os
import json
import urllib.request
import urllib.parse
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "undam-secret-change-me")
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")
@app.route("/terms")
def terms():
    return render_template("terms.html")
SEOUL_TZ = ZoneInfo("Asia/Seoul")
ELEMENT_KO = {"木": "목", "火": "화", "土": "토", "金": "금", "水": "수"}

GAN_KO = {
    "甲": "갑", "乙": "을", "丙": "병", "丁": "정", "戊": "무",
    "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계",
}
BRANCH_KO = {
    "子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사",
    "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해",
}
SHISHEN_KO = {
    "比肩": "비견",
    "劫財": "겁재", "劫财": "겁재",
    "食神": "식신",
    "傷官": "상관", "伤官": "상관",
    "偏財": "편재", "偏财": "편재",
    "正財": "정재", "正财": "정재",
    "七殺": "편관", "七杀": "편관",
    "偏官": "편관",
    "正官": "정관",
    "偏印": "편인",
    "正印": "정인",
    "日主": "일간",
}


def ganji_ko(value):
    value = (value or "").strip()
    if len(value) < 2:
        return value
    gan = GAN_KO.get(value[0])
    branch = BRANCH_KO.get(value[1])
    if not gan or not branch:
        return value
    return f"{gan}{branch}({value})"


def wuxing_pair_ko(value):
    value = (value or "").strip()
    if not value or value == "미상":
        return value
    korean = "".join(ELEMENT_KO.get(ch, ch) for ch in value)
    return f"{korean}({value})"


def shishen_ko(value):
    value = (value or "").strip()
    korean = SHISHEN_KO.get(value)
    return f"{korean}({value})" if korean else value


def parse_date(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError("생년월일을 입력해 주세요.")

    # 19570412처럼 숫자 8자리만 입력한 경우
    digits_only = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"\d{8}", digits_only):
        year = int(digits_only[:4])
        month = int(digits_only[4:6])
        day = int(digits_only[6:8])
    else:
        # 1957-4-12, 1957.4.12, 1957/4/12, 1957년 4월 12일 등을 모두 허용
        parts = re.findall(r"\d+", raw)
        if len(parts) != 3 or len(parts[0]) != 4:
            raise ValueError(
                "생년월일 형식을 확인해 주세요. 예: 1957-04-12, 1957.4.12, 19570412"
            )
        year, month, day = map(int, parts)

    if not (1800 <= year <= 2050):
        raise ValueError("출생연도를 1800~2050년 범위로 입력해 주세요.")
    if not (1 <= month <= 12):
        raise ValueError("출생 월을 1~12 사이로 입력해 주세요.")
    if not (1 <= day <= 31):
        raise ValueError("출생 일을 1~31 사이로 입력해 주세요.")

    return year, month, day


def parse_time(value):
    value = (value or "").strip()
    if not value:
        return None

    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
    else:
        compact = value.replace(" ", "")
        match = re.fullmatch(r"(오전|오후)(\d{1,2})시(?:(\d{1,2})분)?", compact)
        if not match:
            raise ValueError("출생시간 형식을 확인해 주세요. 예: 05:00")
        ampm, hour_text, minute_text = match.groups()
        hour = int(hour_text)
        minute = int(minute_text or 0)
        if not 1 <= hour <= 12:
            raise ValueError("출생시간의 시각을 확인해 주세요.")
        if ampm == "오전":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("출생시간을 00:00~23:59 범위로 입력해 주세요.")
    return hour, minute


def convert_to_solar(year, month, day, calendar_type, leap_month):
    calendar = KoreanLunarCalendar()
    is_lunar = calendar_type == "음력"
    is_leap = leap_month == "윤달"

    if is_lunar:
        if not calendar.setLunarDate(year, month, day, is_leap):
            raise ValueError(
                "입력한 음력 날짜를 변환할 수 없습니다. 날짜와 평달/윤달을 확인해 주세요."
            )
        solar_iso = calendar.SolarIsoFormat()
        solar_year, solar_month, solar_day = map(int, solar_iso.split("-"))
        lunar_text = f"{year:04d}-{month:02d}-{day:02d} ({'윤달' if is_leap else '평달'})"
    else:
        if not calendar.setSolarDate(year, month, day):
            raise ValueError("입력한 양력 날짜를 확인해 주세요.")
        solar_year, solar_month, solar_day = year, month, day
        lunar_text = calendar.LunarIsoFormat().replace(" Intercalation", " (윤달)")
        if "(윤달)" not in lunar_text:
            lunar_text += " (평달)"

    solar_text = f"{solar_year:04d}-{solar_month:02d}-{solar_day:02d}"
    return solar_year, solar_month, solar_day, solar_text, lunar_text


def build_manse(year, month, day, calendar_type, leap_month, birthtime, gender, birthplace):
    solar_year, solar_month, solar_day, solar_text, lunar_text = convert_to_solar(
        year, month, day, calendar_type, leap_month
    )

    parsed_time = parse_time(birthtime)
    has_birthtime = parsed_time is not None
    hour, minute = parsed_time if has_birthtime else (12, 0)

    solar = Solar.fromYmdHms(solar_year, solar_month, solar_day, hour, minute, 0)
    lunar = solar.getLunar()
    eight = lunar.getEightChar()
    eight.setSect(2)

    year_pillar_raw = eight.getYear()
    month_pillar_raw = eight.getMonth()
    day_pillar_raw = eight.getDay()
    time_pillar_raw = eight.getTime() if has_birthtime else None

    year_pillar = ganji_ko(year_pillar_raw)
    month_pillar = ganji_ko(month_pillar_raw)
    day_pillar = ganji_ko(day_pillar_raw)
    time_pillar = ganji_ko(time_pillar_raw) if has_birthtime else "출생시간 미상"

    year_wuxing = eight.getYearWuXing()
    month_wuxing = eight.getMonthWuXing()
    day_wuxing = eight.getDayWuXing()
    time_wuxing = eight.getTimeWuXing() if has_birthtime else "미상"

    visible_wuxing = year_wuxing + month_wuxing + day_wuxing
    if has_birthtime:
        visible_wuxing += eight.getTimeWuXing()
    element_counts = {
        ELEMENT_KO[element]: visible_wuxing.count(element)
        for element in ("木", "火", "土", "金", "水")
    }
    element_text = " · ".join(f"{name} {count}" for name, count in element_counts.items())

    shishen_gan = [
        shishen_ko(eight.getYearShiShenGan()),
        shishen_ko(eight.getMonthShiShenGan()),
        shishen_ko(eight.getDayShiShenGan()),
    ]
    if has_birthtime:
        shishen_gan.append(shishen_ko(eight.getTimeShiShenGan()))

    now = datetime.now(SEOUL_TZ)
    today_lunar = Solar.fromYmd(now.year, now.month, now.day).getLunar()
    current_year_ganzhi = ganji_ko(today_lunar.getYearInGanZhiExact())

    daeyun_text = "출생시간 미상으로 정밀 대운 계산을 생략합니다."
    current_daeyun = "확정하지 않음"
    luck_start_text = "출생시간 미상으로 계산하지 않음"

    if has_birthtime:
        gender_num = 1 if gender == "남성" else 0
        yun = eight.getYun(gender_num, 2)
        luck_start_text = (
            f"출생 후 {yun.getStartYear()}년 {yun.getStartMonth()}개월 "
            f"{yun.getStartDay()}일, {yun.getStartSolar().toYmd()} 전후"
        )
        daeyun_items = yun.getDaYun(10)[1:9]
        daeyun_parts = []
        for item in daeyun_items:
            daeyun_name = ganji_ko(item.getGanZhi())
            daeyun_parts.append(
                f"{daeyun_name} ({item.getStartAge()}~{item.getEndAge()}세, "
                f"{item.getStartYear()}~{item.getEndYear()})"
            )
            if item.getStartYear() <= now.year <= item.getEndYear():
                current_daeyun = (
                    f"{daeyun_name} 대운 "
                    f"({item.getStartAge()}~{item.getEndAge()}세, "
                    f"{item.getStartYear()}~{item.getEndYear()})"
                )
        daeyun_text = " / ".join(daeyun_parts)

    pillars_text = (
        f"년주 {year_pillar} / 월주 {month_pillar} / "
        f"일주 {day_pillar} / 시주 {time_pillar}"
    )
    wuxing_text = (
        f"년주 {wuxing_pair_ko(year_wuxing)} / "
        f"월주 {wuxing_pair_ko(month_wuxing)} / "
        f"일주 {wuxing_pair_ko(day_wuxing)} / "
        f"시주 {wuxing_pair_ko(time_wuxing)}"
    )

    return {
        "solar_text": solar_text,
        "lunar_text": lunar_text,
        "pillars_text": pillars_text,
        "year_pillar": year_pillar,
        "month_pillar": month_pillar,
        "day_pillar": day_pillar,
        "time_pillar": time_pillar,
        "wuxing_text": wuxing_text,
        "element_text": element_text,
        "wood_count": element_counts["목"],
        "fire_count": element_counts["화"],
        "earth_count": element_counts["토"],
        "metal_count": element_counts["금"],
        "water_count": element_counts["수"],
        "shishen_text": " / ".join(shishen_gan),
        "luck_start_text": luck_start_text,
        "daeyun_text": daeyun_text,
        "current_daeyun": current_daeyun,
        "current_year": now.year,
        "current_year_ganzhi": current_year_ganzhi,
        "has_birthtime": has_birthtime,
    }


def make_chart_text(manse, name, gender, birthtime, birthplace):
    time_text = birthtime if birthtime else "모름"
    place_text = birthplace if birthplace else "미입력"
    return f"""만세력 계산 결과
이름: {name}
성별: {gender}
양력 환산: {manse['solar_text']}
음력: {manse['lunar_text']}
출생시간: {time_text}
출생지역: {place_text}
사주팔자: {manse['pillars_text']}
오행(천간·지지): {manse['wuxing_text']}
표면 오행 분포: {manse['element_text']}
십신(천간 기준): {manse['shishen_text']}
대운 시작: {manse['luck_start_text']}
대운 흐름: {manse['daeyun_text']}
현재 대운: {manse['current_daeyun']}
{manse['current_year']}년 세운 간지: {manse['current_year_ganzhi']}"""

@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    try:
        data = request.get_json(silent=True) or {}

        imp_uid = data.get("imp_uid", "")
        merchant_uid = data.get("merchant_uid", "")

          
        if os.environ.get("PAYMENT_TEST_MODE") == "1":
            session["payment_verified"] = True
            return jsonify({
                "ok": True,
                "message": "테스트 결제가 확인되었습니다."
            })

        if not imp_uid or not merchant_uid:
            return jsonify({"ok": False, "message": "결제정보가 없습니다."}), 400

        api_key = os.environ.get("PORTONE_API_KEY")
        api_secret = os.environ.get("PORTONE_API_SECRET")

        if not api_key or not api_secret:
            return jsonify({
                "ok": False,
                "message": "결제 서버 설정이 완료되지 않았습니다."
            }), 500

        token_body = json.dumps({
            "imp_key": api_key,
            "imp_secret": api_secret
        }).encode("utf-8")

        token_request = urllib.request.Request(
            "https://api.iamport.kr/users/getToken",
            data=token_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(token_request, timeout=15) as response:
            token_result = json.loads(response.read().decode("utf-8"))

        access_token = token_result["response"]["access_token"]

        payment_url = (
            "https://api.iamport.kr/payments/"
            + urllib.parse.quote(imp_uid)
        )

        payment_request = urllib.request.Request(
            payment_url,
            headers={"Authorization": access_token},
            method="GET"
        )

        with urllib.request.urlopen(payment_request, timeout=15) as response:
            payment_result = json.loads(response.read().decode("utf-8"))

        payment = payment_result.get("response") or {}

        if payment.get("status") != "paid":
            return jsonify({
                "ok": False,
                "message": "결제가 완료된 상태가 아닙니다."
            }), 400

        if int(payment.get("amount", 0)) != 9900:
            return jsonify({
                "ok": False,
                "message": "결제금액이 일치하지 않습니다."
            }), 400

        if payment.get("merchant_uid") != merchant_uid:
            return jsonify({
                "ok": False,
                "message": "주문번호가 일치하지 않습니다."
            }), 400

        session["payment_verified"] = True

        return jsonify({
            "ok": True,
            "message": "결제가 확인되었습니다."
        })

    except Exception as e:
        print("PAYMENT VERIFY ERROR:", e)
        return jsonify({
            "ok": False,
            "message": "결제 확인 중 오류가 발생했습니다."
        }), 500
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    manse = None
    partner_manse = None
    form = request.form.to_dict() if request.method == "POST" else {}
    
    if request.method == "POST":

        if not session.pop("payment_verified", False):
            return render_template(
                "index.html",
                result=None,
                error="먼저 9,900원 결제를 완료해 주세요.",
                manse=None,
                form=form
            )

        try:
            name = form.get("name", "").strip()
            gender = form.get("gender", "").strip()
            calendar_type = form.get("calendar_type", "양력").strip()
            leap_month = form.get("leap_month", "평달").strip()
            birthdate = form.get("birthdate", "").strip()
            birthtime = form.get("birthtime", "").strip()
            birthplace = ""
            consultation_type = form.get("consultation_type", "personal").strip()
            question = form.get("question", "").strip()
            partner_name = form.get("partner_name", "").strip()
            partner_gender = form.get("partner_gender", "").strip()
            partner_calendar_type = form.get("partner_calendar_type", "").strip()
            partner_leap_month = form.get("partner_leap_month", "평달").strip()
            partner_birthdate = form.get("partner_birthdate", "").strip()
            partner_birthtime = form.get("partner_birthtime", "").strip()
            if not name:
                raise ValueError("이름을 입력해 주세요.")
            if gender not in ("남성", "여성"):
                raise ValueError("성별을 선택해 주세요.")
            if calendar_type not in ("양력", "음력"):
                raise ValueError("양력 또는 음력을 선택해 주세요.")
            if leap_month not in ("평달", "윤달"):
                raise ValueError("평달 또는 윤달을 선택해 주세요.")
            if not birthdate:
                raise ValueError("생년월일을 입력해 주세요.")

            year, month, day = parse_date(birthdate)
            manse = build_manse(
                year,
                month,
                day,
                calendar_type,
                leap_month,
                birthtime,
                gender,
                birthplace,
                )
            partner_chart_text = ""

            if consultation_type == "compatibility":
                if not partner_name:
                    raise ValueError("궁합 상담을 위해 상대방 이름을 입력해 주세요.")
                if partner_gender not in ("남성", "여성"):
                    raise ValueError("상대방 성별을 선택해 주세요.")
                if partner_calendar_type not in ("양력", "음력"):
                    raise ValueError("상대방의 양력 또는 음력을 선택해 주세요.")
                if partner_leap_month not in ("평달", "윤달"):
                    raise ValueError("상대방의 평달 또는 윤달을 선택해 주세요.")
                if not partner_birthdate:
                    raise ValueError("상대방 생년월일을 입력해 주세요.")
    
                p_year, p_month, p_day = parse_date(partner_birthdate)
    
                partner_manse = build_manse(
                    p_year,
                    p_month,
                    p_day,
                    partner_calendar_type,
                    partner_leap_month,
                    partner_birthtime,
                    partner_gender,
                    "",
                )
    
                partner_chart_text = make_chart_text(
                    partner_manse,
                    partner_name,
                    partner_gender,
                    partner_birthtime,
                    "",
                )
            chart_text = make_chart_text(manse, name, gender, birthtime, birthplace)
            question_text = question or "전체적인 사주와 앞으로의 삶의 흐름을 알려주세요."
            compatibility_text = ""
            if consultation_type == "compatibility":
                compatibility_text = f"""
    다음은 궁합 상담 상대방의 만세력 자료입니다.
    
    {partner_chart_text}
    
    이번 상담은 개인 사주 상담이 아니라 두 사람의 궁합 상담입니다.
    두 사람의 일간, 오행, 십신, 사주 구조와 대운 흐름을 서로 비교하여
    성격의 조화, 서로 보완되는 점, 갈등이 생기기 쉬운 부분,
    관계 유지에 도움이 되는 소통 방법을 중심으로 설명하세요.
    """
            prompt = f"""
다음은 프로그램이 만세력 계산을 통해 산출한 확정 사주 자료입니다.
아래 계산값은 기초 데이터이므로 간지, 사주팔자, 오행, 십신, 대운, 세운을 임의로 바꾸거나 다시 계산하지 마세요.

당신은 전통 명리학의 원리를 일반인이 이해하기 쉽게 풀어주는 한국어 사주 상담가입니다.
전문용어를 사용할 때는 반드시 쉬운 설명을 함께 붙이세요.
근거 없이 미래를 단정하거나 공포감을 주는 표현은 사용하지 마세요.
의료, 법률, 투자 결과를 확정적으로 예언하지 마세요.

[본인 만세력 자료]
{chart_text}

[궁합 자료]
{compatibility_text}

[상담자가 궁금해하는 내용]
{question_text}

아래 순서를 반드시 지켜서 답변하세요.
항목을 빠뜨리거나 순서를 바꾸지 마세요.
같은 내용을 여러 항목에서 반복하지 마세요.

## 1. 사주 핵심 요약
- 이 사주의 가장 중요한 특징을 3~5문장으로 먼저 설명하세요.
- 일간, 오행의 전체 균형, 계절적 특징을 함께 고려하세요.
- 처음 보는 사람도 자신의 사주 특징을 바로 이해할 수 있게 설명하세요.

## 2. 성격과 타고난 기질
- 성격의 강점
- 조심해야 할 성향
- 감정 표현 방식
- 판단과 행동 스타일
을 실제 생활에서 나타날 수 있는 모습과 함께 설명하세요.

## 3. 인간관계와 인연
- 가족, 친구, 직장 동료 등 사람을 대하는 방식
- 잘 맞는 사람의 성향
- 갈등이 생기기 쉬운 상황
- 관계를 편안하게 만드는 방법
을 현실적으로 설명하세요.

## 4. 직업운과 사업운
- 어떤 업무환경이나 역할에 강점이 있는지
- 조직생활과 독립·사업 중 어떤 방식이 더 편한지
- 일을 할 때 장점과 주의점
을 설명하세요.
직업이나 사업의 성공·실패를 단정하지 마세요.

## 5. 재물운
- 돈을 벌고 관리하는 성향
- 지출 또는 투자에서 조심할 점
- 재물을 안정적으로 관리하는 데 도움이 되는 방향
을 설명하세요.
수익이나 손실을 확정적으로 예언하지 마세요.

## 6. 생활과 건강 참고
- 사주상 나타나는 생활 리듬과 스트레스 성향
- 휴식, 운동, 수면, 생활습관에서 참고할 점
을 설명하세요.
질병을 진단하거나 치료를 지시하지 말고 생활 참고 수준으로만 설명하세요.

## 7. 대운과 올해의 흐름
- 현재 대운의 전체 분위기
- {manse['current_year']}년의 주요 흐름
- 기회가 커질 수 있는 부분
- 신중해야 할 부분
을 설명하세요.
좋다·나쁘다로 단순 단정하지 말고 어떤 기운이 강해지고 그것이 생활에 어떻게 나타날 수 있는지를 설명하세요.

## 8. 맞춤 질문과 종합 조언
먼저 상담자의 질문에 직접 답하세요.

질문:
{question_text}

그 다음 전체 사주를 종합하여
- 지금 집중하면 좋은 것
- 서두르지 않는 것이 좋은 것
- 사람 관계에서 기억할 점
- 앞으로 삶을 운영하는 데 도움이 될 한마디
를 정리하세요.

궁합 상담인 경우에는 위의 개인 사주 상담 1~8번 목차를 사용하지 마세요.
개인 사주 내용을 길게 반복하지 말고 반드시 아래 궁합 전용 8개 항목만 순서대로 작성하세요.
결과의 큰 제목은 반드시 "운담 궁합상담"으로 작성하세요.

## 1. 두 사람의 사주 핵심 비교
- 두 사람의 일간, 오행, 기질과 전체적인 사주 구조를 비교해 설명하세요.
- 서로 비슷한 점과 다른 점을 이해하기 쉽게 설명하세요.

## 2. 성격과 기질의 조화
- 두 사람의 성격, 감정 표현, 판단 방식의 차이를 비교하세요.
- 서로 편안하게 느끼는 부분과 조율이 필요한 부분을 설명하세요.

## 3. 애정과 정서 궁합
- 정서적 교감, 애정 표현 방식, 서로에게 기대하는 부분을 설명하세요.
- 관계에서 안정감을 높이는 방법을 함께 제시하세요.

## 4. 갈등이 생기기 쉬운 부분
- 두 사람 사이에서 오해나 충돌이 생길 수 있는 부분을 설명하세요.
- 누가 옳고 그르다고 단정하지 말고 현실적인 해결 방법을 제시하세요.

## 5. 생활과 재물 궁합
- 생활 습관, 소비와 저축, 재정 관리, 일상적인 역할 분담의 차이를 설명하세요.
- 함께 생활할 때 도움이 되는 현실적인 방법을 알려주세요.

## 6. 서로 보완하는 방법
- 각자의 장점이 상대방에게 어떤 도움이 되는지 설명하세요.
- 서로 부족한 부분을 부담 없이 보완할 수 있는 방법을 제시하세요.

## 7. 앞으로의 관계 흐름
- 현재 대운과 세운을 참고하여 두 사람 관계에서 주목할 흐름을 설명하세요.
- 미래를 확정적으로 단정하지 말고 관계를 안정적으로 이어가는 방향을 중심으로 설명하세요.

## 8. 종합 궁합 조언
- 두 사람의 궁합을 전체적으로 정리하세요.
- 잘 맞는 점, 조심할 점, 오래 관계를 유지하는 데 도움이 되는 행동을 구체적으로 제시하세요.
- 마지막에는 두 사람이 실생활에서 기억하면 좋은 한마디를 작성하세요.
문체 규칙:
1. 따뜻하고 차분한 존댓말을 사용하세요.
2. 지나치게 신비하거나 공포를 조장하는 표현은 사용하지 마세요.
3. 명리학 용어를 나열하지 말고 반드시 뜻을 풀어 설명하세요.
4. 같은 문장을 반복하지 마세요.
5. 각 항목은 읽기 편한 짧은 문단으로 작성하세요.
6. 사용자의 이름이 제공되어 있으면 자연스럽게 이름을 사용하되 과도하게 반복하지 마세요.
7. 결과는 충분히 상세하게 설명하되 불필요하게 장황하지 않게 작성하세요.
"""
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

            client = OpenAI(
                api_key=api_key,
                timeout=90.0,
                max_retries=0,
            )

            response = client.responses.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"),
                input=prompt,
                reasoning={"effort": "low"},
                max_output_tokens=5000,
                store=False,
            )

            ai_text = (response.output_text or "").strip()
            if not ai_text:
                raise RuntimeError("AI 상담 결과가 비어 있습니다. 다시 시도해 주세요.")

            result = ai_text

        except Exception as exc:
            print(f"AI-SAZU-CAFE error: {exc!r}", flush=True)
            error = f"오류가 발생했습니다: {exc}"

    return render_template(
        "index.html",
        result=result,
        error=error,
        form=form,
        manse=manse,
        partner_manse=partner_manse,
    )


@app.get("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
