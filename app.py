import os
import random
import string
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, g, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Cloudflare Worker URL
CLOUDFLARE_WORKER_URL = os.environ.get('CLOUDFLARE_WORKER_URL', '')

# Admin paroly
ADMIN_SIFRE = os.environ.get('ADMIN_SIFRE', 'admin123')

# Veritabany yoly
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turnuva.db')

# CSRF token saklamak üçin
_csrf_tokens = {}


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        # katilimcilar
        db.execute("""
            CREATE TABLE IF NOT EXISTS katilimcilar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referans_kodu TEXT UNIQUE NOT NULL,
                ad TEXT NOT NULL,
                pubg_id TEXT NOT NULL,
                telefon TEXT NOT NULL,
                ulasim TEXT NOT NULL,
                takim_kodu TEXT,
                takim_lideri INTEGER DEFAULT 0,
                odeme_durumu INTEGER DEFAULT 0,
                admin_onay INTEGER DEFAULT 0,
                kayit_tarihi TEXT NOT NULL,
                odeme_tarihi TEXT,
                onay_tarihi TEXT
            )
        """)
        # takimlar
        db.execute("""
            CREATE TABLE IF NOT EXISTS takimlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                takim_kodu TEXT UNIQUE NOT NULL,
                takim_adi TEXT,
                lider_referans TEXT NOT NULL,
                uye1_referans TEXT,
                uye2_referans TEXT,
                uye3_referans TEXT,
                durum INTEGER DEFAULT 0
            )
        """)
        # ayarlar (turnir maglumatlary, bayraklar)
        db.execute("""
            CREATE TABLE IF NOT EXISTS ayarlar (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Default ayarlar
        defaults = {
            'turnir_senesi': '25 Iýul 2026',
            'turnir_wagty': '20:00 (TM)',
            'turnir_karta': 'Erangel',
            'turnir_gatnasym': 'Squad (4 kişi)',
            'turnir_tolek': '5 Manat',
            'turnir_tolek_usuly': 'TMCell SMS',
            'turnir_yer_sany': '100',
            'bayrak_1': '300 Manat|+ 🏆 Kubok',
            'bayrak_2': '150 Manat',
            'bayrak_3': '50 Manat',
            'bayrak_jemi': '500 M'
        }
        for key, value in defaults.items():
            db.execute("INSERT OR IGNORE INTO ayarlar (key, value) VALUES (?, ?)", (key, value))

        # Indeksler
        db.execute("CREATE INDEX IF NOT EXISTS idx_katilimci_ref ON katilimcilar(referans_kodu)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_katilimci_takim ON katilimcilar(takim_kodu)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_takim_kod ON takimlar(takim_kodu)")
        db.commit()


def get_ayar(key, default=''):
    db = get_db()
    row = db.execute('SELECT value FROM ayarlar WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_ayar(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO ayarlar (key, value) VALUES (?, ?)', (key, value))
    db.commit()


def generate_ref_code():
    db = get_db()
    while True:
        code = 'PUBG-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        existing = db.execute('SELECT 1 FROM katilimcilar WHERE referans_kodu = ?', (code,)).fetchone()
        if not existing:
            return code


def generate_csrf_token():
    token = secrets.token_urlsafe(32)
    _csrf_tokens[token] = datetime.now()
    return token


def validate_csrf_token(token):
    return token in _csrf_tokens


def send_telegram_message(message):
    if not CLOUDFLARE_WORKER_URL:
        return False
    try:
        response = requests.post(
            f"{CLOUDFLARE_WORKER_URL}/send-message",
            json={'message': message},
            timeout=10
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_stats():
    db = get_db()
    stats = db.execute("""
        SELECT 
            COUNT(*) as toplam,
            SUM(CASE WHEN odeme_durumu = 1 THEN 1 ELSE 0 END) as odeme_yapan,
            SUM(CASE WHEN admin_onay = 1 THEN 1 ELSE 0 END) as onaylanan
        FROM katilimcilar
    """).fetchone()
    yer_sany = int(get_ayar('turnir_yer_sany', '100'))
    return {
        'toplam': stats['toplam'] or 0,
        'odeme_yapan': stats['odeme_yapan'] or 0,
        'onaylanan': stats['onaylanan'] or 0,
        'yer_sany': yer_sany,
        'galan': max(0, yer_sany - (stats['toplam'] or 0))
    }


def get_turnir_data():
    return {
        'senesi': get_ayar('turnir_senesi'),
        'wagty': get_ayar('turnir_wagty'),
        'karta': get_ayar('turnir_karta'),
        'gatnasym': get_ayar('turnir_gatnasym'),
        'tolek': get_ayar('turnir_tolek'),
        'tolek_usuly': get_ayar('turnir_tolek_usuly')
    }


def get_bayraklar():
    b1 = get_ayar('bayrak_1').split('|')
    b2 = get_ayar('bayrak_2').split('|')
    b3 = get_ayar('bayrak_3').split('|')
    return {
        'bir': {'mukdar': b1[0], 'bonus': b1[1] if len(b1) > 1 else ''},
        'iki': {'mukdar': b2[0], 'bonus': b2[1] if len(b2) > 1 else ''},
        'uc': {'mukdar': b3[0], 'bonus': b3[1] if len(b3) > 1 else ''},
        'jemi': get_ayar('bayrak_jemi')
    }


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ===================== ROUTES =====================

@app.route('/')
def index():
    stats = get_stats()
    turnir = get_turnir_data()
    bayraklar = get_bayraklar()
    return render_template('index.html', stats=stats, turnir=turnir, bayraklar=bayraklar)


@app.route('/kayit')
def kayit():
    stats = get_stats()
    if stats['toplam'] >= stats['yer_sany']:
        return redirect(url_for('index'))
    return render_template('kayit.html')


@app.route('/api/kayit-ol', methods=['POST'])
def api_kayit_ol():
    data = request.get_json()

    csrf_token = data.get('csrf_token', '')
    if not validate_csrf_token(csrf_token):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})

    ad = data.get('ad', '').strip()
    pubg_id = data.get('pubg_id', '').strip()
    telefon = data.get('telefon', '').strip()
    ulasim = data.get('ulasim', '').strip()

    if not all([ad, pubg_id, telefon, ulasim]):
        return jsonify({'success': False, 'message': 'Ahli maglumatlary dolduryň!'})

    telefon_clean = telefon.replace(' ', '').replace('-', '').replace('+', '')
    if not telefon_clean.isdigit() or len(telefon_clean) < 8:
        return jsonify({'success': False, 'message': 'Telefon belgisi nadogry!'})

    stats = get_stats()
    if stats['toplam'] >= stats['yer_sany']:
        return jsonify({'success': False, 'message': 'Ähli ýerler doldy!'})

    ref_code = generate_ref_code()
    kayit_tarihi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    db.execute("""
        INSERT INTO katilimcilar (referans_kodu, ad, pubg_id, telefon, ulasim, kayit_tarihi)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ref_code, ad, pubg_id, telefon, ulasim, kayit_tarihi))
    db.commit()

    msg = f"""🎮 <b>TÄZE KATYLYJY!</b>

👤 Ady: <b>{ad}</b>
🆔 PUBG ID: <code>{pubg_id}</code>
📞 Telefon: <code>{telefon}</code>
💬 Ulaşmak: {ulasim}
🔑 Referans kody: <code>{ref_code}</code>
📅 Sene: {kayit_tarihi}

⏳ <b>Töleg garaşylýar...</b>"""

    send_telegram_message(msg)

    return jsonify({
        'success': True,
        'referans_kodu': ref_code,
        'message': 'Ustunlikli hasaba alyndyňyz!'
    })


