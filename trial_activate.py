import os, time, requests, hashlib, json as _json
from seleniumbase import SB
from selenium.webdriver.common.keys import Keys

EMAIL    = os.environ["ACCOUNT_EMAIL"]
PASSWORD = os.environ.get("ACCOUNT_PASSWORD", "Seeker2026!!")
MULE     = os.environ["MULE_NAME"]
CARD_NUM = os.environ["CARD_NUM"]
CARD_EXP = os.environ["CARD_EXP"]
CARD_CVV = os.environ["CARD_CVV"]
CARD_NAME = os.environ["CARD_NAME"]
FIREBASE  = os.environ["FIREBASE_URL"]
TG_TOKEN  = os.environ["TG_TOKEN"]
TG_CHAT   = os.environ["TG_CHAT"]

ADDR_LINE1 = "7734 J.B Roxas Olympia"
ADDR_CITY  = "Makati City"
ADDR_ZIP   = "1207"

def tg(msg):
    try: requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg}, timeout=10)
    except: pass

def fb(data):
    requests.patch(f"{FIREBASE}/swarm/{MULE}.json", json=data, timeout=10)

def fill(sb, sel, val):
    """Fill using execCommand insertText — confirmed working on Stripe inputs"""
    import json as _json
    try:
        js = """(function(){
            var el = document.querySelector(""" + _json.dumps(sel) + """);
            if(!el) return 'not found';
            el.focus(); el.click();
            document.execCommand('selectAll');
            document.execCommand('delete');
            document.execCommand('insertText', false, """ + _json.dumps(str(val)) + """);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            el.blur();
            return el.value;
        })()"""
        result = sb.cdp.evaluate(js)
        print(f"  filled {sel[:40]}: {str(result)[:20]}", flush=True)
        return True
    except Exception as e:
        print(f"  fill fail {sel[:40]}: {str(e)[:60]}", flush=True)
        return False

print(f"Trial: {MULE} ({EMAIL})", flush=True)

mule_data = requests.get(f"{FIREBASE}/swarm/{MULE}.json", timeout=10).json() or {}
jwt = mule_data.get("jwt_token", "")

