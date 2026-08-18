
# AI 사주카페 — SAZU FREE 버전

구조:
고객 입력 → SAZU 전문 만세력 API → OpenAI → 상담 보고서

## 먼저 할 일
`.env.example` 파일을 복사해 이름을 `.env`로 바꾸고 아래처럼 입력합니다.

SAZU_API_KEY=방금_복사한_SAZU_API_키
OPENAI_API_KEY=나중에_발급받을_OpenAI_API_키
OPENAI_MODEL=gpt-5-mini

API 키는 따옴표 없이 넣어도 됩니다.

## 실행
Windows 기준:

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

그 다음 브라우저에서:
http://127.0.0.1:5000

## 시험 순서
1. SAZU_API_KEY만 먼저 입력
2. 프로그램 실행
3. 생년월일시 입력
4. `① SAZU 연결 시험` 클릭
5. 연결 성공 확인
6. OpenAI API 키 추가
7. `② AI 종합상담 시작` 테스트

## 보안
- API 키를 채팅이나 공개 게시판에 올리지 마세요.
- `.env` 파일을 다른 사람에게 보내지 마세요.
- 웹페이지 자바스크립트 안에 키를 직접 넣지 마세요.
- Free 키는 현재 대시보드 안내상 90일 만료입니다.

## 주의
전통 명리학은 과학적으로 검증된 미래예측 방법이 아닙니다.
의료·법률·재정 등 중요한 결정의 유일한 근거로 사용하지 않도록 운영하세요.
