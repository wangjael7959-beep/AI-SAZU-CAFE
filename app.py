import os
from flask import Flask, render_template, request
from openai import OpenAI

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    result = error = None
    form = request.form.to_dict() if request.method == "POST" else {}
    if request.method == "POST":
        try:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            prompt = f"""전통 명리학을 현대적인 상담 언어로 설명하세요. 단정적 예언이나 공포 조장은 금지합니다.
이름: {form.get('name')}
성별: {form.get('gender')}
생년월일: {form.get('birthdate')}
달력: {form.get('calendar')}
윤달 여부: {form.get('leap')}
태어난 시간: {form.get('birthtime')}
출생지역: {form.get('birthplace')}
질문: {form.get('question')}
현재 앱에는 정확한 만세력 계산 엔진이 없으므로 간지나 대운을 임의로 만들지 말고, 필요한 부분은 '전문 만세력 API 연동 후 확정'이라고 표시하세요.
상담 요약, 성향과 강점, 인간관계·가정, 일·재물, 생활 조언, 앞으로의 방향, 질문 답변 순으로 한국어로 작성하세요."""
            response = client.responses.create(model=os.environ.get("OPENAI_MODEL","gpt-5-mini"), input=prompt)
            result = response.output_text
        except Exception as e:
            error = f"AI 상담 중 오류가 발생했습니다: {e}"
    return render_template("index.html", result=result, error=error, form=form)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
