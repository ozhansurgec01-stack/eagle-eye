
import urllib.request
import urllib.error
import json as _json
import time as _time

def _tr_to_float(s):
    s = s.replace("$", "").strip()
    s = s.replace(".", "").replace(",", ".")
    return float(s)

def _fmt_try(v):
    return f"{v:,.2f} \u20ba".replace(",", "X").replace(".", ",").replace("X", ".")

def _fmt_usd(v):
    return f"{v:,.2f} $".replace(",", "X").replace(".", ",").replace("X", ".")

_DEFAULT_DATA = {
    "btc": "77.452,50 $",
    "ons": "4.637,69 $",
    "gram": "7.181,65 \u20ba",
    "ayar22": "6.437,47 \u20ba",
    "ceyrek": "11.540,86 \u20ba",
    "yarim": "23.081,72 \u20ba",
    "tam": "46.022,27 \u20ba"
}

_cache = {"data": None, "ts": 0}
_last_good = {"data": None}
CACHE_TTL = 300  # saniye (5 dakika, rate limit'e karsi)

def _fetch_market_data_live():
    data = dict(_last_good["data"] or _DEFAULT_DATA)

    try:
        req = urllib.request.Request(
            "https://finans.truncgil.com/today.json",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            j = _json.loads(resp.read().decode("utf-8"))

        if "gram-altin" in j:
            data["gram"] = _fmt_try(_tr_to_float(j["gram-altin"]["Satış"]))
        if "22-ayar-bilezik" in j:
            data["ayar22"] = _fmt_try(_tr_to_float(j["22-ayar-bilezik"]["Satış"]))
        if "ceyrek-altin" in j:
            data["ceyrek"] = _fmt_try(_tr_to_float(j["ceyrek-altin"]["Satış"]))
        if "yarim-altin" in j:
            data["yarim"] = _fmt_try(_tr_to_float(j["yarim-altin"]["Satış"]))
        if "tam-altin" in j:
            data["tam"] = _fmt_try(_tr_to_float(j["tam-altin"]["Satış"]))
        if "ons" in j:
            data["ons"] = _fmt_usd(_tr_to_float(j["ons"]["Satış"]))
    except Exception as e:
        print("Truncgil altın verisi alınamadı, önceki/varsayılan kullanılıyor:", e)

    try:
        req2 = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req2, timeout=6) as resp2:
            j2 = _json.loads(resp2.read().decode("utf-8"))
        data["btc"] = _fmt_usd(float(j2["price"]))
    except Exception as e:
        print("Binance BTC verisi alınamadı, önceki/varsayılan kullanılıyor:", e)

    try:
        req3 = urllib.request.Request(
            "https://api.coinpaprika.com/v1/global",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req3, timeout=6) as resp3:
            j3 = _json.loads(resp3.read().decode("utf-8"))
        dominance = j3["bitcoin_dominance_percentage"]
        data["btc_dominance"] = f"{dominance:.1f}%"
    except Exception as e:
        print("CoinPaprika BTC dominans verisi alınamadı, önceki/varsayılan kullanılıyor:", e)

    _last_good["data"] = data
    return data

def get_live_market_data():
    now = _time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    data = _fetch_market_data_live()
    _cache["data"] = data
    _cache["ts"] = now
    return data



import urllib.request
import json as _json


import urllib.request
import json


from datetime import timedelta
from flask import Flask, render_template_string, request, make_response, jsonify
import requests
import feedparser
import os
from datetime import datetime, timedelta, timezone
TR_TZ = timezone(timedelta(hours=3))
import urllib.parse

app = Flask(__name__)
app.secret_key = "eagle_eye_cok_gizli_ve_sabit_anahtar_2026"
app.permanent_session_lifetime = timedelta(days=30)

COUNTER_FILE = "visitor_count.txt"
VISITOR_LOG_FILE = "visitor_log.jsonl"
visited_ips = set()
visitor_ips_history = set()

def get_location_from_ip(ip):
    try:
        if ip in ("127.0.0.1", "localhost") or ip.startswith("192.168.") or ip.startswith("10."):
            return "Yerel Ağ"
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip}?fields=status,country,city,query",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            j = _json.loads(resp.read().decode("utf-8"))
        if j.get("status") == "success":
            city = j.get("city", "")
            country = j.get("country", "")
            return f"{city}, {country}".strip(", ")
        return "Bilinmiyor"
    except Exception:
        return "Bilinmiyor"