def get_jwt_via_browser(email, password):
    """Login via browser with SHA256 password + Turnstile solve, return token cookie"""
    print("Getting JWT via browser...", flush=True)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    result = [None]

    def react_set(sb, sel, val):
        import json as jmod
        code = """
            var el=document.querySelector(SEL);
            if(!el)return 'not found';
            var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el,VAL);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return 'ok';
        """.replace("SEL", jmod.dumps(sel)).replace("VAL", jmod.dumps(val))
        try: return sb.cdp.evaluate("(function(){" + code + "})()")
        except: return None

    with SB(uc=True, headless=False, xvfb=False) as sb:
        sb.open("https://mulerun.com/signin")
        time.sleep(4)

        # Wait for page to fully render
        time.sleep(3)
        url_now = sb.get_current_url()
        print(f"  Initial URL: {url_now[:70]}", flush=True)

        # If redirected to Google — navigate back and force email login
        if "google.com" in url_now or "accounts.google" in url_now:
            print("  Google redirect detected — going back to email login", flush=True)
            sb.open("https://mulerun.com/signin")
            time.sleep(4)

        # Dump page to see what login options exist
        page_text = sb.cdp.evaluate("document.body.innerText.substring(0,500)") or ""
        print(f"  Signin page: {str(page_text)[:150]}", flush=True)

        # Try clicking email-based login option (various text variants)
        for txt in ["Continue with Email", "Sign in with Email", "Email", "Use email"]:
            try:
                sb.click(f"text={txt}", timeout=2)
                time.sleep(2)
                print(f"  Clicked: {txt}", flush=True)
                break
            except: pass

        # Also try by selector
        for sel in ['a[href*="email"]', 'button[data-provider="email"]', '[class*="email"]']:
            try:
                sb.click(sel, timeout=2)
                time.sleep(2)
                print(f"  Clicked email selector: {sel}", flush=True)
                break
            except: pass

        # Check URL again
        url_now2 = sb.get_current_url()
        print(f"  After email click: {url_now2[:70]}", flush=True)

        # Fill via React native setter
        r1 = react_set(sb, "input[type=email]", email)
        print(f"  email set: {r1}", flush=True)
        time.sleep(0.5)
        r2 = react_set(sb, "input[type=password]", password_hash)
        print(f"  pw set (sha256): {r2}", flush=True)
        time.sleep(0.5)

        # If email field not found, try direct URL with email param
        if r1 == "not found":
            print("  Email field missing — trying /signin?method=email", flush=True)
            sb.open("https://mulerun.com/signin?method=email")
            time.sleep(3)
            r1 = react_set(sb, "input[type=email]", email)
            print(f"  email set retry: {r1}", flush=True)
            r2 = react_set(sb, "input[type=password]", password_hash)
            print(f"  pw set retry: {r2}", flush=True)
            time.sleep(0.5)

        # Solve Turnstile BEFORE submitting
        print("  Solving Turnstile...", flush=True)
        try: sb.uc_gui_handle_captcha(); time.sleep(3)
        except Exception as e: print(f"  Captcha err: {e}", flush=True)

        # Submit via JS
        sb.cdp.evaluate("""(function(){
            var b=Array.from(document.querySelectorAll('button')).find(function(x){
                return x.textContent.toUpperCase().indexOf('CONTINUE')>=0 || x.type==='submit';
            });
            if(b){b.removeAttribute('disabled');b.click();return 'clicked';}
            return 'no button';
        })()""")
        print("  Submitted", flush=True)
        time.sleep(6)

        url = sb.get_current_url()
        print(f"  URL: {url[:60]}", flush=True)

        # Read token cookie (httpOnly, only readable via Selenium)
        cookies = sb.get_cookies()
        names = [c["name"] for c in cookies]
        print(f"  Cookies: {names}", flush=True)

        token = next((c["value"] for c in cookies if c["name"] == "token"), None)
        if token and len(str(token)) > 50:
            result[0] = str(token)
            print(f"  JWT from 'token' cookie: {result[0][:20]}...", flush=True)
        else:
            print(f"  'token' cookie not found. All: {names}", flush=True)
            # Fallback: any eyJ cookie that isn't __mule-ch__
            for c in cookies:
                v = c.get("value", "")
                if v.startswith("eyJ") and len(v) > 100 and c["name"] != "__mule-ch__":
                    result[0] = v
                    print(f"  JWT fallback from '{c['name']}': {v[:20]}...", flush=True)
                    break

    return result[0]

if not jwt:
    jwt = get_jwt_via_browser(EMAIL, PASSWORD)
    if jwt: fb({"jwt_token": jwt, "jwt_saved_at": int(time.time())})
    else: fb({"trial_activation": "jwt_missing"}); exit(1)

hdrs = {"Authorization": f"Bearer {jwt}", "Origin": "https://mulerun.com", "Content-Type": "application/json"}
bal = requests.get("https://mulerun.com/user/balance", headers=hdrs, timeout=10)
print(f"Balance check: {bal.status_code}", flush=True)
if bal.status_code != 200:
    print("JWT invalid, re-login...", flush=True)
    jwt = get_jwt_via_browser(EMAIL, PASSWORD)
    if not jwt: fb({"trial_activation": "jwt_invalid"}); exit(1)
    hdrs["Authorization"] = f"Bearer {jwt}"
    fb({"jwt_token": jwt, "jwt_saved_at": int(time.time())})

info = requests.get("https://mulerun.com/user/info", headers=hdrs, timeout=10).json()
plan = info.get("data", {}).get("plan", {})
print(f"Current plan: trial={plan.get('trial_status',0)} sub={plan.get('subscription_status',False)}", flush=True)
if plan.get("subscription_status") or plan.get("trial_status", 0) > 0:
    requests.delete("https://mulerun.com/user/subscription", headers=hdrs, timeout=10)
    fb({"trial_activation": "success", "auto_renew_cancelled": True, "trial_safe": True})
    tg(f"✅ {MULE}: existing sub cancelled, safe."); exit(0)

cr = requests.post("https://mulerun.com/user/subscription/subscription-super/month",
    headers=hdrs, timeout=15)
