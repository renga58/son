import requests
import re
import math
import sqlite3
import json
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)

# --- AYARLAR VE GÜVENLİK ---
app.secret_key = 'bu_cok_gizli_bir_anahtar_flashodds_pro_v4'
BOT_API_KEY = "190358" # Botun VIP Şifresi
DB_NAME = "maclar.db"
TEAMS_FILE = "teams.json"

# --- MASKELENMİŞ HEADERS (Chrome Gibi Görünmesi İçin) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Cache-Control": "max-age=0"
}

LEAGUE_MAP = {
    "Türkiye Süper Lig": 52, "Türkiye 1.Lig": 53, "Premier Lig": 17, "LaLiga": 8,
    "Bundesliga": 35, "Serie A": 23, "Ligue1": 34, "Hollanda Eredivisie": 37,
    "İskoçya Premiership": 36, "Belçika Pro League": 38, "Saudi Pro League": 1055,
    "Yunanistan Super League": 286, "Avustralya Ligi": 153, "LaLiga 2": 54,
    "Serie B": 55, "2. Bundesliga": 44, "Liga Portugal": 238,
    "Romanya SuperLiga": 128, "İsviçre Super League": 77
}

# --- FLASK LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- KULLANICI MODELİ ---
class User(UserMixin):
    def __init__(self, id, username, password, role='user', logo=''):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.logo = logo

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(id=user[0], username=user[1], password=user[2], role=user[3], logo=user[4])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Yetkisiz alan!", "error")
            return redirect(url_for('analyze_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- VERİTABANI ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT, league TEXT, home TEXT, away TEXT, 
                  prediction_market TEXT, prediction_prob REAL, 
                  actual_hg INTEGER, actual_ag INTEGER, 
                  status TEXT DEFAULT 'pending', result INTEGER DEFAULT -1,
                  all_probs TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  role TEXT DEFAULT 'user',
                  logo TEXT DEFAULT '')''')
    
    c.execute("SELECT * FROM users WHERE username = 'kemir'")
    if not c.fetchone():
        hashed_pw = generate_password_hash("2000532694Aa/")
        admin_logo = "https://cdn-icons-png.flaticon.com/512/2825/2825688.png"
        c.execute("INSERT INTO users (username, password, role, logo) VALUES (?, ?, 'admin', ?)", 
                  ('kemir', hashed_pw, admin_logo))
        print("👑 Admin kullanıcısı (kemir) oluşturuldu!")
    conn.commit()
    conn.close()

init_db()
TEAMS_DATA = {}
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f: TEAMS_DATA = json.load(f)

# --- BU İKİ FONKSİYONU ESKİLERİYLE DEĞİŞTİR ---

def get_team_id(url):
    """
    URL içindeki ID'yi Regex ile garanti şekilde alır.
    https://www.sofascore.com/tr/football/team/arsenal/42 -> 42 olarak döner.
    """
    try:
        # 1. Linkin sonundaki boşlukları temizle
        url = url.strip()
        
        # 2. Regex ile linkin sonundaki sayıyı yakala (En sağlam yöntem)
        # Bu kod "/12345" veya "/12345/" şeklindeki her şeyi bulur.
        match = re.search(r'/(\d+)(?:/)?$', url)
        
        if match:
            found_id = int(match.group(1))
            # print(f"🆔 ID BULUNDU: {found_id} (Linkten: {url})") # İstersen bunu açıp loga bakabilirsin
            return found_id
        else:
            print(f"❌ ID BULUNAMADI: {url} linkinde sayı yok.")
            return None
    except Exception as e:
        print(f"❌ ID AYIKLAMA HATASI: {str(e)}")
        return None

def get_sofascore_stats(team_url, is_home):
    tid = get_team_id(team_url)
    
    # Varsayılan değerler (Veri çekemezsek 1-1 çıkmasının sebebi bu)
    default = {"gf": 1.3, "ga": 1.3, "form": 1.0}
    
    if not tid:
        print(f"⚠️ ID YOK: {team_url} için ID bulunamadı, varsayılan dönülüyor.")
        return default
        
    try:
        # API URL'si
        url = f"https://api.sofascore.com/api/v1/team/{tid}/performance"
        
        # Sofascore'u kandıran Chrome Başlıkları
        fake_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.sofascore.com/",
            "Origin": "https://www.sofascore.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        }

        # İsteği at (Timeout 15 saniye)
        r = requests.get(url, headers=fake_headers, timeout=15)
        
        if r.status_code == 403:
            print(f"⛔ ENGEL (403): Sofascore VDS IP'sini engelledi. ID: {tid}")
            return default
            
        if r.status_code != 200:
            print(f"❌ API HATASI: Kod {r.status_code} - ID: {tid}")
            return default
            
        data = r.json()
        matches = data.get("events", [])[:10] # Son 10 maçı al
        
        if not matches:
            print(f"⚠️ MAÇ YOK: ID {tid} için maç verisi gelmedi.")
            return default
            
        # İstatistik Hesaplama
        gf, ga, pts = 0, 0, 0
        match_count = len(matches)
        
        for e in matches:
            if "homeScore" not in e or "awayScore" not in e: continue
            
            h_s = e["homeScore"].get("current", 0)
            a_s = e["awayScore"].get("current", 0)
            
            if e["homeTeam"]["id"] == tid: 
                my, opp = h_s, a_s
            else: 
                my, opp = a_s, h_s
                
            gf += my
            ga += opp
            
            if my > opp: pts += 3
            elif my == opp: pts += 1
            
        stats = {
            "gf": gf / match_count,
            "ga": ga / match_count,
            "form": 0.8 + (pts / match_count / 3) * 0.4
        }
        
        # print(f"✅ İSTATİSTİK ALINDI: ID {tid} -> GF: {stats['gf']:.2f}")
        return stats

    except Exception as e:
        print(f"❌ KRİTİK HATA: {str(e)}")
        return default

def poisson(xg, g):
    return (math.exp(-xg) * xg**g) / math.factorial(g)

def calculate_odds_impact(o, c):
    try:
        o, c = float(o), float(c)
        return ((o-c)/o)*0.5 if o>0 else 0
    except: return 0

# --- SAYFA ROTALARI ---

@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('analyze_page'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('analyze_page'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_data = c.fetchone()
        conn.close()
        if user_data and check_password_hash(user_data[2], password):
            user = User(id=user_data[0], username=user_data[1], password=user_data[2], role=user_data[3], logo=user_data[4])
            login_user(user)
            return redirect(url_for('analyze_page'))
        else: flash('Hatalı giriş!', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role, logo FROM users")
    users = c.fetchall()
    conn.close()
    return render_template('admin.html', users=users, current_user=current_user)

@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def add_user():
    username = request.form['username']
    password = request.form['password']
    logo = request.form.get('logo', '')
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role, logo) VALUES (?, ?, 'user', ?)", (username, hashed_pw, logo))
        conn.commit()
        conn.close()
        flash(f"{username} eklendi.", "success")
    except: flash("Kullanıcı adı zaten var!", "error")
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Kendini silemezsin!", "error")
        return redirect(url_for('admin_panel'))
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    flash("Kullanıcı silindi.", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_user', methods=['POST'])
@login_required
@admin_required
def edit_user():
    user_id = request.form['user_id']
    username = request.form['username']
    password = request.form['password']
    logo = request.form['logo']
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if password.strip():
        hashed_pw = generate_password_hash(password)
        c.execute("UPDATE users SET username=?, password=?, logo=? WHERE id=?", (username, hashed_pw, logo, user_id))
    else:
        c.execute("UPDATE users SET username=?, logo=? WHERE id=?", (username, logo, user_id))
    conn.commit()
    conn.close()
    flash("Güncellendi.", "success")
    return redirect(url_for('admin_panel'))

# --- APP ROUTES ---
@app.route('/analyze')
@login_required
def analyze_page():
    frontend_teams = {}
    for lig, takimlar in TEAMS_DATA.items():
        frontend_teams[lig] = []
        for t_name, t_data in takimlar.items():
            logo = t_data.get("logo", "") if isinstance(t_data, dict) else ""
            frontend_teams[lig].append({"name": t_name, "logo": logo})
    return render_template('analyze.html', teams=frontend_teams, current_user=current_user)

@app.route('/dashboard')
@login_required
def dashboard_page():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE status='pending' ORDER BY id DESC")
    pending = c.fetchall()
    c.execute("SELECT * FROM matches WHERE status='finished' ORDER BY id DESC")
    finished = c.fetchall()
    conn.close()
    return render_template('dashboard.html', pending=pending, finished=finished, current_user=current_user)

# --- API ROTALARI ---

@app.route('/api/get_fixtures', methods=['POST'])
def get_fixtures():
    api_key = request.headers.get('X-Api-Key')
    if api_key != BOT_API_KEY:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "msg": "Yetkisiz Erişim!"}), 401

    data = request.json
    league_id = LEAGUE_MAP.get(data.get('league'))
    if not league_id: return jsonify({"success": False, "msg": "Lig yok"}), 400
    try:
        # Fikstür çekerken de yeni header'ı kullan
        r_s = requests.get(f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/seasons", headers=HEADERS)
        sid = r_s.json()['seasons'][0]['id']
        r_m = requests.get(f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/season/{sid}/events/next/0", headers=HEADERS)
        events = r_m.json().get('events', [])
        fixtures = []
        for e in events:
            d = datetime.fromtimestamp(e.get('startTimestamp', 0)).strftime("%d.%m %H:%M")
            fixtures.append({"home": e['homeTeam']['name'], "away": e['awayTeam']['name'], "date": d})
        return jsonify({"success": True, "fixtures": fixtures})
    except Exception as e: return jsonify({"success": False, "msg": str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    api_key = request.headers.get('X-Api-Key')
    if api_key != BOT_API_KEY:
        if not current_user.is_authenticated:
            return jsonify({"error": "Yetkisiz Erişim!"}), 401

    data = request.json
    league = data.get('league')
    home_name = data.get('home')
    away_name = data.get('away')
    odds = data.get('odds', {})
    
    try:
        home_url = TEAMS_DATA[league][home_name]["url"]
        away_url = TEAMS_DATA[league][away_name]["url"]
    except: return jsonify({"error": "Takım verisi yok"}), 400
    
    h_stats = get_sofascore_stats(home_url, True)
    a_stats = get_sofascore_stats(away_url, False)
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
            
    probs["MS 1"] += calculate_odds_impact(odds.get("ms1_open"), odds.get("ms1_close"))
    probs["Beraberlik"] += calculate_odds_impact(odds.get("msx_open"), odds.get("msx_close"))
    probs["MS 2"] += calculate_odds_impact(odds.get("ms2_open"), odds.get("ms2_close"))
    probs["KG Var"] += calculate_odds_impact(odds.get("kg_var_open"), odds.get("kg_var_close"))
    probs["KG Yok"] += calculate_odds_impact(odds.get("kg_yok_open"), odds.get("kg_yok_close"))
    probs["2.5 Üst"] += calculate_odds_impact(odds.get("ust_open"), odds.get("ust_close"))
    probs["2.5 Alt"] += calculate_odds_impact(odds.get("alt_open"), odds.get("alt_close"))
    
    final_results = {}
    for k, v in probs.items():
        val = max(0.01, min(0.99, v)) * 100
        label = ""
        if val >= 60: label = "🔥 BANKO"
        elif val >= 50: label = "✅ GÜÇLÜ"
        elif val <= 35: label = "⚠️ RİSKLİ"
        final_results[k] = {"percent": round(val, 1), "label": label}
        
    best_market = max(final_results, key=lambda x: final_results[x]["percent"])
    best_prob = final_results[best_market]["percent"]
    all_probs_json = json.dumps(final_results)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO matches (date, league, home, away, prediction_market, prediction_prob, status, result, all_probs) VALUES (?,?,?,?,?,?,'pending', -1, ?)", 
              (datetime.now().strftime("%d.%m %H:%M"), league, home_name, away_name, best_market, best_prob, all_probs_json))
    conn.commit()
    conn.close()
    
    final_results["Tahmini Skor"] = f"{round(hxg)} - {round(axg)}"
    return jsonify(final_results)

@app.route('/api/update_score', methods=['POST'])
@login_required
def update_score():
    data = request.json
    match_id, hg, ag = data.get('id'), int(data.get('hg')), int(data.get('ag'))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT prediction_market FROM matches WHERE id=?", (match_id,))
    row = c.fetchone()
    if not row: return jsonify({"success": False, "msg": "Maç yok"}), 404
    prediction = row[0]
    
    is_win = 0
    if prediction=="MS 1" and hg>ag: is_win=1
    elif prediction=="MS 2" and ag>hg: is_win=1
    elif prediction=="Beraberlik" and hg==ag: is_win=1
    elif prediction=="2.5 Üst" and (hg+ag)>2.5: is_win=1
    elif prediction=="2.5 Alt" and (hg+ag)<2.5: is_win=1
    elif prediction=="KG Var" and (hg>0 and ag>0): is_win=1
    elif prediction=="KG Yok" and (hg==0 or ag==0): is_win=1
    
    c.execute("UPDATE matches SET actual_hg=?, actual_ag=?, status='finished', result=? WHERE id=?", (hg, ag, is_win, match_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_match', methods=['POST'])
@login_required
def delete_match():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM matches WHERE id=?", (request.json.get('id'),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

