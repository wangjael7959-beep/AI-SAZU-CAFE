ㄹimport os

from flask import Flask, render_template, request
from openai import OpenAI

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    form = request.form.to_dict() if request.method == "POST" else {}

    if request.method == "POST":
        try:
            name = form.get("name", "").strip()
            gender = form.get("gender", "").strip()
            calendar_type = form.get("calendar_type", "양력").strip()
            leap_month = form.get("leap_month", "평달").strip()
            birthdate = form.get("birthdate", "").strip()
            birthtime = form.get("birthtime", "").strip()
            birthplace = form.get("birthplace", "").strip()
            question = form.get("question", "").strip()

            if not name:
                raise ValueError("이름을 입력해 주세요.")

            if not gender:
                raise ValueError("성별을 선택해 주세요.")

            if not birthdate:
                raise ValueError("생년월일을 입력해 주세요.")

            birthtime_text = birthtime if birthtime else "모름"
            birthplace_text = birthplace if birthplace else "미입력"
            question_text = (
                question
                if question
                else "전체적인 사주와 앞으로의 삶의 흐름을 알려주세요."
            )

            prompt = f"""
당신은 한국 전통 명리학의 개념을 설명하는 AI 사주 상담가입니다.

아래 정보를 바탕으로 한국어로 이해하기 쉽게 상담해 주세요.

[사용자 정보]

이름: {name}
성별: {gender}
생년월일 기준: {calendar_type}
음력 윤달 여부: {leap_month}
생년월일: {birthdate}
태어난 시간: {birthtime_text}
출생지역: {birthplace_text}

[상담 질문]

{question_text}

[중요한 원칙]

1. 양력인지 음력인지 반드시 구분해서 해석하세요.
2. 음력인 경우 평달/윤달 정보를 고려하세요.
3. 성별과 태어난 시간을 고려하세요.
4. 출생 시간이 없으면 시주를 확정하지 말고,
   시간 정보가 없다는 점을 명확하게 설명하세요.
5. 정확한 만세력 계산 자료가 제공되지 않은 상태라면
   사주팔자의 천간·지지, 대운 시작 나이 등을 임의로 만들어내지 마세요.
6. 계산이 필요한 부분을 추측하지 말고,
   확인 가능한 정보와 일반적인 명리학적 해석을 구분하세요.
7. 질병, 수명, 사고, 죽음, 재산 손실 등을
   확정적으로 예언하지 마세요.
8. 사용자가 불안해질 수 있는 단정적인 표현을 피하세요.
9. 상담은 따뜻하고 현실적인 조언 중심으로 작성하세요.

다음 순서로 답변하세요.

① 입력 정보 정리
② 사주 상담의 전제
③ 성격과 기질
④ 인간관계와 가족
⑤ 일과 재물
⑥ 건강과 생활 습관에 대한 일반적인 조언
⑦ 앞으로의 삶에서 참고할 방향
⑧ 사용자가 질문한 내용에 대한 답변
⑨ 종합 상담

마지막에는 다음 문장을 넣어 주세요.

"※ 이 상담은 전통 명리학을 바탕으로 한 참고용 해석이며,
중요한 의료·법률·재정적 결정은 해당 분야 전문가와 상의하시기 바랍니다."
"""

            api_key = os.environ.get("OPENAI_API_KEY")

            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY가 Render 환경변수에 설정되어 있지 않습니다."
                )

            client = OpenAI(
                api_key=api_key,
                timeout=90.0,
                max_retries=0,
            )

            response = client.responses.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"),
                input=prompt,
                reasoning={"effort": "low"},
                max_output_tokens=1200,
            )

            result = response.output_text

        except Exception as e:
            error = f"AI 상담 중 오류가 발생했습니다: {e}"
            

    return render_template(
        "index.html",
        result=result,
        error=error,
        form=form,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