def log_visitor(ip, user_agent):
    try:
        location = get_location_from_ip(ip)
        entry = {
            "ip": ip,
            "location": location,
            "user_agent": user_agent,
            "time": datetime.now(TR_TZ).strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(VISITOR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Ziyaretçi loglama hatası:", e)

def get_visitor_log(limit=100):
    entries = []
    if os.path.exists(VISITOR_LOG_FILE):
        try:
            with open(VISITOR_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    entries.append(_json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
    entries.reverse()
    return entries

def get_visitor_count():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 1
    return 1

def increment_visitor_count():
    ua = request.headers.get('User-Agent', '').lower()
    is_bot = any(b in ua for b in ['bot', 'crawl', 'spider', 'render', 'uptime', 'ping', 'axios', 'postman', 'go-http-client', 'head'])
    if is_bot:
        return get_visitor_count()
    count = get_visitor_count() + 1
    try:
        with open(COUNTER_FILE, "w") as f:
            f.write(str(count))
    except:
        pass
    return count

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eagle Eye - Pro TR v8.66</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        :root {
            --bg-body: #0b0f19;
            --bg-header: #0f172a;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --card-bg: #111827;
            --card-border: #1f2937;
            --card-hover: #1f2937;
            --brand-color: #38bdf8;
            --marker-bg: rgba(15, 23, 42, 0.95);
            --marker-border: #ffffff;
            --marker-color: #38bdf8;
        }

        body.light-mode {
            --bg-body: #f1f5f9;
            --bg-header: #0f172a;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --card-bg: #ffffff;
            --card-border: #cbd5e1;
            --card-hover: #f8fafc;
            --brand-color: #0284c7;
            --marker-bg: #ffffff;
            --marker-border: #0284c7;
            --marker-color: #ea580c;
        }

        body { background-color: var(--bg-body); color: var(--text-main); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; overflow: hidden; height: 100vh; display: flex; flex-direction: column; transition: background 0.3s, color 0.3s; }
        .header-bar { background: var(--bg-header); color: #fff; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; z-index: 1000; border-bottom: 1px solid #1e293b; }
        .brand { color: var(--brand-color); font-weight: 800; font-size: 0.9rem; letter-spacing: 0.5px; }
        
        .header-right { display: flex; align-items: center; gap: 6px; }
        .clock-badge { font-size: 0.7rem; background: rgba(15, 23, 42, 0.8); color: #38bdf8; padding: 4px 8px; border-radius: 10px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.2); display: flex; align-items: center; gap: 4px; font-family: monospace; letter-spacing: 0.5px; }
        .visitor-badge { font-size: 0.7rem; background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 4px 8px; border-radius: 10px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.3); display: flex; align-items: center; gap: 4px; }
        
        .mode-btn { font-size: 0.7rem; background: rgba(6, 78, 59, 0.8); color: #34d399; padding: 4px 8px; border-radius: 10px; font-weight: 600; border: 1px solid #059669; cursor: pointer; transition: all 0.2s; }
        body.light-mode .mode-btn { background: #e0f2fe; color: #0369a1; border-color: #0284c7; }

        .map-container { width: 100%; height: 45vh; flex-shrink: 0; border-bottom: 2px solid var(--card-border); position: relative; }
        #map { width: 100%; height: 100%; position: absolute; top: 0; bottom: 0; left: 0; right: 0; background: #010409; }
        
        .leaflet-tile-pane { filter: contrast(1.35) saturate(1.6) brightness(0.94); }
        .neon-map .leaflet-tile-pane {
            filter: invert(95%) hue-rotate(190deg) saturate(320%) brightness(120%) contrast(180%);
        }

        .content-section { flex-grow: 1; overflow-y: auto; padding: 15px; -webkit-overflow-scrolling: touch; background: var(--bg-body); transition: background 0.3s; }
        .panel-title { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; color: var(--brand-color); margin-bottom: 10px; font-weight: 700; }
        
        .card-custom { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 12px; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: background 0.3s, border 0.3s; }
        .item-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid var(--card-border); cursor: pointer; }
        .item-row:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
        .item-row:hover { background-color: var(--card-hover); border-radius: 6px; }
        
        .text-date { color: var(--brand-color); font-size: 0.75rem; font-weight: 700; }
        .text-coord { color: var(--text-main); font-size: 0.8rem; font-weight: 700; text-decoration: none; cursor: pointer; }
        
        .badge-energy { background: #0284c7; color: #fff; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; }
        .weather-badges { display: flex; gap: 6px; align-items: center; }
        .badge-weather { background: #065f46; color: #34d399; font-size: 0.75rem; padding: 3px 8px; border-radius: 6px; font-weight: 700; display: flex; align-items: center; gap: 6px; border: 1px solid #059669; }
        .badge-humidity { background: #0369a1; color: #e0f2fe; font-size: 0.75rem; padding: 3px 8px; border-radius: 6px; font-weight: 700; display: flex; align-items: center; gap: 5px; border: 1px solid #0284c7; }

        @keyframes rotateSun {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        @keyframes floatCloud {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-2px); }
            100% { transform: translateY(0px); }
        }
        @keyframes pulseDrop {
            0% { transform: translateY(0px); opacity: 1; }
            50% { transform: translateY(4px); opacity: 0.3; }
            100% { transform: translateY(0px); opacity: 1; }
        }

        .svg-sun { animation: rotateSun 10s linear infinite; transform-origin: center; transform-box: fill-box; }
        .svg-cloud { animation: floatCloud 3s ease-in-out infinite; }
        .svg-rain-drop { animation: pulseDrop 0.9s ease-in-out infinite; }

        .map-icon-box {
            color: var(--marker-color);
            width: 16px;
            height: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            filter: drop-shadow(0 0 3px rgba(0,0,0,0.6));
        }

        .quake-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 5px solid #3b82f6;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: background 0.3s;
        }
        .quake-card:hover { background-color: var(--card-hover); }
        .quake-info { display: flex; flex-direction: column; gap: 4px; }
        .quake-line { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; font-weight: 700; color: var(--text-main); }
        .quake-mag-badge { background: #ea580c; color: #fff; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; font-weight: 800; display: inline-block; }
        .globe-btn {
            background: linear-gradient(135deg, #0ea5e9, #2563eb);
            border: 2px solid #38bdf8;
            border-radius: 50%;
            width: 38px;
            height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            flex-shrink: 0;
        }

        .alert-card { border-left: 4px solid #ef4444; background: var(--card-bg); border-color: var(--card-border); }
        .badge-alert { background: rgba(239, 68, 68, 0.2); color: #fca5a5; font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; font-weight: 700; border: 1px solid rgba(239, 68, 68, 0.4); }
        .event-link { color: var(--text-main); font-size: 0.85rem; text-decoration: none; font-weight: 600; display: block; margin-top: 3px; }
        .event-link:hover { color: var(--brand-color); }
    </style>

<style>
/* Harita ikonlarini ve animasyonlu gunesleri daha kibar ve şık boyut yapalım */
.leaflet-marker-icon svg, .sun-anim {
}
</style>
</head>

<body>

<div id="market-ticker-bar">
    <div class="ticker-track">

        <div class="ticker-content">
            <span>🪙 BİTCOİN: <strong id="t-btc" class="btc">77.452,50 $</strong></span>
            <span class="dot">•</span>
            <span>📊 BTC DOMİNANS: <strong id="t-btcdom" class="btc">--%</strong></span>
            <span class="dot">•</span>
            <span>🟡 ONS ALTIN: <strong id="t-ons" class="ons">4.603,11 $</strong></span>
            <span class="dot">•</span>
            <span>🥇 GRAM ALTIN: <strong id="t-gram" class="gold">7.181,65 ₺</strong></span>
            <span class="dot">•</span>
            <span>💍 22 AYAR: <strong id="t-ayar22" class="gold">6.437,47 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 ÇEYREK: <strong id="t-ceyrek" class="gold">11.540,86 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 YARIM: <strong id="t-yarim" class="gold">23.081,72 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 TAM ALTIN: <strong id="t-tam" class="gold">46.022,27 ₺</strong></span>
            <span class="sep">|</span>
        </div>

        <div class="ticker-content">
            <span>🪙 BİTCOİN: <strong id="t-btc" class="btc">77.452,50 $</strong></span>
            <span class="dot">•</span>
            <span>📊 BTC DOMİNANS: <strong id="t-btcdom" class="btc">--%</strong></span>
            <span class="dot">•</span>
            <span>🟡 ONS ALTIN: <strong id="t-ons" class="ons">4.603,11 $</strong></span>
            <span class="dot">•</span>
            <span>🥇 GRAM ALTIN: <strong id="t-gram" class="gold">7.181,65 ₺</strong></span>
            <span class="dot">•</span>
            <span>💍 22 AYAR: <strong id="t-ayar22" class="gold">6.437,47 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 ÇEYREK: <strong id="t-ceyrek" class="gold">11.540,86 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 YARIM: <strong id="t-yarim" class="gold">23.081,72 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 TAM ALTIN: <strong id="t-tam" class="gold">46.022,27 ₺</strong></span>
            <span class="sep">|</span>
        </div>

    </div>
</div>

<style>
#market-ticker-bar {
    width:100%;
    height:38px;
    min-height:38px;
    background:#05070d;
    border-bottom:1px solid rgba(56,189,248,.3);
    overflow:hidden;
    position:relative;
    z-index:9999;
    margin:0;
    padding:0;
    box-sizing:border-box;
    font-family:Arial,Helvetica,sans-serif;
}

#market-ticker-bar .ticker-track {
    display:flex;
    width:max-content;
    height:38px;
    align-items:center;
    white-space:nowrap;
    animation:flexTickerScroll 30s linear infinite;
    will-change:transform;
}

#market-ticker-bar .ticker-content {
    display:flex;
    flex-shrink:0;
    align-items:center;
    height:38px;
    white-space:nowrap;
    font-size:13px;
    font-weight:600;
    line-height:38px;
    color:#f1f5f9;
    gap:20px;
    padding-right:20px;
    box-sizing:border-box;
}

#market-ticker-bar strong {
    font-weight:700;
}

#market-ticker-bar .btc {
    color:#38bdf8;
}

#market-ticker-bar .ons {
    color:#4ade80;
}

#market-ticker-bar .gold {
    color:#fbbf24;
}

#market-ticker-bar .dot {
    color:#64748b;
}

#market-ticker-bar .sep {
    color:#38bdf8;
    font-weight:bold;
}

@keyframes flexTickerScroll {
    from { transform:translateX(0); }
    to   { transform:translateX(-50%); }
}

@media(max-width:600px) {
    #market-ticker-bar .ticker-content {
        font-size:12px;
        gap:15px;
        padding-right:15px;
    }
}
</style>



    <div style="width: 100%; background: #05070d; border-bottom: 1px solid rgba(56, 189, 248, 0.3); overflow: hidden; position: relative; z-index: 9999; margin: 0; padding: 0;">
        <div style="display: flex; width: 100%; height: 40px; align-items: center; overflow: hidden;">
            <div style="display: inline-flex; align-items: center; white-space: nowrap; animation: perfectScroll 30s linear infinite; font-size: 13px; font-weight: 600; color: #f1f5f9;">
                <span style="margin: 0 15px;">🪙 BİTCOİN: <strong style="color:#38bdf8;">77.452,50 $</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🟡 ONS ALTIN: <strong style="color:#4ade80;">4.603,11 $</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🥇 GRAM ALTIN: <strong style="color:#fbbf24;">7.181,65 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">💍 22 AYAR: <strong style="color:#fbbf24;">6.437,47 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🪙 ÇEYREK: <strong style="color:#fbbf24;">11.540,86 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🪙 YARIM: <strong style="color:#fbbf24;">23.081,72 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🪙 TAM ALTIN: <strong style="color:#fbbf24;">46.022,27 ₺</strong></span>
                <span style="margin: 0 15px; color:#38bdf8;">&nbsp;|&nbsp;</span>
                <span style="margin: 0 15px;">🪙 BİTCOİN: <strong style="color:#38bdf8;">77.452,50 $</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🟡 ONS ALTIN: <strong style="color:#4ade80;">4.603,11 $</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🥇 GRAM ALTIN: <strong style="color:#fbbf24;">7.181,65 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">💍 22 AYAR: <strong style="color:#fbbf24;">6.437,47 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🪙 ÇEYREK: <strong style="color:#fbbf24;">11.540,86 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🪙 YARIM: <strong style="color:#fbbf24;">23.081,72 ₺</strong></span>
                <span style="margin: 0 10px; color:#64748b;">•</span>
                <span style="margin: 0 15px;">🪙 TAM ALTIN: <strong style="color:#fbbf24;">46.022,27 ₺</strong></span>
            </div>
        </div>
    </div>
    <style>
    @keyframes perfectScroll {
        0% { transform: translateX(0); }
        100% { transform: translateX(-50%); }
    }
    </style>
    

    <div class="header-bar">
        <div class="brand">🦅 EAGLE EYE v8.66</div>
        <div class="header-right">
            <div class="clock-badge" id="liveClock">⏳ --:--:--</div>
            <div class="visitor-badge">
                👁️ {{ visitor_count }}
            </div>
            <div id="modeToggleBtn" class="mode-btn" onclick="toggleTheme()">● LIGHT</div>
        </div>
    </div>

    <div class="map-container">
        <div id="map" class="neon-map"></div>
    </div>

    <div class="content-section">
        <div class="panel-title">🌦️ Başlıca İller Hava Durumu & Nem</div>
        <div class="card-custom">
            {% for w in weather_list %}
            <div class="item-row" onclick="panToLocation({{ w.lat }}, {{ w.lon }}, '<b>🌦️ Hava Durumu: {{ w.city }}</b><br><b>Sıcaklık:</b> {{ w.temp }}°C<br><b>Nem:</b> %{{ w.humidity }}<br><b>Durum:</b> {{ w.desc }}', 6)">
                <div>
                    <div class="text-date">{{ w.city }}</div>
                    <div class="text-coord">{{ w.desc }}</div>
                </div>
                <div class="weather-badges">
                    <span class="badge-humidity">
                        {{ w.humidity_svg | safe }} %{{ w.humidity }}
                    </span>
                    <span class="badge-weather">
                        {{ w.svg_icon | safe }} {{ w.temp }}°C
                    </span>
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="panel-title mt-4">🌍 Son Depremler (Büyüklük >= 3.0)</div>
        <div>
            {% if earthquakes %}
                {% for q in earthquakes %}
                <div class="quake-card" onclick="panToLocation({{ q.lat }}, {{ q.lon }}, '<b>🚨 Deprem</b><br><b>Yer:</b> {{ q.title }}<br><b>Büyüklük:</b> {{ q.mag }}<br><b>Derinlik:</b> {{ q.depth }} km<br><b>Tarih:</b> {{ q.date_str }}', 6)">
                    <div class="quake-info">
                        <div class="quake-line" style="color: var(--text-muted); font-size: 0.75rem;">
                            🕒 {{ q.date_str }} &nbsp;&nbsp; 📍 <span style="color: var(--text-main); font-weight: 800;">{{ q.title }}</span>
                        </div>
                        <div class="quake-line">
                            💥 Şiddet: <span class="quake-mag-badge">{{ q.mag }}</span>
                        </div>
                        <div class="quake-line" style="color: var(--text-muted); font-size: 0.75rem;">
                            📏 Derinlik: {{ q.depth }} km
                        </div>
                    </div>
                    <div class="globe-btn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1 4-10z"></path></svg>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="card-custom" style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 5px;">Son 24 saatte 3.0 ve üzeri deprem bulunmuyor.</div>
            {% endif %}
        </div>

        <div class="panel-title mt-4">✨ Son Düşen Ateş Topları (NASA)</div>
        <div class="card-custom">
            {% for m in meteors %}
            <div class="item-row" onclick="panToLocation({{ m.lat_num }}, {{ m.lon_num }}, '<b>✨ Ateş Topu (NASA)</b><br><b>Tarih:</b> {{ m.date }}<br><b>Enerji:</b> {{ m.energy }} J', 6)">
                <div>
                    <div class="text-date">{{ m.date }}</div>
                    <div class="text-coord">Konum: {{ m.lat }}, {{ m.lon }}</div>
                </div>
                <span class="badge-energy">{{ m.energy }} J</span>
            </div>
            {% endfor %}
        </div>

        <div class="panel-title mt-4">🚨 Türkiye Gündem Akışı</div>
        {% for e in events %}
        <div class="card-custom alert-card">
            <div class="d-flex justify-content-between align-items-center">
                <span class="badge-alert">{{ e.keyword }}</span>
                <span style="font-size: 0.7rem; color: var(--text-muted); font-weight: 600;">{{ e.source }}</span>
            </div>
            <a href="{{ e.link }}" target="_blank" class="event-link">{{ e.title }}</a>
        </div>
        {% endfor %}
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        function updateClock() {
            var now = new Date();
            var hours = String(now.getHours()).padStart(2, '0');
            var minutes = String(now.getMinutes()).padStart(2, '0');
            var seconds = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('liveClock').innerHTML = '🕒 ' + hours + ':' + minutes + ':' + seconds;
        }
        setInterval(updateClock, 1000);
        updateClock();

        var map = L.map('map', {zoomControl: true}).setView([39.0, 35.0], 5);

        var baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19, attribution: '&copy; OpenStreetMap'
        }).addTo(map);

        function toggleTheme() {
            var body = document.body;
            var mapDiv = document.getElementById('map');
            var btn = document.getElementById('modeToggleBtn');
            
            body.classList.toggle('light-mode');
            
            if(body.classList.contains('light-mode')) {
                mapDiv.classList.remove('neon-map');
                btn.innerHTML = "● LIGHT";
            } else {
                mapDiv.classList.add('neon-map');
                btn.innerHTML = "● DARK";
            }
        }

        setTimeout(function(){ map.invalidateSize(); }, 300);

        function panToLocation(lat, lon, popupText, zoomLevel) {
            if(lat && lon && !isNaN(lat) && !isNaN(lon)) {
                map.flyTo([lat, lon], zoomLevel, { duration: 1.5 });
                L.popup().setLatLng([lat, lon]).setContent("<div style='font-family:sans-serif; color:#111;'>" + popupText + "</div>").openOn(map);
            }
        }

        var weatherData = {{ weather_list | safe }};

        L.marker([40.2552, 40.2249], { icon: L.divIcon({ html: '<div style="font-size:11px;font-weight:600;color:#334155;white-space:nowrap;">Bayburt</div>', className: '', iconSize: [60,14], iconAnchor: [30,7] }) }).addTo(map);
        weatherData.forEach(function(w) {
            if(w.lat && w.lon) {
                var customHtml = '<div class="map-icon-box">' + w.map_svg + '</div>';
                var customIcon = L.divIcon({
                    html: customHtml,
                    className: 'custom-weather-marker',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                });

                L.marker([w.lat, w.lon], { icon: customIcon })
                 .addTo(map)
                 .bindPopup("<div style='font-family:sans-serif; color:#111;'><b>🌦️ " + w.city + "</b><br><b>Sıcaklık:</b> " + w.temp + "°C<br><b>Nem:</b> %" + w.humidity + "<br><b>Durum:</b> " + w.desc + "</div>");
            }
        });

        var quakeData = {{ map_quakes | safe }};
        quakeData.forEach(function(q) {
            if(q.lat !== null && q.lon !== null && !isNaN(q.lat) && !isNaN(q.lon)) {
                var colorVal = q.mag >= 4.0 ? '#ef4444' : '#f97316';
                var radiusVal = Math.max(q.mag * 1.2, 3);
                L.circleMarker([q.lat, q.lon], { color: colorVal, fillColor: colorVal, fillOpacity: 0.5, weight: 1.2, radius: radiusVal })
                 .addTo(map)
                 .bindPopup("<div style='font-family:sans-serif; color:#111;'><b>🚨 Deprem</b><br><b>Yer:</b> " + q.title + "<br><b>Büyüklük:</b> " + q.mag + "<br><b>Derinlik:</b> " + q.depth + " km<br><b>Tarih:</b> " + q.date_str + "</div>");
            }
        });

        var meteorData = {{ map_meteors | safe }};
        meteorData.forEach(function(m) {
            if(m.lat !== null && m.lon !== null && !isNaN(m.lat) && !isNaN(m.lon)) {
                L.circleMarker([m.lat, m.lon], { color: '#fb923c', fillColor: '#f97316', fillOpacity: 0.5, weight: 1.2, radius: 4 })
                 .addTo(map)
                 .bindPopup("<div style='font-family:sans-serif; color:#111;'><b>✨ Ateş Topu (NASA)</b><br><b>Tarih:</b> " + m.date + "<br><b>Enerji:</b> " + m.energy + " J</div>");
            }
        });
    </script>

