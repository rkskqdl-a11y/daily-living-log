import os, hmac, hashlib, requests, time, json, random, re
from datetime import datetime, date
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 시스템 설정]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2) 

CLIENT_ID = os.environ.get('CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()

STYLE_FIX = """
<style>
    h1, h2, h3 { line-height: 1.6!important; margin-bottom: 25px!important; color: #222; word-break: keep-all; }
    .table-container { width: 100%; overflow-x: auto; margin: 30px 0; border: 1px solid #eee; border-radius: 8px; }
    table { width: 100%; min-width: 600px; border-collapse: collapse; line-height: 1.6; font-size: 15px; }
    th, td { border: 1px solid #f0f0f0; padding: 15px; text-align: left; }
    th { background-color: #fafafa; font-weight: bold; }
    .prod-img { display: block; margin: 0 auto; max-width: 350px; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    p { line-height: 1.9; margin-bottom: 25px; color: #444; }
</style>
"""

# [수정] 수동 광고 테스트를 위해 무조건 AD 모드로 작동하도록 설정
def get_daily_strategy():
    # 테스트 기간 동안은 무조건 모든 슬롯에서 광고 발행
    return {"ad_slots": [0, 1, 2, 3, 4, 5], "desc": "🧪 테스트 모드: 광고 강제 발행"}

KEYWORDS = {
    "INFO": ["면역력 높이는 건강 습관", "치킨 영양 성분 분석", "냉동식품 건강하게 먹는 법"],
    "AD": ["쿠팡 추천 간식", "인기 냉동식품", "자취생 필수템", "홈파티 메뉴 추천"]
}

# ==========================================
# [2. 쿠팡 API 엔진 (기존 성공 로직 유지)]
# ==========================================
def fetch_coupang_get_api(path, query_string=""):
    method = "GET"
    full_path = f"/v2/providers/affiliate_open_api/apis/openapi{path}"
    url = f"https://api-gateway.coupang.com{full_path}"
    if query_string: url += f"?{query_string}"

    try:
        ts = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        msg = ts + method + full_path + query_string
        sig = hmac.new(SECRET_KEY.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={ts}, signature={sig}"
        headers = {"Authorization": auth, "Content-Type": "application/json"}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json().get('data', [])
        return None
    except Exception as e:
        print(f"❌ 쿠팡 연결 오류: {e}")
        return None

# ==========================================
# [3. AI 생성 엔진 (REST API 직접 호출 - 404 완벽 해결)]
# ==========================================
def generate_content_rest(post_type, keyword, product=None):
    """SDK를 쓰지 않고 구글 API에 직접 요청하여 404 에러를 원천 차단합니다."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    if post_type == "AD" and product:
        prompt = f"전문 요리 에디터로서 '{product['productName']}' 제품의 맛과 특징을 2,000자 이상의 HTML로 상세히 리뷰하세요. <h3> 섹션 구분 필수. 제품 구매 링크: {product['productUrl']}"
        img_html = f'<div style="text-align:center; margin-bottom:30px;"><img src="{product["productImage"]}" class="prod-img"></div>'
    else:
        prompt = f"전문 건강 정보 에디터로서 '{keyword}' 주제의 HTML 가이드를 2,000자 이상 작성하세요. <table>과 리스트를 포함하세요."
        img_html = ""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        res_json = response.json()
        
        # 결과 텍스트 추출
        res_text = res_json['candidates'][0]['content']['parts'][0]['text']
        
        # 가공
        content = STYLE_FIX + img_html + re.sub(r'\*\*|##|`|#', '', res_text)
        if post_type == "AD":
            content += f"<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        
        return "전문 가이드:", content
    except Exception as e:
        print(f"❌ AI 생성 실패 (REST): {str(e)}")
        if 'res_json' in locals(): print(f"응답내용: {res_json}")
        return None, None

# ==========================================
# [4. 블로그 포스팅 및 메인 컨트롤러]
# ==========================================
def post_to_blog(title, content):
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        if not creds.valid: creds.refresh(Request())
        service = build('blogger', 'v3', credentials=creds)
        res = service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 블로그 발행 실패: {e}")
        return None

def main():
    strategy = get_daily_strategy()
    hour_idx = datetime.now().hour // 4 
    is_ad = True # [테스트] 무조건 광고 모드 실행
    
    print(f"📢 {strategy['desc']} 모드 가동 중")
    
    if is_ad:
        # 소바바치킨 등 상품 확보 성공 로직
        products = fetch_coupang_get_api("/products/goldbox")
        if not products:
            products = fetch_coupang_get_api("/products/bestcategories/1012", "limit=10") # 식품 카테고리
            
        if products and isinstance(products, list):
            prod = products[random.randint(0, len(products)-1)]
            print(f"✅ 상품 확보: {prod['productName']}")
            prefix, html = generate_content_rest("AD", prod['productName'], prod)
            
            if html:
                title = f"[내돈내산] {prod['productName']} 솔직 후기 및 맛있게 먹는 법"
                url = post_to_blog(title, html)
                if url:
                    print(f"🚀 광고글 발행 성공: {url}")
                    return 

    # 실패 시 정보글 예비 로직
    kw = random.choice(KEYWORDS["INFO"])
    prefix, html = generate_content_rest("INFO", kw)
    if html:
        post_to_blog(f"{kw} 완벽 가이드", html)
        print("✅ 정보글 발행 완료")

if __name__ == "__main__":
    main()
