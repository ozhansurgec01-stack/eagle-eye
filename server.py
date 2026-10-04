import re

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
    data.pop("cumhuriyet", None)

    def tr_float(x):
        return float(x.replace(".", "").replace(",", "."))

    def update_if_valid(key, value, minimum=0):
        if value is None or value <= minimum:
            return
        old = data.get(key)
        if old:
            try:
                old_value = tr_float(
                    old.replace("₺", "").replace("$", "").strip()
                )
                # Ani ve gerçek dışı sıçramayı engelle
                if old_value > 0 and abs(value - old_value) / old_value > 0.12:
                    print(f"Fiyat sıçraması reddedildi: {key} {value}")
                    return
            except Exception:
                pass
        data[key] = _fmt_try(value) if key != "ons" else _fmt_usd(value)

    # ==========================================================
    # 1) ANA KAYNAK: Doviz.com socket-key
    # ==========================================================
    try:
        r = requests.get(
            "https://altin.doviz.com/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=(3, 6)
        )
        r.raise_for_status()
        text = r.text

        def socket_ask(key):
            m = re.search(
                r'data-socket-key=["\']' + re.escape(key) +
                r'["\'][^>]*data-socket-attr=["\']ask["\'][^>]*>'
                r'\s*([0-9.]+,[0-9]+)',
                text,
                re.I | re.S
            )
            return tr_float(m.group(1)) if m else None

        def socket_spot(key):
            m = re.search(
                r'data-socket-key=["\']' + re.escape(key) +
                r'["\'][^>]*data-socket-attr=["\']s["\'][^>]*>'
                r'\s*([0-9.]+,[0-9]+)',
                text,
                re.I | re.S
            )
            if m:
                return tr_float(m.group(1))
            m2 = re.search(
                r'"asset_key":"' + re.escape(key) +
                r'"[^}]*?"bid":([0-9.]+),"ask":([0-9.]+)',
                text
            )
            return float(m2.group(2)) if m2 else None

        for key, socket_key in {
            "gram": "gram-altin",
            "ayar22": "22-ayar-bilezik",
            "ceyrek": "ceyrek-altin",
            "yarim": "yarim-altin",
            "tam": "tam-altin",
        }.items():
            update_if_valid(key, socket_ask(socket_key))

        for key, socket_key in {
            "usd": "USD",
            "eur": "EUR",
        }.items():
            update_if_valid(key, socket_spot(socket_key))


        # ------------------------------------------------------
        # ONS ALTIN: Doviz.com'un doğrudan Ons Altın sayfası
        # Hesaplama yapılmaz; sayfadaki SATIŞ değeri alınır.
        # ------------------------------------------------------
        try:
            r_ons = requests.get(
                "https://altin.doviz.com/ons",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=(3, 6)
            )
            r_ons.raise_for_status()
            ons_text = r_ons.text

            m_ons = re.search(
                r'data-socket-attr=["\']ask["\'][^>]*>\s*([0-9.]+,[0-9]+)',
                ons_text,
                re.I | re.S
            )

            if not m_ons:
                # Sayfa içindeki satış değerine ikinci doğrudan arama
                m_ons = re.search(
                    r'Satış.{0,500}?([0-9.]+,[0-9]+)',
                    ons_text,
                    re.I | re.S
                )

            if m_ons:
                ons_value = tr_float(m_ons.group(1))
                update_if_valid("ons", ons_value)
                print("Doviz.com canlı ONS verisi OK:", data.get("ons"))
            else:
                print("Doviz.com ONS satış değeri bulunamadı; eski doğrulanmış değer korunuyor.")

        except Exception as e:
            print("Doviz.com ONS alınamadı; eski doğrulanmış değer korunuyor:", e)

        print("Doviz.com ana altın kaynağı OK.")

    except Exception as e:
        print("Doviz.com kullanılamadı, APara yedeğine geçiliyor:", e)

    # ==========================================================
    # 2) YEDEK KAYNAK: APara
    # ==========================================================
    try:
        r = requests.get(
            "https://www.apara.com.tr/altin",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=(3, 6)
        )
        r.raise_for_status()
        text = r.text

        def apara_value(name):
            m = re.search(
                re.escape(name) +
                r".{0,500}?ALIŞ.{0,120}?([0-9.,]+)"
                r".{0,120}?SATIŞ.{0,120}?([0-9.,]+)",
                text,
                re.I | re.S
            )
            return tr_float(m.group(2)) if m else None

        for key, name in {
            "gram": "GRAM ALTIN",
            "ceyrek": "ÇEYREK ALTIN",
            "yarim": "YARIM ALTIN",
            "tam": "TAM ALTIN",
        }.items():
            value = apara_value(name)
            if value is not None:
                # Ana kaynak değeri yoksa yedeği kullan
                if key not in data or not data[key]:
                    data[key] = _fmt_try(value)


        print("APara yedek altın kaynağı OK.")

    except Exception as e:
        print("APara yedek kaynağı kullanılamadı:", e)

    _last_good["data"] = dict(data)

    try:
        cg_key = os.environ.get("COINGECKO_API_KEY", "")
        req2 = urllib.request.Request(
            f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,fetch-ai,storj&vs_currencies=usd,try&x_cg_demo_api_key={cg_key}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req2, timeout=3) as resp2:
            j2 = _json.loads(resp2.read().decode("utf-8"))
        data["btc"] = _fmt_usd(float(j2["bitcoin"]["usd"]))
        if "fetch-ai" in j2:
            data["fet"] = _fmt_try(float(j2["fetch-ai"]["try"]))
        if "storj" in j2:
            data["storj"] = _fmt_try(float(j2["storj"]["try"]))
    except Exception as e:
        print("CoinGecko BTC verisi alınamadı, önceki/varsayılan kullanılıyor:", e)

    try:
        cg_key = os.environ.get("COINGECKO_API_KEY", "")
        req3 = urllib.request.Request(
            f"https://api.coingecko.com/api/v3/global?x_cg_demo_api_key={cg_key}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req3, timeout=3) as resp3:
            j3 = _json.loads(resp3.read().decode("utf-8"))
        dominance = j3["data"]["market_cap_percentage"]["btc"]
        data["btc_dominance"] = f"{dominance:.1f}%"
    except Exception as e:
        print("CoinGecko BTC dominans verisi alınamadı, önceki/varsayılan kullanılıyor:", e)

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

try:
    import psycopg2
except ImportError:
    psycopg2 = None
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


# === EAGLE-EYE KAMERA YONETIMI ===
CAMERAS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "kameralar.json"
)
CAMERAS_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def _kameralar_json_yukle():
    try:
        with open(CAMERAS_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, _json.JSONDecodeError):
        return []


def _kameralar_json_kaydet(data):
    tmp_file = CAMERAS_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_file, CAMERAS_FILE)


