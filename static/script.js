let teams = {}; // Flask gönderdiği JSON
fetch("/").then(r=>r.json()).then(data=>{
    teams=data;
    const leagueSel=document.getElementById("league");
    Object.keys(teams).forEach(l=>{leagueSel.innerHTML+=`<option>${l}</option>`});
    populateTeams();
});
document.getElementById("league").addEventListener("change",populateTeams);
function populateTeams(){
    const l=document.getElementById("league").value;
    const hSel=document.getElementById("home");
    const aSel=document.getElementById("away");
    hSel.innerHTML="";aSel.innerHTML="";
    Object.keys(teams[l]).forEach(t=>{hSel.innerHTML+=`<option>${t}</option>`;aSel.innerHTML+=`<option>${t}</option>`})
}

document.getElementById("analyzeBtn").addEventListener("click",()=>{
    const data={league:document.getElementById("league").value,
                home:document.getElementById("home").value,
                away:document.getElementById("away").value};
    fetch("/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)})
    .then(r=>r.json()).then(res=>{
        let html="<ul>";
        for(const k in res) html+=`<li>${k} : ${res[k]}%</li>`;
        html+="</ul>";
        document.getElementById("analysisResult").innerHTML=html;
    });
});


// Veriyi çek
const teamsDataElement = document.getElementById('teams-data');
const teamsData = JSON.parse(teamsDataElement.textContent);

// Elementler
const leagueSelect = $('#league');
const homeSelect = $('#home');
const awaySelect = $('#away');
const analyzeBtn = document.getElementById("analyzeBtn");
const resultsDiv = document.getElementById("results");

// --- RESİM GÖSTERME FONKSİYONU ---
function formatTeam(state) {
    if (!state.id) return state.text;
    
    // Select2'nin okuduğu ham HTML elementinden veriyi al
    // .attr('data-logo') kullanıyoruz, .data() bazen önbellekte takılır.
    let logoUrl = $(state.element).attr('data-logo'); 
    
    // Logo yoksa sadece metni göster
    if (!logoUrl || logoUrl === "" || logoUrl === "undefined") {
        return state.text;
    }

    // Resmi oluştur
    return $(`<span><img src="${logoUrl}" class="team-logo" /> ${state.text}</span>`);
}

// Select2 Başlat
$(document).ready(function() {
    $('.searchable').select2({
        width: '100%',
        templateResult: formatTeam,
        templateSelection: formatTeam
    });
});

// 1. Ligleri Yükle
for (let leagueName in teamsData) {
    let option = new Option(leagueName, leagueName, false, false);
    leagueSelect.append(option);
}

// 2. Takımları Yükle (GARANTİ YÖNTEM)
function populateTeams() {
    const selectedLeague = leagueSelect.val();
    const teamList = teamsData[selectedLeague];

    // Önce temizle
    homeSelect.empty();
    awaySelect.empty();

    if (teamList) {
        // HTML String biriktirme yöntemi (En hızlı ve hatasız yöntem)
        let homeOptions = "";
        let awayOptions = "";

        teamList.forEach(t => {
            // Burada direkt HTML yazıyoruz. t.logo'nun geldiğinden eminiz.
            // Eğer t.logo boşsa bile boş string gider, kod patlamaz.
            homeOptions += `<option value="${t.name}" data-logo="${t.logo}">${t.name}</option>`;
            awayOptions += `<option value="${t.name}" data-logo="${t.logo}">${t.name}</option>`;
        });

        // Tek seferde ekle
        homeSelect.append(homeOptions);
        awaySelect.append(awayOptions);
        
        // Varsayılan olarak 2. takımı seç
        if(teamList.length > 1) {
            // Değeri ata ve değişikliği tetikle
            awaySelect.val(teamList[1].name).trigger('change');
        }
    }
    
    // Select2'ye "Ben değiştim, güncelle" de
    homeSelect.trigger('change');
    awaySelect.trigger('change');
}

// Olay Dinleyicileri
leagueSelect.on('select2:select', populateTeams);
populateTeams(); // Başlangıçta çalıştır

// 3. ANALİZ İŞLEMİ (Aynı kalıyor)
analyzeBtn.addEventListener("click", async () => {
    // ... (Eski kodun aynısı burası) ...
    const league = leagueSelect.val();
    const home = homeSelect.val();
    const away = awaySelect.val();
    
    const oddsData = {
        ms1_open: document.getElementById('ms1_open').value, ms1_close: document.getElementById('ms1_close').value,
        msx_open: document.getElementById('msx_open').value, msx_close: document.getElementById('msx_close').value,
        ms2_open: document.getElementById('ms2_open').value, ms2_close: document.getElementById('ms2_close').value,
        kg_var_open: document.getElementById('kg_var_open').value, kg_var_close: document.getElementById('kg_var_close').value,
        kg_yok_open: document.getElementById('kg_yok_open').value, kg_yok_close: document.getElementById('kg_yok_close').value,
        ust_open: document.getElementById('ust_open').value, ust_close: document.getElementById('ust_close').value,
        alt_open: document.getElementById('alt_open').value, alt_close: document.getElementById('alt_close').value,
    };

    analyzeBtn.disabled = true;
    analyzeBtn.innerText = "⏳ Veriler Çekiliyor...";
    resultsDiv.style.display = "none";

    try {
        const resp = await fetch("/api/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ league, home, away, odds: oddsData })
        });

        const data = await resp.json();
        
        let html = "<h3>🔥 Analiz Raporu</h3>";
        if(data["Tahmini Skor"]) {
            html += `<div style="text-align:center; font-size:24px; color:#f9e2af; margin-bottom:20px; border:1px solid #fab387; padding:10px; border-radius:8px;">
                        🏆 Tahmini Skor: ${data["Tahmini Skor"]}
                     </div>`;
            delete data["Tahmini Skor"];
        }

        for (const [key, value] of Object.entries(data)) {
            html += `
                <div style="margin-bottom: 12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:bold;">${key}</span>
                        <span>
                            <span style="font-size:12px; font-weight:bold; color:#f9e2af; margin-right:5px;">${value.label}</span>
                            %${value.percent}
                        </span>
                    </div>
                    <div style="background:#45475a; height:10px; border-radius:5px; margin-top:4px;">
                        <div style="background:${value.percent > 60 ? '#a6e3a1' : '#89b4fa'}; width:${value.percent}%; height:100%; border-radius:5px;"></div>
                    </div>
                </div>
            `;
        }
        resultsDiv.innerHTML = html;
        resultsDiv.style.display = "block";

    } catch (err) {
        alert("Hata: " + err);
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.innerText = "🧠 DETAYLI ANALİZ ET";
    }
});