print(f"Checkout: HTTP {cr.status_code}", flush=True)
if cr.status_code != 200:
    print(f"Checkout fail body: {cr.text[:200]}", flush=True)
    fb({"trial_activation": "checkout_failed", "resp": cr.text[:200]}); exit(1)

checkout_url = cr.json()["data"]["normalUrl"]
print(f"URL: {checkout_url[:80]}", flush=True)

with SB(uc=True, headless=False, xvfb=False,
        chromium_arg="--window-size=1920,1080 --disable-blink-features=AutomationControlled --no-sandbox") as sb:
    
    # Apply selenium-stealth to mask automation fingerprints
    try:
        from selenium_stealth import stealth
        stealth(sb.driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        print("  Stealth applied ✅", flush=True)
    except Exception as e:
        print(f"  Stealth skipped: {e}", flush=True)
    
    # Inject canvas fingerprint noise + additional evasions via CDP
    try:
        sb.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
            // Canvas fingerprint noise
            const origGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {
                const ctx = origGetContext.call(this, type, ...args);
                if (ctx && type === '2d') {
                    const origGetImageData = ctx.getImageData.bind(ctx);
                    ctx.getImageData = function(...a) {
                        const d = origGetImageData(...a);
                        for (let i = 0; i < d.data.length; i += 100) {
                            d.data[i] = d.data[i] ^ (Math.random() * 2 | 0);
                        }
                        return d;
                    };
                }
                return ctx;
            };
            // WebGL noise - randomize per session
            const _wglVendors = ['Intel Inc.', 'NVIDIA Corporation', 'Apple Inc.', 'Google Inc. (Intel)'];
            const _wglRenderers = ['Intel Iris Plus Graphics OpenGL Engine', 'ANGLE (Intel, Mesa Intel(R) UHD Graphics 620)', 'NVIDIA GeForce RTX 3060/PCIe/SSE2', 'Apple M1'];
            const _vIdx = Math.floor(Math.random() * _wglVendors.length);
            const _rIdx = Math.floor(Math.random() * _wglRenderers.length);
            const origGetParam = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return _wglVendors[_vIdx];
                if (param === 37446) return _wglRenderers[_rIdx];
                return origGetParam.call(this, param);
            };
            // Remove webdriver
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // Fake battery
            navigator.getBattery = async () => ({charging: true, chargingTime: 0, dischargingTime: Infinity, level: 0.85 + Math.random() * 0.1});
        """})
        print("  CDP evasions injected ✅", flush=True)
    except Exception as e:
        print(f"  CDP skipped: {e}", flush=True)

    sb.open(checkout_url)
    time.sleep(10)
    print(f"Page: {sb.get_title()} / {sb.get_current_url()[:60]}", flush=True)
    try: sb.uc_gui_handle_captcha(); time.sleep(3)
    except: pass

    # ── 1. Read Stripe's default country, use matching ZIP (don't change country) ──
    # Read Stripe's default country and use matching ZIP/address
    print("Reading Stripe default country...", flush=True)
    time.sleep(2)
    
    country_info = sb.cdp.evaluate("""(function(){
        var sels = Array.from(document.querySelectorAll('select'));
        for(var i=0;i<sels.length;i++){
            if(sels[i].options.length > 50)
                return JSON.stringify({current: sels[i].value, name: sels[i].name});
        }
        return JSON.stringify({current:'US', name:'unknown'});
    })()""")
    print(f"  Country info: {country_info}", flush=True)
    
    import json as _json
    try: stripe_country = _json.loads(str(country_info)).get('current','US')
    except: stripe_country = 'US'
    print(f"  Stripe country: {stripe_country}", flush=True)
    
    # Use ZIP that matches Stripe's detected country (DO NOT change country — triggers hCaptcha)
    # Country determined by client IP: Seeker II (SG IP) → SG, GHA Azure (US) → US
    COUNTRY_DATA = {
        'US': ('10001',  '350 5th Ave',     'New York'),
        'PH': ('1207',   '7734 JB Roxas',   'Makati City'),
        'SG': ('238859', '1 Orchard Road',  'Singapore'),  # Orchard Road, valid 6-digit SG ZIP
        'DE': ('10115',  'Unter den Linden 1', 'Berlin'),
        'NZ': ('1010',   '1 Queen St',      'Auckland'),
        'AU': ('2000',   '1 Macquarie St',  'Sydney'),
        'CN': ('100000', '1 Changan Ave',   'Beijing'),
        'GB': ('W1A1AA', '1 Oxford St',     'London'),
        'JP': ('1000001','1 Chiyoda',       'Tokyo'),
        'KR': ('04524',  '1 Sejong-daero',  'Seoul'),
        'MY': ('50000',  '1 Jalan Raja',    'Kuala Lumpur'),
        'ID': ('10110',  '1 Jl Thamrin',    'Jakarta'),
    }
    effective_zip, effective_addr, effective_city = COUNTRY_DATA.get(stripe_country, ('10001','350 5th Ave','New York'))
    print(f"  Using country={stripe_country} ZIP={effective_zip} (no DOM change)", flush=True)

    # ── 2. Fill billing address (main page — real inputs) ───────────────────
    fill(sb, 'input[name="billingName"]',         CARD_NAME);    time.sleep(0.3)
    # Fill address + dismiss autocomplete via CDP key event
    fill(sb, 'input[name="billingAddressLine1"]',  effective_addr); time.sleep(1.2)
    try:
        sb.cdp.evaluate("""(function(){
            var el = document.querySelector('input[name="billingAddressLine1"]');
            if(el) el.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', keyCode:27, bubbles:true}));
        })()""")
        time.sleep(0.5)
    except: pass
    # billingLocality - skip, not present for SG IP
    try:
        locality_els = sb.cdp.evaluate("document.getElementsByName('billingLocality').length")
        if int(str(locality_els).strip() or '0') > 0:
            fill(sb, 'input[name="billingLocality"]', effective_city)
            time.sleep(0.3)
        else:
            print('  billingLocality: not present, skipping', flush=True)
    except:
        print('  billingLocality: skipped', flush=True)
    fill(sb, 'input[name="billingPostalCode"]',    effective_zip);  time.sleep(0.5)

    # ── 3. Fill card fields (main DOM — Stripe Checkout uses main-frame inputs) ─
    # Stripe Checkout renders card fields in main DOM, protected by stripe-origin-frame
    # send_keys works; fields are NOT in separate iframes
    fill(sb, 'input[name="cardNumber"]', CARD_NUM); time.sleep(0.5)
    fill(sb, 'input[name="cardExpiry"]', CARD_EXP); time.sleep(0.5)
    fill(sb, 'input[name="cardCvc"]',    CARD_CVV); time.sleep(0.5)

    # Pre-submit error check
    try:
        errs = sb.cdp.evaluate("""(function(){
            return Array.from(document.querySelectorAll('[class*="Error"i],[role="alert"],[class*="FieldError"i]'))
                .map(function(e){return e.textContent.trim();}).filter(function(s){return s.length>2&&s.length<150;}).join(' | ');
        })()""")
        if errs and str(errs).strip(): print(f"  Pre-submit errors: {errs}", flush=True)
        else: print("  Pre-submit: clean", flush=True)
    except: pass

    # ── 4. Submit + handle hCaptcha ──────────────────────────────────────────
    submitted = False
    for sel in ["button[type=submit]", "//button[contains(.,'Start trial')]",
                "//button[contains(.,'Subscribe')]", "//button[contains(.,'Pay')]"]:
        try: sb.click(sel, timeout=5); print(f"Submitted: {sel}", flush=True); submitted=True; break
        except: pass
    if not submitted: print("No submit button found!", flush=True)

    # Stripe fires hcaptcha-invisible on submit — handle challenge if it appears
    # Try multiple captcha methods
    time.sleep(3)
    for attempt in range(5):
        url_now = sb.get_current_url()
        if "mulerun.com" in url_now and "checkout.stripe.com" not in url_now:
            print(f"  Redirected after captcha attempt {attempt}", flush=True)
            break
        
        # Check if hCaptcha challenge iframe is visible
        try:
            captcha_visible = sb.cdp.evaluate("""(function(){
                var f = document.querySelector('iframe[src*="hcaptcha-inner"]');
                if(!f) return 'no-frame';
                var r = f.getBoundingClientRect();
                return r.height > 10 ? 'visible:'+r.height : 'hidden:'+r.height;
            })()""")
            print(f"  Captcha frame [{attempt+1}]: {captcha_visible}", flush=True)
        except: captcha_visible = 'unknown'
        
        try: sb.uc_gui_handle_captcha(); time.sleep(2)
        except: pass
        try: sb.uc_gui_click_captcha(); time.sleep(2)
        except: pass
        time.sleep(3)

    # ── 5. Wait for redirect ──────────────────────────────────────────────
    for i in range(35):
        time.sleep(2)
        url = sb.get_current_url()
        if i % 3 == 0: print(f"  [{i*2}s] {url[:70]}", flush=True)
        if "mulerun.com" in url and "checkout.stripe.com" not in url:
            print(f"  Redirected: {url}", flush=True); break
        if i > 0 and i % 3 == 0:
            try:
                errs = sb.cdp.evaluate("""(function(){
                    return Array.from(document.querySelectorAll('[class*="Error"i],[role="alert"],[class*="FieldError"i]'))
                        .map(function(e){return e.textContent.trim();}).filter(function(s){return s.length>2&&s.length<150;}).join(' | ');
                })()""")
                if errs and str(errs).strip(): print(f"  Errors: {errs}", flush=True)
            except: pass
    else:
        try:
            # Full diagnostic: page text, iframes, any error elements
            pt = sb.cdp.evaluate("document.body.innerText.substring(0,1000)")
            print(f"Stripe final:\n{pt}", flush=True)
            
            # Check for 3DS / challenge iframe
            frames = sb.cdp.evaluate("""(function(){
                return Array.from(document.querySelectorAll('iframe')).map(function(f){
                    return {name:f.name||'', src:(f.src||'').substring(0,80), id:f.id||''};
                });
            })()""")
            print(f"  iframes: {frames}", flush=True)
            
            # Check ALL text in error-like elements
            all_errs = sb.cdp.evaluate("""(function(){
                var texts = [];
                document.querySelectorAll('*').forEach(function(el){
                    var t = el.textContent.trim();
                    if(t.length > 5 && t.length < 200 && 
                       (t.toLowerCase().includes('declin') || 
                        t.toLowerCase().includes('fail') ||
                        t.toLowerCase().includes('error') ||
                        t.toLowerCase().includes('invalid') ||
                        t.toLowerCase().includes('verif') ||
                        t.toLowerCase().includes('authenticat') ||
                        t.toLowerCase().includes('card'))){
                        texts.push(t);
                    }
                });
                return [...new Set(texts)].slice(0,10).join(' || ');
            })()""")
            print(f"  Error/card text: {all_errs}", flush=True)
        except Exception as e:
            print(f"  Diagnostic err: {e}", flush=True)

# ── 5. Verify ─────────────────────────────────────────────────────────────
# Poll up to 60s for MuleRun webhook to confirm the trial
t2, s2, plan2 = 0, False, {}
for _wi in range(12):
    time.sleep(5)
    info2 = requests.get("https://mulerun.com/user/info", headers=hdrs, timeout=10).json()
    plan2 = info2.get("data", {}).get("plan", {})
    t2 = plan2.get("trial_status", 0)
    s2 = plan2.get("subscription_status", False)
    print(f"Plan [{(_wi+1)*5}s]: trial={t2} sub={s2} name={plan2.get('name','')}", flush=True)
    if t2 or s2:
        break

if t2 or s2:
    dr = requests.delete("https://mulerun.com/user/subscription", headers=hdrs, timeout=10)
    print(f"DELETE: HTTP {dr.status_code}", flush=True)
    fb({"trial_activation": "success", "trial_status": 1, "subscription_status": True,
        "auto_renew_cancelled": True, "trial_safe": True,
        "plan_name": plan2.get("name",""), "trial_days": 7,
        "trial_expires": "", "activated_at": int(time.time())})
    tg(f"✅ TRIAL ACTIVE\nMule: {MULE}\nAccount: {EMAIL}\n7-day trial. Card safe.")
    print("SUCCESS", flush=True)
else:
    fb({"trial_activation": "payment_failed", "plan_data": str(plan2)})
    print(f"❌ Trial payment failed: {MULE} {EMAIL}", flush=True)  # silenced TG spam
    print(f"FAILED: {plan2}", flush=True)
    exit(1)