def _kamera_db_baglan():
    if not CAMERAS_DATABASE_URL:
        return None
    if psycopg2 is None:
        raise RuntimeError(
            "DATABASE_URL tanımlı ancak psycopg2-binary kurulu değil."
        )
    return psycopg2.connect(
        CAMERAS_DATABASE_URL,
        connect_timeout=5
    )


def _kamera_db_hazirla():
    conn = _kamera_db_baglan()
    if conn is None:
        return

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS eagle_eye_kameralar (
                        id BIGSERIAL PRIMARY KEY,
                        sira INTEGER NOT NULL,
                        ad TEXT NOT NULL,
                        lat DOUBLE PRECISION NOT NULL,
                        lon DOUBLE PRECISION NOT NULL,
                        url TEXT NOT NULL,
                        tip TEXT NOT NULL
                    )
                """)

                cur.execute(
                    "SELECT COUNT(*) FROM eagle_eye_kameralar"
                )
                sayi = cur.fetchone()[0]

                if sayi == 0:
                    mevcut = _kameralar_json_yukle()

                    for i, kamera in enumerate(mevcut):
                        if not _kamera_verisini_dogrula(kamera):
                            continue

                        ad, lat, lon, url, tip = kamera

                        cur.execute(
                            """
                            INSERT INTO eagle_eye_kameralar
                            (sira, ad, lat, lon, url, tip)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                i,
                                ad,
                                float(lat),
                                float(lon),
                                url,
                                tip
                            )
                        )
    finally:
        conn.close()


def _kameralar_yukle():
    if not CAMERAS_DATABASE_URL:
        return _kameralar_json_yukle()

    _kamera_db_hazirla()

    conn = _kamera_db_baglan()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ad, lat, lon, url, tip
                FROM eagle_eye_kameralar
                ORDER BY sira, id
            """)

            return [
                [row[0], row[1], row[2], row[3], row[4]]
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def _kameralar_kaydet(data):
    if not CAMERAS_DATABASE_URL:
        return _kameralar_json_kaydet(data)

    _kamera_db_hazirla()

    conn = _kamera_db_baglan()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM eagle_eye_kameralar"
                )

                for i, kamera in enumerate(data):
                    ad, lat, lon, url, tip = kamera

                    cur.execute(
                        """
                        INSERT INTO eagle_eye_kameralar
                        (sira, ad, lat, lon, url, tip)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            i,
                            ad,
                            float(lat),
                            float(lon),
                            url,
                            tip
                        )
                    )
    finally:
        conn.close()


def _kamera_yonetici_mi():
    return request.cookies.get("eagle_owner") == "1"


def _kamera_verisini_dogrula(kamera):
    if not isinstance(kamera, list) or len(kamera) != 5:
        return False

    ad, lat, lon, url, kamera_tipi = kamera

    if not isinstance(ad, str) or not ad.strip():
        return False

    if not isinstance(url, str) or not url.strip():
        return False

    if kamera_tipi not in ("normal", "yt", "hls", "image"):
        return False

    try:
        float(lat)
        float(lon)
    except (TypeError, ValueError):
        return False

    return True


@app.route("/api/kameralar", methods=["GET"])
def api_kameralar():
    return jsonify(_kameralar_yukle())


@app.route("/api/kameralar", methods=["POST"])
def api_kamera_ekle():
    if not _kamera_yonetici_mi():
        return jsonify({
            "ok": False,
            "error": "Yetkisiz kamera yönetimi"
        }), 403

    kamera = request.get_json(silent=True)

    if not _kamera_verisini_dogrula(kamera):
        return jsonify({
            "ok": False,
            "error": "Geçersiz kamera verisi. Beklenen format: [ad, enlem, boylam, url, tip]"
        }), 400

    kameralar = _kameralar_yukle()

    def _kamera_url_anahtari(k):
        if not isinstance(k, list) or len(k) < 4:
            return ""
        url = str(k[3]).strip()
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = parsed.path.rstrip("/")

            if "youtube.com" in host and path.startswith("/live/"):
                video_id = path.split("/live/", 1)[1].split("/", 1)[0]
                return "youtube:" + video_id

            if "youtube.com" in host and path.startswith("/embed/"):
                video_id = path.split("/embed/", 1)[1].split("/", 1)[0]
                return "youtube:" + video_id

            if "youtu.be" in host:
                video_id = path.lstrip("/").split("/", 1)[0]
                return "youtube:" + video_id

            if "youtube.com" in host:
                video_id = parse_qs(parsed.query).get("v", [""])[0]
                if video_id:
                    return "youtube:" + video_id
        except Exception:
            pass

        return url

    yeni_anahtar = _kamera_url_anahtari(kamera)

    if any(_kamera_url_anahtari(k) == yeni_anahtar for k in kameralar):
        return jsonify({
            "ok": False,
            "error": "Bu kamera zaten kayıtlı."
        }), 409

    kameralar.append(kamera)
    _kameralar_kaydet(kameralar)

    return jsonify({
        "ok": True,
        "kamera": kamera,
        "index": len(kameralar) - 1
    })


@app.route("/api/kameralar/<int:index>", methods=["PUT"])
def api_kamera_duzenle(index):
    if not _kamera_yonetici_mi():
        return jsonify({
            "ok": False,
            "error": "Yetkisiz kamera yönetimi"
        }), 403

    kamera = request.get_json(silent=True)

    if not _kamera_verisini_dogrula(kamera):
        return jsonify({
            "ok": False,
            "error": "Geçersiz kamera verisi. Beklenen format: [ad, enlem, boylam, url, tip]"
        }), 400

    kameralar = _kameralar_yukle()

    if index < 0 or index >= len(kameralar):
        return jsonify({
            "ok": False,
            "error": "Kamera bulunamadı"
        }), 404

    kameralar[index] = kamera
    _kameralar_kaydet(kameralar)

    return jsonify({
        "ok": True,
        "kamera": kamera,
        "index": index
    })


@app.route("/api/kameralar/<int:index>", methods=["DELETE"])
def api_kamera_sil(index):
    if not _kamera_yonetici_mi():
        return jsonify({
            "ok": False,
            "error": "Yetkisiz kamera yönetimi"
        }), 403

    kameralar = _kameralar_yukle()

    if index < 0 or index >= len(kameralar):
        return jsonify({
            "ok": False,
            "error": "Kamera bulunamadı"
        }), 404

    silinen = kameralar.pop(index)
    _kameralar_kaydet(kameralar)

    return jsonify({
        "ok": True,
        "silinen": silinen,
        "index": index
    })


# === EAGLE-EYE KAMERA YONETIMI SONU ===

def get_location_from_ip(ip):
    try:
        if ip in ("127.0.0.1", "localhost") or ip.startswith("192.168.") or ip.startswith("10."):
            return "Yerel Ağ"
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip}?fields=status,country,city,query",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
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
        # Botları ve uptime botları loglamayalım
        ua_lower = user_agent.lower()
        if "bot" in ua_lower or "crawler" in ua_lower or "spider" in ua_lower or "uptime" in ua_lower or "go-http-client" in ua_lower:
            return
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

