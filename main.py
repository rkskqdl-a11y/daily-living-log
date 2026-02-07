import os, hmac, hashlib, requests, time, json, random, re
from datetime import datetime, date
# 최신 SDK: pip install google-genai
from google import genai 
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

def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    # 사용자 요청: days_passed <= -1로 설정하여 1단계 건너뛰기 수행 중
    if days_passed <= -1: return {"ad_slots": [1], "desc": "🛡️ 1단계: 신뢰 구축"}
    elif days_passed <= 90: return {"ad_slots": [0, 1, 2, 3, 4, 5], "desc": "📈 2단계: 수익 테스트"} # 테스트를 위해 모든 슬롯 허용 가능
    else: return {"ad_slots": [2, 1, 4], "desc": "💰 3단계: 수익 최적화"}

KEYWORDS = {
    "INFO": ["간수치 낮추는 법", "공복혈당 관리", "역류성 식도염 식단", "불면증 극복 음식", "거북목 스트레칭", "위염에 좋은 과일"],
    "AD": ["면역력 영양제", "부모님 선물 추천", "멀티비타민 베스트", "오메가3 추천"]
}

# ==========================================
# [2. 쿠팡 API 엔진 (HMAC & GET 방식)]
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
        
        # [교정] 공식 규격에 따른 signed-date 헤더 적용
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
# [3. AI 생성 엔진 (Gemini 404 해결)]
# ==========================================
def generate_content(post_type, keyword, product=None):
    try:
        # 최신 SDK Client 인스턴스 생성
        client = genai.Client(api_key=GEMINI_API_KEY)
        # [해결] 모델 ID에서 'models/' 접두사를 제거하고 정확한 명칭 사용
        model_id = "gemini-1.5-flash"

        if post_type == "AD" and product:
            prompt = f"전문 건강 에디터로서 '{product['productName']}' 제품의 특징과 효능을 분석하는 HTML 포스팅을 2,000자 이상 작성하세요. <h3> 섹션 구분 필수. '할인'이나 '최저가' 단어는 제외하세요. 제품 링크: {product['productUrl']}"
            img_html = f'<div style="text-align:center; margin-bottom:30px;"><img src="{product["productImage"]}" class="prod-img"></div>'
            response = client.models.generate_content(model=model_id, contents=prompt)
            res_text = response.text
            content = STYLE_FIX + img_html + re.sub(r'\*\*|##|`|#', '', res_text)
            content += f"<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        else:
            prompt = f"'{keyword}' 주제로 의학적으로 검증된 건강 가이드 HTML 글을 2,000자 이상 작성하세요. 가독성을 위해 <table>과 리스트를 포함하세요."
            response = client.models.generate_content(model=model_id, contents=prompt)
            res_text = response.text
            content = STYLE_FIX + re.sub(r'\*\*|##|`|#', '', res_text)
        
        return "전문 가이드:", content
    except Exception as e:
        # 에러 발생 시 상세 원인 출력
        print(f"❌ AI 생성 실패: {str(e)}")
        return None, None

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
    is_ad = (hour_idx in strategy['ad_slots'])
    
    print(f"📢 {strategy['desc']} - 슬롯: {hour_idx} | 모드: {'AD' if is_ad else 'INFO'}")
    
    if is_ad:
        # 골드박스 상품 수집
        products = fetch_coupang_get_api("/products/goldbox")
        if not products:
            # 실패 시 건강식품 카테고리(1024) 베스트 수집
            products = fetch_coupang_get_api("/products/bestcategories/1024", "limit=10")
            
        if products and isinstance(products, list):
            prod = products[random.randint(0, len(products)-1)]
            print(f"✅ 상품 확보: {prod['productName']}")
            prefix, html = generate_content("AD", prod['productName'], prod)
            if html and (url := post_to_blog(f"[건강추천] {prod['productName']} 분석 보고서", html)):
                print(f"🚀 광고글 완료: {url}")
                return 

    # 정보글 모드 (광고 슬롯이 아니거나 상품 확보 실패 시)
    kw = random.choice(KEYWORDS["INFO"])
    print(f"📘 [INFO] 주제: {kw}")
    prefix, html = generate_content("INFO", kw)
    if html and (url := post_to_blog(f"{kw} 완벽 관리 가이드", html)):
        print(f"✅ 정보글 완료: {url}")

if __name__ == "__main__":
    main()
