import requests, re, math, sqlite3
DB = "data.db"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def team_id_from_url(url):
    return int(re.findall(r"/(\d+)$", url)[0])

def get_team_stats(url):
    tid = team_id_from_url(url)
    r = requests.get(f"https://www.sofascore.com/api/v1/team/{tid}/performance", headers=HEADERS).json()
    matches = r["events"][:10]
    gf=ga=0
    for e in matches:
        if e["homeTeam"]["id"]==tid:
            gf+=e["homeScore"]["current"]
            ga+=e["awayScore"]["current"]
        else:
            gf+=e["awayScore"]["current"]
            ga+=e["homeScore"]["current"]
    return {"gf":gf/len(matches),"ga":ga/len(matches)}

def poisson(xg,g):
    return (math.exp(-xg)*xg**g)/math.factorial(g)

def get_past_stats(home_team, away_team):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""SELECT market,result FROM bets JOIN matches ON bets.match_id=matches.id
                 WHERE played=1 AND (home=? OR away=? OR home=? OR away=?)""",
              (home_team, home_team, away_team, away_team))
    rows=c.fetchall()
    conn.close()
    stats={}
    for market,result in rows:
        if market not in stats: stats[market]={"correct":0,"total":0}
        stats[market]["total"]+=1
        if result: stats[market]["correct"]+=1
    return stats

def analyze_match(home_stats, away_stats, home_team_name, away_team_name):
    hxg=(home_stats["gf"]+away_stats["ga"])/2
    axg=(away_stats["gf"]+home_stats["ga"])/2
    probs={"MS1":0,"X":0,"MS2":0,"O25":0,"BTTS":0}
    for h in range(6):
        for a in range(6):
            p=poisson(hxg,h)*poisson(axg,a)
            if h>a: probs["MS1"]+=p
            elif h==a: probs["X"]+=p
            else: probs["MS2"]+=p
            if h+a>2.5: probs["O25"]+=p
            if h>0 and a>0: probs["BTTS"]+=p
    past=get_past_stats(home_team_name,away_team_name)
    adjusted={}
    for m,base in probs.items():
        adj=base
        if m in past and past[m]["total"]>0:
            accuracy=past[m]["correct"]/past[m]["total"]
            adj=base*0.7 + base*accuracy*0.3
        adjusted[m]=round(adj*100,1)
    return adjusted
