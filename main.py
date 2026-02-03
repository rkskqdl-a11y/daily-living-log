import os, hmac, hashlib, requests, time, json, random
import google.generativeai as genai
from datetime import datetime, date
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# [1. 핵심 설정]
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

# [2. 키워드 DB]
HEALTH_KEYWORDS = [
    "브로콜리 설포라판", "블루베리 안토시아닌", "토마토 라이코펜", "아보카도 효능", "비트 식이섬유",
    "아스파라거스 숙취", "케일 해독주스", "시금치 루테인", "마늘 면역력", "양파 퀘르세틴",
    "연어 오메가3", "고등어 DHA", "굴 아연", "전복 기력", "달걀 콜린"
]

def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14: return {"total": 3, "ad_slots": [1], "desc": "1단계"}
    elif days_passed < 30: return {"total": 4, "ad_slots": [1], "desc": "2단계"}
    else: return {"total": 6, "ad_slots": [0, 2, 4], "desc": "3단계"}

# [3. 쿠팡 API 호출 (에러 추적 강화)]
def fetch_product(kw):
    print(f"🔍 쿠팡에서 '{kw}' 상품 검색 중...")
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query = f"keyword={kw}&limit=1"
    url = f"https://link.coupang.com{path}?{query}"
    
    try:
        t = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        msg = t + "GET" + path + query
        sig = hmac.new(bytes(SECRET_KEY, "utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        header = {"Authorization": f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={t}, signature={sig}"}
        
        res = requests.get(url, headers=header, timeout=15)
        data = res.json()
        
        if res.status_code != 200:
            print(f"❌ 쿠팡 API 에러: {res.status_code} - {res.text}")
            return []
            
        products = data.get('data', {}).get('productData', [])
        if not products:
            print(f"⚠️ '{kw}'에 대한 검색 결과가 없습니다.")
        return products
    except Exception as e:
        print(f"❌ 쿠팡 연결 중 치명적 오류: {str(e)}")
        return []

# [4. 제미나이 글쓰기 (에러 추적 강화)]
def generate_health_post(post_type, keyword, product=None):
    print(f"🎨 제미나이가 {post_type} 글을 쓰는 중...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        disclosure = "<br><br><p style='color:gray;font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>"
        
        if post_type == "AD":
            prompt = f"당신은 영양사입니다. '{keyword}'의 효능을 설명하고 '{product['productName']}' 제품을 추천하는 HTML 글을 작성하세요. 반드시 <table>을 포함하세요. 구매링크: <a href='{product['productUrl']}'>상세보기</a>"
            footer = disclosure
        else:
            prompt = f"당신은 의사입니다. '{keyword}'에 대한 전문적인 건강 정보 HTML 글을 작성하세요. 상품 링크는 넣지 말고 <table>은 넣으세요."
            footer = ""

        response = model.generate_content(prompt)
        if not response.text:
            print("⚠️ 제미나이가 빈 내용을 반환했습니다.")
            return None
        return response.text + footer
    except Exception as e:
        print(f"❌ 제미나이 글쓰기 중 오류: {str(e)}")
        return None

# [5. 블로그 발행 (에러 추적 강화)]
def post_to_blog(title, content):
    print(f"📤 블로그에 '{title}' 발행 시도 중...")
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        service = build('blogger', 'v3', credentials=creds)
        
        body = {'kind': 'blogger#post', 'title': title, 'content': content}
        res = service.posts().insert(blogId=BLOG_ID, body=body).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 블로그 발행 중 오류: {str(e)}")
        return None

# [6. 메인 실행]
def main():
    strat = get_daily_strategy()
    hour_idx = datetime.now().hour // 4 
    
    # [주의] 수동 실행 시에도 결과를 보기 위해 슬롯 제한을 잠시 무시하는 조건 추가 가능
    print(f"🕒 현재 시각 인덱스: {hour_idx} (전략상 총 {strat['total']}회 중 {hour_idx}번째)")

    is_ad = hour_idx in strat['ad_slots']
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {post_type} 모드로 진행합니다. (키워드: {kw})")
    
    if post_type == "AD":
        # 키워드에서 앞글자만 따서 검색 (검색 확률 높임)
        search_kw = kw.split()[0]
        products = fetch_product(search_kw)
        if products:
            html = generate_health_post("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[건강추천] {kw} 관리에 도움되는 법", html)
                if url: print(f"✅ 최종 발행 성공! 주소: {url}")
    else:
        html = generate_health_post("INFO", kw)
        if html:
            url = post_to_blog(f"알고 먹자! {kw}의 놀라운 효능", html)
            if url: print(f"✅ 최종 발행 성공! 주소: {url}")

if __name__ == "__main__":
    main()
