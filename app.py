import requests
import cloudscraper
import re
import math
import sqlite3
import json
import os
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request

app = Flask(__name__)

# --- AYARLAR ---
app.secret_key = 'gizli_anahtar'
BOT_API_KEY = "190358"
TEAMS_FILE = "teams.json"

TEAMS_DATA = {}
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f: TEAMS_DATA = json.load(f)

# --- HELPER FONKSİYONLAR ---
def get_team_id(url):
    try:
        url = url.strip().rstrip('/')
        match = re.search(r'/(\d+)(?:/)?$', url)
        if match: return int(match.group(1))
        return None
    except: return None

def get_sofascore_stats(team_url, is_home):
    tid = get_team_id(team_url)
    default = {"gf": 1.3, "ga": 1.3, "form": 1.0} # Veri çekemezse bu döner (1-1 sebebi)
    
    print(f"🔍 SORGULANIYOR: ID {tid}") # Konsolda görelim

    if not tid: return default
        
    try:
        # VDS üzerinde Cloudscraper kullanıyoruz
        scraper = cloudscraper.create_scraper()
        url = f"https://api.sofascore.com/api/v1/team/{tid}/performance"
        r = scraper.get(url) 
        
        if r.status_code != 200:
            print(f"❌ ENGEL YENDİ! Kod: {r.status_code}")
            return default
            
        data = r.json()
        matches = data.get("events", [])[:10]
        
        if not matches: return default
            
        gf, ga, pts = 0, 0, 0
        match_count = len(matches)
        
        for e in matches:
            if "homeScore" not in e or "awayScore" not in e: continue
            h_s = e["homeScore"].get("current", 0)
            a_s = e["awayScore"].get("current", 0)
            
            if e["homeTeam"]["id"] == tid: my, opp = h_s, a_s
            else: my, opp = a_s, h_s
            gf += my; ga += opp
            if my > opp: pts += 3
            elif my == opp: pts += 1
            
        print(f"✅ VERİ ÇEKİLDİ! Gol Ort: {gf / match_count:.2f}")
        return {
            "gf": gf / match_count,
            "ga": ga / match_count,
            "form": 0.8 + (pts / match_count / 3) * 0.4
        }
    except Exception as e:
        print(f"❌ HATA: {str(e)}")
        return default

def poisson(xg, g):
    return (math.exp(-xg) * xg**g) / math.factorial(g)

# --- ANALİZ API ---
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    # Güvenlik Kontrolü
    if request.headers.get('X-Api-Key') != BOT_API_KEY:
        return jsonify({"error": "Yetkisiz Erişim"}), 401

    data = request.json
    league = data.get('league')
    home_name = data.get('home')
    away_name = data.get('away')
    
    try:
        home_url = TEAMS_DATA[league][home_name]["url"]
        away_url = TEAMS_DATA[league][away_name]["url"]
    except: return jsonify({"error": "Takım json dosyasında bulunamadı"}), 400
    
    h_stats = get_sofascore_stats(home_url, True)
    a_stats = get_sofascore_stats(away_url, False)
    
    # İkisi de default değer döndüyse (Hala engel varsa)
    if h_stats['gf'] == 1.3 and a_stats['gf'] == 1.3:
         return jsonify({"error": "⚠️ Veri çekilemedi (Sofascore Engeli). Lütfen tekrar dene."}), 500

    hxg = ((h_stats["gf"] + a_stats["ga"]) / 2) * h_stats["form"]
    axg = ((a_stats["gf"] + h_stats["ga"]) / 2) * a_stats["form"]
    
    probs = {"MS 1": 0.0, "Beraberlik": 0.0, "MS 2": 0.0, "2.5 Üst": 0.0, "2.5 Alt": 0.0, "KG Var": 0.0, "KG Yok": 0.0}
    for h in range(7):
        for a in range(7):
            p = poisson(hxg, h) * poisson(axg, a)
            if h > a: probs["MS 1"] += p
            elif h == a: probs["Beraberlik"] += p
            else: probs["MS 2"] += p
            if h+a > 2.5: probs["2.5 Üst"] += p
            else: probs["2.5 Alt"] += p
            if h>0 and a>0: probs["KG Var"] += p
            else: probs["KG Yok"] += p
            
    final_results = {}
    for k, v in probs.items():
        val = max(0.01, min(0.99, v)) * 100
        label = "🔥 BANKO" if val >= 60 else "✅ GÜÇLÜ" if val >= 50 else "⚠️ RİSKLİ"
        final_results[k] = {"percent": round(val, 1), "label": label}
        
    final_results["Tahmini Skor"] = f"{round(hxg)} - {round(axg)}"
    return jsonify(final_results)

# --- EN ALTA BUNU YAPIŞTIR ---
if __name__ == '__main__':
    from waitress import serve
    print("🌍 Site 80 portunda yayına açılıyor...")
    print("👉 Admin Paneli: http://localhost/admin")
    # Port 80 yapıyoruz ki linkin sonuna :5000 yazmakla uğraşma
    serve(app, host='0.0.0.0', port=80)

