import logging
import requests
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- AYARLAR ---
TOKEN = "8284888584:AAF7yyeWAQ3jOFUJavCqjQE2GzD7Nlx58sg"  # <--- BURAYI DOLDUR!
API_URL = "http://127.0.0.1:5000/api"      # Flask uygulamanın adresi

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

    # Kullanıcının yazdığı lig adını birleştir (örn: Premier Lig)
    lig_adi = " ".join(context.args)
    
    await update.message.reply_text(f"⏳ **{lig_adi}** fikstürü çekiliyor...", parse_mode='Markdown')

    try:
        # Flask API'ye istek at
        response = requests.post(f"{API_URL}/get_fixtures", json={"league": lig_adi})
        
        if response.status_code != 200:
            await update.message.reply_text("❌ Sunucu hatası veya lig bulunamadı.")
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
            # Kolay kopyalama için komut hazırla
            cmd = f"`/analiz {lig_adi} | {match['home']} | {match['away']}`"
            msg += f"🔸 {match['date']} - {match['home']} vs {match['away']}\nAnaliz için tıkla 👉 {cmd}\n\n"

        # Mesaj çok uzunsa bölmek gerekebilir ama şimdilik tek parça atalım
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Bağlantı hatası: {str(e)}")

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Gelen mesajı '|' işaretine göre böl
    text = " ".join(context.args)
    parts = text.split("|")

    if len(parts) != 3:
        await update.message.reply_text(
            "⚠️ Hatalı format!\n"
            "Doğru kullanım: `/analiz Lig Adı | Ev Sahibi | Deplasman`\n"
            "Not: Araya '|' (dik çizgi) koymayı unutma.", 
            parse_mode='Markdown'
        )
        return

    lig = parts[0].strip()
    ev = parts[1].strip()
    dep = parts[2].strip()

    # KONTROL 1: Bakalım Telegram mesajı bota ulaşıyor mu?
    print(f"Telegram'dan istek geldi: Lig={lig}, Ev={ev}, Dep={dep}")

    await update.message.reply_text(f"🧠 **{ev} vs {dep}** analiz ediliyor... Lütfen bekle.", parse_mode='Markdown')

    try:
        # Flask API'ye istek at
        payload = {
            "league": lig,
            "home": ev,
            "away": dep,
            "odds": {} 
        }
        
        response = requests.post(f"{API_URL}/analyze", json=payload)

        # >>>> SENİN SORDUĞUN SATIR BURAYA GELECEK <<<<
        print(f"API Cevabı: {response.status_code} - {response.text}")
        # >>>> BURADA BİTİYOR <<<<

        data = response.json()

        if "error" in data:
            await update.message.reply_text(f"❌ Hata: {data['error']}\nTakım ismini kontrol et.")
            return

        # Rapor Hazırla
        msg = f"⚽ **ANALİZ RAPORU**\n"
        msg += f"🏆 {ev} vs {dep}\n"
        msg += f"----------------------------\n"
        
        if "Tahmini Skor" in data:
            msg += f"🎯 **Tahmini Skor:** {data['Tahmini Skor']}\n"
            del data["Tahmini Skor"]
        
        msg += f"----------------------------\n"

        # En yüksek ihtimali bulmak için sıralama
        sorted_items = sorted(data.items(), key=lambda item: item[1]['percent'], reverse=True)

        for key, value in sorted_items:
            icon = "⚪"
            if value['percent'] >= 60: icon = "🔥"
            elif value['percent'] >= 50: icon = "✅"
            elif value['percent'] <= 35: icon = "⚠️"

            msg += f"{icon} **{key}:** %{value['percent']}  _{value['label']}_\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        print(f"HATA OLUŞTU: {e}") # Konsola hatayı bas
        await update.message.reply_text(f"❌ Sunucuya bağlanılamadı. `app.py` çalışıyor mu?\nHata: {str(e)}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('fikstur', fikstur))
    application.add_handler(CommandHandler('analiz', analiz))
    
    print("🤖 Bot çalışıyor...")
    application.run_polling()