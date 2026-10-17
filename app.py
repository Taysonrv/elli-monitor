import json
import argparse
import os
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()


def read(name, default):
    path = ROOT / name
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def save(name, value):
    path = ROOT / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def config():
    return read('config.json', {})


def telegram(message):
    cfg = config()
    token = os.environ.get('TELEGRAM_BOT_TOKEN') or cfg.get('telegram_token')
    chat = os.environ.get('TELEGRAM_CHAT_ID') or cfg.get('telegram_chat_id')
    if not token or not chat:
        raise ValueError('Configure o token e o chat_id do Telegram em config.json.')
    request = urllib.request.Request(
        'https://api.telegram.org/bot' + token + '/sendMessage',
        data=json.dumps({'chat_id': chat, 'text': message}).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise ValueError('Telegram recusou a mensagem. Verifique as credenciais.')
    except urllib.error.HTTPError as error:
        messages = {
            401: 'Token do Telegram inválido. Confira telegram_token em config.json.',
            404: 'Endpoint do bot não encontrado. Confira o formato do token.',
            400: 'Telegram recusou o destino ou os dados. Confira telegram_chat_id e envie /start ao seu bot.',
            403: 'O bot não tem permissão para enviar. Desbloqueie o bot e envie /start; em grupos, confira as permissões.',
            429: 'Limite de mensagens do Telegram atingido. Aguarde antes de tentar novamente.'
        }
        raise ValueError(messages.get(error.code, f'Telegram respondeu HTTP {error.code}. Tente novamente mais tarde.')) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError('Não foi possível conectar ao Telegram. Confira internet, proxy, VPN e certificados HTTPS.') from None


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('records'), list):
        raise ValueError('O arquivo precisa conter uma lista records.')
    seen = set()
    for row in data['records']:
        if not isinstance(row, dict) or row.get('source') not in ('metricool', 'shop', 'affiliate'):
            raise ValueError('Cada registro precisa de source: metricool, shop ou affiliate.')
        key = (row['source'], row.get('id'))
        if not isinstance(key[1], str) or not key[1] or key in seen:
            raise ValueError('Use IDs de texto únicos por origem.')
        seen.add(key)
        for field in ('views', 'likes', 'comments', 'shares', 'revenue', 'commission'):
            if field in row and (isinstance(row[field], bool) or not isinstance(row[field], (int, float)) or not 0 <= row[field] < 1e15):
                raise ValueError('Valores numéricos inválidos em ' + field)
    return data


def ingest(data):
    validate(data)
    with LOCK:
        state = read('state.json', {'seen': [], 'alerts': [], 'pending': []})
        seen = set(state['seen'])
        records = read('data.json', {'records': []})['records']
        indexed = {(r['source'], r['id']): r for r in records}
        for row in data['records']:
            indexed[(row['source'], row['id'])] = row
            key = row['source'] + ':' + row['id']
            if key not in seen and row['source'] in ('shop', 'affiliate'):
                label = 'Pedido da loja' if row['source'] == 'shop' else 'Conversão de afiliada'
                message = f"{label}: {row.get('title', row['id'])} | Receita R$ {row.get('revenue', 0):.2f} | Comissão R$ {row.get('commission', 0):.2f}"
                alert = {'id': key, 'text': message, 'time': datetime.now(timezone.utc).isoformat()}
                state['alerts'].insert(0, alert)
                state['pending'].append(alert)
            seen.add(key)
        state['seen'] = sorted(seen)
        save('data.json', {'records': list(indexed.values()), 'updated_at': datetime.now(timezone.utc).isoformat()})
        save('state.json', state)


def flush():
    with LOCK:
        cfg = config()
        if not cfg.get('telegram_enabled', False):
            return
        state = read('state.json', {'seen': [], 'alerts': [], 'pending': []})
        while state['pending']:
            telegram(state['pending'][0]['text'])
            state['pending'].pop(0)
            save('state.json', state)


def worker():
    while True:
        try:
            inbox = ROOT / 'inbox.json'
            if inbox.exists():
                ingest(read('inbox.json', {}))
                inbox.unlink()
            flush()
            save('health.json', {'error': None, 'checked_at': datetime.now(timezone.utc).isoformat()})
        except Exception as error:
            save('health.json', {'error': str(error), 'checked_at': datetime.now(timezone.utc).isoformat()})
        time.sleep(30)


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/status':
            with LOCK:
                cfg = config()
                self.reply(200, {'data': read('data.json', {'records': [], 'updated_at': None}),
                    'state': read('state.json', {'alerts': [], 'pending': []}),
                    'health': read('health.json', {}),
                    'telegram': bool(cfg.get('telegram_enabled') and
                        (cfg.get('telegram_token') or os.environ.get('TELEGRAM_BOT_TOKEN')) and
                        (cfg.get('telegram_chat_id') or os.environ.get('TELEGRAM_CHAT_ID')))})
        elif self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write((ROOT / 'index.html').read_bytes())
        else:
            self.reply(404, {'error': 'Não encontrado'})

    def do_POST(self):
        if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.reply(403, {'error': 'Origem bloqueada'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'Envie JSON'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2_000_000:
                raise ValueError('Tamanho inválido')
            payload = json.loads(self.rfile.read(length))
            if self.path == '/api/import':
                ingest(payload)
                self.reply(200, {'message': 'Dados importados. Alertas disponíveis no painel; Telegram processado em até 30 segundos.'})
            elif self.path == '/api/test-telegram':
                telegram('Elli Monitor: conexão de notificações funcionando.')
                self.reply(200, {'message': 'Mensagem de teste enviada.'})
            else:
                self.reply(404, {'error': 'Não encontrado'})
        except (ValueError, json.JSONDecodeError) as error:
            self.reply(400, {'error': str(error)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Elli Monitor local')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('A porta deve estar entre 1 e 65535.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    threading.Thread(target=worker, daemon=True).start()
    print(f'Elli Monitor: http://127.0.0.1:{args.port} — Ctrl+C para encerrar', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nElli Monitor encerrado.')
    finally:
        server.server_close()