<script>
    window.addEventListener('DOMContentLoaded', () => {
        const clientIp = "{{ real_ip }}";
        const clientLocation = "{{ real_location }}";
        const box = document.createElement('div');
        box.innerHTML = '🦅 Eagle Eye Radar<br><span style="font-size: 11px; color: #94a3b8;">IP: ' + clientIp + ' &bull; ' + clientLocation + '</span>';
        box.style.position = 'fixed';
        box.style.top = '15px';
        box.style.left = '50%';
        box.style.transform = 'translateX(-50%)';
        box.style.background = '#0f172a';
        box.style.color = '#38bdf8';
        box.style.padding = '10px 20px';
        box.style.borderRadius = '20px';
        box.style.zIndex = '999999';
        box.style.fontSize = '13px';
        box.style.fontWeight = 'bold';
        box.style.textAlign = 'center';
        box.style.boxShadow = '0 5px 15px rgba(0,0,0,0.4)';
        box.style.border = '1px solid #38bdf8';
        
        document.body.appendChild(box);
        setTimeout(() => box.remove(), 5000);
    });
</script>








<script>
async function updateMarketPrices() {
    try {
        let response = await fetch('/api/gold-prices');
        if (!response.ok) return;
        let data = await response.json();

        const map = {
            "t-btc": data.btc,
            "t-btcdom": data.btc_dominance,
            "t-ons": data.ons,
            "t-gram": data.gram,
            "t-ayar22": data.ayar22,
            "t-ceyrek": data.ceyrek,
            "t-yarim": data.yarim,
            "t-tam": data.tam
        };

        for (const id in map) {
            document.querySelectorAll('#' + id).forEach(el => {
                if (map[id] !== undefined) el.textContent = map[id];
            });
        }
    } catch (e) {
        console.log("Piyasa verisi alınamadı:", e);
    }
}
updateMarketPrices();
setInterval(updateMarketPrices, 60000);