@app.route('/odeme/<ref_code>')
def odeme(ref_code):
    db = get_db()
    katilimci = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (ref_code,)
    ).fetchone()
    if not katilimci:
        return redirect(url_for('index'))
    return render_template('odeme.html', katilimci=katilimci)


@app.route('/api/odeme-yapildi', methods=['POST'])
def api_odeme_yapildi():
    data = request.get_json()
    csrf_token = data.get('csrf_token', '')
    if not validate_csrf_token(csrf_token):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})

    ref_code = data.get('referans_kodu', '')
    db = get_db()
    katilimci = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (ref_code,)
    ).fetchone()
    if not katilimci:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})

    odeme_tarihi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute("""
        UPDATE katilimcilar SET odeme_durumu = 1, odeme_tarihi = ? WHERE referans_kodu = ?
    """, (odeme_tarihi, ref_code))
    db.commit()

    msg = f"""💰 <b>TÖLEG BILDIRIMI!</b>

👤 Ady: <b>{katilimci['ad']}</b>
🔑 Referans kody: <code>{ref_code}</code>
📞 Telefon: <code>{katilimci['telefon']}</code>
📅 Töleg senesi: {odeme_tarihi}

✅ <b>Admin tassyklamasy garaşylýar!</b>"""

    send_telegram_message(msg)
    return jsonify({'success': True, 'message': 'Töleg bildirimi ugradyldy!'})


