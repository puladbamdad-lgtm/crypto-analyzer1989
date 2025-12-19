# crypto_analyst.py
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import requests
import numpy as np
from datetime import datetime, timedelta
import ta  # کتابخانه تحلیل تکنیکال

# ----------------------------
# 1. پیکربندی اولیه صفحه
# ----------------------------
st.set_page_config(page_title="تحلیلگر کریپتو", layout="wide")
st.title("🚀 سیستم تحلیل و سیگنال‌دهی ارزهای دیجیتال")

# نوار کناری برای ورودی کاربر
st.sidebar.header("فیلترهای تحلیل")
coin_symbol = st.sidebar.text_input("نماد ارز (مثال: bitcoin)", "bitcoin").lower()
vs_currency = st.sidebar.selectbox("واحد پول", ["usd", "eur", "jpy"])
analysis_days = st.sidebar.slider("بازه تحلیل (روز)", 7, 90, 30)

# ----------------------------
# 2. ماژول دریافت داده (Data Fetcher)
# ----------------------------
class DataFetcher:
    @staticmethod
    def get_coin_data(coin_id, vs_currency, days):
        """دریافت داده‌های قیمت از CoinGecko API"""
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {'vs_currency': vs_currency, 'days': days, 'interval': 'daily'}
            response = requests.get(url, timeout=10)
            data = response.json()
            
            # تبدیل به DataFrame
            prices = data.get('prices', [])
            df = pd.DataFrame(prices, columns=['timestamp', 'price'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # محاسبه حجم (اگر در پاسخ موجود باشد)
            if 'total_volumes' in data:
                volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
                df['volume'] = volumes['volume'].values
            
            return df
        except Exception as e:
            st.error(f"خطا در دریافت داده: {e}")
            return None
    
    @staticmethod
    def get_fear_and_greed_index():
        """دریافت شاخص ترس و طمع"""
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=5)
            data = response.json()
            if data.get('data'):
                return int(data['data'][0]['value'])
        except:
            pass
        return None

# ----------------------------
# 3. ماژول تحلیل تکنیکال
# ----------------------------
class TechnicalAnalyzer:
    @staticmethod
    def analyze(df):
        if df is None or len(df) < 20:
            return {"سیگنال": "داده ناکافی", "اطمینان": 0}
        
        # محاسبه اندیکاتورها
        df['rsi'] = ta.momentum.RSIIndicator(df['price'], window=14).rsi()
        df['sma_20'] = ta.trend.SMAIndicator(df['price'], window=20).sma_indicator()
        df['sma_50'] = ta.trend.SMAIndicator(df['price'], window=50).sma_indicator()
        
        # تحلیل
        latest_rsi = df['rsi'].iloc[-1]
        price = df['price'].iloc[-1]
        sma_20 = df['sma_20'].iloc[-1]
        
        signal = "خنثی"
        confidence = 0
        
        if pd.notna(latest_rsi):
            if latest_rsi < 30 and price > sma_20:
                signal = "خرید (اشباع فروش)"
                confidence = 70
            elif latest_rsi > 70 and price < sma_20:
                signal = "فروش (اشباع خرید)"
                confidence = 65
            elif price > sma_20:
                signal = "روند صعودی"
                confidence = 60
            else:
                signal = "روند نزولی"
                confidence = 55
        
        return {
            "سیگنال": signal,
            "اطمینان": confidence,
            "RSI": round(latest_rsi, 2),
            "قیمت/میانگین‌متحرک": f"{price:.2f}/{sma_20:.2f}"
        }

# ----------------------------
# 4. ماژول تحلیل احساسات و درون زنجیره
# ----------------------------
class SentimentOnChainAnalyzer:
    @staticmethod
    def analyze(coin_id):
        results = {}
        
        # شاخص ترس و طمع
        fgi = DataFetcher.get_fear_and_greed_index()
        results['شاخص_ترس_و_طمع'] = fgi
        
        # تحلیل ساده بر اساس شاخص
        if fgi:
            if fgi <= 25:
                results['سیگنال_احساسات'] = "ترس شدید (فرصت خرید احتمالی)"
                results['امتیاز'] = 75
            elif fgi >= 75:
                results['سیگنال_احساسات'] = "طمع شدید (احتیاط در خرید)"
                results['امتیاز'] = 30
            else:
                results['سیگنال_احساسات'] = "خنثی"
                results['امتیاز'] = 50
        
        return results

# ----------------------------
# 5. موتور تصمیم‌گیری نهایی
# ----------------------------
class SignalEngine:
    @staticmethod
    def generate_final_signal(tech_analysis, sentiment_analysis):
        """ترکیب تحلیل‌ها و تولید سیگنال نهایی"""
        
        tech_signal = tech_analysis.get("سیگنال", "خنثی")
        tech_conf = tech_analysis.get("اطمینان", 0)
        sent_score = sentiment_analysis.get("امتیاز", 50)
        
        # منطق ترکیب (با وزن بیشتر برای تحلیل تکنیکال)
        final_score = (tech_conf * 0.7) + (sent_score * 0.3)
        
        if "خرید" in tech_signal and sent_score > 60:
            return {
                "سیگنال_نهایی": "📈 خرید با اولویت بالا",
                "امتیاز": final_score,
                "توضیحات": "همگرایی مثبت در تحلیل تکنیکال و احساسات"
            }
        elif "فروش" in tech_signal and sent_score < 40:
            return {
                "سیگنال_نهایی": "📉 فروش / احتیاط",
                "امتیاز": final_score,
                "توضیحات": "هشدار نزولی در هر دو تحلیل"
            }
        else:
            return {
                "سیگنال_نهایی": "⚖️ نظارت (بدون اقدام قوی)",
                "امتیاز": final_score,
                "توضیحات": "عدم همگرایی کافی در سیگنال‌ها"
            }

# ----------------------------
# 6. رابط کاربری و اجرای اصلی
# ----------------------------
def main():
    # ایجاد نمونه‌ها
    fetcher = DataFetcher()
    tech_analyzer = TechnicalAnalyzer()
    sent_analyzer = SentimentOnChainAnalyzer()
    engine = SignalEngine()
    
    # نمایش وضعیت دریافت داده
    with st.spinner('در حال دریافت و تحلیل داده‌ها...'):
        # دریافت داده
        df = fetcher.get_coin_data(coin_symbol, vs_currency, analysis_days)
        
        if df is not None and not df.empty:
            # تحلیل‌ها
            tech_result = tech_analyzer.analyze(df)
            sent_result = sent_analyzer.analyze(coin_symbol)
            final_signal = engine.generate_final_signal(tech_result, sent_result)
            
            # ایجاد تب‌های مختلف برای نمایش نتایج
            tab1, tab2, tab3, tab4 = st.tabs(["📊 نمودارها", "🔍 تحلیل تکنیکال", "😊 احساسات بازار", "🎯 سیگنال نهایی"])
            
            with tab1:
                st.subheader("نمودار قیمت و حجم")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df['price'], mode='lines', name='قیمت', line=dict(color='gold')))
                fig.update_layout(height=500, xaxis_title="تاریخ", yaxis_title=f"قیمت ({vs_currency.upper()})")
                st.plotly_chart(fig, use_container_width=True)
                
                # نمایش جدول داده
                with st.expander("مشاهده داده‌های خام"):
                    st.dataframe(df.tail(10))
            
            with tab2:
                st.subheader("نتایج تحلیل تکنیکال")
                col1, col2, col3 = st.columns(3)
                col1.metric("سیگنال", tech_result["سیگنال"])
                col2.metric("درصد اطمینان", f"{tech_result['اطمینان']}%")
                col3.metric("RSI", tech_result["RSI"])
                
                # توضیحات RSI
                st.info("""
                **راهنمای RSI:**
                - زیر ۳۰: منطقه اشباع فروش (امکان رشد)
                - بالای ۷۰: منطقه اشباع خرید (احتیاط)
                - بین ۳۰ تا ۷۰: منطقه تعادل
                """)
            
            with tab3:
                st.subheader("تحلیل احساسات و درون زنجیره")
                if sent_result.get('شاخص_ترس_و_طمع'):
                    fgi = sent_result['شاخص_ترس_و_طمع']
                    st.metric("شاخص ترس و طمع بازار", f"{fgi}/100")
                    
                    # نمایش وضعیت شاخص
                    if fgi <= 25:
                        st.error("😨 ترس شدید حاکم است")
                    elif fgi >= 75:
                        st.warning("😊 طمع شدید حاکم است")
                    else:
                        st.success("😐 احساسات خنثی")
                    
                    st.caption(sent_result.get('سیگنال_احساسات', ''))
            
            with tab4:
                st.subheader("سیگنال ترکیبی نهایی")
                
                # نمایش برجسته سیگنال
                signal_color = "green" if "خرید" in final_signal["سیگنال_نهایی"] else "red" if "فروش" in final_signal["سیگنال_نهایی"] else "gray"
                st.markdown(f"""
                <div style="text-align: center; padding: 20px; border-radius: 10px; background-color: {signal_color}20; border: 2px solid {signal_color};">
                    <h1 style="color: {signal_color};">{final_signal["سیگنال_نهایی"]}</h1>
                    <h3>امتیاز اعتبار: {final_signal["امتیاز"]:.1f}/100</h3>
                    <p>{final_signal["توضیحات"]}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # توصیه اقدام
                st.markdown("---")
                st.subheader("📋 توصیه اقدام")
                advice_map = {
                    "خرید": "• ورود پلکانی با حجم مناسب\n• تعیین حد ضرر ۵-۸٪\n• هدف‌گذاری سود بر اساس مقاومت‌های بعدی",
                    "فروش": "• خروج از پوزیشن‌های خرید\n• امکان شرط‌گذاری بر کاهش قیمت\n• انتظار برای اصلاح قیمتی",
                    "نظارت": "• عدم ورود جدید\n• نظارت بر سطوح کلیدی حمایت/مقاومت\n• انتظار برای تشکیل الگوی واضح‌تر"
                }
                
                for key, advice in advice_map.items():
                    if key in final_signal["سیگنال_نهایی"]:
                        st.text(advice)
                        break
                
                # هشدارهای مهم
                st.markdown("---")
                st.warning("""
                **⚠️ هشدارهای مهم:**
                1. این تحلیل صرفاً کمک‌کننده است و تضمینی بر سودآوری ندارد.
                2. همیشه از مدیریت سرمایه (حد ضرر) استفاده کنید.
                3. بازار کریپتو بسیار پرنوسان است — فقط با سرمایه مازاد معامله کنید.
                """)
        
        else:
            st.error("⚠️ امکان دریافت داده برای این ارز وجود ندارد. لطفاً از صحت نماد اطمینان حاصل کنید.")
            st.info("نمادها باید به فرمت API کوین‌گکو باشند (مثال: bitcoin, ethereum, solana)")

# ----------------------------
# ۷. اجرای برنامه
# ----------------------------
if __name__ == "__main__":
    main()