COUNTER_API_BASE = "https://api.counterapi.dev/v2/eagle-eye-dw3c-visitors/hero-counter"

def _counterapi_headers():
    key = os.environ.get("COUNTERAPI_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def get_visitor_count():
    try:
        r = requests.get(COUNTER_API_BASE, timeout=2, headers=_counterapi_headers())
        if r.status_code == 200:
            count = r.json()["data"]["up_count"]
            try:
                with open(COUNTER_FILE, "w") as f:
                    f.write(str(count))
            except:
                pass
            return count
    except Exception as e:
        print("Sayac okuma hatasi:", e)
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 1
    return 1

def increment_visitor_count():
    ua = request.headers.get('User-Agent', '').lower()
    is_bot = any(b in ua for b in ['bot', 'crawl', 'spider', 'render', 'uptime', 'ping', 'axios', 'postman', 'go-http-client', 'head', 'facebookexternalhit', 'facebookcatalog', 'whatsapp', 'telegram', 'discordbot', 'slackbot', 'linkedinbot', 'twitterbot', 'skypeuripreview', 'w3c_validator', 'pingdom', 'gtmetrix'])
    if is_bot:
        return get_visitor_count()
    try:
        requests.get(f"{COUNTER_API_BASE}/up", timeout=2, headers=_counterapi_headers())
        return get_visitor_count()
    except Exception as e:
        print("Sayac artirma hatasi:", e)
    return get_visitor_count()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentry - Pro TR v8.66</title>
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
        
        .leaflet-tile-pane { filter: contrast(1.2) saturate(1.4) brightness(1.0); }
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
        @keyframes glowMoon {
            0%, 100% { opacity: 1; filter: drop-shadow(0 0 1px currentColor); }
            50% { opacity: 0.75; filter: drop-shadow(0 0 4px currentColor); }
        }
        .svg-moon { animation: glowMoon 3s ease-in-out infinite; transform-origin: center; }

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
            <span>💵 DOLAR: <strong id="t-usd" class="gold">48,12 ₺</strong></span>
            <span class="dot">•</span>
            <span>💶 EURO: <strong id="t-eur" class="gold">56,17 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 BİTCOİN: <strong id="t-btc" class="btc">77.452,50 $</strong></span>
            <span class="dot">•</span>
            <span>🔮 FETCH.AI: <strong id="t-fet" class="gold">0,00 ₺</strong></span>
            <span class="dot">•</span>
            <span>📦 STORJ: <strong id="t-storj" class="gold">0,00 ₺</strong></span>
            <span class="dot">•</span>
            <span>📊 BTC DOMİNANS: <strong id="t-btcdom" class="btc">--%</strong></span>
            <span class="dot">•</span>
            <span>🟡 ONS ALTIN: <strong id="t-ons" class="ons">--,-- $</strong></span>
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
            <span>💵 DOLAR: <strong id="t-usd" class="gold">48,12 ₺</strong></span>
            <span class="dot">•</span>
            <span>💶 EURO: <strong id="t-eur" class="gold">56,17 ₺</strong></span>
            <span class="dot">•</span>
            <span>🪙 BİTCOİN: <strong id="t-btc" class="btc">77.452,50 $</strong></span>
            <span class="dot">•</span>
            <span>🔮 FETCH.AI: <strong id="t-fet" class="gold">0,00 ₺</strong></span>
            <span class="dot">•</span>
            <span>📦 STORJ: <strong id="t-storj" class="gold">0,00 ₺</strong></span>
            <span class="dot">•</span>
            <span>📊 BTC DOMİNANS: <strong id="t-btcdom" class="btc">--%</strong></span>
            <span class="dot">•</span>
            <span>🟡 ONS ALTIN: <strong id="t-ons" class="ons">--,-- $</strong></span>
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
    animation:flexTickerScroll 45s linear infinite;
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
                <span style="margin: 0 15px;">🟡 ONS ALTIN: <strong style="color:#4ade80;">--,-- $</strong></span>
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
                <span style="margin: 0 15px;">🟡 ONS ALTIN: <strong style="color:#4ade80;">--,-- $</strong></span>
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
    


    <style>
    /* === EAGLE-EYE CAMERA UI START === */
    #eagleCameraMenuButton {
        position: fixed;
        left: 10px;
        top: 88px;
        z-index: 20000;
        width: 42px;
        height: 42px;
        border: 1px solid rgba(56,189,248,.45);
        border-radius: 12px;
        background: rgba(2,8,23,.92);
        color: #38bdf8;
        font-size: 21px;
        cursor: pointer;
        box-shadow: 0 6px 20px rgba(0,0,0,.35);
    }

    #eagleCameraBackdrop {
        position: fixed;
        inset: 0;
        z-index: 19998;
        background: rgba(0,0,0,.42);
        display: none;
    }

    #eagleCameraDrawer {
        position: fixed;
        top: 0;
        left: -370px;
        width: 350px;
        max-width: calc(100vw - 30px);
        height: 100vh;
        z-index: 19999;
        background: var(--bg-header);
        color: #fff;
        box-shadow: 10px 0 35px rgba(0,0,0,.45);
        transition: left .22s ease;
        overflow-y: auto;
        box-sizing: border-box;
        padding: 18px;
    }

    #eagleCameraDrawer.open {
        left: 0;
    }

    #eagleCameraBackdrop.open {
        display: block;
    }

    .eagle-camera-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
        font-weight: 800;
        color: #38bdf8;
        font-size: 16px;
    }

    .eagle-camera-close {
        border: 0;
        background: transparent;
        color: #94a3b8;
        font-size: 25px;
        cursor: pointer;
    }

    .eagle-camera-section {
        border: 1px solid rgba(148,163,184,.2);
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 12px;
        background: rgba(15,23,42,.72);
    }

    .eagle-camera-section h3 {
        margin: 0 0 10px;
        font-size: 13px;
        color: #e2e8f0;
    }

    #eagleCameraList {
        max-height: 52vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 4px;
    }

    #eagleCameraList::-webkit-scrollbar {
        width: 6px;
    }

    #eagleCameraList::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 8px;
    }

    .eagle-camera-field {
        width: 100%;
        box-sizing: border-box;
        margin: 4px 0;
        padding: 9px 10px;
        border: 1px solid #334155;
        border-radius: 8px;
        background: #020617;
        color: #f8fafc;
        font-size: 12px;
        outline: none;
    }

    .eagle-camera-field:focus {
        border-color: #38bdf8;
    }

    .eagle-camera-actions {
        display: flex;
        gap: 7px;
        margin-top: 8px;
    }

    .eagle-camera-btn {
        flex: 1;
        border: 0;
        border-radius: 8px;
        padding: 9px 8px;
        cursor: pointer;
        font-weight: 700;
        font-size: 11px;
    }

    .eagle-camera-add {
        background: #0284c7;
        color: #fff;
    }

    .eagle-camera-clear {
        background: #334155;
        color: #e2e8f0;
    }

    .eagle-camera-card {
        border: 1px solid rgba(148,163,184,.2);
        border-radius: 10px;
        padding: 9px;
        margin-top: 8px;
        background: rgba(2,6,23,.72);
    }

    .eagle-camera-card-title {
        font-size: 12px;
        font-weight: 800;
        color: #38bdf8;
        margin-bottom: 6px;
    }

    .eagle-camera-readonly {
        width: 100%;
        box-sizing: border-box;
        margin: 2px 0;
        padding: 6px 7px;
        border: 1px solid #1e293b;
        border-radius: 6px;
        background: #0f172a;
        color: #cbd5e1;
        font-size: 10px;
    }

    .eagle-camera-card-actions {
        display: flex;
        gap: 5px;
        margin-top: 5px;
    }

    .eagle-camera-small {
        flex: 1;
        padding: 6px;
        border: 0;
        border-radius: 6px;
        cursor: pointer;
        font-size: 10px;
        font-weight: 700;
    }

    .eagle-camera-edit {
        background: #0369a1;
        color: #fff;
    }

    .eagle-camera-delete {
        background: #991b1b;
        color: #fff;
    }

    .eagle-camera-watch {
        background: #047857;
        color: #fff;
    }

    #eagleCameraViewer {
        position: fixed;
        inset: 0;
        z-index: 30000;
        display: none;
        align-items: center;
        justify-content: center;
        background: rgba(0,0,0,.78);
        padding: 18px;
        box-sizing: border-box;
    }

    #eagleCameraViewer.open {
        display: flex;
    }

    .eagle-camera-viewer-box {
        width: min(900px, 96vw);
        max-height: 94vh;
        background: #020617;
        border: 1px solid rgba(56,189,248,.45);
        border-radius: 14px;
        box-shadow: 0 15px 50px rgba(0,0,0,.65);
        overflow: hidden;
    }

    .eagle-camera-viewer-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 12px;
        color: #38bdf8;
        font-size: 13px;
        font-weight: 800;
    }

    .eagle-camera-viewer-close {
        border: 0;
        background: transparent;
        color: #94a3b8;
        font-size: 25px;
        cursor: pointer;
        line-height: 1;
    }

    #eagleCameraViewerContent {
        padding: 0 10px 10px;
    }

    #eagleCameraViewerContent iframe,
    #eagleCameraViewerContent video,
    #eagleCameraViewerContent img {
        display: block;
        width: 100%;
        height: min(68vh, 560px);
        border: 0;
        border-radius: 9px;
        background: #000;
        object-fit: contain;
    }

    .eagle-camera-status {
        font-size: 11px;
        color: #94a3b8;
        margin-top: 7px;
        line-height: 1.4;
    }

    .eagle-camera-status.eagle-success {
        color: #22c55e;
        font-weight: 700;
    }
    /* === EAGLE-EYE CAMERA UI END === */
    </style>

    <div class="header-bar">
        <div class="brand">🦅 SENTRY v8.66</div>
