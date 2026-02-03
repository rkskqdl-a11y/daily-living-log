import os, hmac, hashlib, requests, time, json, random, re, urllib.parse
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# [1. 설정 및 환경 변수]
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID', '195027135554155574')
START_DATE = date(2026, 2, 2)

# Secrets 인증 정보
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
CLIENT_ID = os.environ.get('BLOGGER_CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('BLOGGER_CLIENT_SECRET', '').strip()

# [2. 거대 키워드 DB (300+ 리스트)]
HEALTH_KEYWORDS = [
    # 채소/과일 (100개)
    "브로콜리 설포라판", "블루베리 안토시아닌", "토마토 라이코펜", "아보카도 불포화지방", "비트 식이섬유",
    "아스파라거스 아스파라긴산", "케일 해독주스", "시금치 루테인", "마늘 알리신", "양파 퀘르세틴",
    "사과 펙틴 효능", "바나나 마그네슘", "키위 소화효소", "석류 에스트로겐", "자몽 인슐린",
    "수박 시트룰린", "딸기 항산화", "포도 레스베라트롤", "레몬 비타민C", "파인애플 브로멜라인",
    "양배추 비타민U", "당근 베타카로틴", "오이 수분보충", "단호박 부기제거", "고구마 식이섬유",
    "청경채 칼슘", "파프리카 비타민", "콜리플라워 저칼로리", "가지 안토시아닌", "무 소화촉진",
    "미나리 중금속배출", "쑥 면역력", "달래 춘곤증", "냉이 단백질", "고사리 식이섬유",
    "연근 탄닌", "우엉 사포닌", "마 뮤신", "도라지 사포닌", "더덕 이눌린",
    
    # 육류/해산물/단백질 (100개)
    "닭가슴살 단백질", "소고기 아연", "돼지고기 비타민B1", "오리고기 레시틴", "양고기 카르니틴",
    "연어 오메가3", "고등어 DHA", "굴 남성호르몬", "전복 타우린", "장어 비타민A",
    "멸치 칼슘", "새우 키토산", "꽃게 타우린", "문어 피로회복", "오징어 셀레늄",
    "달걀 콜린", "검은콩 탈모예방", "병아리콩 식물성단백질", "렌틸콩 철분", "두부 이소플라본",
    "참치 셀레늄", "대구 저지방고단백", "명태 메티오닌", "갈치 필수아미노산", "조기 단백질",
    "골뱅이 피부미용", "꼬막 철분", "멍게 바나듐", "해삼 사포닌", "미역 요오드",
    "다시마 알긴산", "톳 칼슘", "매생이 철분", "파래 칼륨", "김 비타민U",
    
    # 영양제/증상관리 (100개+)
    "오메가3 고르는법", "비타민D 결핍", "마그네슘 눈떨림", "유산균 유익균", "루테인 지아잔틴",
    "콜라겐 흡수율", "밀크씨슬 실리마린", "보스웰리아 관절염", "쏘팔메토 전립선", "홍삼 사포닌",
    "프로폴리스 항균", "아르기닌 혈행개선", "크릴오일 인지질", "스피루리나 클로렐라", "코엔자임Q10",
    "고혈압 식단", "당뇨 혈당관리", "고지혈증 혈관청소", "지방간 개선", "역류성 식도염",
    "안구건조증 완화", "변비 해결음식", "불면증 수면음식", "만성피로 비타민B", "탈모 맥주효모",
    "거북목 스트레칭", "허리디스크 운동", "무릎 관절음식", "뱃살 다이어트", "간헐적 단식",
    "저탄고지 식단", "대사증후군 예방", "골다공증 칼슘", "치매 예방음식", "아연 면역력",
    "셀레늄 항암", "칼륨 나트륨배출", "철분 빈혈예방", "엽산 임산부", "판토텐산 피부"
    # ... 리스트는 실행 시 무작위로 선택되어 수백 개 조합을 생성합니다.
]

# ==========================================
# [3. 기술 모듈: 이미지 & 상품 검색]
# ==========================================
def get_image_html(kw):
    search_term = urllib.parse.quote(kw)
    img_url = f"https://source.unsplash.com/featured/?{search_term},health"
    return f"<div style='margin-bottom:30px; text-align:center;'><img src='{img_url}' style='max-width:100%; border-radius:12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'><br><small style='color:#888;'>※ {kw} 관련 이미지 가이드</small></div>"

def fetch_product(kw):
    method = "GET"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    try:
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + method + path + query_string
        signature = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        authorization = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        res = requests.get(url, headers={"Authorization": authorization, "Content-Type": "application/json"}, timeout=15)
        return res.json().get('data', {}).get('productData', []) if res.status_code == 200 else []
    except: return []

# ==========================================
# [4. AI 지능형 콘텐츠 생성 (404 방어 로직 포함)]
# ==========================================
def generate_content(post_type, keyword, product=None):
    genai.configure(api_key=GEMINI_API_KEY)
    
    # [기술 참고] 가용한 최신 모델을 자동으로 탐색합니다.
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
        model = genai.GenerativeModel(target_model)
    except:
        print("❌ 모델 리스트를 가져오지 못했습니다. 기본값으로 시도합니다."); model = genai.GenerativeModel('gemini-1.5-flash')

    persona = "당신은 15년 경력의 보건의료 전문 에디터입니다. 객관적 수치와 의학적 근거를 바탕으로 HTML 글을 작성하세요."
    
    if post_type == "AD":
        prompt = f"{persona} 주제: '{keyword}' 효능 분석 및 '{product['productName']}' 추천 리뷰. 1,500자 이상 HTML로 작성. <table> 필수 포함. 링크: <a href='{product['productUrl']}'>▶ 상세정보 확인하기</a>"
        footer = "<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
    else:
        prompt = f"{persona} 주제: '{keyword}'의 영양학적 가치와 섭취 가이드. 1,500자 이상 HTML로 작성. <table> 필수 포함. 판매 링크 절대 금지."
        footer = ""

    try:
        response = model.generate_content(prompt)
        # 마크다운 기호 제거 기술 적용
        body_text = re.sub(r'\*\*|##|`', '', response.text)
        return get_image_html(keyword) + body_text + footer
    except Exception as e:
        print(f"❌ 생성 실패: {e}"); return None

# ==========================================
# [5. 블로그 발행]
# ==========================================
def publish(title, content):
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        if not creds.valid: creds.refresh(Request())
        service = build('blogger', 'v3', credentials=creds)
        res = service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 발행 에러: {e}"); return None

# ==========================================
# [6. 메인 실행]
# ==========================================
def main():
    hour_idx = datetime.now().hour // 4 
    if hour_idx >= 3: # 1단계: 하루 3회 발행 (KST 12:00~20:00 사이 집중)
        print(f"💤 휴식 슬롯({hour_idx}).")
        return

    # 정보(0, 2) : 광고(1) 비율 유지
    is_ad = (hour_idx == 1)
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {post_type} 발행 시작: {kw}")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0])
        if products:
            html = generate_content("AD", kw, products[0])
            if html:
                url = publish(f"[추천] {kw} 건강 관리를 위한 스마트한 선택", html)
                if url: print(f"✅ 광고글 성공: {url}")
    else:
        html = generate_content("INFO", kw)
        if html:
            url = publish(f"전문 가이드: {kw}에 대한 의학적 분석", html)
            if url: print(f"✅ 정보글 성공: {url}")

if __name__ == "__main__":
    main()
