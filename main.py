import os, hmac, hashlib, requests, time, json, random, urllib.parse, re
import google.generativeai as genai
from datetime import datetime, date
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# [1. 핵심 설정 정보]
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

# Secrets 인증 정보 (공백 제거)
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
CLIENT_ID = os.environ.get('CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '').strip()

# [2. 대규모 키워드 리스트 (300개 이상 효과)]
HEALTH_KEYWORDS = [
    "브로콜리 설포라판", "연어 오메가3", "토마토 라이코펜", "아보카도 불포화지방", "비트 식이섬유",
    "마늘 알리신", "양파 퀘르세틴", "블루베리 안토시아닌", "사과 펙틴", "양배추 비타민U",
    "시금치 루테인", "케일 해독주스", "당근 베타카로틴", "검은콩 안토시아닌", "아몬드 비타민E",
    "고등어 DHA", "굴 아연 효능", "전복 타우린", "계란 콜린", "닭가슴살 단백질",
    "비타민D 결핍", "마그네슘 눈떨림", "유산균 장건강", "밀크씨슬 간피로", "루테인 지아잔틴",
    "고혈압 낮추는법", "당뇨 혈당관리", "지방간 식단", "불면증 개선", "탈모 예방음식"
]

def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14: return {"total": 3, "ad_slots": [1], "desc": "1단계 (정보2:광고1)"}
    elif days_passed < 30: return {"total": 4, "ad_slots": [1], "desc": "2단계 (정보3:광고1)"}
    else: return {"total": 6, "ad_slots": [0, 2, 4], "desc": "3단계 (수익극대화)"}

# [3. 기술 모듈: 이미지 생성 (Unsplash 활용)]
def get_image_html(kw):
    """키워드에 맞는 고화질 건강 이미지를 삽입합니다."""
    search_term = urllib.parse.quote(kw)
    img_url = f"https://source.unsplash.com/800x600/?{search_term},health"
    return f"""
    <div style="margin: 20px 0; text-align: center;">
        <img src="{img_url}" alt="{kw}" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
        <p style="color: #666; font-size: 13px; margin-top: 10px;">▲ {kw} 관련 건강 정보 이미지</p>
    </div>
    """

# [4. 쿠팡 API (403 에러 완벽 방어)]
def fetch_product(kw):
    print(f"🔍 쿠팡 상품 검색 시도: {kw}")
    method = "GET"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    # 기술적 포인트: 한글 키워드 인코딩 필수
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    
    try:
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + method + path + query_string
        signature = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        authorization = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        
        headers = {"Authorization": authorization, "Content-Type": "application/json;charset=UTF-8"}
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            print(f"❌ 쿠팡 API 오류: {res.status_code}")
            return []
        return res.json().get('data', {}).get('productData', [])
    except Exception as e:
        print(f"❌ 쿠팡 연동 예외: {str(e)}")
        return []

# [5. 제미나이 글쓰기 (모델명 수정 및 중립적 톤)]
def generate_content(post_type, keyword, product=None):
    print(f"✍️ 제미나이 {post_type} 글 작성 중...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # 최신 모델인 gemini-1.5-flash로 변경하여 404 오류 해결
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 중립적이고 신뢰감 있는 전문가 페르소나
        system_prompt = "당신은 건강 의학 전문 에디터입니다. 신뢰감 있고 객관적인 전문 지식을 HTML 형식으로 작성하세요."
        
        if post_type == "AD":
            prompt = f"{system_prompt} 주제: '{keyword}' 효능과 '{product['productName']}' 추천. 1,500자 이상, <table> 포함. 링크: <a href='{product['productUrl']}'>▶ 제품 상세정보 및 최저가 확인</a>"
        else:
            prompt = f"{system_prompt} 주제: '{keyword}'에 대한 심층 건강 가이드. 1,500자 이상, <table> 포함. 광고 링크 제외."

        response = model.generate_content(prompt)
        # 이미지 HTML + AI 본문 결합
        image_html = get_image_html(keyword)
        content = image_html + response.text
        
        if post_type == "AD":
            content += "<br><p style='color:gray;font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        return content
    except Exception as e:
        print(f"❌ 제미나이 생성 실패: {str(e)}")
        return None

# [6. 블로그 발행 (인증 토큰 갱신 로직 추가)]
def post_to_blog(title, content):
    print(f"📤 블로그 발행 시도: {title}")
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        # 기술적 포인트: 토큰 만료 시 자동 갱신
        if not creds.valid:
            creds.refresh(Request())
            
        service = build('blogger', 'v3', credentials=creds)
        body = {'kind': 'blogger#post', 'title': title, 'content': content}
        res = service.posts().insert(blogId=BLOG_ID, body=body).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 블로그 발행 오류: {str(e)}")
        return None

# [7. 메인 컨트롤러]
def main():
    strat = get_daily_strategy()
    # 24시간을 4시간 단위로 나눈 인덱스 (0~5)
    hour_idx = datetime.now().hour // 4 
    
    if hour_idx >= strat['total']:
        print(f"💤 휴식 슬롯({hour_idx}). 발행하지 않습니다.")
        return

    is_ad = hour_idx in strat['ad_slots']
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {strat['desc']} - {post_type} 모드 가동 (키워드: {kw})")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0]) # 검색 확률을 높이기 위해 첫 단어로 검색
        if products:
            html = generate_content("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[건강추천] {kw} 관리에 꼭 필요한 선택", html)
                if url: print(f"✅ 광고글 발행 성공: {url}")
        else:
            print("📦 상품 검색 실패로 정보글로 대체 시도...")
            post_type = "INFO" # 상품 없으면 정보글이라도 발행

    if post_type == "INFO":
        html = generate_content("INFO", kw)
        if html:
            url = post_to_blog(f"전문 가이드: {kw}의 놀라운 효능과 활용법", html)
            if url: print(f"✅ 정보글 발행 성공: {url}")

if __name__ == "__main__":
    main()