<button id="rainToggleBtn" onclick="toggleRainLayer()" class="nav-btn" style="background: #0284c7; color: white; border: none; padding: 6px 10px; border-radius: 8px; font-size: 11px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 4px;">
    🌧️ YAĞIŞ <span id="rainStatus" style="font-size: 9px; opacity: 0.9;">(AÇIK)</span>
</button>
        <div class="header-right">
            <div class="clock-badge" id="liveClock">⏳ --:--:--</div>
            <div class="visitor-badge">
                👁️ {{ visitor_count }}
            </div>
            <div id="modeToggleBtn" class="mode-btn" onclick="toggleTheme()">● LIGHT</div>
        </div>
    </div>

    <!-- === EAGLE-EYE CAMERA MENU START === -->
    <button id="eagleCameraMenuButton" onclick="eagleToggleCameraMenu()" aria-label="Kamera menüsü">☰</button>
    <div id="eagleCameraBackdrop" onclick="eagleToggleCameraMenu()"></div>

    <aside id="eagleCameraDrawer">
        <div class="eagle-camera-title">
            <span>📹 KAMERA YÖNETİMİ</span>
            <button class="eagle-camera-close" onclick="eagleToggleCameraMenu()">×</button>
        </div>

        <div class="eagle-camera-section">
            <h3>➕ Yeni / Düzenlenen Kamera</h3>

            <input id="eagleCamName" class="eagle-camera-field"
                   placeholder="Kamera adı (bayrak dahil yazılabilir)">

            <input id="eagleCamLat" class="eagle-camera-field"
                   type="number" step="any" placeholder="Enlem">

            <input id="eagleCamLon" class="eagle-camera-field"
                   type="number" step="any" placeholder="Boylam">

            <input id="eagleCamUrl" class="eagle-camera-field"
                   type="text"
                   placeholder="YouTube Live / embed / HLS / kamera URL">

            <select id="eagleCamType" class="eagle-camera-field">
                <option value="yt">YouTube</option>
                <option value="normal">Normal</option>
                <option value="hls">HLS</option>
                <option value="image">Görüntü</option>
            </select>

            <div class="eagle-camera-actions">
                <button class="eagle-camera-btn eagle-camera-add"
                        onclick="eagleSaveCamera()">KAYDET</button>
                <button class="eagle-camera-btn eagle-camera-clear"
                        onclick="eagleClearCameraForm()">TEMİZLE</button>
            </div>

            <div id="eagleCameraEditIndex" style="display:none"></div>
            <div id="eagleCameraStatus" class="eagle-camera-status"></div>
        </div>

        <div class="eagle-camera-section">
            <h3>📡 Kayıtlı Kameralar</h3>
            <div id="eagleCameraList">Kameralar yükleniyor...</div>
        </div>
    </aside>
    <!-- === EAGLE-EYE CAMERA MENU END === -->

    <div id="eagleCameraViewer" onclick="eagleCloseCameraViewer(event)">
        <div class="eagle-camera-viewer-box" onclick="event.stopPropagation()">
            <div class="eagle-camera-viewer-head">
                <span id="eagleCameraViewerTitle">📹 Kamera</span>
                <button class="eagle-camera-viewer-close"
                        onclick="eagleCloseCameraViewer()">×</button>
            </div>
            <div id="eagleCameraViewerContent"></div>
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

        {% if mgm_uyari %}
        <div style="background: linear-gradient(135deg, #b45309, #92400e); border-radius: 12px; padding: 14px 16px; margin-top: 16px; border: 1px solid #f59e0b;">
            <div style="font-weight: 800; font-size: 0.8rem; color: #fef3c7; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 6px;">⚠️ Meteoroloji Uyarısı</div>
            {% for u in mgm_uyari %}
            <div style="color: #fffbeb; font-size: 0.9rem; line-height: 1.4; margin-bottom: 4px;">• {{ u }}</div>
            {% endfor %}
        </div>
        {% endif %}
        <div class="panel-title mt-4">🌍 Son Depremler (Büyüklük >= 4.0)</div>
        <div>
            {% if earthquakes %}
                {% for q in earthquakes %}
                <div class="quake-card" onclick="panToLocation({{ q.lat }}, {{ q.lon }}, '<b>🚨 Deprem</b><br><b>Yer:</b> {{ q.title }}<br><b>Büyüklük:</b> {{ q.mag }}<br><b>Tarih:</b> {{ q.date_str }}', 6)">
                    <div class="quake-info">
                        <div class="quake-line" style="color: var(--text-muted); font-size: 0.75rem;">
                            🕒 {{ q.date_str }} &nbsp;&nbsp; 📍 <span style="color: var(--text-main); font-weight: 800;">{{ q.title }}</span>
                        </div>
                        <div class="quake-line">
                            💥 Şiddet: <span class="quake-mag-badge">{{ q.mag }}</span>
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

        <div class="panel-title mt-4">✨ Son Düşen Meteorlar (NASA)</div>
        <div class="card-custom">
            {% for m in meteors %}
            <div class="item-row" onclick="panToLocation({{ m.lat_num }}, {{ m.lon_num }}, '<b>✨ Meteor (NASA)</b><br><b>Tarih:</b> {{ m.date }}<br><b>Enerji:</b> {{ m.energy }} J', 6)">
                <div>
                    <div class="text-date">{{ m.date }}</div>
                    <div class="text-coord">Konum: {{ m.lat }}, {{ m.lon }}</div>
                </div>
                <span class="badge-energy">{{ m.energy }} J</span>
            </div>
            {% else %}
            <div style="color: var(--text-muted); font-size: 0.85rem; padding: 8px 4px;">Son 30 günde kayıtlı meteor düşüşü yok.</div>
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
            var time = new Intl.DateTimeFormat('tr-TR', {
                timeZone: 'Europe/Istanbul',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).format(now);

            document.getElementById('liveClock').innerHTML = '🕒 ' + time;
        }

        setInterval(updateClock, 1000);
        updateClock();

        var map = L.map('map', {zoomControl: true}).setView([39.0, 35.0], 5);

        var baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19, attribution: '&copy; OpenStreetMap'
        }).addTo(map);

        var rainLayer = null;
        fetch('https://api.rainviewer.com/public/weather-maps.json')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                var host = data.host;
                var frames = data.radar.nowcast && data.radar.nowcast.length > 0 ? data.radar.nowcast : data.radar.past;
                var path = frames[frames.length - 1].path;
                rainLayer = L.tileLayer(host + path + '/256/{z}/{x}/{y}/2/1_1.png', {
                    opacity: 0.6, zIndex: 400
                }).addTo(map);
            })
            .catch(function(err) { console.log('RainViewer yuklenemedi:', err); });

        function toggleRainLayer() {
            var status = document.getElementById('rainStatus');
            var btn = document.getElementById('rainToggleBtn');
            if (rainLayer && map.hasLayer(rainLayer)) {
                map.removeLayer(rainLayer);
                if(status) status.innerText = '(KAPALI)';
                if(btn) { btn.style.opacity = '1'; btn.style.background = '#dc2626'; }
            } else {
                map.addLayer(rainLayer);
                if(status) status.innerText = '(AÇIK)';
                if(btn) { btn.style.opacity = '1'; btn.style.background = '#0284c7'; }
            }
        }

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
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
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
                 .bindPopup("<div style='font-family:sans-serif; color:#111;'><b>🚨 Deprem</b><br><b>Yer:</b> " + q.title + "<br><b>Büyüklük:</b> " + q.mag + "<br><b>Tarih:</b> " + q.date_str + "</div>");
            }
        });

        var meteorData = {{ map_meteors | safe }};
        meteorData.forEach(function(m) {
            if(m.lat !== null && m.lon !== null && !isNaN(m.lat) && !isNaN(m.lon)) {
                L.circleMarker([m.lat, m.lon], { color: '#fb923c', fillColor: '#f97316', fillOpacity: 0.5, weight: 1.2, radius: 4 })
                 .addTo(map)
                 .bindPopup("<div style='font-family:sans-serif; color:#111;'><b>✨ Meteor (NASA)</b><br><b>Tarih:</b> " + m.date + "<br><b>Enerji:</b> " + m.energy + " J</div>");
            }
        });


    </script>

