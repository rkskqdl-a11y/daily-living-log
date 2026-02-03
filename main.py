import os, hmac, hashlib, requests, time, json, random, urllib.parse
import google.generativeai as genai
from datetime import datetime, date
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# [1. 설정 정보]
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

# Secrets 불러오기 (공백 제거)
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
CLIENT_ID = os.environ.get('CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '').strip()

# [2. 키워드 DB]
HEALTH_KEYWORDS = ["브로콜리", "연어", "토마토", "블루베리", "아보카도", "마늘", "양배추", "비타민D"]

def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14: return {"total": 3, "ad_slots": [1], "desc": "1단계 (정보2:광고1)"}
    elif days_passed < 30: return {"total": 4, "ad_slots": [1], "desc": "2단계 (정보3:광고1)"}
    else: return {"total": 6, "ad_slots": [0, 2, 4], "desc": "3단계 (수익극대화)"}

# [3. 쿠팡 API (403 에러 정밀 대응)]
def fetch_product(kw):
    print(f"🔍 쿠팡 상품 검색 시도: {kw}")
    method = "GET"
    base_url = "https://link.coupang.com"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"{base_url}{path}?{query_string}"
    
    try:
        # GMT 타임스탬프 생성
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + method + path + query_string
        
        # HMAC-SHA256 서명
        signature = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        authorization = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        
        headers = {"Authorization": authorization, "Content-Type": "application/json;charset=UTF-8"}
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            print(f"❌ 쿠팡 API 오류: {res.status_code}")
            print(f"📝 응답 본문: {res.text[:200]}") # 에러 메시지 상세 출력
            return []
            
        return res.json().get('data', {}).get('productData', [])
    except Exception as e:
        print(f"❌ 쿠팡 연동 중 예외 발생: {str(e)}")
        return []

# [4. 제미나이 글쓰기]
def generate_content(post_type, keyword, product=None):
    print(f"✍️ 제미나이 {post_type} 글 작성 중...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        if post_type == "AD":
            prompt = f"전문 영양사로서 '{keyword}'의 효능을 설명하고 '{product['productName']}'을 추천하는 HTML 글을 작성하세요. 반드시 <table>을 포함하세요. 구매링크: <a href='{product['productUrl']}'>👉 상세정보 확인</a>"
        else:
            prompt = f"건강 에디터로서 '{keyword}'에 대한 심층 가이드를 HTML로 작성하세요. <table>을 포함하고 광고 링크는 넣지 마세요."

        response = model.generate_content(prompt)
        content = response.text
        if post_type == "AD":
            content += "<br><p style='color:gray;font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        return content
    except Exception as e:
        print(f"❌ 제미나이 생성 실패: {str(e)}")
        return None

# [5. 블로그 발행 (발행 실패 원인 완전 노출)]
def post_to_blog(title, content):
    print(f"📤 블로그 발행 시도: {title}")
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        service = build('blogger', 'v3', credentials=creds)
        
        body = {'kind': 'blogger#post', 'title': title, 'content': content}
        res = service.posts().insert(blogId=BLOG_ID, body=body).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 블로그 API 상세 에러: {str(e)}")
        return None

# [6. 메인 실행]
def main():
    # API 키 일부만 출력하여 설정 확인 (보안상 앞 4자리만)
    print(f"🔑 설정 확인: AccessKey({ACCESS_KEY[:4]}...), ClientID({CLIENT_ID[:4]}...)")
    
    strat = get_daily_strategy()
    hour_idx = datetime.now().hour // 4 
    
    if hour_idx >= strat['total']:
        print(f"💤 휴식 슬롯({hour_idx}). 발행하지 않습니다.")
        return

    is_ad = hour_idx in strat['ad_slots']
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {strat['desc']} - {post_type} 모드 가동 (키워드: {kw})")
    
    if post_type == "AD":
        products = fetch_product(kw)
        if products:
            html = generate_content("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[추천] {kw} 건강을 위한 필수 아이템", html)
                if url: print(f"✅ 광고글 발행 성공: {url}")
        else:
            print("📦 상품 검색 실패로 중단합니다.")
    else:
        html = generate_content("INFO", kw)
        if html:
            url = post_to_blog(f"건강백과: {kw}의 놀라운 효능과 활용법", html)
            if url: print(f"✅ 정보글 발행 성공: {url}")

if __name__ == "__main__":
    main()
