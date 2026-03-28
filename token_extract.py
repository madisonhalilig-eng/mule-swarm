import sys, os, time, json, requests, traceback, random, string, re, uuid, hashlib

EMAIL    = os.environ.get("SIGNUP_EMAIL", "")
REFERRAL = os.environ.get("REFERRAL_CODE", "2LQB6HJMFQG9")
CARD_NUM  = os.environ.get("CARD_NUM",  "4834420888062209")
CARD_EXP  = os.environ.get("CARD_EXP",  "03/30")
CARD_CVV  = os.environ.get("CARD_CVV",  "750")
CARD_NAME = os.environ.get("CARD_NAME", "Madison Halili")
PASSWORD = "Seeker2026!!"
PASSWORD_HASH = hashlib.sha256(PASSWORD.encode()).hexdigest()
os.environ.setdefault("DISPLAY", ":99")

BOT = "8610087969:AAF5klMKLZmAugYwUeNnvAEU-ePkGtI-htM"
CHAT = "6061270898"
FIREBASE = "https://life-os-447d0-default-rtdb.asia-southeast1.firebasedatabase.app"

def get_mailporary_email():
    r = requests.get("https://mailporary.com/", timeout=15)
    jwt_match = re.search(r"(eyJhbGciOiJIUzI1NiJ9\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)", r.text)
    if not jwt_match: return None, None
    jwt = jwt_match.group(1)
    domains = ["sisood.com","disefl.com","suarj.com","mfxis.com","anogz.com","oeralb.com"]
    uname = "".join(random.choices(string.ascii_lowercase, k=9))
    return f"{uname}@{random.choice(domains)}", jwt

def extract_otp(body_text):
    m = re.search(r"special verification code\.\s*\n+\s*([A-Z0-9]{4,8})\b", body_text)
    if m: return m.group(1)
    for line in body_text.split("\n"):
        line = line.strip()
        if re.match(r"^[A-Z0-9]{4,8}$", line) and not line.isdigit():
            if line not in {"MULERUN","EMAIL","CODE","YOUR","HERE","DONE","CLICK"}:
                return line
    return None

