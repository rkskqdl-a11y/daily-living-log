import os, hmac, hashlib, requests, time, json, random, re, urllib.parse, traceback
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# [1. 설정 및 환경 변수]
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
CLIENT_ID = os.environ.get('BLOGGER_CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('BLOGGER_CLIENT_SECRET', '').strip()

# 시각적 버그 수정 CSS
STYLE_FIX = """
<style>
    h1, h2, h3 { line-height: 1.6 !important; margin-bottom: 20px !important; word-break: keep-all; }
    .table-container { width: 100%; overflow-x: auto; margin: 25px 0; -webkit-overflow-scrolling: touch; }
    table { width: 100%; min-width: 600px; border-collapse: collapse; line-height: 1.5; }
    th, td { border: 1px solid #eee; padding: 12px; text-align: left; }
    th { background-color: #f9f9f9; }
    img { display: block; margin: 0 auto; max-width: 100%; height: auto; border-radius: 10px; }
</style>
"""

HEALTH_KEYWORDS = ["마그네슘", "콜라겐", "비타민D", "오메가3", "루테인", "밀크씨슬", "유산균", "아연"]

# [2. 기술 모듈]
def get_image_html(kw):
    """이미지 엑박 방지를 위해 loremflickr 사용"""
    search_term = urllib.parse.quote(kw)
    img_url = f"https://loremflickr.com/800/500/{search_term},health"
    return f'<div style="margin: 20px 0; text-align: center;"><img src="{img_url}" alt="{kw}"><p style="color: #888; font-size: 13px;">▲ {kw} 참고 이미지</p></div>'

def fetch_product(kw):
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    try:
        ts = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        msg = ts + "GET" + path + query_string
        sig = hmac.new(SECRET_KEY.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={ts}, signature={sig}"
        res = requests.get(url, headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=15)
        return res.json().get('data', {}).get('productData', []) if res.status_code == 200 else []
    except: return []

# [3. 지능형 모델 선택 및 글 생성]
def generate_content(post_type, keyword, product=None):
    print(f"✍️ 제미나이 연결 시도 중...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # [핵심] 가용 모델 자동 탐색 로직 추가 (404 에러 방지)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 순위: 1.5-flash -> 1.5-pro -> 첫 번째 사용 가능 모델
        if 'models/gemini-1.5-flash' in models: target = 'models/gemini-1.5-flash'
        elif 'models/gemini-1.5-pro' in models: target = 'models/gemini-1.5-pro'
        elif 'models/gemini-pro' in models: target = 'models/gemini-pro'
        else: target = models[0]
        
        print(f"✅ 선택된 모델: {target}")
        model = genai.GenerativeModel(target)
        
        prompt = f"건강 전문 에디터로서 '{keyword}'에 대한 HTML 포스팅을 1,500자 이상 작성하세요. <table>을 반드시 포함하고 <div class='table-container'>로 감싸세요."
        if post_type == "AD":
            prompt += f" 추가로 '{product['productName']}' 제품을 추천하고 <a href='{product['productUrl']}'>상세보기</a> 링크를 넣으세요."

        response = model.generate_content(prompt)
        clean_text = re.sub(r'\*\*|##|`|#', '', response.text)
        footer = "<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>" if post_type == "AD" else ""
        
        return STYLE_FIX + get_image_html(keyword) + clean_text + footer
    except Exception as e:
        print(f"❌ 생성 실패 상세 에러:\n{traceback.format_exc()}")
        return None

# [4. 블로그 발행]
def post_to_blog(title, content):
    print(f"📤 블로그 발행 시도 중...")
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        if not creds.valid: creds.refresh(Request())
        service = build('blogger', 'v3', credentials=creds)
        res = service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 발행 실패 상세 에러:\n{traceback.format_exc()}")
        return None

# [5. 메인 실행]
def main():
    hour_idx = datetime.now().hour // 4 
    if hour_idx >= 3: return

    is_ad = (hour_idx == 1)
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {post_type} 프로세스 시작 (주제: {kw})")
    
    if post_type == "AD":
        products = fetch_product(kw)
        if products:
            html = generate_content("AD", kw, products[0])
            if html and (url := post_to_blog(f"[추천] {kw} 건강 관리를 위한 선택", html)):
                print(f"✅ 발행 성공: {url}")
    else:
        if (html := generate_content("INFO", kw)) and (url := post_to_blog(f"전문 가이드: {kw}의 놀라운 효능", html)):
            print(f"✅ 발행 성공: {url}")

if __name__ == "__main__":
    main()
