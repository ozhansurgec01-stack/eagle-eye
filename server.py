from flask import Flask, render_template_string, request
import requests
import feedparser
import os
from datetime import datetime
import urllib.parse

app = Flask(__name__)

COUNTER_FILE = "visitor_count.txt"
visited_ips = set()
visitor_ips_history = set()

def get_visitor_count():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 1
    return 1

def increment_visitor_count():
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
    <title>Eagle Eye - Pro TR v8.64</title>
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
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid #ffffff;
            border-radius: 50%;
            width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 6px rgba(255, 255, 255, 0.5);
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
</head>
<body>

    <div class="header-bar">
        <div class="brand">🦅 EAGLE EYE v8.64</div>
        <div class="header-right">
            <div class="clock-badge" id="liveClock">⏳ --:--:--</div>
            <div class="visitor-badge">
                👁️ {{ visitor_count }}
            </div>
            <div id="modeToggleBtn" class="mode-btn" onclick="toggleTheme()">● DARK</div>
        </div>
    </div>

    <div class="map-container">
        <div id="map" class="neon-map"></div>
    </div>

    <div class="content-section">
        <div class="panel-title">🌦️ Başlıca İller Hava Durumu & Nem</div>
        <div class="card-custom">
            {% for w in weather_list %}
            <div class="item-row" onclick="panToLocation({{ w.lat }}, {{ w.lon }}, '<b>🌦️ Hava Durumu: {{ w.city }}</b><br><b>Sıcaklık:</b> {{ w.temp }}°C<br><b>Nem:</b> %{{ w.humidity }}<br><b>Durum:</b> {{ w.desc }}', 8)">
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
                <div class="quake-card" onclick="panToLocation({{ q.lat }}, {{ q.lon }}, '<b>🚨 Deprem</b><br><b>Yer:</b> {{ q.title }}<br><b>Büyüklük:</b> {{ q.mag }}<br><b>Derinlik:</b> {{ q.depth }} km<br><b>Tarih:</b> {{ q.date_str }}', 8)">
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
            <div class="item-row" onclick="panToLocation({{ m.lat_num }}, {{ m.lon_num }}, '<b>✨ Ateş Topu (NASA)</b><br><b>Tarih:</b> {{ m.date }}<br><b>Enerji:</b> {{ m.energy }} J', 2)">
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
        weatherData.forEach(function(w) {
            if(w.lat && w.lon) {
                var customHtml = '<div class="map-icon-box">' + w.map_svg + '</div>';
                var customIcon = L.divIcon({
                    html: customHtml,
                    className: 'custom-weather-marker',
                    iconSize: [18, 18],
                    iconAnchor: [9, 9]
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
</body>
</html>
"""

@app.route("/")
def index():
    global visitor_count
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    visitor_count = get_visitor_count()
    
    if user_ip not in visited_ips:
        visited_ips.add(user_ip)
        if user_ip not in visitor_ips_history:
            visitor_ips_history.add(user_ip)
            if visitor_count == 1 and len(visitor_ips_history) == 1:
                pass
            else:
                visitor_count = increment_visitor_count()

    current_hour = datetime.now().hour
    is_night = current_hour >= 19 or current_hour < 6

    weather_list = []
    cities = [
        {"name": "İstanbul", "lat": 41.0082, "lon": 28.9784},
        {"name": "Ankara", "lat": 39.9334, "lon": 32.8597},
        {"name": "İzmir", "lat": 38.4192, "lon": 27.1287},
        {"name": "Antalya", "lat": 36.8969, "lon": 30.7133},
        {"name": "Trabzon", "lat": 41.0027, "lon": 39.7168},
        {"name": "Adana", "lat": 37.0000, "lon": 35.3213},
        {"name": "Diyarbakır", "lat": 37.9144, "lon": 40.2306},
        {"name": "Erzurum", "lat": 39.9043, "lon": 41.2679},
        {"name": "Samsun", "lat": 41.2867, "lon": 36.33},
        {"name": "Van", "lat": 38.4891, "lon": 43.4089}
    ]
    
    tr_translations = {
        "sunny": "Güneşli", "clear": "Açık", "partly cloudy": "Parçalı Bulutlu",
        "cloudy": "Bulutlu", "overcast": "Çok Bulutlu", "mist": "Puslu",
        "patchy rain possible": "Bölgesel Yağmur İhtimali", "patchy rain nearby": "Yakınlarda Bölgesel Yağmur",
        "light rain": "Hafif Yağmurlu", "moderate rain": "Yağmurlu", "heavy rain": "Şiddetli Yağmurlu",
        "thunderstorm": "Fırtınalı", "light rain shower": "Hafif Yağmurlu Sağanak"
    }
    
    sun_svg = '''<svg class="svg-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M6.34 17.66l-1.41 1.41"></path><path d="M19.07 4.93l-1.41 1.41"></path></svg>'''
    moon_svg = '''<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
    
    cloud_svg = '''<svg class="svg-cloud" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg>'''
    rain_svg = '''<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path class="svg-cloud" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path><line class="svg-rain-drop" x1="8" y1="22" x2="8" y2="24" stroke="#ffffff"></line><line class="svg-rain-drop" x1="12" y1="22" x2="12" y2="24" stroke="#ffffff" style="animation-delay: 0.3s;"></line><line class="svg-rain-drop" x1="16" y1="22" x2="16" y2="24" stroke="#ffffff" style="animation-delay: 0.6s;"></line></svg>'''
    
    map_sun_svg = '''<svg class="svg-sun" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#facc15" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M6.34 17.66l-1.41 1.41"></path><path d="M19.07 4.93l-1.41 1.41"></path></svg>'''
    map_moon_svg = '''<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
    
    map_cloud_svg = '''<svg class="svg-cloud" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg>'''
    map_rain_svg = '''<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path class="svg-cloud" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path><line class="svg-rain-drop" x1="8" y1="22" x2="8" y2="24" stroke="#ffffff"></line><line class="svg-rain-drop" x1="12" y1="22" x2="12" y2="24" stroke="#ffffff" style="animation-delay: 0.3s;"></line><line class="svg-rain-drop" x1="16" y1="22" x2="16" y2="24" stroke="#ffffff" style="animation-delay: 0.6s;"></line></svg>'''

    for c in cities:
        try:
            encoded_city = urllib.parse.quote(c['name'])
            r = requests.get(f"https://wttr.in/{encoded_city}?format=j1", timeout=3).json()
            current = r["current_condition"][0]
            temp = current["temp_C"]
            humidity = current["humidity"]
            raw_desc = current["weatherDesc"][0]["value"]
            
            desc_lower_key = raw_desc.strip().lower()
            desc = tr_translations.get(desc_lower_key, raw_desc)
            
            d_lower = desc.lower()
            if "yağmur" in d_lower or "rain" in d_lower or "fırtına" in d_lower or "sağanak" in d_lower:
                svg_icon, map_svg = rain_svg, map_rain_svg
            elif "bulut" in d_lower or "cloud" in d_lower or "pus" in d_lower or "overcast" in d_lower:
                svg_icon, map_svg = cloud_svg, map_cloud_svg
            else:
                if is_night:
                    svg_icon, map_svg = moon_svg, map_moon_svg
                    if "açık" in desc.lower() or "güneşli" in desc.lower():
                        desc = "Açık (Gece)"
                else:
                    svg_icon, map_svg = sun_svg, map_sun_svg
            
            weather_list.append({
                "city": c["name"], "temp": temp, "humidity": humidity, "desc": desc,
                "svg_icon": svg_icon, "map_svg": map_svg, "lat": c["lat"], "lon": c["lon"]
            })
        except:
            default_icon = moon_svg if is_night else sun_svg
            default_map_icon = map_moon_svg if is_night else map_sun_svg
            weather_list.append({
                "city": c["name"], "temp": "--", "humidity": "--", "desc": "Güncel",
                "svg_icon": default_icon, "map_svg": default_map_icon, "lat": c["lat"], "lon": c["lon"]
            })

    meteors = []
    map_meteors = []
    try:
        url = "https://ssd-api.jpl.nasa.gov/fireball.api"
        res = requests.get(url).json()
        fields = res.get("fields", [])
        rows = res.get("data", [])
        for row in rows[:3]:
            lat_val = row[fields.index("lat")] if "lat" in fields and row[fields.index("lat")] else None
            lon_val = row[fields.index("lon")] if "lon" in fields and row[fields.index("lon")] else None
            lat_dir = row[fields.index("lat-dir")] if "lat-dir" in fields and row[fields.index("lat-dir")] else ""
            lon_dir = row[fields.index("lon-dir")] if "lon-dir" in fields and row[fields.index("lon-dir")] else ""
            
            lat_num = float(lat_val) if lat_val else 0
            if lat_dir == 'S': lat_num = -lat_num
            lon_num = float(lon_val) if lon_val else 0
            if lon_dir == 'W': lon_num = -lon_num

            date_str = row[fields.index("date")]
            energy_val = row[fields.index("energy")] if "energy" in fields else "?"

            meteors.append({"date": date_str, "lat": f"{lat_val} {lat_dir}", "lon": f"{lon_val} {lon_dir}", "lat_num": lat_num, "lon_num": lon_num, "energy": energy_val})
            if lat_val and lon_val:
                map_meteors.append({"lat": lat_num, "lon": lon_num, "date": date_str, "energy": energy_val})
    except:
        pass

    earthquakes = []
    map_quakes = []
    try:
        q_url = "https://api.orhanaydogdu.com.tr/deprem/kandilli/live"
        q_res = requests.get(q_url, timeout=5).json()
        if q_res.get("status"):
            for q in q_res.get("result", []):
                mag = float(q.get("mag", 0))
                if mag >= 3.0:
                    title = q.get("title")
                    depth = q.get("depth", 0)
                    date_val = "Güncel"
                    for k, v in q.items():
                        if isinstance(v, str) and (("-" in v and ":" in v) or ("." in v and ":" in v)) and len(v) > 10:
                            date_val = v
                            break

                    lat, lng = None, None
                    try:
                        if q.get("lat") is not None: lat = float(q.get("lat"))
                        if q.get("lng") is not None: lng = float(q.get("lng"))
                        elif q.get("lon") is not None: lng = float(q.get("lon"))
                        if (lat is None or lng is None) and "geojson" in q:
                            coords = q["geojson"].get("coordinates", [])
                            if len(coords) >= 2: lng, lat = float(coords[0]), float(coords[1])
                    except:
                        pass
                    
                    if lat is not None and lng is not None:
                        earthquakes.append({"title": title, "date_str": str(date_val), "mag": mag, "depth": depth, "lat": lat, "lon": lng})
                        map_quakes.append({"lat": lat, "lon": lng, "mag": mag, "depth": depth, "title": title, "date_str": str(date_val)})
    except:
        pass

    events = []
    try:
        feed = feedparser.parse("https://www.trthaber.com/sondakika.rss")
        for entry in feed.entries[:5]:
            events.append({"title": entry.title, "link": entry.link, "source": "TRT Haber", "keyword": "GÜNCEL"})
    except:
        pass

    return render_template_string(HTML_TEMPLATE, weather_list=weather_list, meteors=meteors, map_meteors=map_meteors, earthquakes=earthquakes[:6], map_quakes=map_quakes, events=events, visitor_count=visitor_count)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