let lastSeenVisitorTime = null;
async function checkNewVisitor() {
    try {
        let response = await fetch('/api/latest-visitor');
        if (!response.ok) return;
        let data = await response.json();
        if (!data.time) return;

        if (lastSeenVisitorTime === null) {
            lastSeenVisitorTime = data.time;
            return;
        }

        if (data.time !== lastSeenVisitorTime) {
            lastSeenVisitorTime = data.time;
            const box = document.createElement('div');
            box.innerHTML = '👀 Yeni Ziyaretçi<br><span style="font-size: 11px; color: #94a3b8;">' + data.location + '</span>';
            box.style.position = 'fixed';
            box.style.top = '15px';
            box.style.left = '50%';
            box.style.transform = 'translateX(-50%)';
            box.style.background = '#0f172a';
            box.style.color = '#34d399';
            box.style.padding = '10px 20px';
            box.style.borderRadius = '20px';
            box.style.zIndex = '999999';
            box.style.fontSize = '13px';
            box.style.fontWeight = 'bold';
            box.style.textAlign = 'center';
            box.style.boxShadow = '0 5px 15px rgba(0,0,0,0.4)';
            box.style.border = '1px solid #34d399';
            document.body.appendChild(box);
            setTimeout(() => box.remove(), 5000);
        }
    } catch (e) {
        console.log("Ziyaretçi kontrolü alınamadı:", e);
    }
}
checkNewVisitor();
setInterval(checkNewVisitor, 8000);
</script>

