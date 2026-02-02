import os, hmac, hashlib, requests, time, json, random
import google.generativeai as genai
from datetime import datetime, date
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ==========================================
# [1. 핵심 설정 및 환경 변수]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# ==========================================
# [2. 대규모 건강 키워드 DB]
# ==========================================
HEALTH_KEYWORDS = [
    "브로콜리 설포라판 효능", "블루베리 시력 보호", "토마토 라이코펜 섭취법", "아보카도 심혈관 건강", "비트 혈압 조절",
    "아스파라거스 간 해독", "케일 항산화 작용", "시금치 눈 건강 영양소", "마늘 면역력 강화", "양파 혈관 청소",
    "닭가슴살 단백질 식단", "연어 오메가3 염증", "고등어 두뇌 발달", "굴 아연 보충", "전복 기력 회복",
    "달걀 콜린 기억력", "오메가3 고르는법", "비타민D 결핍 증상", "마그네슘 눈떨림", "유산균 장 건강",
    "고혈압 식단 가이드", "당뇨 혈당 관리 채소", "지방간 개선 습관", "불면증 극복 음식", "탈모 예방 성분",
    "사과 아침 효능", "바나나 마그네슘", "키위 소화 효소", "양배추 위 점막 보호", "당근 시력 개선",
    "소고기 사태 단백질", "돼지고기 비타민B1", "오리고기 불포화지방", "조기 소화 잘되는 생선", "멸치 칼슘 흡수",
    "루테인 지아잔틴 효능", "콜라겐 피부 탄력", "밀크씨슬 간 피로", "보스웰리아 무릎 건강", "홍삼 면역력",
    "거북목 스트레칭", "뱃살 빠지는 음식", "치매 예방 식단", "골다공증 예방", "만성피로 회복 팁"
    # ... (내부적으로 랜덤 조합을 통해 수백 개 키워드 효과를 냄)
]

# ==========================================
# [3. 자동 스케줄 및 비율 로직]
# ==========================================
def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14:
        return {"total": 3, "ad_slots": [1], "desc": "1단계: 신뢰 구축기 (2:1)"}
    elif days_passed < 30:
        return {"total": 4, "ad_slots": [1], "desc": "2단계: 성장 가속기 (3:1)"}
    else:
        return {"total": 6, "ad_slots": [0, 2, 4], "desc": "3단계: 수익 극대화기 (3:3)"}

# ==========================================
# [4. 콘텐츠 생성 (대가성 문구 포함)]
# ==========================================
def generate_health_post(post_type, keyword, product=None):
    personas = ["건강 전문의", "임상 영양사", "스포츠 테라피스트", "식품공학 박사"]
    patterns = [
        "초반(문제 제기) - 중반(과학적 분석) - 중반2(해결책) - 종반(비교표) - 마무리",
        "초반(통계 제시) - 중반(상식 교정) - 중반2(실천 가이드) - 종반(핵심 요약) - 마무리"
    ]
    
    selected_persona = random.choice(personas)
    selected_pattern = random.choice(patterns)
    
    # 쿠팡 파트너스 대가성 문구
    disclosure = "<br><br><p style='color:gray;font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>"
    
    if post_type == "AD":
        prompt = f"""당신은 {selected_persona}입니다. 
        주제: '{keyword}'와 관련된 {product['productName']} 추천.
        구조: {selected_pattern} 순서로 HTML 작성.
        조건: 반드시 <table>을 포함하고, 구매 유도 문구를 자연스럽게 넣으세요.
        구매 링크: <a href='{product['productUrl']}'>👉 상세정보 확인하기</a>"""
        content_footer = disclosure
    else:
        prompt = f"""당신은 {selected_persona}입니다. 
        주제: '{keyword}'에 대한 전문 정보 가이드.
        구조: {selected_pattern} 순서로 HTML 작성.
        조건: 판매 링크 금지, <table> 필수 포함."""
        content_footer = ""

    try:
        response = model.generate_content(prompt)
        return response.text + content_footer
    except: return None

# ==========================================
# [5. 핵심 연동 함수]
# ==========================================
def get_auth_header(m, p, q=""):
    t = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
    msg = t + m + p + q
    sig = hmac.new(bytes(SECRET_KEY, "utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={t}, signature={sig}"

def fetch_product(kw):
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query = f"keyword={kw}&limit=1"
    url = f"https://link.coupang.com{path}?{query}"
    try:
        res = requests.get(url, headers={"Authorization": get_auth_header("GET", path, query)}, timeout=10)
        return res.json().get('data', {}).get('productData', [])
    except: return []

def post_to_blog(title, content, is_ad=False):
    creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    service = build('blogger', 'v3', credentials=creds)
    
    # 이전 광고글 링크 불러오기 (내부 링크용)
    history_link = ""
    if os.path.exists("history.txt"):
        with open("history.txt", "r") as f:
            links = [l.strip() for l in f.readlines() if l.strip()]
            if links: history_link = f"<p><b>📌 함께 읽으면 좋은 건강 팁:</b> <a href='{random.choice(links)}'>보기</a></p>"

    body = {'kind': 'blogger#post', 'title': title, 'content': content + history_link}
    res = service.posts().insert(blogId=BLOG_ID, body=body).execute()
    
    if is_ad:
        with open("history.txt", "a") as f: f.write(res['url'] + "\n")
    return res['url']

# ==========================================
# [6. 메인 실행]
# ==========================================
def main():
    strat = get_daily_strategy()
    hour_idx = datetime.now().hour // 4 
    
    if hour_idx >= strat['total']:
        print(f"💤 휴식 모드 (현재 슬롯: {hour_idx})")
        return

    is_ad = hour_idx in strat['ad_slots']
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {strat['desc']} 가동 - {post_type} 발행 준비")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0])
        if products:
            html = generate_health_post("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[건강추천] {kw} 관리에 도움되는 법", html, True)
                print(f"✅ 광고글 완료: {url}")
    else:
        html = generate_health_post("INFO", kw)
        if html:
            url = post_to_blog(f"필독! {kw}에 대해 몰랐던 사실", html)
            print(f"✅ 정보글 완료: {url}")

if __name__ == "__main__":
    main()
