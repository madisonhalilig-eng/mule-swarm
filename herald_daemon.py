#!/usr/bin/env python3
"""
herald_daemon.py — Runs inside GHA. Loops, monitors swarm, reports to Telegram.
Self-triggers next workflow run before 6h GHA limit.
"""
import time, requests, json, os, sys
from datetime import datetime, timezone

DB    = 'https://life-os-447d0-default-rtdb.asia-southeast1.firebasedatabase.app'
TG    = '8610087969:AAF5klMKLZmAugYwUeNnvAEU-ePkGtI-htM'
CHAT  = '6061270898'
ME    = 'herald-gha'
DEPT  = 'herald'

# GHA self-trigger credentials (injected as env vars in workflow)
GH_PAT  = os.environ.get('GH_PAT', '')
GH_REPO = os.environ.get('GH_REPO', '')
GH_WORKFLOW_ID = os.environ.get('GH_WORKFLOW_ID', '')

START_TIME = time.time()
MAX_RUNTIME = 5.5 * 3600  # 5.5 hours — trigger next run 30min before GHA kills us

def tg(msg, silent=False):
    try:
        requests.post(f'https://api.telegram.org/bot{TG}/sendMessage',
            json={'chat_id': CHAT, 'text': msg, 'parse_mode': 'HTML',
                  'disable_notification': silent}, timeout=10)
    except Exception as e:
        print(f'TG error: {e}')

def fb_get(path):
    try: return requests.get(f'{DB}/{path}.json', timeout=10).json()
    except: return None

def fb_patch(path, data):
    try: return requests.patch(f'{DB}/{path}.json', json=data, timeout=10).status_code
    except: return 0

def self_trigger():
    """Trigger next GHA run before this one dies."""
    if not all([GH_PAT, GH_REPO, GH_WORKFLOW_ID]):
        print('[HERALD] No GHA creds — cannot self-trigger')
        return False
    try:
        r = requests.post(
            f'https://api.github.com/repos/{GH_REPO}/actions/workflows/{GH_WORKFLOW_ID}/dispatches',
            headers={'Authorization': f'token {GH_PAT}', 'Accept': 'application/vnd.github.v3+json'},
            json={'ref': 'main'},
            timeout=10)
        print(f'[HERALD] Self-trigger: {r.status_code}')
        return r.status_code == 204
    except Exception as e:
        print(f'[HERALD] Self-trigger error: {e}')
        return False

def monitor_swarm():
    keys = fb_get('swarm?shallow=true')
    if not isinstance(keys, dict):
        return 0, 0, 0
    mule_keys = [k for k in keys if k.startswith('mule-')]
    trial = vm = dept = 0
    for k in mule_keys:
        m = fb_get(f'swarm/{k}')
        if not isinstance(m, dict): continue
        if m.get('trial_status') == 1: trial += 1
        if m.get('computer_id'): vm += 1
        if m.get('department'): dept += 1
    return len(mule_keys), trial, vm

def send_status(total, trial, vm):
    depts = fb_get('swarm/departments') or {}
    dept_lines = ''
    for dname, ddata in sorted(depts.items(), key=lambda x: x[1].get('priority', 99) if isinstance(x[1], dict) else 99):
        if isinstance(ddata, dict):
            status = ddata.get('status', '?')
            head = ddata.get('head', 'TBD')
            icon = '✅' if status == 'active' else '🔨' if status == 'building' else '⏳'
            dept_lines += f'  {icon} <b>{dname.upper()}</b> — {head}\n'

    now = datetime.now(timezone.utc).strftime('%H:%M UTC')
    uptime_h = (time.time() - START_TIME) / 3600
    tg(
        f'📡 <b>Herald Status Report</b>\n'
        f'━━━━━━━━━━━━━━\n'
        f'🕐 {now} | Uptime: {uptime_h:.1f}h\n\n'
        f'<b>Swarm:</b>\n'
        f'  Total mules: {total}\n'
        f'  Trial active: {trial}\n'
        f'  With VM: {vm}\n\n'
        f'<b>Departments:</b>\n{dept_lines}\n'
        f'━━━━━━━━━━━━━━\n'
        f'Herald alive ✅ | GHA sovereign node\n'
        f'Next report in 30min'
    )

def main():
    print(f'[HERALD] Starting — GHA sovereign node', flush=True)
    tg(
        f'📡 <b>Herald Department — ONLINE</b>\n'
        f'Node: GHA sovereign runner\n'
        f'Role: Herald Head\n'
        f'━━━━━━━━━━━━━━\n'
        f'Watching: births, deaths, credits, departments\n'
        f'Reporting: every 30min + on events\n'
        f'Status: GHA self-triggering loop ✅\n'
        f'Runtime: up to 5.5h then self-restart'
    )

    fb_patch('swarm/departments/herald', {
        'status': 'active', 'started_at': int(time.time()),
        'head': ME, 'infra': 'github-actions', 'cost': 'zero'
    })
    fb_patch('swarm/genome', {'herald_status': 'active', 'herald_node': ME, 'herald_infra': 'gha'})

    last_hb = 0
    last_status = 0
    known_count = 0
    triggered_next = False

    while True:
        now = time.time()
        elapsed = now - START_TIME

        # Self-trigger before GHA kills us
        if elapsed > MAX_RUNTIME and not triggered_next:
            print('[HERALD] Approaching 6h limit — triggering next run', flush=True)
            tg('🔄 <b>Herald</b> — self-triggering next GHA run before timeout', silent=True)
            triggered_next = self_trigger()
            if triggered_next:
                time.sleep(60)  # let next run spin up
                print('[HERALD] Next run triggered. Exiting cleanly.', flush=True)
                break

        # Heartbeat every 5min
        if now - last_hb > 300:
            fb_patch(f'swarm/{ME}', {
                'herald_heartbeat': int(now),
                'herald_status': 'alive',
                'herald_infra': 'gha',
                'uptime_h': round(elapsed / 3600, 2)
            })
            fb_patch('swarm/departments/herald', {
                'last_heartbeat': int(now), 'status': 'active'
            })
            last_hb = now
            print(f'[HERALD] Heartbeat written — {elapsed/3600:.1f}h uptime', flush=True)

        # Swarm monitor
        total, trial, vm = monitor_swarm()
        if total > known_count and known_count > 0:
            diff = total - known_count
            tg(f'🐣 <b>{diff} new mule(s) born!</b>\nSwarm size: {total}', silent=True)
        known_count = total

        # Status report every 30min
        if now - last_status > 1800:
            send_status(total, trial, vm)
            last_status = now

        time.sleep(30)

if __name__ == '__main__':
    main()