<script>
    window.addEventListener('DOMContentLoaded', () => {
        const clientIp = "{{ real_ip }}";
        const clientLocation = "{{ real_location }}";
        const box = document.createElement('div');
        box.innerHTML = '🦅 Sentry Radar<br><span style="font-size: 11px; color: #94a3b8;">IP: ' + clientIp + ' &bull; ' + clientLocation + '</span>';
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
            "t-usd": data.usd,
            "t-eur": data.eur,
            "t-btc": data.btc,
            "t-fet": data.fet,
            "t-storj": data.storj,
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
function playVisitorBeep() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start();
        osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
        console.log("Ses calinamadi:", e);
    }
}

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
            playVisitorBeep();
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

setInterval(function() {
    location.reload();
}, 180000);
</script>


<script>
/* === EAGLE-EYE CAMERA JS START === */

let eagleCameraData = [];

function eagleToggleCameraMenu() {
    document.getElementById('eagleCameraDrawer').classList.toggle('open');
    document.getElementById('eagleCameraBackdrop').classList.toggle('open');
}

function eagleYouTubeEmbedUrl(url) {
    let youtubeId = '';

    try {
        const u = new URL(url);

        if (u.hostname.includes('youtu.be')) {
            youtubeId = u.pathname.split('/').filter(Boolean)[0] || '';
        } else if (u.hostname.includes('youtube.com')) {
            if (u.pathname.startsWith('/embed/')) {
                youtubeId = u.pathname.split('/')[2];
            } else if (u.pathname.startsWith('/live/')) {
                youtubeId = u.pathname.split('/')[2];
            } else {
                youtubeId = u.searchParams.get('v') || '';
            }
        }
    } catch (e) {
        console.error('YouTube URL HATASI:', e);
    }

    if (youtubeId) {
        return 'https://www.youtube.com/embed/' + youtubeId + '?autoplay=1&mute=1';
    }

    return url;
}

