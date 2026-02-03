import os, hmac, hashlib, requests, time, json, random, urllib.parse
import google.generativeai as genai
from datetime import datetime, date
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# [1. 설정]
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

# [2. 키워드 DB]
HEALTH_KEYWORDS = ["브로콜리", "연어 오메가3", "토마토 라이코펜", "블루베리", "아보카도", "마늘", "양배추", "단백질 쉐이크"]

def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14: return {"total": 3, "ad_slots": [1], "desc": "1단계"}
    elif days_passed < 30: return {"total": 4, "ad_slots": [1], "desc": "2단계"}
    else: return {"total": 6, "ad_slots": [0, 2, 4], "desc": "3단계"}

# [3. 쿠팡 API - 인코딩 및 서명 해결]
def fetch_product(kw):
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    # 한국어 키워드를 쿠팡 규격에 맞게 인코딩
    encoded_kw = urllib.parse.quote(kw)
    query_string = f"keyword={encoded_kw}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    
    try:
        method = "GET"
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + method + path + query_string
        
        signature = hmac.new(bytes(SECRET_KEY, "utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        
        headers = {"Authorization": authorization, "Content-Type": "application/json"}
        res = requests.request(method, url, headers=headers, timeout=15)
        
        # JSON이 아닌 에러 페이지가 왔을 때를 위한 처리
        if res.status_code != 200:
            print(f"❌ 쿠팡 API 응답 오류 ({res.status_code}): {res.text[:100]}")
            return []
            
        return res.json().get('data', {}).get('productData', [])
    except Exception as e:
        print(f"❌ 쿠팡 연동 오류: {str(e)}")
        return []

# [4. 제미나이 글쓰기]
def generate_health_post(post_type, keyword, product=None):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        disclosure = "<br><br><p style='color:gray;font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        
        if post_type == "AD":
            prompt = f"건강 전문가로서 '{keyword}' 효능과 '{product['productName']}' 추천 리뷰를 HTML로 쓰세요. <table> 포함. 링크: <a href='{product['productUrl']}'>상세보기</a>"
            footer = disclosure
        else:
            prompt = f"의학 에디터로서 '{keyword}' 전문 정보를 HTML로 쓰세요. <table> 포함. 링크는 제외."
            footer = ""

        response = model.generate_content(prompt)
        return response.text + footer
    except: return None

# [5. 블로그 발행]
def post_to_blog(title, content):
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        service = build('blogger', 'v3', credentials=creds)
        body = {'kind': 'blogger#post', 'title': title, 'content': content}
        res = service.posts().insert(blogId=BLOG_ID, body=body).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 블로그 발행 오류: {str(e)}")
        return None

# [6. 메인]
def main():
    strat = get_daily_strategy()
    hour_idx = datetime.now().hour // 4 
    
    if hour_idx >= strat['total']:
        print(f"💤 휴식 모드 (슬롯 {hour_idx})")
        return

    is_ad = hour_idx in strat['ad_slots']
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {post_type} 발행 시작 (키워드: {kw})")
    
    if post_type == "AD":
        products = fetch_product(kw)
        if products:
            html = generate_health_post("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[추천] {kw} 관리에 꼭 필요한 아이템", html)
                if url: print(f"✅ 발행 성공: {url}")
        else:
            print("📦 상품을 찾지 못해 발행을 건너뜁니다.")
    else:
        html = generate_health_post("INFO", kw)
        if html:
            url = post_to_blog(f"건강 가이드: {kw}의 놀라운 효능", html)
            if url: print(f"✅ 발행 성공: {url}")

if __name__ == "__main__":
    main()
