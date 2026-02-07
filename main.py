import os, hmac, hashlib, requests, time, json, random, re
from datetime import datetime, date
# [성공 포인트] 애드픽 코드에서 사용한 라이브러리 규격 그대로 사용
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 시스템 설정]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = datetime(2026, 2, 2) # 애드픽 코드 방식인 datetime으로 통일

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

# [수동 테스트] 2단계 수익 테스트 모드 강제 진입
def get_daily_strategy():
    days_diff = (datetime.now() - START_DATE).days
    # 수동 테스트를 위해 현재 날짜(5일차)에서 AD 모드가 작동하도록 설정
    if days_diff <= 10: 
        return {"ad_slots": [0, 1, 2, 3, 4, 5], "desc": "🧪 애드픽 로직 이식 테스트 모드"}
    else:
        return {"ad_slots": [1, 4], "desc": "📈 2단계: 수익 테스트"}

# ==========================================
# [2. 쿠팡 API 엔진 (인증 성공 로직)]
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
    except:
        return None

# ==========================================
# [3. 성공한 애드픽 로직 기반 AI 엔진]
# ==========================================
def generate_content_adpick_style(post_type, keyword, product=None):
    """성공한 애드픽 코드의 제미나이 호출 방식을 100% 그대로 적용했습니다."""
    try:
        # [성공 로직 1] SDK 설정 및 모델 선언
        genai.configure(api_key=GEMINI_API_KEY)
        # [성공 로직 2] 애드픽 코드에서 성공한 모델명 그대로 사용
        model = genai.GenerativeModel('models/gemini-2.5-flash')

        persona = "전문 건강 큐레이터로서 다정하고 친근한 말투(~해요, ✨💖)로 작성하세요."

        if post_type == "AD" and product:
            prompt = f"{persona} 주제: '{product['productName']}' 리뷰. [TITLE] 제목 [/TITLE] [BODY] 본문 1500자 이상 [/BODY] 형식 엄수. 제품 링크: {product['productUrl']}"
        else:
            prompt = f"{persona} 주제: '{keyword}' 가이드. [TITLE] 제목 [/TITLE] [BODY] 본문 1500자 이상 [/BODY] 형식 엄수."

        # [성공 로직 3] 콘텐츠 생성 및 텍스트 추출
        res = model.generate_content(prompt).text
        
        # [성공 로직 4] 태그 기반 파싱
        title = res.split('[TITLE]')[1].split('[/TITLE]')[0].strip()
        body = res.split('[BODY]')[1].split('[/BODY]')[0].strip()
        
        # HTML 가공
        clean_body = re.sub(r'\*\*|##|`|#', '', body)
        body_html = "".join([f"<p style='margin-bottom:32px; line-height:1.8;'>{line.strip()}</p>" for line in clean_body.split('\n') if line.strip()])
        
        if post_type == "AD":
            img_html = f'<div style="text-align:center; margin:30px 0;"><img src="{product["productImage"]}" class="prod-img"></div>'
            btn_html = f'<div style="text-align:center; margin-top:30px;"><a href="{product["productUrl"]}" style="background:#ff69b4; color:#fff; padding:15px 30px; text-decoration:none; border-radius:30px; font-weight:bold;">✨ 제품 보러가기 ✨</a></div>'
            return title, STYLE_FIX + img_html + body_html + btn_html + "<p style='color:gray; font-size:12px; text-align:center;'>쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        
        return title, STYLE_FIX + body_html
    except Exception as e:
        print(f"❌ AI 생성 오류: {e}")
        return None, None

def post_to_blog(title, content):
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        if not creds.valid: creds.refresh(Request())
        service = build('blogger', 'v3', credentials=creds)
        service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return True
    except:
        return False

# ==========================================
# [4. 메인 컨트롤러]
# ==========================================
def main():
    strategy = get_daily_strategy()
    print(f"🚀 [엔진 가동] {strategy['desc']}")
    
    # 상품 확보 (오메가3 등)
    products = fetch_coupang_get_api("/products/goldbox")
    if not products:
        products = fetch_coupang_get_api("/products/bestcategories/1024", "limit=10")
        
    if products:
        prod = products[random.randint(0, len(products)-1)]
        print(f"✅ 상품 확보: {prod['productName']}")
        
        title, html = generate_content_adpick_style("AD", prod['productName'], prod)
        if title and html:
            if post_to_blog(title, html):
                print(f"🎉 [최종] 성공적으로 발행되었습니다!")
                return

    print("⚠️ 광고글 실패로 정보글 전환")
    title, html = generate_content_adpick_style("INFO", "공복 혈당 관리법")
    if title and html:
        post_to_blog(title, html)

if __name__ == "__main__":
    main()