</body>
<
<style>
/* EAGLE EYE DARALTMA */
#eagle-eye,
.eagle-eye,
#eagleEye,
.eagleEye {
    transform:scale(0.88);
    transform-origin:left center;
    max-width:88%;
}

#clock,
.clock,
#saat,
.saat,
#counter,
.counter,
#sayac,
.sayac {
    transform:scale(0.88);
    transform-origin:left center;
    max-width:88%;
}

@media(max-width:600px) {
    #eagle-eye,
    .eagle-eye,
    #eagleEye,
    .eagleEye,
    #clock,
    .clock,
    #saat,
    .saat,
    #counter,
    .counter,
    #sayac,
    .sayac {
        transform:scale(0.82);
        max-width:82%;
    }
}
</style>

/html>
"""


@app.route("/api/gold-prices")
def api_gold_prices():
    return jsonify(get_live_market_data())

@app.route("/api/latest-visitor")
def api_latest_visitor():
    entries = get_visitor_log(1)
    if entries:
        e = entries[0]
        return jsonify({"time": e.get("time"), "location": e.get("location"), "ip": e.get("ip")})
    return jsonify({})


_weather_cache = {"data": None, "ts": 0}
WEATHER_CACHE_TTL = 600  # saniye (10 dakika)

def get_weather_data(is_night):
    now = _time.time()
    if _weather_cache["data"] is not None and (now - _weather_cache["ts"]) < WEATHER_CACHE_TTL:
        return _weather_cache["data"]

    weather_list = []
    cities = [
        {"name": "İstanbul", "lat": 41.0082, "lon": 28.9784},
        {"name": "Ankara", "lat": 39.9334, "lon": 32.8597},
        {"name": "İzmir", "lat": 38.4192, "lon": 27.1287},
        {"name": "Antalya", "lat": 36.8969, "lon": 30.7133},
        {"name": "Trabzon", "lat": 41.0015, "lon": 39.7178},
        {"name": "Adana", "lat": 37.0000, "lon": 35.3213},
        {"name": "Diyarbakır", "lat": 37.9144, "lon": 40.2306},
        {"name": "Erzurum", "lat": 39.9043, "lon": 41.2679},
        {"name": "Samsun", "lat": 41.2867, "lon": 36.33},
        {"name": "Van", "lat": 38.4891, "lon": 43.4089},
        {"name": "Bayburt", "lat": 40.2552, "lon": 40.2249},
    ]
    
    tr_translations = {
        "sunny": "Güneşli", "clear": "Açık", "partly cloudy": "Parçalı Bulutlu",
        "cloudy": "Bulutlu", "overcast": "Çok Bulutlu", "mist": "Puslu",
        "patchy rain possible": "Bölgesel Yağmur İhtimali", "patchy rain nearby": "Yakınlarda Bölgesel Yağmur",
        "light rain": "Hafif Yağmurlu", "moderate rain": "Yağmurlu", "heavy rain": "Şiddetli Yağmurlu",
        "thunderstorm": "Fırtınalı", "light rain shower": "Hafif Yağmurlu Sağanak"
    }
    
    sun_svg = '''<svg class="svg-sun" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M6.34 17.66l-1.41 1.41"></path><path d="M19.07 4.93l-1.41 1.41"></path></svg>'''
    moon_svg = '''<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
    cloud_svg = '''<svg class="svg-cloud" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg>'''
    rain_svg = '''<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path class="svg-cloud" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path><line class="svg-rain-drop" x1="8" y1="22" x2="8" y2="24"></line><line class="svg-rain-drop" x1="12" y1="22" x2="12" y2="24" style="animation-delay: 0.3s;"></line><line class="svg-rain-drop" x1="16" y1="22" x2="16" y2="24" style="animation-delay: 0.6s;"></line></svg>'''

    humidity_svg = '''<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path></svg>'''

    try:
        # OpenWeatherMap API Entegrasyonu ile Şehir Hava Durumları Çekme
        owm_key = "F101d05649baa9df699647cef10546ae"
        updated_cities = []
        
        for c in cities:
            try:
                lat = c.get('lat')
                lon = c.get('lon')
                name = c.get('name', 'Bilinmeyen')
                if lat is not None and lon is not None:
                    owm_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={owm_key}&units=metric&lang=tr"
                    r = requests.get(owm_url, timeout=5)
                    if r.status_code == 200:
                        d = r.json()
                        temp = str(round(d['main']['temp']))
                        humidity = str(d['main']['humidity'])
                        wdesc = d['weather'][0]['description'].capitalize()
                        
                        updated_cities.append({
                            "name": name,
                            "lat": lat,
                            "lon": lon,
                            "temp": temp,
                            "humidity": humidity,
                            "desc": wdesc
                        })
            except Exception as e:
                print("OWM Fetch Error:", e)

        # OpenWeatherMap verilerini şablona ve ikonlara uyarlayalım
        for uc in updated_cities:
            desc = uc['desc']
            svg_icon = sun_svg if not is_night else moon_svg
            map_svg = sun_svg if not is_night else moon_svg
            
            desc_lower = desc.lower()
            if "yağmur" in desc_lower or "sağanak" in desc_lower or "rain" in desc_lower:
                svg_icon = rain_svg
                map_svg = rain_svg
            elif "bulut" in desc_lower or "pus" in desc_lower or "kapalı" in desc_lower or "cloud" in desc_lower:
                svg_icon = cloud_svg
                map_svg = cloud_svg

            weather_list.append({
                "city": uc['name'],
                "lat": uc['lat'],
                "lon": uc['lon'],
                "temp": uc['temp'],
                "humidity": uc['humidity'],
                "desc": desc,
                "svg_icon": svg_icon,
                "map_svg": map_svg,
                "humidity_svg": humidity_svg
            })

        if weather_list:
            _weather_cache["data"] = weather_list
        _weather_cache["ts"] = now
        return weather_list

    except Exception as e:
        print("Hava durumu genel hata:", e)
        return weather_list

ZIYARETCI_SIFRE = "eagle2026"  # bunu istediğin gibi değiştirebilirsin

@app.route("/ziyaretciler")
def ziyaretciler():
    girilen_sifre = request.args.get("sifre", "")
    if girilen_sifre != ZIYARETCI_SIFRE:
        return """
        <html><head><meta charset="utf-8"><title>Giriş</title>
        <style>
            body { background:#0b0f1a; color:#e5e7eb; font-family:sans-serif; padding:40px; text-align:center; }
            input { padding:10px; border-radius:8px; border:1px solid #38bdf8; background:#111827; color:#fff; font-size:16px; }
            button { padding:10px 20px; border-radius:8px; border:none; background:#38bdf8; color:#111; font-weight:bold; margin-left:8px; font-size:16px; }
        </style></head><body>
        <h2>🦅 Eagle Eye - Giriş Gerekli</h2>
        <form method="get">
            <input type="password" name="sifre" placeholder="Şifre">
            <button type="submit">Gir</button>
        </form>
        </body></html>
        """
    entries = get_visitor_log(200)
    rows = ""
    for e in entries:
        rows += f"<tr><td style='padding:8px;border-bottom:1px solid #333;'>{e.get('time','')}</td><td style='padding:8px;border-bottom:1px solid #333;'>{e.get('ip','')}</td><td style='padding:8px;border-bottom:1px solid #333;'>{e.get('location','')}</td><td style='padding:8px;border-bottom:1px solid #333;font-size:12px;color:#999;'>{e.get('user_agent','')[:80]}</td></tr>"
    html = f"""
    <html><head><meta charset="utf-8"><title>Ziyaretçi Kayıtları</title>
    <style>
        body {{ background:#0b0f1a; color:#e5e7eb; font-family:sans-serif; padding:20px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ text-align:left; padding:8px; border-bottom:2px solid #38bdf8; color:#38bdf8; }}
    </style></head><body>
    <h2>🦅 Eagle Eye - Ziyaretçi Kayıtları (son {len(entries)})</h2>
    <table><tr><th>Tarih/Saat</th><th>IP</th><th>Konum</th><th>Tarayıcı</th></tr>
    {rows}
    </table>
    </body></html>
    """
    return html

@app.route("/")
def index():
    global visitor_count
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    visitor_count = get_visitor_count()
    
    has_visited = request.cookies.get('eagle_eye_visited')
    ua_check = request.headers.get('User-Agent', '').lower()
    is_bot_check = any(b in ua_check for b in ['bot', 'crawl', 'spider', 'render', 'uptime', 'ping', 'axios', 'postman', 'go-http-client', 'head'])

    real_ip = user_ip.split(',')[0].strip()
    real_location = get_location_from_ip(real_ip)

    if not has_visited:
        visitor_count = increment_visitor_count()
    else:
        visitor_count = get_visitor_count()

    if not is_bot_check:
        log_visitor(real_ip, request.headers.get('User-Agent', ''))

    current_hour = datetime.now(TR_TZ).replace(tzinfo=None).hour
    is_night = current_hour >= 19 or current_hour < 6

    weather_list = get_weather_data(is_night)
    earthquakes = []
    map_quakes = []
    try:
        feed = feedparser.parse("http://www.koeri.boun.edu.tr/scripts/lst0.asp")
        for entry in feed.entries[:15]:
            title = entry.title
            parts = title.split()
            if len(parts) >= 1:
                try:
                    mag = float(parts[0])
                    if mag >= 3.0:
                        earthquakes.append({
                            "title": title, "mag": mag, "depth": "5.0", 
                            "date_str": entry.published if hasattr(entry, 'published') else "Şimdi",
                            "lat": 39.0, "lon": 35.0
                        })
                        map_quakes.append({
                            "title": title, "mag": mag, "depth": "5.0", 
                            "date_str": "Şimdi", "lat": 39.0, "lon": 35.0
                        })
                except:
                    pass
    except:
        pass

    meteors = [
        {"date": "2026-08-23", "lat": "47.7 N", "lon": "119.4 W", "lat_num": 47.7, "lon_num": -119.4, "energy": "1.2e10"},
        {"date": "2026-08-20", "lat": "19.5 S", "lon": "176.2 E", "lat_num": -19.5, "lon_num": 176.2, "energy": "3.4e10"}
    ]
    map_meteors = meteors

    events = []
    try:
        feed = feedparser.parse("https://www.trthaber.com/sondakika.rss")
        for entry in feed.entries[:8]:
            events.append({
                "keyword": "SON DAKİKA",
                "source": "TRT Haber",
                "title": entry.title,
                "link": entry.link
            })
    except:
        events = [
            {"keyword": "BİLGİ", "source": "Sistem", "title": "Gündem akışı şu an yüklenemedi.", "link": "#"}
        ]

    res = make_response(render_template_string(
        HTML_TEMPLATE,
        visitor_count=visitor_count,
        real_ip=real_ip,
        real_location=real_location,
        weather_list=weather_list,
        earthquakes=earthquakes,
        map_quakes=map_quakes,
        meteors=meteors,
        map_meteors=map_meteors,
        events=events
    ))
    if not request.cookies.get('eagle_eye_visited'):
        res.set_cookie('eagle_eye_visited', 'true', max_age=365*24*60*60)
    return res

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