async function eagleLoadCameras() {
    const list = document.getElementById('eagleCameraList');

    try {
        const response = await fetch('/api/kameralar', { cache: 'no-store' });

        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }

        eagleCameraData = await response.json();

        if (!Array.isArray(eagleCameraData)) {
            throw new Error('Geçersiz kamera verisi');
        }

        if (!eagleCameraData.length) {
            list.innerHTML = '<div class="eagle-camera-status">Kayıtlı kamera yok.</div>';
            return;
        }

        list.innerHTML = eagleCameraData.map((kamera, index) => {
            const ad = kamera[0] ?? '';
            const lat = kamera[1] ?? '';
            const lon = kamera[2] ?? '';
            const url = kamera[3] ?? '';
            const tip = kamera[4] ?? '';

            return `
                <div class="eagle-camera-card">
                    <div class="eagle-camera-card-title">
                        <span>${eagleEscapeHtml(index + 1 + '. ' + ad)}</span>
                    </div>

                    <div class="eagle-camera-card-actions">
                        <button class="eagle-camera-small eagle-camera-watch"
                                onclick="eagleWatchCamera(${index})">▶ İZLE</button>
                        <button class="eagle-camera-small eagle-camera-edit"
                                onclick="eagleEditCamera(${index})">✏ DÜZENLE</button>
                        <button class="eagle-camera-small eagle-camera-delete"
                                onclick="eagleDeleteCamera(${index})">🗑 SİL</button>
                    </div>
                </div>
            `;
        }).join('');

        const debugStatus = document.getElementById('eagleCameraStatus');
        if (debugStatus) {
            debugStatus.textContent =
                'DEBUG — API: ' + eagleCameraData.length +
                ' | DOM: ' + list.querySelectorAll('.eagle-camera-card').length +
                ' | Son: ' + (eagleCameraData[eagleCameraData.length - 1]?.[0] || '');
        }

        console.log('EAGLE CAMERA DEBUG:', {
            apiCount: eagleCameraData.length,
            domCards: list.querySelectorAll('.eagle-camera-card').length,
            lastCamera: eagleCameraData[eagleCameraData.length - 1]?.[0] || ''
        });
    } catch (error) {
        list.innerHTML =
            '<div class="eagle-camera-status">Kameralar yüklenemedi: ' +
            eagleEscapeHtml(error.message) + '</div>';
    }
}

function eagleEscapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function eagleEscapeAttr(value) {
    return eagleEscapeHtml(value);
}

function eagleSetForm(kamera, index) {
    document.getElementById('eagleCamName').value = kamera[0] ?? '';
    document.getElementById('eagleCamLat').value = kamera[1] ?? '';
    document.getElementById('eagleCamLon').value = kamera[2] ?? '';
    document.getElementById('eagleCamUrl').value = kamera[3] ?? '';
    document.getElementById('eagleCamType').value = kamera[4] ?? 'normal';
    document.getElementById('eagleCameraEditIndex').textContent = index;
    document.getElementById('eagleCameraStatus').textContent =
        'Düzenleme modu: #' + (index + 1);
}

function eagleEditCamera(index) {
    const kamera = eagleCameraData[index];

    if (!kamera) {
        return;
    }

    eagleSetForm(kamera, index);
    document.getElementById('eagleCamName').focus();
}


async function eagleLoadHlsForViewer() {
    if (window.Hls) return true;

    return await new Promise(function(resolve) {
        const existing = document.querySelector('script[data-eagle-hls="1"]');

        if (existing) {
            existing.addEventListener('load', function() { resolve(!!window.Hls); });
            existing.addEventListener('error', function() { resolve(false); });
            return;
        }

        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/hls.js@latest';
        script.dataset.eagleHls = '1';

        script.onload = function() {
            resolve(!!window.Hls);
        };

        script.onerror = function() {
            resolve(false);
        };

        document.head.appendChild(script);
    });
}

async function eagleWatchCamera(index) {
    const kamera = eagleCameraData[index];

    if (!kamera) return;

    const name = String(kamera[0] ?? 'Kamera');
    const rawUrl = String(kamera[3] ?? '').trim();
    const type = String(kamera[4] ?? 'normal').toLowerCase();

    if (!rawUrl) return;

    const viewer = document.getElementById('eagleCameraViewer');
    const title = document.getElementById('eagleCameraViewerTitle');
    const content = document.getElementById('eagleCameraViewerContent');

    title.textContent = '📹 ' + name;
    content.innerHTML = '';

    viewer.classList.add('open');

    if (type === 'yt') {
        const iframe = document.createElement('iframe');

        iframe.src = eagleYouTubeEmbedUrl(rawUrl);
        iframe.allow =
            'autoplay; encrypted-media; picture-in-picture';
        iframe.allowFullscreen = true;

        content.appendChild(iframe);
        return;
    }

    if (type === 'image') {
        const img = document.createElement('img');

        img.src = rawUrl;
        img.alt = name;

        content.appendChild(img);
        return;
    }

    if (type === 'hls') {
        const video = document.createElement('video');

        video.controls = true;
        video.autoplay = true;
        video.muted = true;
        video.playsInline = true;

        content.appendChild(video);

        if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = rawUrl;
            video.play().catch(function(){});
            return;
        }

        const hlsReady = await eagleLoadHlsForViewer();

        if (hlsReady && window.Hls && Hls.isSupported()) {
            const hls = new Hls();

            hls.loadSource(rawUrl);
            hls.attachMedia(video);

            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                video.play().catch(function(){});
            });

            video._eagleHls = hls;
            return;
        }

        content.innerHTML =
            '<div style="padding:30px;text-align:center;color:#e2e8f0;">' +
            'Bu tarayıcı HLS canlı yayını oynatamıyor.' +
            '</div>';

        return;
    }

    const iframe = document.createElement('iframe');

    iframe.src = rawUrl;
    iframe.allow =
        'autoplay; encrypted-media; picture-in-picture';
    iframe.allowFullscreen = true;

    content.appendChild(iframe);
}

function eagleCloseCameraViewer(event) {
    if (event && event.target !== event.currentTarget) return;

    const viewer = document.getElementById('eagleCameraViewer');
    const content = document.getElementById('eagleCameraViewerContent');

    if (!viewer) return;

    const video = content.querySelector('video');

    if (video && video._eagleHls) {
        try {
            video._eagleHls.destroy();
        } catch (e) {}
    }

    content.innerHTML = '';
    viewer.classList.remove('open');
}

function eagleClearCameraForm() {
    document.getElementById('eagleCamName').value = '';
    document.getElementById('eagleCamLat').value = '';
    document.getElementById('eagleCamLon').value = '';
    document.getElementById('eagleCamUrl').value = '';
    document.getElementById('eagleCamType').value = 'yt';
    document.getElementById('eagleCameraEditIndex').textContent = '';
    document.getElementById('eagleCameraStatus').textContent = '';
}

function eagleGetCameraForm() {
    const name = document.getElementById('eagleCamName').value.trim();
    const lat = Number(document.getElementById('eagleCamLat').value);
    const lon = Number(document.getElementById('eagleCamLon').value);
    const url = document.getElementById('eagleCamUrl').value.trim();
    const type = document.getElementById('eagleCamType').value;

    if (!name || !url || !Number.isFinite(lat) || !Number.isFinite(lon)) {
        throw new Error('Ad, enlem, boylam ve URL alanları zorunludur.');
    }

    return [name, lat, lon, url, type];
}

