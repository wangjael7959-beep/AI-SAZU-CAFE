import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request
from openai import OpenAI
from korean_lunar_calendar import KoreanLunarCalendar
from lunar_python import Solar

app = Flask(__name__)
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
        "wuxing_text": wuxing_text,
        "element_text": element_text,
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


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    manse = None
    form = request.form.to_dict() if request.method == "POST" else {}

    if request.method == "POST":
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
            prompt = f"""다음은 프로그램이 만세력 계산을 통해 산출한 사주 자료입니다.
아래 계산값은 확정된 기초 데이터이므로 간지, 사주팔자, 오행, 십신, 대운, 세운을 임의로 변경하거나 다시 계산하지 마세요.
당신은 이 자료를 바탕으로 전통 명리학의 원리를 이해하기 쉽게 풀어주는 한국어 사주 상담가입니다.

{chart_text}
{compatibility_text}
상담 질문: {question_text}

상담 원칙:
1. 반드시 위에 제공된 만세력 계산값을 기준으로 해석합니다.
2. 일간을 중심으로 월주와 계절, 오행의 분포와 균형, 십신의 관계를 종합하여 설명합니다.
3. 단순히 오행의 개수만 세어 강약을 단정하지 말고 계절과 사주 전체의 관계를 함께 고려합니다.
4. 현재 대운과 {manse['current_year']}년 세운을 함께 살펴 현재의 흐름을 설명합니다.
5. 대운과 세운은 좋다 또는 나쁘다고 단정하기보다 어떤 기운이 강해지고 어떤 부분에 주의하면 좋은지 구체적으로 설명합니다.
6. 성격은 장점과 주의할 점을 함께 설명하여 상담자가 자신의 삶에 활용할 수 있도록 합니다.
7. 직업, 사업, 재물은 적성 및 관리 방향을 중심으로 설명하고 성공, 실패, 수익 또는 손실을 확정적으로 예언하지 않습니다.
8. 인간관계와 가족은 갈등을 단정하지 말고 관계의 성향과 원활한 소통 방법을 중심으로 설명합니다.
9. 건강은 질병을 진단하거나 특정 질병 발생을 예언하지 말고 생활 습관과 건강관리 관점에서만 설명합니다.
10. 출생시간이 없으면 시주와 정밀 대운을 추측하여 만들어내지 않습니다.
11. 출생지역은 상담 맥락에만 사용하며 현재 버전에서는 별도의 경도 또는 진태양시 보정을 하지 않습니다.
12. 23시 전후 출생은 명리 유파에 따라 일주 경계가 달라질 수 있음을 필요한 경우 짧게 알려줍니다.
13. 사망, 큰 사고, 중병, 파산, 이혼 등 불안을 조장하는 사건을 확정적으로 예언하지 않습니다.
14. 상담자의 질문을 가장 중요하게 다루고, 일반적인 설명만 반복하지 않습니다.
15. 어려운 명리학 용어가 나오면 일반인이 이해할 수 있도록 쉬운 말로 함께 설명합니다.
16. 같은 내용을 반복하지 말고 따뜻하고 차분하며 구체적인 한국어로 작성합니다.

답변 순서:
1. 사주 핵심 요약
2. 성격과 타고난 기질
3. 인간관계와 가족
4. 직업, 사업과 재물 흐름
5. 건강과 생활 리듬
6. 현재 대운과 {manse['current_year']}년 세운
7. 질문에 대한 집중 답변
8. 앞으로의 생활 조언

각 항목에서는 단순한 좋은 말보다 위 만세력 자료의 어떤 요소를 근거로 그렇게 해석하는지 자연스럽게 설명하세요.
전체 상담은 읽기 편한 분량으로 작성하고 지나치게 단정적인 표현은 피하세요.

마지막에는 반드시 다음 문장을 그대로 넣으세요:
사주 해석은 전통 명리학을 바탕으로 한 참고용 상담이며 의료·법률·투자 판단을 대신하지 않습니다.""" 

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
                max_output_tokens=2200,
                store=False,
            )

            ai_text = (response.output_text or "").strip()
            if not ai_text:
                raise RuntimeError("AI 상담 결과가 비어 있습니다. 다시 시도해 주세요.")

            result = chart_text + "\n\nAI 사주 상담\n" + ai_text

        except Exception as exc:
            print(f"AI-SAZU-CAFE error: {exc!r}", flush=True)
            error = f"오류가 발생했습니다: {exc}"

    return render_template(
        "index.html",
        result=result,
        error=error,
        form=form,
        manse=manse,
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
