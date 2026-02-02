import os
import hmac
import hashlib
import requests
import time
import json
import random
import google.generativeai as genai
from datetime import datetime, date
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ==========================================
# [1. 핵심 설정 및 환경 변수]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)  # 프로젝트 시작일

# 깃허브 Secrets에서 불러오는 값들
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

# 제미나이 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# ==========================================
# [2. 전략 로직: 자동 증량 스케줄러]
# ==========================================
def get_current_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14:
        return {"total": 3, "info_ratio": 0.7, "desc": "1단계: 신뢰 구축기 (일 3회)"}
    elif days_passed < 30:
        return {"total": 4, "info_ratio": 0.7, "desc": "2단계: 성장 가속기 (일 4회)"}
    else:
        return {"total": 6, "info_ratio": 0.6, "desc": "3단계: 수익 극대화기 (일 6회)"}

# ==========================================
# [3. 쿠팡 API: 상품 수집 로직]
# ==========================================
def get_auth_header(method, path, query_string=""):
    timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
    message = timestamp + method + path + query_string
    signature = hmac.new(bytes(SECRET_KEY, "utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"

def fetch_coupang_products(keyword="인기템"):
    method = "GET"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={keyword}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    headers = {"Authorization": get_auth_header(method, path, query_string), "Content-Type": "application/json"}
    
    try:
        res = requests.request(method, url, headers=headers, timeout=10)
        return res.json().get('data', {}).get('productData', [])
    except Exception as e:
        print(f"❌ 쿠팡 API 호출 실패: {e}")
        return []

# ==========================================
# [4. 제미나이: 전략적 콘텐츠 생성]
# ==========================================
def generate_content(post_type, product=None):
    personas = ["살림 전문가", "가성비 쇼핑 분석가", "까다로운 리뷰어", "트렌드 큐레이터"]
    persona = random.choice(personas)
    
    if post_type == "AD" and product:
        prompt = f"""당신은 {persona}입니다. 아래 상품에 대한 'Why(구매 이유)'가 담긴 리뷰를 작성하세요.
        상품명: {product['productName']}, 가격: {product['productPrice']}원
        조건:
        1. 첫 문단에서 '왜 지금 이 제품을 사야 하는지' 논리적으로 설득하세요.
        2. 핵심 스펙을 HTML <table> 태그를 사용하여 비교표로 만드세요.
        3. 전체 글은 HTML(<h2>, <p>, <ul>) 형식을 갖춰야 합니다.
        4. 구매 링크: <a href='{product['productUrl']}'>👉 상품 상세정보 및 최저가 확인하기</a>"""
    else:
        prompt = f"""당신은 {persona}입니다. 쇼핑 정보성 가이드를 작성하세요.
        주제: 최근 가성비 가전 고르는 법 또는 현명한 소비 트렌드.
        조건:
        1. 특정 상품의 판매 링크는 절대 포함하지 마세요.
        2. 독자에게 진짜 도움이 되는 팁을 3가지 이상 포함하세요.
        3. HTML 형식을 사용하며, 전문적인 느낌을 주세요."""
        
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ 제미나이 생성 실패: {e}")
        return None

# ==========================================
# [5. 블로그스팟: 발행 및 내부 링크 관리]
# ==========================================
def post_to_blogger(title, content, is_ad=False):
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token",
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        service = build('blogger', 'v3', credentials=creds)
        
        # 내부 링크(Internal Linking) 전략 적용
        internal_link_html = ""
        if os.path.exists("posted_ads.txt"):
            with open("posted_ads.txt", "r") as f:
                links = [l.strip() for l in f.readlines() if l.strip()]
                if links:
                    target = random.choice(links)
                    internal_link_html = f"<br><br><div style='background:#f9f9f9;padding:15px;border-radius:10px;'><p><b>💡 함께 읽어보면 좋은 쇼핑 가이드:</b> <a href='{target}'>관련 포스팅 보기</a></p></div>"
        
        final_content = content + internal_link_html
        body = {'kind': 'blogger#post', 'title': title, 'content': final_content}
        
        result = service.posts().insert(blogId=BLOG_ID, body=body).execute()
        url = result.get('url')
        
        # 광고글인 경우 URL 저장 (다음 정보글에서 링크로 활용)
        if is_ad and url:
            with open("posted_ads.txt", "a") as f:
                f.write(url + "\n")
        return url
    except Exception as e:
        print(f"❌ 블로그 발행 실패: {e}")
        return None

# ==========================================
# [6. 메인 실행 컨트롤러]
# ==========================================
def main():
    strategy = get_current_strategy()
    current_hour = datetime.now().hour
    
    # 1단계일 때는 하루 6번 실행 중 특정 시간(UTC 3, 11, 19)에만 실제 발행
    if strategy['total'] == 3 and current_hour not in [3, 11, 19]:
        print(f"⏳ 현재 시간(UTC {current_hour}시)은 쉬어가는 타임입니다. (1단계 정책)")
        return

    print(f"🔥 {strategy['desc']} 시작!")
    
    # 발행 타입 결정
    post_type = "AD" if random.random() > strategy['info_ratio'] else "INFO"
    
    if post_type == "AD":
        kw = random.choice(["가성비 가전", "생활필수품", "주방꿀템", "자취필수템"])
        products = fetch_coupang_products(kw)
        if products:
            product = products[0]
            content = generate_content("AD", product)
            if content:
                url = post_to_blogger(f"[추천] {product['productName']}", content, is_ad=True)
                print(f"✅ 광고글 발행 성공: {url}")
    else:
        content = generate_content("INFO")
        if content:
            url = post_to_blogger("현명한 소비자를 위한 쇼핑 가이드", content)
            print(f"✅ 정보성 글 발행 성공: {url}")

if __name__ == "__main__":
    main()