async function eagleSaveCamera() {
    const status = document.getElementById('eagleCameraStatus');

    try {
        const kamera = eagleGetCameraForm();
        const editIndex = document.getElementById('eagleCameraEditIndex').textContent.trim();

        const isEdit = editIndex !== '';
        const endpoint = isEdit
            ? '/api/kameralar/' + encodeURIComponent(editIndex)
            : '/api/kameralar';

        const response = await fetch(endpoint, {
            method: isEdit ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(kamera)
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(result.error || ('HTTP ' + response.status));
        }

        eagleClearCameraForm();

        status.className = 'eagle-camera-status eagle-success';
        status.textContent = isEdit
            ? '✅ Kamera başarı ile güncellenmiştir.'
            : '✅ Kamera başarı ile eklenmiştir.';

        await eagleLoadCameras();

    } catch (error) {
        status.textContent = '❌ ' + error.message;
    }
}

async function eagleDeleteCamera(index) {
    if (!confirm('Bu kamera kaydını silmek istediğine emin misin?')) {
        return;
    }

    const status = document.getElementById('eagleCameraStatus');

    try {
        const response = await fetch(
            '/api/kameralar/' + encodeURIComponent(index),
            { method: 'DELETE' }
        );

        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(result.error || ('HTTP ' + response.status));
        }

        status.textContent = '✅ Kamera silindi.';
        eagleClearCameraForm();
        await eagleLoadCameras();

    } catch (error) {
        status.textContent = '❌ ' + error.message;
    }
}

eagleLoadCameras();

