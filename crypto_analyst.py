# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import requests
import time
import os
import bcrypt
from datetime import datetime, timedelta
import ta

# ==================== پیکربندی اولیه ====================
st.set_page_config(page_title="سیستم تحلیل حرفه‌ای کریپتو", layout="wide", initial_sidebar_state="collapsed")

# ==================== ماژول احراز هویت ====================
class Authenticator:
    """مدیریت امن ورود کاربر"""
    
    @staticmethod
    def initialize():
        """بارگذاری یا تنظیم اولیه کاربر از متغیرهای محیطی"""
        # خواندن از متغیرهای محیطی Render (ایمن‌ترین روش)
        username = os.environ.get("APP_USERNAME", "admin")
        password_hash = os.environ.get("APP_PASSWORD_HASH", "")
        
        # اگر هش در محیط تعریف نشده، از رمز پیش‌فرض استفاده کن (فقط برای توسعه)
        if not password_hash:
            default_password = "admin123"
            password_hash = bcrypt.hashpw(default_password.encode(), bcrypt.gensalt()).decode()
            st.warning("⚠️ از رمز عبور پیش‌فرض استفاده می‌شود. لطفاً در Render متغیرهای APP_USERNAME و APP_PASSWORD_HASH را تنظیم کنید.")
        
        # ذخیره در state جلسه Streamlit
        if "auth" not in st.session_state:
            st.session_state.auth = {
                "username": username,
                "password_hash": password_hash,
                "is_authenticated": False,
                "login_attempts": 0
            }
    
    @staticmethod
    def login_form():
        """نمایش فرم ورود و بررسی اعتبار"""
        st.markdown("<h1 style='text-align: center; color: #ffcc00;'>🔒 ورود به سیستم تحلیل کریپتو</h1>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                username = st.text_input("نام کاربری", placeholder="admin")
                password = st.text_input("رمز عبور", type="password", placeholder="••••••••")
                submit = st.form_submit_button("ورود به سیستم", use_container_width=True)
            
            if submit:
                auth_state = st.session_state.auth
                
                # بررسی تعداد دفعات تلاش ناموفق
                if auth_state["login_attempts"] >= 3:
                    st.error("❌ حساب به دلیل تلاش‌های ناموفق زیاد موقتاً قفل شده است. 5 دقیقه دیگر تلاش کنید.")
                    time.sleep(0.5)
                    st.rerun()
                
                # بررسی اعتبار
                correct_username = (username == auth_state["username"])
                correct_password = bcrypt.checkpw(password.encode(), auth_state["password_hash"].encode())
                
                if correct_username and correct_password:
                    auth_state["is_authenticated"] = True
                    auth_state["login_attempts"] = 0
                    st.success("✅ ورود موفقیت‌آمیز! در حال انتقال...")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    auth_state["login_attempts"] += 1
                    remaining_attempts = 3 - auth_state["login_attempts"]
                    st.error(f"❌ اطلاعات ورود نادرست است. {remaining_attempts} تلاش باقی مانده.")
                    time.sleep(1)
                    return False
        return False

# ==================== ماژول دریافت داده ====================
class DataFetcher:
    """دریافت امن و مدیریت خطا برای داده‌های کوین‌گکو"""
    
    def __init__(self):
        self.api_key = os.environ.get("COINGECKO_API_KEY", "CG-YOUR-DEMO-KEY")
        self.base_url = "https://api.coingecko.com/api/v3"
        self.headers = {"x-cg-demo-api-key": self.api_key} if self.api_key != "CG-YOUR-DEMO-KEY" else {}
    
    def _make_request(self, url, params=None, max_retries=3):
        """تابع اصلی درخواست با قابلیت تلاش مجدد"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=20)
                
                # بررسی خطای محدودیت نرخ (429)
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 10  # افزایش تاخیر در هر تلاش
                    st.warning(f"⏳ درخواست شما محدود شده است. {wait_time} ثانیه صبر کنید... (تلاش {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()  # بررسی سایر خطاهای HTTP
                return response.json()
                
            except requests.exceptions.Timeout:
                st.warning(f"⏱️ درخواست timeout شد. تلاش مجدد... ({attempt+1}/{max_retries})")
            except requests.exceptions.ConnectionError:
                st.warning(f"🔌 خطای اتصال. تلاش مجدد... ({attempt+1}/{max_retries})")
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                st.error(f"🚫 خطای شبکه: {str(e)[:100]}")
                break
        
        st.error("❌ پس از چندین تلاش، دریافت داده ممکن نشد.")
        return None
    
    def get_coin_data(self, coin_id, vs_currency="usd", days=30):
        """دریافت داده‌های تاریخی قیمت و حجم"""
        if not coin_id or not coin_id.strip():
            st.error("لطفاً نام ارز را وارد کنید.")
            return None
            
        coin_id = coin_id.strip().lower()
        url = f"{self.base_url}/coins/{coin_id}/market_chart"
        params = {"vs_currency": vs_currency, "days": days}
        
        data = self._make_request(url, params)
        if not data:
            return None
        
        try:
            # پردازش داده‌های قیمت
            prices = data.get("prices", [])
            if not prices:
                st.error("داده‌ای برای این ارز یافت نشد.")
                return None
                
            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            
            # پردازش داده‌های حجم
            volumes = data.get("total_volumes", [])
            if volumes:
                df["volume"] = [v[1] for v in volumes]
            
            # دریافت اطلاعات تکمیلی ارز
            info_url = f"{self.base_url}/coins/{coin_id}"
            info = self._make_request(info_url, params={"localization": "false"})
            if info:
                st.session_state["coin_info"] = {
                    "name": info.get("name", coin_id),
                    "symbol": info.get("symbol", "").upper(),
                    "market_cap": info.get("market_data", {}).get("market_cap", {}).get(vs_currency, 0),
                    "rank": info.get("market_cap_rank", "N/A")
                }
            
            return df
            
        except Exception as e:
            st.error(f"❌ خطا در پردازش داده‌ها: {str(e)[:200]}")
            return None
    
    def get_fear_greed_index(self):
        """دریافت شاخص ترس و طمع"""
        try:
            url = "https://api.alternative.me/fng/"
            data = self._make_request(url)
            if data and "data" in data and len(data["data"]) > 0:
                return int(data["data"][0]["value"])
        except:
            pass
        return None

# ==================== ماژول تحلیل تکنیکال ====================
class TechnicalAnalyzer:
    """تحلیل تکنیکال با اندیکاتورهای پیشرفته"""
    
    @staticmethod
    def analyze(df):
        if df is None or len(df) < 20:
            return {"سیگنال": "داده ناکافی", "اطمینان": 0, "جزئیات": {}}
        
        try:
            # محاسبه اندیکاتورها
            df["rsi"] = ta.momentum.RSIIndicator(df["price"], window=14).rsi()
            df["sma_20"] = ta.trend.SMAIndicator(df["price"], window=20).sma_indicator()
            df["sma_50"] = ta.trend.SMAIndicator(df["price"], window=50).sma_indicator()
            df["ema_12"] = ta.trend.EMAIndicator(df["price"], window=12).ema_indicator()
            
            # محاسبه مکدی
            macd = ta.trend.MACD(df["price"])
            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()
            
            # محاسبه باندهای بولینگر
            bollinger = ta.volatility.BollingerBands(df["price"], window=20)
            df["bb_high"] = bollinger.bollinger_hband()
            df["bb_low"] = bollinger.bollinger_lband()
            
            latest = df.iloc[-1]
            
            # تحلیل چند فاکتوره
            signal_score = 0
            reasons = []
            
            # تحلیل RSI
            if pd.notna(latest["rsi"]):
                if latest["rsi"] < 30:
                    signal_score += 25
                    reasons.append("RSI در منطقه اشباع فروش 📉")
                elif latest["rsi"] > 70:
                    signal_score -= 20
                    reasons.append("RSI در منطقه اشباع خرید 📈")
            
            # تحلیل میانگین‌های متحرک
            if pd.notna(latest["sma_20"]) and pd.notna(latest["price"]):
                if latest["price"] > latest["sma_20"]:
                    signal_score += 15
                    reasons.append("قیمت بالای میانگین ۲۰ روزه 🟢")
                else:
                    signal_score -= 10
                    reasons.append("قیمت زیر میانگین ۲۰ روزه 🔴")
                
                # کراس صعودی
                if len(df) > 50 and pd.notna(latest["sma_50"]):
                    if df["sma_20"].iloc[-2] < df["sma_50"].iloc[-2] and latest["sma_20"] > latest["sma_50"]:
                        signal_score += 20
                        reasons.append("کراس طلایی صعودی ⭐")
            
            # تحلیل مکدی
            if pd.notna(latest["macd"]) and pd.notna(latest["macd_signal"]):
                if latest["macd"] > latest["macd_signal"]:
                    signal_score += 10
                    reasons.append("MACD مثبت ↗️")
            
            # تحلیل باندهای بولینگر
            if pd.notna(latest["bb_low"]) and pd.notna(latest["price"]):
                if latest["price"] < latest["bb_low"]:
                    signal_score += 15
                    reasons.append("قیمت در کف باند بولینگر 📊")
            
            # تعیین سیگنال نهایی
            if signal_score >= 40:
                final_signal = "خرید قوی 🟢"
                confidence = min(90, 60 + signal_score)
            elif signal_score >= 20:
                final_signal = "خرید متوسط 🟡"
                confidence = 50 + signal_score
            elif signal_score <= -20:
                final_signal = "فروش قوی 🔴"
                confidence = min(90, 60 - signal_score)
            elif signal_score <= 0:
                final_signal = "فروش متوسط 🟠"
                confidence = 50 - signal_score
            else:
                final_signal = "خنثی ⚪"
                confidence = 50
            
            return {
                "سیگنال": final_signal,
                "اطمینان": min(95, max(5, confidence)),
                "RSI": round(latest["rsi"], 2) if pd.notna(latest["rsi"]) else None,
                "قیمت": round(latest["price"], 4),
                "SMA_20": round(latest["sma_20"], 4) if pd.notna(latest["sma_20"]) else None,
                "MACD": round(latest["macd"], 4) if pd.notna(latest["macd"]) else None,
                "دلایل": reasons[:3]  # فقط ۳ دلیل اول
            }
            
        except Exception as e:
            st.error(f"خطا در تحلیل تکنیکال: {str(e)[:100]}")
            return {"سیگنال": "خطای تحلیل", "اطمینان": 0, "جزئیات": {}}

# ==================== رابط کاربری اصلی ====================
def main_dashboard():
    """داشبورد اصلی پس از ورود موفق"""
    
    # نوار کناری تنظیمات
    with st.sidebar:
        st.image("https://cryptologos.cc/logos/bitcoin-btc-logo.png", width=80)
        st.markdown("### ⚙️ تنظیمات تحلیل")
        
        coin_id = st.text_input(
            "شناسه ارز (CoinGecko ID)",
            value="bitcoin",
            help="مثال: bitcoin, ethereum, solana, cardano"
        )
        
        vs_currency = st.selectbox("واحد پول", ["usd", "eur", "gbp", "jpy"])
        analysis_days = st.slider("بازه زمانی (روز)", 7, 365, 30)
        
        col1, col2 = st.columns(2)
        with col1:
            fetch_btn = st.button("🔍 تحلیل کن", type="primary", use_container_width=True)
        with col2:
            if st.button("🚪 خروج", use_container_width=True):
                st.session_state.auth["is_authenticated"] = False
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📊 اطلاعات API")
        fetcher = DataFetcher()
        if fetcher.api_key == "CG-YOUR-DEMO-KEY":
            st.warning("از کلید API پیش‌فرض استفاده می‌شود.")
        else:
            st.success("کلید API شخصی فعال است.")
    
    # بخش اصلی داشبورد
    st.title("🚀 سیستم تحلیل و سیگنال‌دهی ارزهای دیجیتال")
    
    if not fetch_btn:
        st.info("⏳ لطفاً شناسه ارز را وارد کرده و روی دکمه «تحلیل کن» کلیک کنید.")
        return
    
    with st.spinner("🔍 در حال دریافت و تحلیل داده‌ها..."):
        # ایجاد نمونه‌ها
        fetcher = DataFetcher()
        analyzer = TechnicalAnalyzer()
        
        # دریافت داده‌ها
        progress_bar = st.progress(0)
        
        # مرحله ۱: دریافت داده‌های قیمت
        st.write("**مرحله ۱:** دریافت داده‌های تاریخی...")
        df = fetcher.get_coin_data(coin_id, vs_currency, analysis_days)
        progress_bar.progress(30)
        
        if df is None or df.empty:
            st.error(f"""
            ### ❌ خطا در دریافت داده
            دلایل احتمالی:
            1. شناسه `{coin_id}` در CoinGecko موجود نیست
            2. محدودیت موقت API (هر ۵۰ درخواست در دقیقه)
            3. مشکل اتصال به اینترنت
            
            **راه‌حل‌ها:**
            - شناسه صحیح را از [لیست CoinGecko](https://www.coingecko.com) بررسی کنید
            - ۱ دقیقه صبر کرده و مجدد تلاش کنید
            - از API Key شخصی استفاده کنید
            """)
            return
        
        # مرحله ۲: تحلیل تکنیکال
        st.write("**مرحله ۲:** تحلیل تکنیکال...")
        tech_result = analyzer.analyze(df)
        progress_bar.progress(60)
        
        # مرحله ۳: دریافت شاخص ترس و طمع
        st.write("**مرحله ۳:** تحلیل احساسات بازار...")
        fear_greed = fetcher.get_fear_greed_index()
        progress_bar.progress(90)
        
        # مرحله ۴: تولید نتیجه نهایی
        st.write("**مرحله ۴:** تولید گزارش نهایی...")
        
        # نمایش اطلاعات ارز
        if "coin_info" in st.session_state:
            info = st.session_state["coin_info"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("نام ارز", info["name"])
            with col2:
                st.metric("نماد", info["symbol"])
            with col3:
                st.metric("رتبه بازار", f"#{info['rank']}" if info['rank'] != "N/A" else "N/A")
            with col4:
                formatted_mcap = f"{info['market_cap']:,.0f}" if info['market_cap'] else "N/A"
                st.metric("ارزش بازار", f"${formatted_mcap}")
        
        # تب‌های نتایج
        tab1, tab2, tab3 = st.tabs(["📈 نمودارها", "📊 تحلیل فنی", "🎯 سیگنال نهایی"])
        
        with tab1:
            # نمودار قیمت
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df.index, y=df['price'], mode='lines', 
                                     name='قیمت', line=dict(color='#00ff88', width=2)))
            fig1.update_layout(title='نمودار قیمت', height=400, 
                              xaxis_title='تاریخ', yaxis_title=f'قیمت ({vs_currency.upper()})',
                              template='plotly_dark')
            st.plotly_chart(fig1, use_container_width=True)
            
            # نمودار حجم
            if 'volume' in df.columns:
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(x=df.index, y=df['volume'], name='حجم معاملات',
                                     marker_color='#ffaa00'))
                fig2.update_layout(title='حجم معاملات', height=300,
                                  xaxis_title='تاریخ', yaxis_title='حجم',
                                  template='plotly_dark')
                st.plotly_chart(fig2, use_container_width=True)
        
        with tab2:
            # نتایج تحلیل تکنیکال
            st.subheader("📊 نتایج تحلیل تکنیکال")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                color = "green" if "خرید" in tech_result["سیگنال"] else "red" if "فروش" in tech_result["سیگنال"] else "gray"
                st.markdown(f"<h2 style='color: {color}; text-align: center;'>{tech_result['سیگنال']}</h2>", 
                           unsafe_allow_html=True)
            
            with col2:
                st.metric("درجه اطمینان", f"{tech_result['اطمینان']}%")
            
            with col3:
                if tech_result["RSI"]:
                    rsi_status = "اشباع فروش 🟢" if tech_result["RSI"] < 30 else "اشباع خرید 🔴" if tech_result["RSI"] > 70 else "نرمال ⚪"
                    st.metric("شاخص RSI", f"{tech_result['RSI']} ({rsi_status})")
            
            # نمایش دلایل تحلیل
            if tech_result["دلایل"]:
                st.markdown("**دلایل سیگنال:**")
                for reason in tech_result["دلایل"]:
                    st.markdown(f"- {reason}")
            
            # نمایش شاخص ترس و طمع
            if fear_greed:
                st.markdown("---")
                st.subheader("😨😊 شاخص ترس و طمع بازار")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.progress(fear_greed / 100, text=f"امتیاز: {fear_greed}/100")
                
                with col2:
                    if fear_greed <= 25:
                        st.error("ترس شدید")
                    elif fear_greed >= 75:
                        st.warning("طمع شدید")
                    else:
                        st.success("احساسات متعادل")
        
        with tab3:
            # سیگنال نهایی با طراحی ویژه
            st.subheader("🎯 سیگنال نهایی و توصیه اقدام")
            
            signal_color = "linear-gradient(90deg, #00ff88, #00cc66)" if "خرید" in tech_result["سیگنال"] else \
                         "linear-gradient(90deg, #ff4444, #cc0000)" if "فروش" in tech_result["سیگنال"] else \
                         "linear-gradient(90deg, #888888, #444444)"
            
            st.markdown(f"""
            <div style="
                background: {signal_color};
                border-radius: 15px;
                padding: 30px;
                text-align: center;
                color: white;
                margin: 20px 0;
                box-shadow: 0 10px 20px rgba(0,0,0,0.3);
            ">
                <h1 style="margin: 0; font-size: 2.5em;">{tech_result['سیگنال']}</h1>
                <h2 style="margin: 10px 0; font-size: 1.8em;">با اطمینان {tech_result['اطمینان']}%</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # توصیه‌های عملیاتی
            st.markdown("### 📋 توصیه اقدام")
            
            if "خرید قوی" in tech_result["سیگنال"]:
                advice = """
                - **ورود پلکانی**: ۴۰٪ سرمایه در قیمت فعلی، ۳۰٪ در اصلاح ۵٪، ۳۰٪ در اصلاح ۱۰٪
                - **حد ضرر**: ۸-۱۰٪ زیر نقطه ورود اولیه
                - **اهداف سود**: ۱۵٪ (هدف اول)، ۳۰٪ (هدف دوم)، ۵۰٪ (هدف نهایی)
                - **ریسک به ریوارد**: ۱:۳ به بالا
                """
            elif "خرید" in tech_result["سیگنال"]:
                advice = """
                - **ورود آزمایشی**: ۲۰-۳۰٪ سرمایه با حد ضرر تنگ (۵-۷٪)
                - **منتظر تایید**: صبر برای شکست مقاومت کلیدی قبل از افزایش پوزیشن
                - **هدف سود**: ۱۰-۲۰٪
                """
            elif "فروش" in tech_result["سیگنال"]:
                advice = """
                - **خروج از پوزیشن‌های خرید**: فروش ۵۰٪ فوری، ۵۰٪ در پولبک
                - **امکان Short**: فقط برای معامله‌گران حرفه‌ای با حد ضرر ۵٪
                - **انتظار برای سیگنال برگشت**: تشکیل کندل reversal در حمایت
                """
            else:
                advice = """
                - **عدم ورود جدید**: منتظر سیگنال واضح‌تر بمانید
                - **نظارت بر سطوح**: حمایت‌ها و مقاومت‌های کلیدی را زیر نظر داشته باشید
                - **حفظ نقدینگی**: تا زمان تشکیل الگوی مشخص، نقد بمانید
                """
            
            st.markdown(advice)
            
            # هشدارهای مهم
            st.markdown("---")
            st.warning("""
            ### ⚠️ هشدارهای مهم
            1. این تحلیل صرفاً کمک‌کننده است و تضمینی برای سودآوری ندارد.
            2. بازار کریپتو بسیار پرنوسان است — تنها با سرمایه مازاد معامله کنید.
            3. همیشه از حد ضرر (Stop Loss) استفاده نمایید.
            4. نظرات شخصی شما بر اساس این تحلیل نیست.
            """)
        
        progress_bar.progress(100)
        st.success("✅ تحلیل با موفقیت انجام شد!")
        
        # دکمه خروج
        if st.button("🔄 تحلیل ارز دیگری", type="secondary"):
            st.rerun()

# ==================== برنامه اصلی ====================
def main():
    """تابع اصلی اجرای برنامه"""
    
    # مقداردهی اولیه احراز هویت
    Authenticator.initialize()
    
    # بررسی وضعیت ورود
    if not st.session_state.auth["is_authenticated"]:
        # نمایش فرم ورود
        Authenticator.login_form()
        
        # نکات امنیتی در پاورقی
        st.markdown("---")
        st.caption("""
        **نکات امنیتی:**
        - این سیستم برای استفاده شخصی طراحی شده است.
        - رمز عبور به صورت هش شده ذخیره می‌شود.
        - پس از ۳ تلاش ناموفق، دسترسی موقتاً مسدود می‌شود.
        """)
        
    else:
        # نمایش داشبورد اصلی
        main_dashboard()

# ==================== اجرای برنامه ====================
if __name__ == "__main__":
    main()
