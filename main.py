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
    h1, h2, h3 { line-height: 1.6!important; margin-bottom: 25 Korea!important; color: #222; word-break: keep-all; }
    .table-container { width: 100%; overflow-x: auto; margin: 30px 0; border: 1px solid #eee; border-radius: 8px; }
    table { width: 100%; min-width: 600px; border-collapse: collapse; line-height: 1.6; font-size: 15px; }
    th, td { border: 1px solid #f0f0f0; padding: 15px; text-align: left; }
    th { background-color: #fafafa; font-weight: bold; }
    .prod-img { display: block; margin: 0 auto; max-width: 350px; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    p { line-height: 1.9; margin-bottom: 25px; color: #444; }
</style>
"""

def get_daily_strategy():
    # [수동 테스트용] 현재 무조건 광고 발행 모드
    return {"ad_slots": [0, 1, 2, 3, 4, 5], "desc": "🧪 수동 테스트 모드: 광고 강제 발행"}

KEYWORDS = {
    "INFO": ["사무용 의자 고르는 법", "인체공학 의자의 중요성", "바른 자세 유지법"],
    "AD": ["쿠팡 의자 추천", "사무용 의자 베스트", "가성비 의자 리뷰"]
}

# ==========================================
# [2. 쿠팡 API 엔진]
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
# [3. AI 생성 엔진 (v1 Stable 경로로 수정)]
# ==========================================
def generate_content_final(post_type, keyword, product=None):
    """
    v1beta에서 발생하던 404 에러를 해결하기 위해 
    2026년 정식 버전인 v1 엔드포인트를 사용합니다.
    """
    # [핵심] 정식 v1 경로 사용
    base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    url = f"{base_url}?key={GEMINI_API_KEY}"
    
    if post_type == "AD" and product:
        prompt = f"전문 리뷰어로서 '{product['productName']}' 제품의 장점을 2,000자 이상의 HTML로 상세히 리뷰하세요. <h3> 섹션 구분 필수. 제품 구매 링크: {product['productUrl']}"
        img_html = f'<div style="text-align:center; margin-bottom:30px;"><img src="{product["productImage"]}" class="prod-img"></div>'
    else:
        prompt = f"건강/가구 전문 에디터로서 '{keyword}' 주제의 HTML 가이드를 2,000자 이상 작성하세요. <table>과 리스트를 포함하세요."
        img_html = ""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        # API 요청
        response = requests.post(url, json=payload, timeout=40)
        res_json = response.json()
        
        # 404 에러가 여전히 난다면 모델명을 다르게 시도 (Fallback)
        if response.status_code == 404:
            print("🔄 v1 경로 실패, 대안 모델로 재시도 중...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
            response = requests.post(url, json=payload, timeout=40)
            res_json = response.json()

        # 데이터 파싱
        if 'candidates' in res_json:
            res_text = res_json['candidates'][0]['content']['parts'][0]['text']
            content = STYLE_FIX + img_html + re.sub(r'\*\*|##|`|#', '', res_text)
            if post_type == "AD":
                content += f"<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
            return "전문 가이드:", content
        else:
            print(f"⚠️ AI 응답 구조 오류: {res_json}")
            return None, None
            
    except Exception as e:
        print(f"❌ AI 생성 최종 실패: {str(e)}")
        return None, None

# ==========================================
# [4. 블로그 포스팅 및 실행]
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
    print(f"📢 [TEST] 광고 강제 발행 모드 가동 중 (2026-v1-Stable)")
    
    # 1. 상품 확보 (키루에 의자 등)
    products = fetch_coupang_get_api("/products/goldbox")
    if not products:
        products = fetch_coupang_get_api("/products/bestcategories/1015", "limit=10") # 홈인테리어
        
    if products:
        prod = products[0]
        print(f"✅ 상품 확보: {prod['productName'][:30]}...")
        
        # 2. AI 본문 생성
        prefix, html = generate_content_final("AD", prod['productName'], prod)
        
        if html:
            # 3. 블로그 포스팅
            title = f"[추천] {prod['productName'][:40]} 솔직 분석 및 가이드"
            url = post_to_blog(title, html)
            if url:
                print(f"🚀 [성공] 광고글 발행 완료: {url}")
                return

    # 실패 시 예비 정보글
    print("⚠️ 광고글 발행 실패로 정보글 전환 시도...")
    kw = random.choice(KEYWORDS["INFO"])
    prefix, html = generate_content_final("INFO", kw)
    if html:
        post_to_blog(f"{kw} 완벽 가이드", html)
        print("✅ 정보글 발행 완료")

if __name__ == "__main__":
    main()