/* === EAGLE-EYE CAMERA JS END === */
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

    sun_svg = '''<svg class="svg-sun" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M6.34 17.66l-1.41 1.41"></path><path d="M19.07 4.93l-1.41 1.41"></path></svg>'''
    moon_svg = '''<svg class="svg-moon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
    cloud_svg = '''<svg class="svg-cloud" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg>'''
    rain_svg = '''<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path class="svg-cloud" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path><line class="svg-rain-drop" x1="8" y1="22" x2="8" y2="24"></line><line class="svg-rain-drop" x1="12" y1="22" x2="12" y2="24" style="animation-delay: 0.3s;"></line><line class="svg-rain-drop" x1="16" y1="22" x2="16" y2="24" style="animation-delay: 0.6s;"></line></svg>'''
    humidity_svg = '''<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path></svg>'''

    owm_key = os.environ.get("OWM_API_KEY", "")
    for c in cities:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={c['lat']}&lon={c['lon']}&appid={owm_key}&units=metric&lang=tr"
            try:
                res = requests.get(url, timeout=4)
            except requests.exceptions.Timeout:
                res = requests.get(url, timeout=4)

            if res.status_code == 200:
                data = res.json()
                temp = str(round(data['main']['temp']))
                humidity = str(data['main']['humidity'])
                owm_id = data['weather'][0]['id']
                owm_main = data['weather'][0]['main'].lower()
                desc = data['weather'][0]['description'].capitalize()

                if is_night and owm_id == 800:
                    desc = "Açık"

                svg_icon = sun_svg if not is_night else moon_svg
                map_svg = sun_svg if not is_night else moon_svg

                if "rain" in owm_main or "drizzle" in owm_main or "snow" in owm_main:
                    svg_icon = rain_svg
                    map_svg = rain_svg
                elif "cloud" in owm_main or "mist" in owm_main or "fog" in owm_main or "haze" in owm_main:
                    svg_icon = cloud_svg
                    map_svg = cloud_svg

                weather_list.append({
                    "city": c['name'], "lat": c['lat'], "lon": c['lon'],
                    "temp": temp, "humidity": humidity, "desc": desc,
                    "svg_icon": svg_icon, "map_svg": map_svg, "humidity_svg": humidity_svg
                })
            else:
                print(f"HAVA DURUMU HATASI ({c['name']}): status={res.status_code}")
        except Exception as e:
            print(f"HAVA DURUMU HATASI ({c['name']}): {e}")

    if weather_list:
        _weather_cache["data"] = weather_list
    _weather_cache["ts"] = now
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
        <h2>🦅 Sentry - Giriş Gerekli</h2>
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
    <h2>🦅 Sentry - Ziyaretçi Kayıtları (son {len(entries)})</h2>
    <table><tr><th>Tarih/Saat</th><th>IP</th><th>Konum</th><th>Tarayıcı</th></tr>
    {rows}
    </table>
    </body></html>
    """
    return html

@app.route("/")
def index():
    global visitor_count
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    real_location = get_location_from_ip(user_ip)
    _ua_check = request.headers.get('User-Agent', '').lower()
    _is_bot_visit = any(b in _ua_check for b in ['bot', 'crawl', 'spider', 'render', 'uptime', 'ping', 'axios', 'postman', 'go-http-client', 'head', 'facebookexternalhit', 'facebookcatalog', 'whatsapp', 'telegram', 'discordbot', 'slackbot', 'linkedinbot', 'twitterbot', 'skypeuripreview', 'w3c_validator', 'pingdom', 'gtmetrix'])
    if not _is_bot_visit:
        log_visitor(user_ip, request.headers.get('User-Agent', 'Bilinmiyor'))
    
    visitor_count = get_visitor_count()

    is_owner_link = request.args.get("owner") == "eagleowner2026"
    is_owner_cookie = request.cookies.get("eagle_owner") == "1"
    is_owner = is_owner_link or is_owner_cookie
    
    # Yerel test IP'lerinde sayacı arttırma
    is_local = user_ip in ["127.0.0.1", "localhost"] or user_ip.startswith("192.168.")
    has_visited_cookie = request.cookies.get("eagle_visited") == "1"
    is_new_real_visitor = False
    if not is_owner and not is_local and not has_visited_cookie:
        visitor_count = increment_visitor_count()
        is_new_real_visitor = True

    current_hour = datetime.now(TR_TZ).hour
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
        {"name": "Van", "lat": 38.4891, "lon": 43.4089},
        {"name": "Bayburt", "lat": 40.2552, "lon": 40.2249}
    ]
    
    tr_translations = {
        "sunny": "Güneşli", "clear": "Açık", "partly cloudy": "Parçalı Bulutlu",
        "cloudy": "Bulutlu", "overcast": "Çok Bulutlu", "mist": "Puslu",
        "patchy rain possible": "Bölgesel Yağmur İhtimali", "patchy rain nearby": "Yakınlarda Bölgesel Yağmur",
        "light rain": "Hafif Yağmurlu", "moderate rain": "Yağmurlu", "heavy rain": "Şiddetli Yağmurlu",
        "thunderstorm": "Fırtınalı", "light rain shower": "Hafif Yağmurlu Sağanak",
        "thundery outbreaks in nearby": "Yakınlarda Gök Gürültülü Sağanak", "thundery outbreaks possible": "Gök Gürültülü Sağanak İhtimali", "moderate or heavy rain shower": "Kuvvetli Sağanak Yağmur", "patchy light rain": "Hafif Yerel Yağmur"
    }
    
    sun_svg = '''<svg class="svg-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M6.34 17.66l-1.41 1.41"></path><path d="M19.07 4.93l-1.41 1.41"></path></svg>'''
    moon_svg = '''<svg class="svg-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
    
    cloud_svg = '''<svg class="svg-cloud" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg>'''
    mist_svg = '''<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="8" x2="21" y2="8"></line><line x1="5" y1="12" x2="19" y2="12"></line><line x1="3" y1="16" x2="21" y2="16"></line></svg>'''
    rain_svg = '''<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path class="svg-cloud" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path><line class="svg-rain-drop" x1="8" y1="22" x2="8" y2="24" stroke="#ffffff"></line><line class="svg-rain-drop" x1="12" y1="22" x2="12" y2="24" stroke="#ffffff" style="animation-delay: 0.3s;"></line><line class="svg-rain-drop" x1="16" y1="22" x2="16" y2="24" stroke="#ffffff" style="animation-delay: 0.6s;"></line></svg>'''
    
    map_sun_svg = '''<svg class="svg-sun" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M6.34 17.66l-1.41 1.41"></path><path d="M19.07 4.93l-1.41 1.41"></path></svg>'''
    map_moon_svg = '''<svg class="svg-moon" width="10" height="10" viewBox="0 0 24 24" fill="#fde047" stroke="#fde047" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
    
    map_cloud_svg = '''<svg class="svg-cloud" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg>'''
    map_mist_svg = '''<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="8" x2="21" y2="8"></line><line x1="5" y1="12" x2="19" y2="12"></line><line x1="3" y1="16" x2="21" y2="16"></line></svg>'''
    map_rain_svg = '''<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="3.5" fill="#38bdf8" fill-opacity="0.3" stroke-linecap="round" stroke-linejoin="round"><path class="svg-cloud" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path><line class="svg-rain-drop" x1="8" y1="22" x2="8" y2="24" stroke="#2563eb"></line><line class="svg-rain-drop" x1="12" y1="22" x2="12" y2="24" stroke="#2563eb" style="animation-delay: 0.3s;"></line><line class="svg-rain-drop" x1="16" y1="22" x2="16" y2="24" stroke="#2563eb" style="animation-delay: 0.6s;"></line></svg>'''

    for c in cities:
        try:
            encoded_city = urllib.parse.quote(c['name'])
            r = requests.get(f"https://wttr.in/{encoded_city}?format=j1", timeout=2).json()
            current = r["current_condition"][0]
            temp = current["temp_C"]
            humidity = current["humidity"]
            raw_desc = current["weatherDesc"][0]["value"]
            
            desc_lower_key = raw_desc.strip().lower()
            desc = tr_translations.get(desc_lower_key, raw_desc)
            
            d_lower = desc.lower()
            if "yağmur" in d_lower or "rain" in d_lower or "fırtına" in d_lower or "sağanak" in d_lower:
                svg_icon, map_svg = rain_svg, map_rain_svg
            elif "pus" in d_lower or "mist" in d_lower or "sis" in d_lower:
                svg_icon, map_svg = mist_svg, map_mist_svg
            elif "bulut" in d_lower or "cloud" in d_lower or "overcast" in d_lower:
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

        cutoff = datetime.utcnow() - timedelta(days=30)
        date_idx = fields.index("date") if "date" in fields else None
        if date_idx is not None:
            recent_rows = []
            for row in rows:
                try:
                    row_date = datetime.strptime(row[date_idx], "%Y-%m-%d %H:%M:%S")
                    if row_date >= cutoff:
                        recent_rows.append(row)
                except Exception:
                    pass
            rows = recent_rows

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

    mgm_uyari = []
    try:
        mgm_res = requests.get("https://www.mgm.gov.tr/mobile/tahmin-uyari-liste.aspx", timeout=3)
        mgm_text = mgm_res.text
        items = re.findall(
            r'<li>(\d{2}\.\d{2}\.\d{4})\s*<br/>\s*<a[^>]*>([^<]+)</a>\s*</li>',
            mgm_text
        )
        for tarih, baslik in items:
            baslik = baslik.strip()
            if baslik:
                mgm_uyari.append(baslik)
        mgm_uyari = mgm_uyari[:3]
    except Exception as e:
        print("MGM uyari alinamadi:", e)

    earthquakes = []
    map_quakes = []
    try:
        # Turkiye ve cevresi icin USGS API'si (whitelist dostu, resmi/global kaynak)
        usgs_url = (
            "https://earthquake.usgs.gov/fdsnws/event/1/query"
            "?format=geojson&minmagnitude=4.0"
            "&minlatitude=35.5&maxlatitude=42.5"
            "&minlongitude=25.5&maxlongitude=45.0"
            "&orderby=time&limit=20"
        )
        q_res = requests.get(usgs_url, timeout=5).json()
        for feature in q_res.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                lng, lat = coords[0], coords[1]
                depth = coords[2] if len(coords) > 2 else 0
                mag = props.get("mag", 0)
                title = props.get("place", "Bilinmeyen konum")
                time_ms = props.get("time", 0)
                date_val = datetime.utcfromtimestamp(time_ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if time_ms else "Güncel"

                earthquakes.append({"title": title, "date_str": date_val, "mag": mag, "depth": depth, "lat": lat, "lon": lng})
                map_quakes.append({"lat": lat, "lon": lng, "mag": mag, "depth": depth, "title": title, "date_str": date_val})
    except Exception as e:
        print("Deprem verisi alinamadi (USGS):", e)

    events = []
    try:
        rss_res = requests.get("https://www.trthaber.com/sondakika.rss", timeout=5)
        rss_res.encoding = "utf-8"
        feed = feedparser.parse(rss_res.text)
        for entry in feed.entries[:5]:
            events.append({"title": entry.title, "link": entry.link, "source": "TRT Haber", "keyword": "GÜNCEL"})
    except:
        pass

    resp = make_response(render_template_string(HTML_TEMPLATE, real_ip=user_ip, real_location=real_location, weather_list=weather_list, meteors=meteors, map_meteors=map_meteors, earthquakes=earthquakes[:6], map_quakes=map_quakes, events=events, visitor_count=visitor_count, mgm_uyari=mgm_uyari))
    if is_owner_link:
        resp.set_cookie('eagle_owner', '1', max_age=365*24*60*60)
    if is_new_real_visitor:
        resp.set_cookie('eagle_visited', '1', max_age=365*24*60*60)
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)
