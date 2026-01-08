import logging
import requests
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --- AYARLAR ---
# 1. BotFather'dan aldığın Token'ı buraya yapıştır
TOKEN = "8284888584:AAF7yyeWAQ3jOFUJavCqjQE2GzD7Nlx58sg" 

# 2. Render Site Linkini buraya yapıştır (Sonuna /api EKLEMEYİ UNUTMA)
# Örnek: "https://flashodds-pro.onrender.com/api"
API_URL = "https://hananaliz.onrender.com/api" 

# 3. Siteye girmek için VIP Kartı Şifresi (app.py ile AYNI OLMALI)
BOT_API_KEY = "190358"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 **FlashOdds Pro Botuna Hoş Geldin!**\n\n"
        "Komutlar:\n"
        "📅 `/fikstur <Lig Adı>` -> Maçları listeler\n"
        "🧠 `/analiz <Lig> | <Ev> | <Dep>` -> Analiz yapar\n\n"
        "Örnek:\n"
        "`/analiz Premier Lig | Arsenal | Liverpool`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def fikstur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen lig adı girin.\nÖrnek: `/fikstur Premier Lig`", parse_mode='Markdown')
        return

    lig_adi = " ".join(context.args)
    await update.message.reply_text(f"⏳ **{lig_adi}** fikstürü çekiliyor...", parse_mode='Markdown')

    try:
        # VIP KARTI (Header) Hazırla
        headers = {"X-Api-Key": BOT_API_KEY}
        
        # Siteye İstek At (Kartı göstererek)
        response = requests.post(f"{API_URL}/get_fixtures", json={"league": lig_adi}, headers=headers)
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Sunucu Hatası: {response.status_code}")
            return

        data = response.json()
        if not data.get("success"):
            await update.message.reply_text(f"⚠️ Hata: {data.get('msg')}")
            return

        fixtures = data.get("fixtures", [])
        if not fixtures:
            await update.message.reply_text("📭 Bu hafta maç yok.")
            return

        msg = f"📅 **{lig_adi} - Fikstür**\n\n"
        for match in fixtures:
            cmd = f"`/analiz {lig_adi} | {match['home']} | {match['away']}`"
            msg += f"🔸 {match['date']} - {match['home']} vs {match['away']}\nAnaliz 👉 {cmd}\n\n"

        # Mesaj çok uzunsa Telegram hata verebilir, şimdilik 4000 karakter sınırı yokmuş gibi atıyoruz
        if len(msg) > 4000:
            await update.message.reply_text(msg[:4000] + "\n... (Liste çok uzun, kesildi)", parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Bağlantı hatası: {str(e)}")

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    parts = text.split("|")

    if len(parts) != 3:
        await update.message.reply_text(
            "⚠️ Hatalı format!\n"
            "Doğru kullanım: `/analiz Lig | Ev | Dep`\n"
            "Örnek: `/analiz LaLiga | Real Madrid | Barcelona`", 
            parse_mode='Markdown'
        )
        return

    lig = parts[0].strip()
    ev = parts[1].strip()
    dep = parts[2].strip()

    await update.message.reply_text(f"🧠 **{ev} vs {dep}** analiz ediliyor...", parse_mode='Markdown')

    try:
        payload = {
            "league": lig,
            "home": ev,
            "away": dep,
            "odds": {} 
        }
        
        # VIP KARTI (Header) Hazırla
        headers = {"X-Api-Key": BOT_API_KEY}

        # Siteye İstek At (Kartı göstererek)
        response = requests.post(f"{API_URL}/analyze", json=payload, headers=headers)
        data = response.json()

        if "error" in data:
            # Yetki hatası mı yoksa takım mı bulunamadı?
            msg = data['error']
            if response.status_code == 401:
                msg = "🔐 Yetkisiz Giriş! API Key hatalı."
            await update.message.reply_text(f"❌ Hata: {msg}")
            return

        # Rapor Hazırla
        msg = f"⚽ **ANALİZ RAPORU**\n"
        msg += f"🏆 {ev} vs {dep}\n"
        msg += f"----------------------------\n"
        
        if "Tahmini Skor" in data:
            msg += f"🎯 **Skor:** {data['Tahmini Skor']}\n"
            del data["Tahmini Skor"]
        
        msg += f"----------------------------\n"

        # Yüzdeleri sırala (Büyükten küçüğe)
        sorted_items = sorted(data.items(), key=lambda item: item[1]['percent'], reverse=True)

        for key, value in sorted_items:
            icon = "⚪"
            if value['percent'] >= 60: icon = "🔥"
            elif value['percent'] >= 50: icon = "✅"
            elif value['percent'] <= 35: icon = "⚠️"

            msg += f"{icon} **{key}:** %{value['percent']}  _{value['label']}_\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Sunucuya bağlanılamadı.\nHata: {str(e)}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('fikstur', fikstur))
    application.add_handler(CommandHandler('analiz', analiz))
    
    print("🤖 Bot çalışıyor... (Render'a bağlanıyor)")
    application.run_polling()