@app.route('/profil/<ref_code>')
def profil(ref_code):
    db = get_db()
    katilimci = db.execute("""
        SELECT k.*, t.takim_adi, t.takim_kodu as t_kod
        FROM katilimcilar k
        LEFT JOIN takimlar t ON k.takim_kodu = t.takim_kodu
        WHERE k.referans_kodu = ?
    """, (ref_code,)).fetchone()
    if not katilimci:
        return redirect(url_for('index'))

    takim_arkadaslari = []
    if katilimci['takim_kodu']:
        takim_arkadaslari = db.execute("""
            SELECT ad, pubg_id, referans_kodu, admin_onay 
            FROM katilimcilar 
            WHERE takim_kodu = ? AND referans_kodu != ?
        """, (katilimci['takim_kodu'], ref_code)).fetchall()

    return render_template('profil.html', katilimci=katilimci, takim_arkadaslari=takim_arkadaslari)


@app.route('/takim/<ref_code>')
def takim(ref_code):
    db = get_db()
    katilimci = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (ref_code,)
    ).fetchone()
    if not katilimci:
        return redirect(url_for('index'))
    return render_template('takim.html', katilimci=katilimci)


@app.route('/api/takim-olustur', methods=['POST'])
def api_takim_olustur():
    data = request.get_json()
    csrf_token = data.get('csrf_token', '')
    if not validate_csrf_token(csrf_token):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})

    lider_ref = data.get('lider_ref', '')
    takim_adi = data.get('takim_adi', '').strip()

    if not takim_adi or len(takim_adi) < 2:
        return jsonify({'success': False, 'message': 'Topar ady 2 harpdan uly bolmaly!'})

    db = get_db()
    lider = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (lider_ref,)
    ).fetchone()
    if not lider:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    if lider['takim_kodu']:
        return jsonify({'success': False, 'message': 'Siz eýýäm topar bolduňyz!'})

    takim_kodu = 'TEAM-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    db.execute("""
        INSERT INTO takimlar (takim_kodu, takim_adi, lider_referans)
        VALUES (?, ?, ?)
    """, (takim_kodu, takim_adi, lider_ref))
    db.execute("""
        UPDATE katilimcilar SET takim_kodu = ?, takim_lideri = 1 WHERE referans_kodu = ?
    """, (takim_kodu, lider_ref))
    db.commit()

    return jsonify({'success': True, 'takim_kodu': takim_kodu, 'message': 'Topar üstünlikli döredildi!'})


@app.route('/api/takima-katil', methods=['POST'])
def api_takima_katil():
    data = request.get_json()
    csrf_token = data.get('csrf_token', '')
    if not validate_csrf_token(csrf_token):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})

    uye_ref = data.get('uye_ref', '')
    takim_kodu = data.get('takim_kodu', '').strip().upper()

    db = get_db()
    uye = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (uye_ref,)
    ).fetchone()
    if not uye:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    if uye['takim_kodu']:
        return jsonify({'success': False, 'message': 'Siz eýýäm topar bolduňyz!'})

    takim = db.execute(
        'SELECT * FROM takimlar WHERE takim_kodu = ?', (takim_kodu,)
    ).fetchone()
    if not takim:
        return jsonify({'success': False, 'message': 'Topar kody nädogry!'})

    uye_sayisi = db.execute(
        'SELECT COUNT(*) as say FROM katilimcilar WHERE takim_kodu = ?', (takim_kodu,)
    ).fetchone()['say']
    if uye_sayisi >= 4:
        return jsonify({'success': False, 'message': 'Bu topar eýýäm doly (4 kişi)!'})

    db.execute("""
        UPDATE katilimcilar SET takim_kodu = ? WHERE referans_kodu = ?
    """, (takim_kodu, uye_ref))
    if not takim['uye1_referans']:
        db.execute('UPDATE takimlar SET uye1_referans = ? WHERE takim_kodu = ?', (uye_ref, takim_kodu))
    elif not takim['uye2_referans']:
        db.execute('UPDATE takimlar SET uye2_referans = ? WHERE takim_kodu = ?', (uye_ref, takim_kodu))
    elif not takim['uye3_referans']:
        db.execute('UPDATE takimlar SET uye3_referans = ? WHERE takim_kodu = ?', (uye_ref, takim_kodu))
    db.commit()

    msg = f"""👥 <b>TOPARA TÄZE AGZA!</b>

Topar: <b>{takim['takim_adi']}</b>
Kody: <code>{takim_kodu}</code>

Täze agza: <b>{uye['ad']}</b>
PUBG ID: <code>{uye['pubg_id']}</code>

