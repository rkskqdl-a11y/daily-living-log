import os, hmac, hashlib, requests, time, json, random, re
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 시스템 설정]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = datetime(2026, 2, 2) 

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
# [2. 전략적 스케줄링] - 하루 최대 6회 실행 (7개 이하 준수)
# ==========================================
def get_daily_strategy():
    days_diff = (datetime.now() - START_DATE).days
    
    if days_diff <= 14:
        return {"ad_slots": [], "desc": "🛡️ 1단계-A: 초정밀 신뢰 구축 (100% 정보글)"}
    elif days_diff <= 30: 
        return {"ad_slots": [3], "desc": "🛡️ 1단계-B: 신뢰 안착 모드 (하루 1회 광고)"}
    elif days_diff <= 90:
        return {"ad_slots": [1, 4], "desc": "📈 2단계: 수익 테스트 모드 (하루 2회 광고)"}
    else:
        return {"ad_slots": [1, 3, 5], "desc": "💰 3단계: 수익 최적화 모드 (하루 3회 광고)"}

# ==========================================
# [3. 대규모 건강/음식 키워드 DB]
# ==========================================
KEYWORDS_INFO = [
    # 기존 요청 키워드
    "간수치 낮추는 법", "공복혈당 관리", "역류성 식도염 식단", "불면증 극복 음식", "거북목 스트레칭", "위염에 좋은 과일",
    "고혈압 낮추는 차", "지방간 수치 개선", "만성 변비 탈출", "아토피 보습 관리", "대상포진 면역력", "통풍 요산 관리",
    "아침 사과의 효능", "액상과당의 위험성", "비타민D 합성 시간", "마그네슘 부족 증상", "오메가3 고르는 법", "단백질 하루 권장량",
    "간헐적 단식 효과", "저탄고지 부작용", "안구건조증 예방", "허리디스크 좋은 운동", "비염 완화 생활습관", "족저근막염 스트레칭",
    "브로콜리 세척법", "귀리의 효능", "토마토 라이코펜", "강황 커큐민 효과", "물 마시는 건강한 습관", "카페인 중독 탈출법",
    "내장지방 빼는 법", "기초대사량 높이기", "림프 순환 마사지", "면역력 높이는 영양제", "피로회복에 좋은 음식", "눈 건강 지키는 법",
    
    # 과일/채소 효능 및 먹는 법
    "블루베리 안토시아닌 효능", "아보카도 하루 섭취량", "석류 여성 건강 효능", "당근 비타민A 흡수율 높이는 법", 
    "양배추 위 건강 효능", "키위 소화 효능", "바나나 공복 섭취 주의점", "포도 레스베라트롤 효능", "마늘 알리신 극대화하는 법",
    "양파 퀘르세틴 효능", "시금치 루테인 효능", "파프리카 색깔별 차이", "브로콜리 설포라판 효능", "비트 혈관 건강",
    
    # 곡물/견과류 효능 및 먹는 법
    "현미 발아 효능", "귀리 베타글루칸 효능", "검은콩 안토시아닌과 탈모", "호두 뇌 건강 효능", "아몬드 하루 권장량",
    "브라질너트 셀레늄 주의점", "메밀 루틴 효능", "보리 식이섬유 효능", "퀴노아 단백질 효능", "율무 부종 완화",
    
    # 고기/생선/단백질
    "닭가슴살 건강하게 먹는 법", "연어 오메가3 효능", "고등어 혈관 건강", "소고기 철분 흡수 돕는 음식",
    "오리고기 불포화지방산", "계란 노른자 콜레스테롤 진실", "두부 식물성 단백질 효능", "멸치 칼슘 흡수 높이기",
    "굴 아연 효능", "전복 기력 회복 효능", "돼지고기 비타민B1 효능",
    
    # 차(Tea)/전통차 효능 및 먹는 법
    "녹차 카테킨 효능", "생강차 염증 완화", "대추차 수면 도움", "매실액 소화 효능", "우엉차 다이어트 효과",
    "루이보스차 항산화", "페퍼민트차 집중력", "보리차 수분 보충", "히비스커스차 혈압 조절", "돼지감자차 이눌린 효능",
    
    # 식습관/생활건강
    "천천히 씹어 먹기의 효과", "식후 바로 누우면 안 되는 이유", "공복에 먹으면 좋은 음식", "자기 전 피해야 할 음식",
    "혈당 스파이크 방지 식사법", "나트륨 배출 돕는 칼륨 음식", "탄산음료 끊는 법", "야식 증후군 탈출하기",
    "식초 트릭 혈당 관리법", "건강한 식용유 고르는 법"
]

# ==========================================
# [4. 쿠팡 API 엔진]
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
# [5. AI 생성 엔진 & 링크 정제]
# ==========================================
def generate_content_final(post_type, keyword, product=None):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('models/gemini-2.5-flash')

        persona = "30대 여성 마케팅 전문가 '토리놀이'입니다. 다정하고 친근한 말투(~해요, ✨💖)로 작성하세요."

        if post_type == "AD" and product:
            prompt = f"{persona} 주제: '{product['productName']}' 리뷰. [TITLE] 제목 [/TITLE] [BODY] 본문 1500자 이상 [/BODY] 형식 엄수. **주의: 본문 내용에 제품 URL 주소는 절대 적지 마세요.**"
        else:
            # [보강] 효능과 먹는 법을 포함하도록 지시
            prompt = f"{persona} 주제: '{keyword}'의 효능과 효과적으로 먹는 법 가이드. [TITLE] 제목 [/TITLE] [BODY] 본문 1500자 이상 상세히 [/BODY] 형식 엄수. <table>로 영양 성분이나 비교표를 포함하세요."

        res = model.generate_content(prompt).text
        
        title = res.split('[TITLE]')[1].split('[/TITLE]')[0].strip()
        body = res.split('[BODY]')[1].split('[/BODY]')[0].strip()
        
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
    
    # 정보글 모드
    kw = random.choice(KEYWORDS_INFO)
    print(f"📘 정보 모드: '{kw}' 생성 중")
    title, html = generate_content_final("INFO", kw)
    if title and html:
        post_to_blog(title, html)
        print(f"🎉 [최종] '{kw}' 정보 포스팅 발행 성공!")

if __name__ == "__main__":
    main()
