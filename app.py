
import os, json, requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

SAZU_URL = "https://api.sazu.app/v1/sazu/calculate"
SAZU_API_KEY = os.getenv("SAZU_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

SYSTEM_INSTRUCTIONS = """
당신은 AI 사주카페의 상담문 작성 도우미다.
전문 만세력 API가 제공한 데이터만 설명한다.
연주·월주·일주·시주, 대운, 오행, 신강/신약 등을 스스로 다시 계산하지 않는다.
API에 없는 격국·용신·신살·합형충파해 등을 임의로 만들지 않는다.
미래는 확정적으로 예언하지 않고 전통 명리학의 참고 해석으로 표현한다.
질병·수명·사고·법률결과·투자수익을 단정하지 않는다.
공포를 조성하거나 굿·부적·고액 결제를 유도하지 않는다.
쉬운 한국어로 작성한다.

구성:
1. 한눈에 보는 핵심 요약
2. 사주 원국의 특징
3. 오행과 균형
4. 성향과 강점
5. 인간관계·가족의 경향
6. 일·직업·재물의 경향
7. 대운 흐름(데이터가 있을 때만)
8. 생활에 적용할 조언
9. 참고 안내

마지막에 반드시 다음 취지로 안내한다:
이 내용은 전통 명리학에 기반한 참고용 해석이며, 의료·법률·재정 등 중요한 결정은 해당 분야 전문가와 상의하세요.
"""

def call_sazu(p):
    if not SAZU_API_KEY:
        raise RuntimeError("SAZU_API_KEY가 설정되지 않았습니다.")

    date_part, time_part = p["birth"].split("T")
    y, m, d = map(int, date_part.split("-"))
    hh, mm = map(int, time_part[:5].split(":"))

    body = {
        "birthYear": y,
        "birthMonth": m,
        "birthDay": d,
        "birthHour": hh,
        "birthMinute": mm,
        "isFemale": p.get("gender") == "female",
        "isLunar": p.get("calendar") == "lunar",
        "trueSolarTime": True,
    }
    city = (p.get("city") or "").strip()
    if city:
        body["birthCity"] = city

    headers = {
        "x-api-key": SAZU_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    r = requests.post(SAZU_URL, headers=headers, json=body, timeout=40)
    r.raise_for_status()
    data = r.json()

    if not data.get("success"):
        err = data.get("error") or {}
        raise RuntimeError(f"SAZU 오류: {err.get('message') or err.get('code') or '알 수 없는 오류'}")
    return data

def call_openai(profile, sazu_response):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    user_input = f"""
고객 정보:
- 이름/호칭: {profile.get('name') or '고객'}
- 출생 일시: {profile['birth']}
- 성별: {'여성' if profile.get('gender') == 'female' else '남성'}
- 달력: {'음력' if profile.get('calendar') == 'lunar' else '양력'}
- 출생도시: {profile.get('city') or '미입력'}
- 궁금한 점: {profile.get('question') or '종합적인 삶의 흐름'}

SAZU API 응답:
{json.dumps(sazu_response, ensure_ascii=False, indent=2)}

위 JSON에 실제로 존재하는 정보만 근거로 상담 보고서를 작성해라.
없는 필드는 추정하거나 생성하지 마라.
"""

    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "instructions": SYSTEM_INSTRUCTIONS,
            "input": user_input,
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()

    if data.get("output_text"):
        return data["output_text"]

    texts = []
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("text"):
                texts.append(c["text"])
    if texts:
        return "\n".join(texts)
    raise RuntimeError("AI 상담 텍스트를 찾지 못했습니다.")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/test-sazu", methods=["POST"])
def test_sazu():
    try:
        p = request.get_json(force=True)
        if not p.get("birth"):
            return jsonify({"ok": False, "error": "출생 일시를 입력하세요."}), 400
        return jsonify({"ok": True, "sazu": call_sazu(p)})
    except requests.HTTPError as e:
        body = ""
        try:
            body = e.response.text[:1000]
        except Exception:
            pass
        return jsonify({"ok": False, "error": f"SAZU API 호출 오류: {e} {body}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        p = request.get_json(force=True)
        if not p.get("birth"):
            return jsonify({"ok": False, "error": "출생 일시를 입력하세요."}), 400
        sazu = call_sazu(p)
        text = call_openai(p, sazu)
        return jsonify({"ok": True, "sazu": sazu, "interpretation": text})
    except requests.HTTPError as e:
        body = ""
        try:
            body = e.response.text[:1000]
        except Exception:
            pass
        return jsonify({"ok": False, "error": f"외부 API 호출 오류: {e} {body}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
