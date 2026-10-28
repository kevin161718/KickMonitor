"""Kick Guard: read-only channel monitoring. No viewer generation."""
from flask import Flask, jsonify, render_template, request
import os, re, time, sqlite3, json, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

app = Flask(__name__)
app.json.ensure_ascii = False
ROOT=Path(__file__).parent
DB=Path(os.getenv('SQLITE_PATH',str(ROOT/'kick_guard.db')))
IS_VERCEL=bool(os.getenv('VERCEL'))
CHANNEL_RE=re.compile(r'^[a-zA-Z0-9_-]{2,35}$')

def normalize_channel(raw):
    val=str(raw or '').strip().lower().rstrip('/')
    if 'kick.com/' in val: val=val.split('kick.com/',1)[1].split('/',1)[0].split('?',1)[0]
    return val if CHANNEL_RE.fullmatch(val) else None

def fetch_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'KickGuardMonitoring/1.0 (Read-only dashboard)','Accept':'application/json','Referer':'https://kick.com/'})
    with urllib.request.urlopen(req,timeout=9) as resp:
        if resp.status!=200: raise ValueError(f'HTTP {resp.status}')
        return json.load(resp)

def db():
    con=sqlite3.connect(DB,timeout=5)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, channel TEXT NOT NULL, ts INTEGER NOT NULL, viewers INTEGER, online INTEGER NOT NULL, source TEXT NOT NULL)')
    con.execute('CREATE INDEX IF NOT EXISTS ix_channel_ts ON samples(channel,ts)')
    return con

@app.get('/')
def index(): return render_template('index.html')

@app.get('/api/health')
def health(): return jsonify({'ok':True,'storage':'browser (Vercel)' if IS_VERCEL else 'SQLite local + navegador','time':int(time.time())})

@app.get('/api/channel/<channel>')
def channel_info(channel):
    name=normalize_channel(channel)
    if not name: return jsonify({'error':'Nombre de canal inválido'}),400
    try:
        # Endpoint público de web no documentado; puede cambiar o restringirse.
        data=fetch_json(f'https://kick.com/api/v2/channels/{name}')
        live=data.get('livestream') or {}
        is_online=bool(live)
        viewer=live.get('viewer_count') if is_online else None
        source='kick.com/api/v2/channels'
        if is_online and viewer is None and live.get('id'):
            try:
                counts=fetch_json(f'https://kick.com/current-viewers?ids[]={int(live["id"])}')
                if isinstance(counts,list) and counts and isinstance(counts[0],dict):
                    viewer=counts[0].get('viewers')
                    source='kick.com/current-viewers'
            except Exception:
                pass
        viewer=int(viewer) if viewer is not None and str(viewer).isdigit() else None
        result={'channel':name,'channel_id':data.get('id'),'stream_id':live.get('id'), 'online':is_online,'viewers':viewer,'title':live.get('session_title') or live.get('title') or '', 'at':int(time.time()),'source':source}
        if not IS_VERCEL:
            try:
                with db() as con:
                    con.execute('INSERT INTO samples(channel,ts,viewers,online,source) VALUES(?,?,?,?,?)',(name,result['at'],viewer,int(is_online),source))
                    con.execute('DELETE FROM samples WHERE ts < ?', (int(time.time())-400*86400,))
            except (sqlite3.Error,OSError): pass
        response=jsonify(result);response.headers['Cache-Control']='no-store';return response
    except urllib.error.HTTPError as err:
        status=err.code
        return jsonify({'error':f'Kick respondió HTTP {status}. Puede bloquear consultas externas.','channel':name}), 503 if status in (403,429) else 502
    except Exception as err:
        return jsonify({'error':'No fue posible obtener datos de Kick. Revisá el canal o intentá más tarde.','detail':str(err)[:140]}),502

@app.get('/api/history/<channel>')
def history(channel):
    name=normalize_channel(channel)
    if not name:return jsonify({'error':'Canal inválido'}),400
    if IS_VERCEL:return jsonify({'samples':[],'note':'Historial guardado en el navegador en Vercel'})
    try:
        with db() as con:
            rows=con.execute('SELECT ts,viewers,online FROM samples WHERE channel=? ORDER BY ts DESC LIMIT 2000',(name,)).fetchall()
        return jsonify({'samples':[{'at':a,'viewers':v,'online':bool(o)} for a,v,o in reversed(rows)]})
    except (sqlite3.Error,OSError):return jsonify({'samples':[]})


@app.get('/api/stats/<channel>')
def stats(channel):
    """Server-side calendar summaries for local deployments; browser fallback on Vercel."""
    name=normalize_channel(channel)
    if not name:return jsonify({'error':'Canal inválido'}),400
    if IS_VERCEL:return jsonify({'storage':'browser','groups':{},'note':'Vercel no tiene base SQLite persistente'})
    try:
        from zoneinfo import ZoneInfo
        from collections import defaultdict
        zone=ZoneInfo(os.getenv('ANALYTICS_TIMEZONE','America/Montevideo'))
        with db() as con:
            records=con.execute('SELECT ts,viewers FROM samples WHERE channel=? AND ts>=? AND viewers IS NOT NULL ORDER BY ts',(name,int(time.time())-400*86400)).fetchall()
        groups={k:defaultdict(lambda:{'sum':0,'n':0,'peak':0}) for k in ('hour','day','month')}
        for ts,viewers in records:
            stamp=datetime.fromtimestamp(ts,zone)
            for kind,key in [('hour',stamp.strftime('%Y-%m-%d-%H')),('day',stamp.strftime('%Y-%m-%d')),('month',stamp.strftime('%Y-%m'))]:
                item=groups[kind][key];item['sum']+=viewers;item['n']+=1;item['peak']=max(item['peak'],viewers)
        return jsonify({'storage':'sqlite','channel':name,'timezone':str(zone),'groups':{kind:[{'period':key,'average':round(item['sum']/item['n'],2),'peak':item['peak'],'samples':item['n']} for key,item in sorted(entries.items())] for kind,entries in groups.items()}})
    except (sqlite3.Error,OSError,KeyError) as err:
        return jsonify({'error':'No se pudieron calcular las estadísticas','detail':str(err)[:140]}),500

if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.getenv('PORT',5000)),debug=False)
