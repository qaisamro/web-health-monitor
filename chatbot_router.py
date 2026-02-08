from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db import SessionLocal
from models import Monitor, CheckResult
from typing import List
from pydantic import BaseModel
import logging
import os
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Initialize Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
model = None


def init_gemini():
    global model
    if not GOOGLE_API_KEY:
        logger.warning("No GOOGLE_API_KEY found")
        return

    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        # Use gemini-pro which works with v0.8.3
        model = genai.GenerativeModel("gemini-pro")
        logger.info(f"✅ Gemini AI (gemini-pro) initialized successfully")
    except Exception as e:
        logger.error(f"❌ Gemini setup error: {e}")
        model = None


init_gemini()


class ChatRequest(BaseModel):
    message: str


router = APIRouter(prefix="/api/v1/chat", tags=["AI Chatbot"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("")
async def chat_with_uptime_bot(req: ChatRequest, db: Session = Depends(get_db)):
    user_msg = req.message.lower()
    monitors = db.query(Monitor).all()

    # Intent Matching Logic (Rule-based)

    # 1. System Status (حالة النظام)
    if any(
        x in user_msg for x in ["حالة النظام", "status", "system status", "الوضع العام"]
    ):
        up_count = sum(1 for m in monitors if not m.checks or m.checks[-1].is_up)
        down_count = len(monitors) - up_count
        return {
            "reply": f"📊 تقرير حالة النظام:\n• عدد المواقع المراقبة: {len(monitors)}\n• تعمل بنجاح: {up_count} ✅\n• متوقفة: {down_count} ❌"
        }

    # 2. Down Sites (المواقع المتوقفة)
    if any(
        x in user_msg
        for x in ["المواقع المتوقفة", "errors", "down sites", "المشاكل", "issues"]
    ):
        down_sites = []
        for m in monitors:
            last = (
                db.query(CheckResult)
                .filter(CheckResult.monitor_id == m.id)
                .order_by(CheckResult.checked_at.desc())
                .first()
            )
            if last and not last.is_up:
                down_sites.append(f"• {m.name}: {last.error}")

        if down_sites:
            return {
                "reply": "❌ المواقع التي تواجه مشاكل حالياً:\n" + "\n".join(down_sites)
            }
        return {
            "reply": "✅ ممتاز! لا توجد أي مواقع متوقفة حالياً. جميع الأنظمة تعمل بكفاءة."
        }

    # 3. Slowest Sites (أبطأ المواقع)
    if any(
        x in user_msg
        for x in ["أبطأ المواقع", "slow", "performance", "الأداء", "speed"]
    ):
        # Sort by performance score (ascending) -> bad scores first
        scored = [m for m in monitors if m.perf_score is not None]
        scored.sort(key=lambda x: x.perf_score)

        if not scored:
            return {
                "reply": "⚠️ لم يتم جمع بيانات الأداء بعد. يرجى الانتظار قليلاً أو تشغيل فحص جديد."
            }

        reply = "⚡ تحليل الأداء (الأقل كفاءة أولاً):\n"
        for m in scored[:3]:  # Top 3 worst
            reply += f"• {m.name}: تقييم {m.perf_score}/100 (FCP: {m.perf_fcp}s)\n"
        return {"reply": reply}

    # 4. Latest Audit (آخر فحص)
    if any(x in user_msg for x in ["آخر فحص", "latest", "recent", "فحص"]):
        return {
            "reply": "🔍 يمكنك الضغط على زر 'Check Now' في لوحة التحكم لتشغيل فحص فوري لأي موقع. سيظهر لك التقرير فوراً في القائمة."
        }

    # 5. Help / Greeting
    return {
        "reply": "مرحباً بك! 👋 أنا مساعدك الآلي. يمكنك سؤالي عن:\n1️⃣ حالة النظام\n2️⃣ المواقع المتوقفة\n3️⃣ أبطأ المواقع\n\nأو اضغط على الأزرار المقترحة أعلاه!"
    }


def get_detailed_context(db, monitors):
    ctx = "Current Monitor Status:\n"
    for m in monitors:
        last = (
            db.query(CheckResult)
            .filter(CheckResult.monitor_id == m.id)
            .order_by(CheckResult.checked_at.desc())
            .first()
        )
        status = "UP" if not last or last.is_up else "DOWN"

        ctx += f"--- Site: {m.name} ({m.url}) ---\n"
        ctx += f"Status: {status}\n"
        if not (not last or last.is_up):
            ctx += f"Error: {last.error}\n"

        if m.perf_score is not None:
            ctx += f"Performance Score: {m.perf_score}/100\n"
            ctx += f"Core Web Vitals:\n"
            ctx += f"  - FCP (First Contentful Paint): {m.perf_fcp}s\n"
            ctx += f"  - LCP (Largest Contentful Paint): {m.perf_lcp}s\n"
            ctx += f"  - CLS (Cumulative Layout Shift): {m.perf_cls}\n"
            ctx += f"  - TBT (Total Blocking Time): {m.perf_tbt}ms\n"

            ctx += f"Category Scores:\n"
            ctx += f"  - SEO: {m.perf_seo}/100\n"
            ctx += f"  - Accessibility: {m.perf_accessible}/100\n"
            ctx += f"  - Best Practices: {m.perf_best_practices}/100\n"

            if m.perf_details:
                ctx += "Top Issues:\n"
                # Handle list of dicts safely
                try:
                    details = m.perf_details if isinstance(m.perf_details, list) else []
                    for issue in details[:3]:
                        ctx += f"  - {issue.get('title', 'Issue')}: {issue.get('description', '')[:100]}...\n"
                except:
                    pass
        else:
            ctx += "Performance Data: N/A (Audit pending or failed)\n"
        ctx += "\n"
    return ctx


def generate_smart_fallback(msg: str, monitors: List[Monitor], db: Session) -> str:
    msg = msg.lower()

    # Personalized Greeting
    if any(x in msg for x in ["مرحبا", "سلام", "اهلا", "hi", "hello"]):
        return "أهلاً بك! أنا مساعد الأداء الذكي (في وضع الحماية). كيف يمكنني مساعدتك في مواقعك اليوم؟ 🚀"

    # Per-Site Explanation Logic
    target_site = None
    for m in monitors:
        if m.name.lower() in msg or (m.url and m.url.lower() in msg):
            target_site = m
            break

    if target_site:
        last = (
            db.query(CheckResult)
            .filter(CheckResult.monitor_id == target_site.id)
            .order_by(CheckResult.checked_at.desc())
            .first()
        )
        is_up = not last or last.is_up
        status_text = (
            "يعمل بشكل جيد ✅"
            if is_up
            else f"متوقف حالياً ❌ (السبب: {last.error if last else 'غير معروف'})"
        )

        reply = f"بخصوص موقع {target_site.name}:\n"
        reply += f"• الحالة: {status_text}\n"

        if target_site.perf_score:
            reply += f"• درجة الأداء: {target_site.perf_score}/100\n"
            reply += (
                f"• سرعة التحميل (FCP): {target_site.perf_fcp or 'غير متوفر'} ثانية\n"
            )
            if target_site.perf_details:
                reply += "• أهم التوصيات:\n"
                for issue in target_site.perf_details[:2]:
                    reply += f"  - {issue.get('title', '')}\n"
        else:
            reply += "• ملاحظة: لم نقم بإجراء فحص أداء شامل لهذا الموقع بعد. يمكنك الضغط على 'Refresh Audit' لبدء التحليل."

        return reply

    # Global Status
    if any(x in msg for x in ["حالة", "الوضع", "status", "health"]):
        down = [m.name for m in monitors if m.checks and not m.checks[-1].is_up]
        if down:
            return f"يوجد مشكلة في {len(down)} مواقع: ({', '.join(down)}). بقية المواقع تعمل بشكل مستقر. ⚠️"
        return (
            f"جميع المواقع الـ {len(monitors)} التي أراقبها تعمل بشكل ممتاز حالياً! ✅"
        )

    # Default Answer
    return "أنا أرى بياناتك بوضوح، ولكن يبدو أن خدمة Gemini AI لم تفعّل بعد في حساب Google الخاص بك. يمكنك سؤالي عن حالة المواقع أو أداء موقع معين وسأجيبك فوراً! 📊"
