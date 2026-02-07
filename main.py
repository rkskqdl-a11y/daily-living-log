import os, hmac, hashlib, requests, time, json, random, re
from datetime import datetime, date
# [성공 포인트] 애드픽 코드에서 사용한 구형 SDK 규격 유지
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 시스템 설정]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = datetime(2026, 2, 2) #

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
    .prod-img { display: block; margin: 0 auto; max-width: 450px; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    p { line-height: 1.8; margin-bottom: 32px; color: #444; }
</style>
"""

# ==========================================
# [2. 전략적 스케줄링] -
# ==========================================
def get_daily_strategy():
    days_diff = (datetime.now() - START_DATE).days
    
    # [A] 초정밀 신뢰 구축 기간 (시작 후 14일까지): 100% 정보글만 발행
    if days_diff <= 14:
        return {"ad_slots": [], "desc": "🛡️ 1단계-A: 초정밀 신뢰 구축 (100% 정보글)"}
    
    # [B] 신뢰 안착 기간 (15일 ~ 30일): 하루 1회 광고 허용
    elif days_diff <= 30: 
        return {"ad_slots": [3], "desc": "🛡️ 1단계-B: 신뢰 안착 모드 (하루 1회 광고)"}
    
    # [C] 수익 테스트 기간 (31일 ~ 90일): 하루 2회 광고
    elif days_diff <= 90:
        return {"ad_slots": [1, 4], "desc": "📈 2단계: 수익 테스트 모드 (하루 2회 광고)"}
    
    # [D] 수익 최적화 기간 (91일 이후): 하루 3회 광고
    else:
        return {"ad_slots": [1, 3, 5], "desc": "💰 3단계: 수익 최적화 모드 (하루 3회 광고)"}

# ==========================================
# [3. 쿠팡 API 엔진] -
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
        if res.status_code == 200: return res.json().get('data', [])
        return None
    except: return None

# ==========================================
# [4. 애드픽 스타일 AI 엔진 & 링크 정제] -
# ==========================================
def generate_content_final(post_type, keyword, product=None):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # [성공 로직] 애드픽 코드에서 검증된 모델명 사용
        model = genai.GenerativeModel('models/gemini-2.5-flash')

        persona = "30대 여성 마케팅 전문가 '토리놀이'입니다. 다정하고 친근한 말투(~해요, ✨💖)로 작성하세요."

        if post_type == "AD" and product:
            prompt = f"{persona} 주제: '{product['productName']}' 리뷰. [TITLE] 제목 [/TITLE] [BODY] 본문 1500자 이상 [/BODY] 형식 엄수. **주의: 본문 내용에 제품 URL 주소는 절대 적지 마세요.**"
        else:
            prompt = f"{persona} 주제: '{keyword}' 가이드. [TITLE] 제목 [/TITLE] [BODY] 본문 1500자 이상 [/BODY] 형식 엄수."

        res = model.generate_content(prompt).text
        
        # 태그 기반 파싱
        title = res.split('[TITLE]')[1].split('[/TITLE]')[0].strip()
        body = res.split('[BODY]')[1].split('[/BODY]')[0].strip()
        
        # [정제] 본문 내 지저분한 링크 및 특수 문구 완벽 제거
        clean_body = re.sub(r'https?://\S+', '', body) 
        clean_body = re.sub(r'\[.*?\]\(.*?\)', '', clean_body) 
        clean_body = re.sub(r'⭐.*?⭐', '', clean_body)
        clean_body = re.sub(r'\*\*|##|`|#', '', clean_body) 
        
        body_html = "".join([f"<p>{line.strip()}</p>" for line in clean_body.split('\n') if line.strip()])
        
        if post_type == "AD":
            img_html = f'<div style="text-align:center; margin:30px 0;"><img src="{product["productImage"]}" class="prod-img"></div>'
            btn_style = "display:inline-block; padding:15px 35px; background:#ff69b4; color:#fff; text-decoration:none; border-radius:30px; font-weight:bold; margin:25px 0; box-shadow: 0 4px 15px rgba(255,105,180,0.3);"
            btn_html = f'<div style="text-align:center;"><a href="{product["productUrl"]}" target="_blank" style="{btn_style}">✨ {product["productName"]} 보러가기 ✨</a><p style="font-size:12px; color:#888; margin-top:10px;">쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p></div>'
            return title, STYLE_FIX + img_html + body_html + btn_html
        
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
    except: return False

# ==========================================
# [5. 메인 컨트롤러]
# ==========================================
def main():
    strategy = get_daily_strategy()
    hour_idx = datetime.now().hour // 4 
    is_ad = (hour_idx in strategy['ad_slots'])
    
    print(f"🚀 [엔진 가동] {strategy['desc']} (슬롯: {hour_idx})")
    
    if is_ad:
        products = fetch_coupang_get_api("/products/goldbox")
        if not products: products = fetch_coupang_get_api("/products/bestcategories/1024", "limit=10")
        if products:
            prod = products[random.randint(0, len(products)-1)]
            print(f"✅ 광고 모드: {prod['productName']} 수집 성공")
            title, html = generate_content_final("AD", prod['productName'], prod)
            if title and html:
                if post_to_blog(title, html):
                    print("🎉 [최종] 광고 포스팅 발행 성공!")
                    return
    
    # 정보글 모드 (슬롯이 아니거나 상품 확보 실패 시)
    kw_list = ["간수치 낮추는 법", "공복혈당 관리", "불면증 극복 음식", "거북목 스트레칭", "장 건강 지키는 식단", "아침 사과의 효능"]
    kw = random.choice(kw_list)
    print(f"📘 정보 모드: '{kw}' 생성 중")
    title, html = generate_content_final("INFO", kw)
    if title and html:
        post_to_blog(title, html)
        print(f"🎉 [최종] '{kw}' 정보 포스팅 발행 성공!")

if __name__ == "__main__":
    main()