def get_otp(email, jwt, timeout=90):
    encoded = requests.utils.quote(email, safe="")
    headers = {"Authorization": f"Bearer {jwt}", "X-Request-ID": str(uuid.uuid4()), "X-Timestamp": str(int(time.time()))}
    for i in range(timeout // 10):
        headers["X-Request-ID"] = str(uuid.uuid4())
        headers["X-Timestamp"] = str(int(time.time()))
        try:
            mr = requests.get(f"https://web.mailporary.com/api/v1/mailbox/{encoded}", headers=headers, timeout=10)
            msgs = mr.json() if mr.status_code == 200 else []
            if msgs:
                headers["X-Request-ID"] = str(uuid.uuid4())
                headers["X-Timestamp"] = str(int(time.time()))
                mr2 = requests.get(f"https://web.mailporary.com/api/v1/mailbox/{encoded}/{msgs[0]['id']}", headers=headers, timeout=10)
                otp = extract_otp(mr2.json().get("body", {}).get("text", ""))
                if otp:
                    print(f"OTP: {otp}", flush=True)
                    return otp
        except Exception as e:
            print(f"Poll error: {e}", flush=True)
        time.sleep(10)
    return None

def tg(msg):
    try: requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", json={"chat_id": CHAT, "text": msg}, timeout=5)
    except: pass

if not EMAIL:
    EMAIL, MAIL_JWT = get_mailporary_email()
    if not EMAIL: sys.exit("No email")
    print(f"Email: {EMAIL}", flush=True)
else:
    r = requests.get("https://mailporary.com/", timeout=15)
    m = re.search(r"(eyJhbGciOiJIUzI1NiJ9\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)", r.text)
    MAIL_JWT = m.group(1) if m else None

NICK = "mk" + "".join(random.choices(string.ascii_lowercase, k=4)) + str(int(time.time()) % 9999)
print(f"=== {EMAIL} / {NICK} ===", flush=True)

def run_js(sb, code):
    try: return sb.cdp.evaluate(f"(function(){{{code}}})()")
    except:
        try: return sb.execute_script(f"(function(){{{code}}})()")
        except: return None

def react_set(sb, sel, val):
    run_js(sb, f"""
        var el=document.querySelector({json.dumps(sel)});
        if(!el)return;
        var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,"value").set;
        s.call(el,{json.dumps(val)});
        el.dispatchEvent(new Event("input",{{bubbles:true}}));
        el.dispatchEvent(new Event("change",{{bubbles:true}}));
    """)

from seleniumbase import SB
with SB(uc=True, headless=False, xvfb=False) as sb:
    # Visit referral link to set cookie
    sb.open(f"https://mulerun.com/invitation/{REFERRAL}")
    sb.sleep(3)
    
    # Verify cookie was set
    cookies = {c["name"]: c["value"] for c in sb.get_cookies()}
    print(f"referral_code cookie: {cookies.get('referral_code', 'NOT SET')}", flush=True)
    
    # Should auto-redirect to /signup, but navigate explicitly if not
    if "signup" not in sb.get_current_url():
        sb.open("https://mulerun.com/signup")
        sb.sleep(3)
    
    # Click "Sign up with Email"
    try: sb.click('button:contains("Sign up with Email")', timeout=5)
    except: pass
    sb.sleep(2)

    # Fill form
    react_set(sb, 'input[name="email"]', EMAIL)
    react_set(sb, 'input[type="password"]', PASSWORD_HASH)
    react_set(sb, 'input[name="username"]', NICK)
    sb.sleep(1)

    # Solve Turnstile
    print("Solving Turnstile...", flush=True)
    try: sb.uc_gui_handle_captcha()
    except: pass
    sb.sleep(3)

    # Check token
    token = run_js(sb, "return document.querySelector('[name=cf-turnstile-response]') ? document.querySelector('[name=cf-turnstile-response]').value : ''")
    token = str(token) if token else ""
    print(f"TOKEN_LEN={len(token)}", flush=True)

    if len(token) < 100:
        print(f"❌ Turnstile failed (len={len(token)})", flush=True)
        sys.exit("No token")

    # Submit via requests (same pattern that got 200 before) with cookie
    payload = {"username": NICK, "email": EMAIL, "password": PASSWORD_HASH, "token": token, "referralCode": REFERRAL}
    hdrs = {"Content-Type":"application/json","Origin":"https://mulerun.com",
            "Referer":"https://mulerun.com/signup","Cookie":f"referral_code={REFERRAL}"}
    resp = requests.post("https://mulerun.com/auth/local/pre-register", json=payload, headers=hdrs, timeout=30)
    print(f"pre-register: {resp.status_code} {resp.text[:200]}", flush=True)

    if resp.status_code == 200 and '"ok"' in resp.text:
        print("Polling OTP...", flush=True)
        otp = get_otp(EMAIL, MAIL_JWT)
        if not otp:
            print(f"❌ OTP timeout email={EMAIL}", flush=True)
            sys.exit("No OTP")

        # Register AND process-pending-signup via BROWSER XHR
        # This way browser gets Set-Cookie session from /register,
        # then immediately fires /user/impact/process-pending-signup 
        # with that session + the referral_code cookie still in the jar
        print("Registering + activating referral via browser XHR...", flush=True)
        xhr_result = run_js(sb, f"""
            var done = false;
            var result = {{}};
            
            // Step 1: Register via XHR (browser gets session cookie from Set-Cookie)
            var xhr1 = new XMLHttpRequest();
            xhr1.open('POST', 'https://mulerun.com/auth/local/register', false); // sync
            xhr1.setRequestHeader('Content-Type', 'application/json');
            xhr1.withCredentials = true;
            xhr1.send(JSON.stringify({{
                email: '{EMAIL}',
                code: '{otp}',
                username: '{NICK}',
                password: '{PASSWORD_HASH}'
            }}));
            result.register_status = xhr1.status;
            result.register_body = xhr1.responseText.substring(0, 200);
            
            // Step 2: If register OK, call process-pending-signup (browser now has session cookie)
            if (xhr1.status === 200 && xhr1.responseText.indexOf('ok') !== -1) {{
                var xhr2 = new XMLHttpRequest();
                xhr2.open('POST', 'https://mulerun.com/user/impact/process-pending-signup', false); // sync
                xhr2.withCredentials = true;
                xhr2.send(null);
                result.pending_status = xhr2.status;
                result.pending_body = xhr2.responseText.substring(0, 200);
                
                // Step 3: Check current balance to confirm
                var xhr3 = new XMLHttpRequest();
                xhr3.open('GET', 'https://mulerun.com/user/balance', false); // sync
                xhr3.withCredentials = true;
                xhr3.send(null);
                result.balance_status = xhr3.status;
                result.balance_body = xhr3.responseText.substring(0, 300);
            }}
            
            return JSON.stringify(result);
        """)
        print(f"XHR chain result: {{xhr_result}}", flush=True)

        # Parse result
        import json as _json
        referral_activated = False
        balance_info = "unknown"
        pending_status = 0
        try:
            res = _json.loads(str(xhr_result))
            reg_status = res.get('register_status', 0)
            reg_body = res.get('register_body', '')
            pending_status = res.get('pending_status', 0)
            pending_body = res.get('pending_body', '')
            balance_status = res.get('balance_status', 0)
            balance_body = res.get('balance_body', '')
            print("Register: " + str(reg_status) + " " + reg_body, flush=True)
            print("process-pending-signup: " + str(pending_status) + " " + pending_body, flush=True)
            print("Balance: " + str(balance_status) + " " + balance_body, flush=True)
            referral_activated = pending_status in [200, 201, 204]
            balance_info = balance_body[:100]
        except Exception as pe:
            print("Parse error: " + str(pe) + " | raw: " + str(xhr_result)[:200], flush=True)

        mule_name = "mule-" + "".join(random.choices(string.ascii_lowercase, k=4))
        entry = {
            "name": mule_name,
            "email": EMAIL,
            "username": NICK,
            "password": PASSWORD,
            "referral": REFERRAL,
            "created_at": int(time.time()),
            "method": "GHA-v5",
            "status": "registered",
            "referral_activated": referral_activated,
            "balance": balance_info
        }
        try:
            with open("swarm_backup.jsonl", "a") as bf:
                bf.write(_json.dumps(entry) + "\n")
        except Exception as we:
            print("Backup write error: " + str(we), flush=True)
        try:
            requests.patch(FIREBASE + "/swarm/" + mule_name + ".json", json=entry, timeout=10)
        except Exception as fe:
            print("Firebase error: " + str(fe), flush=True)
        tg_msg = ("✅ NEW MULE\n"
                  "Name: " + mule_name + "\n"
                  "Email: " + EMAIL + "\n"
                  "Nick: " + NICK + "\n"
                  "Referral: " + REFERRAL + "\n"
                  "pending_signup HTTP: " + str(pending_status) + "\n"
                  "Balance: " + balance_info[:80] + "\n"
                  "referral_activated: " + str(referral_activated))
        tg(tg_msg)
        print("SUCCESS: " + mule_name, flush=True)

        # DEBUG: find where trial/upgrade button lives
        try:
            import time as _dbt
            print("Post-reg URL: " + sb.get_current_url(), flush=True)
            # Check /chat (home after login)
            sb.open("https://mulerun.com/chat")
            _dbt.sleep(4)
            _chat_btns = run_js(sb, "return Array.from(document.querySelectorAll('button,a,[role=button]')).map(function(e){return e.textContent.trim().substring(0,50);}).filter(function(s){return /upgrade|trial|super|plan|billing|subscri/i.test(s);}).join(' | ');")
            print("Chat upgrade btns: " + str(_chat_btns), flush=True)
            # Check /workspace
            sb.open("https://mulerun.com/workspace")
            _dbt.sleep(4)
            _ws_btns = run_js(sb, "return Array.from(document.querySelectorAll('button,a,[role=button]')).map(function(e){return e.textContent.trim().substring(0,50);}).filter(function(s){return /upgrade|trial|super|plan|billing|subscri/i.test(s);}).join(' | ');")
            print("Workspace upgrade btns: " + str(_ws_btns), flush=True)
            # Check /workspace/account
            sb.open("https://mulerun.com/workspace/account")
            _dbt.sleep(4)
            _acc_url = sb.get_current_url()
            _acc_btns = run_js(sb, "return Array.from(document.querySelectorAll('button,a,[role=button]')).map(function(e){return e.textContent.trim().substring(0,50);}).filter(function(s){return s.length>2;}).join(' | ');")
            print("Account URL: " + _acc_url + " btns: " + str(_acc_btns)[:200], flush=True)
            # Check /workspace/plans or /pricing
            for _path in ["/workspace/plans", "/pricing", "/workspace/upgrade"]:
                sb.open("https://mulerun.com" + _path)
                _dbt.sleep(3)
                _purl = sb.get_current_url()
                _ptitle = run_js(sb, "return document.title;")
                print(_path + " -> " + _purl + " title:" + str(_ptitle), flush=True)
        except Exception as _dbe:
            print("Debug err: " + str(_dbe), flush=True)

        # DEBUG: post-registration state
        try:
            import time as _dbt
            print("URL after register: " + sb.get_current_url(), flush=True)
            _all_c = [c["name"]+"="+c["value"][:15] for c in sb.get_cookies()]
            print("Cookies: " + str(_all_c), flush=True)
            sb.open("https://mulerun.com")
            _dbt.sleep(3)
            print("Home URL: " + sb.get_current_url(), flush=True)
            sb.open("https://mulerun.com/workspace/billing")
            _dbt.sleep(5)
            print("Billing URL: " + sb.get_current_url(), flush=True)
            print("Billing title: " + str(run_js(sb, "return document.title;")), flush=True)
            _btns = run_js(sb, "return Array.from(document.querySelectorAll('button,a')).map(function(e){return e.textContent.trim().substring(0,40);}).filter(function(s){return s.length>1;}).slice(0,20).join(' | ');")
            print("Billing buttons: " + str(_btns), flush=True)
        except Exception as _dbe:
            print("Debug err: " + str(_dbe), flush=True)
        # Save JWT while browser still open
        import time as _jwt_t
        try:
            _jwt = next((c["value"] for c in sb.get_cookies() if c["name"] == "token"), None)
            if _jwt and len(str(_jwt)) > 30:
                requests.patch(FIREBASE + "/swarm/" + mule_name + ".json",
                    json={"jwt_token": _jwt, "jwt_saved_at": int(_jwt_t.time())}, timeout=10)
                print("JWT saved", flush=True)
            else:
                print("JWT not found in cookies", flush=True)
        except Exception as _je:
            print("JWT save error: " + str(_je), flush=True)

        # Trial handled by separate Trial Activator workflow (clean IP per job)
# SAVE JWT TO FIREBASE — enables trial activator to work without re-login
# ============================================================
if mule_name:
    import time as _jwt_time
    try:
        _jwt = next((c["value"] for c in sb.get_cookies() if c["name"] == "token"), None)
        if not _jwt:
            try: _jwt = sb.execute_script("return localStorage.getItem('token');")
            except: pass
        if _jwt and len(str(_jwt)) > 30:
            requests.patch(FIREBASE + "/swarm/" + mule_name + ".json",
                json={"jwt_token": _jwt, "jwt_saved_at": int(_jwt_time.time())}, timeout=10)
            print("JWT saved to Firebase", flush=True)
        else:
            print("JWT not found in session", flush=True)
    except Exception as _je:
        print("JWT save error: " + str(_je), flush=True)


# Dispatch Trial Activator for this mule (separate job = clean IP each time)
if mule_name:
    try:
        import os as _os2
        _gh_token = _os2.environ.get("GH_DISPATCH_TOKEN", "")
        if _gh_token:
            _ta_r = requests.post(
                "https://api.github.com/repos/moreshiofficial-rgb/mule-swarm/actions/workflows/252592321/dispatches",
                headers={"Authorization": "token " + _gh_token,
                         "Accept": "application/vnd.github.v3+json"},
                json={"ref": "main", "inputs": {
                    "mule_name": mule_name,
                    "account_email": EMAIL,
                    "account_password": "Seeker2026!!"
                }}, timeout=15)
            print("Trial Activator dispatched: HTTP " + str(_ta_r.status_code), flush=True)
        else:
            print("Trial Activator: GH_DISPATCH_TOKEN not set", flush=True)
    except Exception as _tae:
        print("Trial Activator dispatch err: " + str(_tae)[:60], flush=True)

print("Birth+trial complete for " + (mule_name or EMAIL), flush=True)


# ============================================================
# WORKER BOOT — Start job queue loop after successful signup
# Every mule born becomes a producer automatically
# ============================================================
import subprocess as _sp, os as _os

if mule_name and entry.get("status") == "registered":
    try:
        # job_worker.py is in the repo — already checked out by GHA
        import shutil as _sh
        _wpath = "/home/runner/work/mule-swarm/mule-swarm/job_worker.py"
        _wpath2 = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "job_worker.py")
        if not _os.path.exists(_wpath) and _os.path.exists(_wpath2):
            _wpath = _wpath2

        if _os.path.exists(_wpath):
            _sp.Popen(
                ["nohup", "python3", _wpath, "--department", "producer", "--id", mule_name],
                stdout=open(f"/tmp/{mule_name}_worker.log", "w"),
                stderr=_sp.STDOUT,
                start_new_session=True
            )
            print(f"Worker loop started: {mule_name} | department=producer", flush=True)
            requests.patch(f"{FIREBASE}/swarm/{mule_name}.json",
                json={"worker_loop": "started", "department": "producer"}, timeout=10)
        else:
            print("job_worker.py not found — skipping worker boot", flush=True)
    except Exception as _we:
        print(f"Worker boot error: {_we}", flush=True)

print("=== DONE ===", flush=True)
