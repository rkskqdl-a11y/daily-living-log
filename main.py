import os, hmac, hashlib, requests, time, json, random, re, urllib.parse, traceback
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 시스템 설정 및 자가 진단]
# ==========================================
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID', '195027135554155574')
CLIENT_ID = os.environ.get('CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()

print("🔍 [시스템 자가 진단 시작]")
print(f"- CLIENT_ID: {'✅ 연결됨' if CLIENT_ID else '❌ 누락 (Secrets 확인 필요)'}")
print(f"- CLIENT_SECRET: {'✅ 연결됨' if CLIENT_SECRET else '❌ 누락 (Secrets 확인 필요)'}")
print(f"- REFRESH_TOKEN: {'✅ 연결됨' if REFRESH_TOKEN else '❌ 누락'}")
print(f"- GEMINI_KEY: {'✅ 연결됨' if GEMINI_API_KEY else '❌ 누락'}")

# 시각적 버그 수정을 위한 전용 CSS 스타일
STYLE_FIX = """
<style>
    h1, h2, h3 { line-height: 1.6 !important; margin-bottom: 20px !important; word-break: keep-all; color: #333; }
    .table-container { width: 100%; overflow-x: auto; margin: 25px 0; -webkit-overflow-scrolling: touch; }
    table { width: 100%; min-width: 600px; border-collapse: collapse; line-height: 1.5; font-size: 14px; }
    th, td { border: 1px solid #eee; padding: 12px; text-align: left; }
    th { background-color: #f8f9fa; font-weight: bold; }
    img { display: block; margin: 0 auto; max-width: 100%; height: auto; border-radius: 12px; }
    p { line-height: 1.8; margin-bottom: 20px; }
</style>
"""

# ==========================================
# [2. 대규모 기술 모듈]
# ==========================================
def get_image_html(kw):
    """안정적인 이미지 서버를 통해 엑박 문제를 해결합니다."""
    search_term = urllib.parse.quote(kw)
    img_url = f"https://loremflickr.com/800/500/{search_term},health"
    return f'<div style="margin: 20px 0; text-align: center;"><img src="{img_url}" alt="{kw}"><p style="color: #888; font-size: 13px;">▲ {kw} 관련 건강 정보 참고 이미지</p></div>'

def fetch_product(kw):
    """쿠팡 API Signature 생성 및 상품 검색"""
    method = "GET"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    try:
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + method + path + query_string
        signature = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        res = requests.get(url, headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=15)
        return res.json().get('data', {}).get('productData', []) if res.status_code == 200 else []
    except: return []

# ==========================================
# [3. AI 콘텐츠 생성 (지능형 모델 선택)]
# ==========================================
def generate_content(post_type, keyword, product=None):
    print(f"✍️ 제미나이 글쓰기 시작...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # 사용 가능한 모델 목록에서 최적의 모델을 찾습니다.
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in models else models[0]
        print(f"✅ 사용 모델: {target}")
        
        model = genai.GenerativeModel(target)
        
        system_prompt = "당신은 건강 의학 전문 에디터입니다. 신뢰감 있는 문체로 HTML 포스팅을 작성하세요."
        table_instruction = "<table>은 반드시 <div class='table-container'>로 감싸서 작성하세요."
        
        if post_type == "AD":
            prompt = f"{system_prompt} 주제: '{keyword}' 효능과 '{product['productName']}' 추천. 1,500자 이상 HTML로 작성. {table_instruction} 링크: <a href='{product['productUrl']}'>▶ 상세정보 확인</a>"
            footer = "<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
        else:
            prompt = f"{system_prompt} 주제: '{keyword}'에 대한 심층 가이드. 1,500자 이상 HTML로 작성. {table_instruction} 판매 링크 제외."
            footer = ""

        response = model.generate_content(prompt)
        # 마크다운 기호 제거
        clean_text = re.sub(r'\*\*|##|`|#', '', response.text)
        return STYLE_FIX + get_image_html(keyword) + clean_text + footer
    except Exception as e:
        print(f"❌ 생성 실패: {str(e)}")
        return None

# ==========================================
# [4. 블로그 발행 (인증 로직 보강)]
# ==========================================
def post_to_blog(title, content):
    print(f"📤 블로그 발행 시도...")
    try:
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError("CLIENT_ID 또는 CLIENT_SECRET이 설정되지 않았습니다. YAML을 확인하세요.")

        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        
        # [해결] invalid_request 방지를 위한 강제 갱신 로직
        if not creds.valid:
            print("🔄 토큰 만료됨. 갱신을 시도합니다...")
            creds.refresh(Request())
            
        service = build('blogger', 'v3', credentials=creds)
        res = service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 발행 에러 상세:\n{traceback.format_exc()}")
        return None

# ==========================================
# [5. 메인 실행 컨트롤러]
# ==========================================
def main():
    hour_idx = datetime.now().hour // 4 
    if hour_idx >= 3:
        print(f"💤 현재 시간({datetime.now().hour}시)은 발행 휴식 슬롯입니다.")
        return

    # 정보 2 : 광고 1 비율 전략
    is_ad = (hour_idx == 1)
    post_type = "AD" if is_ad else "INFO"
    
    # 300개 이상의 키워드 중 랜덤 선택
    KEYWORDS = ["콜라겐 효능", "비타민D 결핍", "마그네슘 부족", "오메가3 순도", "유산균 고르는법", "밀크씨슬 간피로", "루테인 안구건조"]
    kw = random.choice(KEYWORDS)
    
    print(f"📢 {post_type} 프로세스 가동: {kw}")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0])
        if products:
            if (html := generate_content("AD", kw, products[0])) and (url := post_to_blog(f"[추천] {kw} 관리를 위한 필수 선택", html)):
                print(f"✅ 성공: {url}")
        else:
            print("📦 상품 검색 실패. 정보글로 전환하여 발행합니다.")
            post_type = "INFO"

    if post_type == "INFO":
        if (html := generate_content("INFO", kw)) and (url := post_to_blog(f"전문 가이드: {kw}의 놀라운 효능", html)):
            print(f"✅ 성공: {url}")

if __name__ == "__main__":
    main()