Topardaky agza sany: {uye_sayisi + 1}/4"""

    send_telegram_message(msg)
    return jsonify({'success': True, 'message': f'Topara üstünlikli goşuldyňyz! ({uye_sayisi + 1}/4)'})


# ===================== ADMIN PANEL =====================

@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')


@app.route('/api/admin-login', methods=['POST'])
def api_admin_login():
    data = request.get_json()
    sifre = data.get('sifre', '')
    if sifre != ADMIN_SIFRE:
        return jsonify({'success': False, 'message': 'Parol nädogry!'})
    session['admin_logged_in'] = True
    session.permanent = True
    return jsonify({'success': True, 'message': 'Giriş üstünlikli!'})


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin/panel')
@admin_required
def admin_panel():
    db = get_db()
    stats = db.execute("""
        SELECT 
            COUNT(*) as toplam,
            SUM(CASE WHEN odeme_durumu = 1 THEN 1 ELSE 0 END) as odeme_yapan,
            SUM(CASE WHEN admin_onay = 1 THEN 1 ELSE 0 END) as onaylanan
        FROM katilimcilar
    """).fetchone()

    katilimcilar = db.execute("""
        SELECT k.*, t.takim_adi 
        FROM katilimcilar k
        LEFT JOIN takimlar t ON k.takim_kodu = t.takim_kodu
        ORDER BY k.kayit_tarihi DESC
    """).fetchall()

    takimlar = db.execute("""
        SELECT t.*, k.ad as lider_ady
        FROM takimlar t
        JOIN katilimcilar k ON t.lider_referans = k.referans_kodu
        ORDER BY t.id DESC
    """).fetchall()

    turnir = get_turnir_data()
    bayraklar = get_bayraklar()

    return render_template('admin_panel.html', stats=stats, katilimcilar=katilimcilar, 
                          takimlar=takimlar, turnir=turnir, bayraklar=bayraklar)


@app.route('/api/admin-ayarlari-kaydet', methods=['POST'])
@admin_required
def api_admin_ayarlari_kaydet():
    data = request.get_json()
    csrf_token = data.get('csrf_token', '')
    if not validate_csrf_token(csrf_token):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})

    for key, value in data.items():
        if key != 'csrf_token' and value:
            set_ayar(key, value)
    return jsonify({'success': True, 'message': 'Ayarlar üstünlikli saklandy!'})


@app.route('/api/admin-onayla', methods=['POST'])
@admin_required
def api_admin_onayla():
    data = request.get_json()
    ref_code = data.get('referans_kodu', '')
    db = get_db()
    katilimci = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (ref_code,)
    ).fetchone()
    if not katilimci:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})

    onay_tarihi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute("""
        UPDATE katilimcilar SET admin_onay = 1, onay_tarihi = ? WHERE referans_kodu = ?
    """, (onay_tarihi, ref_code))
    db.commit()

    msg = f"""✅ <b>TASSYKLANDY!</b>

👤 Ady: <b>{katilimci['ad']}</b>
🔑 Referans kody: <code>{ref_code}</code>
📅 Tassyklama senesi: {onay_tarihi}

✅ <b>Katylyjy üstünlikli tassyklandy!</b>"""

    send_telegram_message(msg)
    return jsonify({'success': True, 'message': 'Katylyjy tassyklandy!'})


@app.route('/api/admin-reddet', methods=['POST'])
@admin_required
def api_admin_reddet():
    data = request.get_json()
    ref_code = data.get('referans_kodu', '')
    db = get_db()
    katilimci = db.execute(
        'SELECT * FROM katilimcilar WHERE referans_kodu = ?', (ref_code,)
    ).fetchone()
    if not katilimci:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})

    db.execute('UPDATE katilimcilar SET admin_onay = 2 WHERE referans_kodu = ?', (ref_code,))
    db.commit()

    msg = f"""❌ <b>RET EDILDI!</b>

👤 Ady: <b>{katilimci['ad']}</b>
🔑 Referans kody: <code>{ref_code}</code>
📅 Sene: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

❌ <b>Katylyjy ret edildi!</b>"""

    send_telegram_message(msg)
    return jsonify({'success': True, 'message': 'Katylyjy ret edildi!'})


@app.route('/api/katilimci/<ref_code>')
def api_katilimci(ref_code):
    db = get_db()
    katilimci = db.execute("""
        SELECT k.*, t.takim_adi 
        FROM katilimcilar k
        LEFT JOIN takimlar t ON k.takim_kodu = t.takim_kodu
        WHERE k.referans_kodu = ?
    """, (ref_code,)).fetchone()
    if not katilimci:
        return jsonify({'success': False})
    return jsonify({'success': True, 'katilimci': dict(katilimci)})


@app.route('/api/csrf-token')
def api_csrf_token():
    token = generate_csrf_token()
    return jsonify({'success': True, 'csrf_token': token})


# Programma başlanda database tablisalaryny döret
with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    
