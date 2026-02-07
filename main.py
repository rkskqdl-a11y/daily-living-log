import os, hmac, hashlib, requests, time, json, random, re, urllib.parse, traceback
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 시스템 설정 및 자동 날짜 계산]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)  # 블로그 시작 날짜 고정

# 환경 변수(Secrets) 매핑
CLIENT_ID = os.environ.get('CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()

# [디자인 수리] 제목 겹침 및 표 넘침 방지 전용 CSS
STYLE_FIX = """
<style>
    h1, h2, h3 { line-height: 1.6 !important; margin-bottom: 25px !important; color: #222; word-break: keep-all; }
    .table-container { width: 100%; overflow-x: auto; margin: 30px 0; border: 1px solid #eee; border-radius: 8px; -webkit-overflow-scrolling: touch; }
    table { width: 100%; min-width: 600px; border-collapse: collapse; line-height: 1.6; font-size: 15px; }
    th, td { border: 1px solid #f0f0f0; padding: 15px; text-align: left; }
    th { background-color: #fafafa; font-weight: bold; }
    .prod-img { display: block; margin: 0 auto; max-width: 350px; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    p { line-height: 1.9; margin-bottom: 25px; color: #444; }
</style>
"""

# ==========================================
# [2. 초안전 자동 배합 로직 (방탄 스케줄)]
# ==========================================
def get_daily_strategy():
    days_passed = (date.today() - START_DATE).days
    
    if days_passed <= -1: # 1단계: 신뢰 구축 (5:1)
        return {"ad_slots": [3], "desc": "🛡️ 1단계: 신뢰 구축 모드"}
    elif days_passed <= 90: # 2단계: 수익 테스트 (4:2)
        return {"ad_slots": [1, 4], "desc": "📈 2단계: 수익 테스트 모드"}
    else: # 3단계: 수익 최적화 (3:3)
        return {"ad_slots": [1, 3, 5], "desc": "💰 3단계: 수익 최적화 모드"}

# ==========================================
# [3. 초거대 키워드 및 10,000개 조합 요소]
# ==========================================
KEYWORDS = {
    "INFO": [
        "간수치 낮추는 법", "공복혈당 관리", "역류성 식도염 식단", "불면증 극복 음식", "거북목 스트레칭", "비타민D 햇빛", "마그네슘 부족 증상", "오메가3 고르는법", "탈모 예방 습관", "면역력 높이는 법",
        "손목 터널 증후군", "무릎 관절염 식단", "고혈압 낮추는 차", "지방간 수치 개선", "위염에 좋은 과일", "장누수 증후군 해결", "만성 변비 탈출", "아토피 보습", "대상포진 면역력", "통풍 요산 관리",
        "공복 사과 효능", "아침 식사 대용", "저탄고지 부작용", "당독소 줄이는 법", "항산화 식품", "비타민D 합성 시간", "식이섬유 많은 음식", "칼륨 풍부한 채소", "단백질 권장량", "수면의 질 높이기"
        # ... 키워드 300개 이상 내부 로테이션
    ],
    "AD": [
        "rTG 오메가3 추천", "저분자 콜라겐 펩타이드", "고함량 마그네슘 영양제", "질 유산균 효능", "쏘팔메토 전립선 건강", "루테인 지아잔틴", "보스웰리아 추출물", "MSM 식이유황 가루", "코엔자임Q10 항산화", "산양유 단백질 파우더",
        "유기농 양배추즙", "ABC주스 착즙액", "포스파티딜세린 뇌영양제", "비오틴 탈모 영양제", "초임계 보스웰리아", "콘드로이친 1200", "홍삼정 추천", "녹용 보약", "저당 두유", "구운 견과류 세트"
        # ... 광고 키워드 300개 이상 내부 로테이션
    ]
}

t_styles = ["전문 가이드:", "[필독]", "몰랐던 사실:", "심층 분석:", "건강 백과:", "현명한 선택:", "오늘의 추천:", "완벽 정리:", "의학 정보:", "생활의 지혜:"]
i_styles = ["질문형", "공감형", "데이터형", "경고형", "경험형", "이슈형", "인사형", "통계형", "사례형", "호기심형"]
b_styles = ["가이드형", "체크리스트형", "비교형", "팩트체크형", "Q&A형", "스토리형", "분석형", "실험형", "장단점형", "요약형"]
o_styles = ["실천형", "요약형", "안부형", "습관형", "응원형", "소통형", "예고형", "마인드형", "인사형", "질문형"]

# ==========================================
# [4. 기술 모듈]
# ==========================================
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

def generate_content(post_type, keyword, product=None):
    ts, ins, bs, os = random.choice(t_styles), random.choice(i_styles), random.choice(b_styles), random.choice(o_styles)
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in models else models[0] # 모델 자동 탐색
        model = genai.GenerativeModel(target)
        
        prompt = f"전문 에디터로서 '{keyword}'에 대해 1,500자 이상 HTML로 작성하세요. 구성:[도입-{ins},본론-{bs},결론-{os}]. <table>은 <div class='table-container'>로 감싸세요. 마크다운 기호(**, ##)는 절대 사용하지 마세요."
        if post_type == "AD":
            img_html = f'<div style="text-align:center; margin-bottom:30px;"><img src="{product["productImage"]}" class="prod-img"></div>'
            prompt += f" 추가로 '{product['productName']}' 추천과 링크 <a href='{product['productUrl']}'>▶ 상세정보</a>를 넣으세요."
            res = model.generate_content(prompt).text
            content = STYLE_FIX + img_html + re.sub(r'\*\*|##|`|#', '', res) + "<br><p style='color:gray; font-size:12px;'>쿠팡 파트너스 수수료를 제공받을 수 있습니다.</p>"
        else:
            res = model.generate_content(prompt).text # 정보글 이미지 제거
            content = STYLE_FIX + re.sub(r'\*\*|##|`|#', '', res)
        return ts, content
    except: return None, None

def post_to_blog(title, content):
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        if not creds.valid: creds.refresh(Request()) # 토큰 자동 갱신
        service = build('blogger', 'v3', credentials=creds)
        res = service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 발행 에러: {str(e)}"); return None

# ==========================================
# [5. 메인 컨트롤러 (자동 진화 스케줄)]
# ==========================================
def main():
    strategy = get_daily_strategy()
    hour_idx = datetime.now().hour // 4  # 하루 6회 슬롯
    
    is_ad = (hour_idx in strategy['ad_slots'])
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(KEYWORDS[post_type])
    
    print(f"📢 {strategy['desc']} 가동 중 - [{post_type}] 발행: {kw}")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0])
        if products:
            ts, html = generate_content("AD", kw, products[0])
            if html and (url := post_to_blog(f"{ts} {kw} 건강 관리 가이드", html)):
                print(f"✅ 성공: {url}")
        else: post_type = "INFO"

    if post_type == "INFO":
        ts, html = generate_content("INFO", kw)
        if html and (url := post_to_blog(f"{ts} {kw}의 모든 것", html)):
            print(f"✅ 성공: {url}")

if __name__ == "__main__":
    main()
