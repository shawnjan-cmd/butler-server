# Butler AI: PC Automation — Full Master Audit v3
### Fixes · Tricks · Upgrade Ideas · Anti-Patterns · Onboarding Tips · New Coverage
*Deep audit of v7.1.0 — May 2026 · Expanded from v2 with 8 new sections and ~60 new issues*

---

> **How to read this:** Every issue has the problem, then **✅ HOW TO FIX IT**, then **💡 UPGRADE IDEA** where relevant, then **⛔ WHAT NOT TO DO** (the traps that look like fixes but make things worse or get you rejected faster). Severity tags: 🔴 Blocker · 🟠 High · 🟡 Medium · 🟢 Low.

> **What's new in v3:** New Part 8 (React Native Architecture), Part 9 (Server Performance & Reliability), Part 10 (Post-Launch Operations), Part 11 (iOS Considerations), plus expanded coverage of every existing section with additional issues found in deeper analysis.

---

# PART 1 — PLAY STORE BLOCKERS

---

## 🔴 B1 — Missing Feature Graphic (Required to Publish)

The Play Store **will not let you hit the Publish button** without a Feature Graphic. It is mandatory, not optional.

**Required spec:** 1024 × 500 px, JPEG or 24-bit PNG (no transparency), under 8 MB, RGB color space.

**✅ HOW TO FIX IT:**
The fastest free path:
1. Go to **Canva** (canva.com) → create a custom size 1024 × 500 px
2. Dark background (`#020407` matches your app theme)
3. Left side: Butler AI logo + app name in your monospace font, large
4. Right side: One clean app screenshot or an abstract circuit/terminal graphic
5. Tagline: *"Remote PC Automation · Local AI · No Cloud"*
6. Export as JPEG (quality 90%) — will be well under 8 MB
7. Upload in Play Console → Store Listing → Graphics → Feature Graphic

**Paid option:** Figma, Adobe Express, or hire a designer on Fiverr (~$10–$20)

**Content rules to follow:**
- No "Best App" / "#1" / award claims unless you can prove them
- No screenshots of competitors
- No text that will look tiny — it renders at ~300px wide in some views
- No time-limited promotions ("Free this week" etc.)
- Do NOT put the Google Play badge/logo on it — Google prohibits this

**💡 UPGRADE IDEA:** Make 3 feature graphic variants (seasonal, dark, light) and A/B test them in Play Console's "Custom Store Listings" feature to see which drives more installs.

**⛔ WHAT NOT TO DO:**
- Don't use a screenshot as your feature graphic — it will look compressed and blurry at banner size
- Don't use transparency/alpha channel PNG — Play Console will reject it silently
- Don't skip this thinking it's optional because you saw it work without one — it was a different account type or cached listing

---

## 🔴 B2 — Closed Testing Gate (12 Testers × 14 Days)

If your Google Play developer account was created after November 13, 2023 (personal account), you **cannot publish to Production at all** until this is done. This is a hard gate — no workaround.

**✅ HOW TO FIX IT (Step by Step):**

**Step 1 — Create the Closed Testing track:**
Play Console → Your App → Testing → Closed Testing → Create Track → name it "Alpha" or "beta-v1"

**Step 2 — Upload your AAB:**
Build with `eas build --platform android --profile production` → upload the `.aab` to the Closed Testing track (NOT Internal Testing)

**Step 3 — Get 12 testers:**
Options in order of reliability:
- Friends/family with Android devices (best — Google trusts these accounts)
- r/androiddev or r/indiegaming on Reddit — post "looking for beta testers"
- Discord communities (Expo, React Native, Android dev servers)
- Paid service like PrimeTestLab (~$11–$15) — fastest, 4–6 hour start
- **DO NOT** create fake Google accounts yourself — Google's machine learning detects correlated device fingerprints and will flag your account

**Step 4 — Send testers the opt-in link:**
Play Console → Closed Testing → Manage Track → copy the "Join testing" URL → send to testers. They must click it AND install the app (not just click the link).

**Step 5 — Wait 14 consecutive days:**
The timer runs per tester from when they opt in. If a tester opts out and re-opts in, their 14-day clock restarts from zero. Check that all 12 remain opted in throughout.

**Step 6 — Apply for Production Access:**
After 14 days: Play Console → Dashboard → "Apply for production access" → answer the questionnaire honestly about your app's purpose and testing process

**💡 UPGRADE IDEA:** During the 14-day testing period, ask your testers to leave honest bug reports. Use those to ship at least one AAB update during the window — it signals to Google that the app is actively maintained. Create a tiny feedback form (Google Form works fine) and include the link in your beta tester email.

**⛔ WHAT NOT TO DO:**
- Don't use Internal Testing track — it does NOT count toward the 12/14 requirement. Must be Closed Testing.
- Don't submit for production access the moment 14 days passes — make sure all 12 testers are still showing as opted in
- Don't use emulators — Google can detect them and they rarely count as legitimate testers
- Don't use a single device with multiple accounts — Google fingerprints hardware

---

## 🔴 B3 — App Access Instructions Missing a Working Demo Server

Because the app needs a PC server to do anything, Google's reviewers will open it, see the "Connect to your PC" screen, have no way to proceed, and mark it as non-functional → rejection.

**✅ HOW TO FIX IT:**

**Option A — Host a permanent demo server (best):**
1. Get a cheap VPS (DigitalOcean $4/month, Oracle Free Tier, Hetzner €3/month)
2. Run `butler_server.py` on it exposed on a public IP (temporarily, for review period)
3. Pre-pair it with a known test deviceId + token
4. Write the IP, port, and the pre-generated token into your App Access instructions

**Option B — Add a demo/mock mode to the app:**
Add a `DEMO_MODE` flag that activates when no server is connected. In demo mode:
- Show fake but realistic CPU/RAM/Disk metrics (animated, cycling values)
- Show the 70+ scripts list (they're already bundled client-side)
- Show example chat responses from a local response array
- Show sample knowledge base entries

This is also genuinely useful for users who want to explore before setting up their PC.

```typescript
// In serverConnection.ts — add demo mode
export const DEMO_MODE_KEY = '@butler_demo_mode';

export const DEMO_METRICS = {
  cpu: { percent: 34, cores: 8 },
  memory: { percent: 67, used_gb: 10.8, total_gb: 16 },
  disk: { percent: 55, used_gb: 275, total_gb: 500 },
};
```

**In App Access Instructions in Play Console, write exactly:**
```
TESTING WITHOUT A PC:
Tap "Demo Mode" on the connection screen to explore all features
with simulated data. No server required for review.

TESTING WITH LIVE SERVER:
1. On Home tab, tap "SCAN QR TO PAIR" → tap "Manual IP" tab
2. IP: [YOUR_DEMO_SERVER_IP]  Port: 8766
3. Tap CONNECT

ONBOARDING: App has 10 welcome screens. Tap CONTINUE on each.
Consents are required — all must be accepted to proceed.
Script execution requires a manual tap. Safety scanner is always active.
```

**💡 UPGRADE IDEA:** Ship the demo mode as a real feature. Market it as "Try Butler AI before setting up your server." This also removes a huge barrier for new users who are hesitant to run a Python server.

**⛔ WHAT NOT TO DO:**
- Don't say in App Access "the app requires a PC — reviewers cannot test it" — this is the fastest way to get rejected. Never tell Google its reviewers can't test your app.
- Don't hardcode a home server IP — your router's DHCP will reassign it and the instructions will be wrong by review time
- Don't make the demo mode look worse than real mode — reviewers form their first impression from it

---

## 🔴 B4 — Port Mismatch: Server Runs on 8766, Instructions Say 5000

`butler_server.py` hardcodes `PORT = 8766`. The App Access instructions in `app.json` say port 5000. Reviewers will enter 5000, get "connection refused", and fail your app.

**✅ HOW TO FIX IT — pick ONE of these:**

**Option A (Recommended) — Make the port configurable via `.env`:**
```python
# butler_server.py
PORT = int(os.environ.get('BUTLER_PORT', 8766))
```
Then standardize your docs and App Access instructions to say 8766.

**Option B — Change the server to 5000:**
```python
PORT = 5000
```
And update App Access instructions to say 5000.

Either way, do a global search in the codebase for every hardcoded port reference:
```bash
grep -rn "8765\|8766\|5000\|PORT" . --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json"
```
Count every unique port value and consolidate to one.

**⛔ WHAT NOT TO DO:**
- Don't change just `app.json` — the actual server must match
- Don't use port 80 or 443 — these require elevated privileges on Mac/Linux and will fail for most users

---

## 🔴 B5 — `.env` File Committed to Git

Already covered in the previous audit. Here's the full fix with extra details.

**✅ HOW TO FIX IT:**

**Step 1 — Fix .gitignore RIGHT NOW:**
```bash
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
git add .gitignore
git commit -m "fix: exclude .env from git tracking"
```

**Step 2 — Remove from git history (required — it's already committed):**
Using BFG Repo Cleaner (easier than git filter-branch):
```bash
# Download BFG: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files .env your-repo.git
cd your-repo.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```

**Step 3 — Rotate credentials:**
- Go to supabase.com → your project → Settings → API → regenerate the anon key
- Even though the account is "deleted" per the code comment, rotate everything anyway

**Step 4 — Add a pre-commit hook to prevent this happening again:**
```bash
# .git/hooks/pre-commit (make executable: chmod +x)
#!/bin/sh
if git diff --cached --name-only | grep -qE "^\.env$"; then
  echo "ERROR: Attempting to commit .env file. Remove it from staging."
  exit 1
fi
```

**💡 UPGRADE IDEA:** Use `git-secrets` or `truffleHog` in CI to automatically scan for accidentally committed secrets. GitHub has a built-in Secret Scanning feature (free for public repos) that alerts you.

**⛔ WHAT NOT TO DO:**
- Don't just delete the file and commit the deletion — the file is still in git history and visible via `git log -p`
- Don't rotate the keys BEFORE purging history — the old key is still in the history even after rotation

---

## 🔴 B6 — **NEW** — `android.package` and `bundle ID` Must Be Locked Before First AAB Upload

Once you upload any AAB to any track in Play Console (including Internal Testing), the `applicationId` is **permanently locked**. You cannot rename it later. Any future rename means a brand-new app with zero reviews, zero installs, zero ranking.

Your current ID is `com.butlerai.pc.automation`. This is actually fine — but before you upload, confirm it is correct in all three places:

```bash
# Check all three must match:
grep -n "package\|applicationId\|bundleIdentifier" app.json eas.json android/app/build.gradle
```

**✅ HOW TO FIX IT:**
If they don't all match, fix them now before any upload. After first upload, this field is frozen.

Also run a quick sanity check:
```bash
# Verify package name is syntactically valid (no hyphens, starts with letter, 3+ segments)
echo "com.butlerai.pc.automation" | python3 -c "
import sys, re
name = sys.stdin.read().strip()
parts = name.split('.')
assert len(parts) >= 3, 'Need 3+ segments'
for p in parts:
    assert re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', p), f'Invalid segment: {p}'
print('Package name OK')
"
```

---

---

# PART 2 — PLAY STORE HIGH PRIORITY

---

## 🟠 H1 — Inconsistent App Name (Butler AI vs BOTER vs Botler vs 4 Others)

Your codebase has at least 5 different names for the same app. This causes confusion for reviewers and violates Play Store guidelines around misleading content.

**✅ HOW TO FIX IT:**

Run this to find every occurrence:
```bash
grep -rn "BOTER\|Botler\|Nexus Command\|CommandCube\|butler ai\|Butler AI" . \
  --include="*.ts" --include="*.tsx" --include="*.json" --include="*.md" \
  -i | grep -v node_modules | grep -v ".git"
```

Create a find-and-replace plan. Canonical name: **"Butler AI: PC Automation"**
- In-app display name (header, splash): **"Butler AI"** (short form is fine in UI)
- Package ID stays: `com.butlerai.pc.automation` ✅
- Play Store listing title: **"Butler AI: PC Automation"**
- Privacy policy and all legal docs: **"Butler AI: PC Automation"**
- Privacy policy must NOT say "Nexus Command Center" or "CommandCube" — these will confuse Google reviewers who are cross-checking the in-app policy against the store listing

**⛔ WHAT NOT TO DO:**
- Don't rename the package ID (`com.butlerai.pc.automation`) — once published, changing it means a completely new app with zero reviews
- Don't leave "BOTER" in STORE_LISTING.md thinking it doesn't matter — it matters if you use that doc as your actual listing text

---

## 🟠 H2 — Data Safety Form Declares Dead Services (Supabase + Gemini)

`DATA_SAFETY.md` declares that chat text is sent to Supabase and Google Gemini. But `supabaseClient.ts` stubs everything out (`supabase = null`, `isSupabaseConfigured() = false`). Google's automated SDK scanner will find `@supabase/supabase-js` in your binary, see that you declared it sends data, and then find the actual network calls don't happen — this creates a trust red flag.

**✅ HOW TO FIX IT:**

**Step 1 — Remove the dead SDK from package.json:**
```bash
pnpm remove @supabase/supabase-js
```
Then delete or simplify `services/supabaseClient.ts` to have zero imports from the SDK:
```typescript
// supabaseClient.ts - fully stubbed, no SDK dependency
export const supabase = null;
export const isSupabaseConfigured = (): boolean => false;
export const getSupabaseUrl = (): string => '';
```

**Step 2 — Update Data Safety form to reflect reality:**
Current state: Ollama runs locally, no external AI calls exist.
Answer "Does your app collect or share user data?" → **NO** for everything except:
- Device IDs: YES (local UUID for pairing, never shared)
- Camera: YES (QR scan only, never stored or shared)
- Network info: YES (LAN scan to find PC, never shared)

**Step 3 — Update DATA_SAFETY.md to match:**
Remove all Gemini and Supabase references. Change the "Messages" data type answer from YES to NO.

**💡 UPGRADE IDEA:** If you plan to re-add cloud AI in the future, create a feature flag system where the Data Safety form can be updated in sync with the feature toggle. Never let the form get ahead of or behind the actual behavior.

**⛔ WHAT NOT TO DO:**
- Don't leave the Supabase SDK in the bundle just because the client is stubbed — the SDK itself does initialization calls and may phone home even if your code doesn't actively call it
- Don't declare data sharing that doesn't happen — even in an "abundance of caution" way. False positives in Data Safety are as bad as missed disclosures.

---

## 🟠 H3 — Age Gate Says 18+ But App Rating and Description Say Teen 13+

**In `welcome.tsx` Screen 3 (consent):**
> `"I am 18 years of age or older"` — labeled as required

**In `app.json` and store description:**
> `"Teen (13+)"` and `"intended for developers and technical users aged 13 and above"`

This is a direct contradiction. If you say 13+ in the store but gate access behind an 18+ consent checkbox, you're either lying to the store or blocking your stated audience. Either way, Google reviewers will catch it.

**✅ HOW TO FIX IT — pick the age and stick to it everywhere:**

**Option A — Teen 13+:**
Change the welcome screen consent text from:
```tsx
label="I am 18 years of age or older"
sublabel="Butler AI is a developer tool for adults only"
```
to:
```tsx
label="I am 13 years of age or older"
sublabel="Butler AI is a developer tool for technical users 13 and above"
```
Update `PRIVACY_POLICY.md`, `STORE_LISTING.md`, `SECURITY_AND_PLAYSTORE_COMPLIANCE.md` everywhere it says "18+" or "adults only."

**Option B — Mature/Adults (17+):**
If you genuinely believe the app requires maturity (terminal access, script execution on a PC), go with 17+ in the IARC questionnaire. Then change the consent to "17 years of age or older" and update the store description to say "17+ recommended."

**Recommendation:** Go with **Teen 13+**. Most developers who'd use a Python remote execution app are teenagers or older. "18+ adults only" will reduce your install numbers without any real safety benefit and will create a friction/trust mismatch that reviewers notice.

**⛔ WHAT NOT TO DO:**
- Don't say 18+ in the consent and 13+ in the store — this will get flagged as deceptive
- Don't set the IARC rating to "Everyone" — script execution and terminal access will push it to Teen minimum

---

## 🟠 H4 — `/api/reset_pair` Is Completely Unauthenticated

This is a critical server security bug. `POST /api/reset_pair` requires no auth token and completely unlinks the paired device, opening the server for anyone to pair with it. Any device on your network can call this and lock you out of your own server.

**✅ HOW TO FIX IT:**

Add auth check AND require a PIN confirmation:
```python
@app.route("/api/reset_pair", methods=["POST"])
def reset_pair():
    # Must be authenticated as the currently paired device
    dev = auth_device()
    if not dev:
        return jsonify({"error": "Unauthorized — must be paired to reset"}), 401
    # Require an explicit confirmation field
    d = request.get_json(force=True) or {}
    if d.get("confirm") != "RESET_CONFIRMED":
        return jsonify({"error": "Include confirm: 'RESET_CONFIRMED' to proceed"}), 400
    STATE["deviceId"] = None
    STATE["lockedAt"] = None
    save_state()
    return jsonify({"status": "ok", "message": "Pairing reset."})
```

**⛔ WHAT NOT TO DO:**
- Don't just add auth and assume it's fine — also add the explicit confirmation body so it can't be triggered by a misconfigured HTTP client accidentally hitting the endpoint

---

## 🟠 H5 — Remove Unused SDKs Creating Permission and Data Safety Risks

These packages are in `package.json` but appear nowhere in actual code. Each one inflates your APK, may trigger SDK-level network calls, and causes Data Safety mismatches:

| Package | Risk |
|---|---|
| `@stripe/stripe-react-native` | Device fingerprinting SDK, fraud detection calls |
| `react-native-webrtc` | Declares CAMERA + RECORD_AUDIO in its manifest |
| `expo-location` | May register location permission in the manifest |
| `expo-contacts` | Contacts permission implications |
| `expo-media-library` | READ_MEDIA_IMAGES permission |
| `expo-calendar` | Calendar access |
| `expo-screen-capture` | Screen recording |
| `@supabase/supabase-js` | Network calls even when stubbed |

**✅ HOW TO FIX IT:**
```bash
pnpm remove @stripe/stripe-react-native react-native-webrtc expo-location \
  expo-contacts expo-media-library expo-calendar expo-screen-capture \
  @supabase/supabase-js
```

After removal, rebuild the AAB and verify the final `AndroidManifest.xml`:
```bash
# After EAS build, download the AAB and check manifest
bundletool build-apks --bundle=app.aab --output=app.apks
unzip -p app.apks splits/base-master.apk | unzip -p - AndroidManifest.xml | \
  aapt dump xmltree /dev/stdin | grep "uses-permission"
```

**💡 UPGRADE IDEA:** Add a comment in `package.json` above each dependency explaining WHY it's included. This forces you to justify every SDK during review. Teams that do this tend to have far leaner APKs.

**⛔ WHAT NOT TO DO:**
- Don't assume that because you never call `Stripe.init()` the SDK is inert — Stripe's SDK registers initializers that run at app startup regardless
- Don't "fix" this by adding everything to `blockedPermissions` — the SDK code still runs, permissions are just blocked at the OS level. Remove the SDKs entirely.

---

## 🟠 H6 — Version Mismatch: App v7.1.0 but Privacy Policy Says v6.0

The live privacy policy at GitHub Pages says "App Version: 6.0." Google reviewers are instructed to check that the privacy policy matches the app being reviewed.

**✅ HOW TO FIX IT:**

In `PRIVACY_POLICY.md`:
```markdown
**App Version:** 7.1.0
**Last Updated:** [today's date]
**Effective Date:** [today's date]
```

After editing, push to GitHub and verify the URL `https://shawnjan-cmd.github.io/privacy-policy-/` loads the updated version. GitHub Pages can take 1–5 minutes to update after a push.

**Auto-version trick for future:** Add a build step that inserts the version into the privacy policy automatically:
```bash
# In your EAS build hook or CI script
VERSION=$(cat app.json | python3 -c "import json,sys; print(json.load(sys.stdin)['expo']['version'])")
sed -i "s/App Version:.*/App Version: $VERSION/" PRIVACY_POLICY.md
```

**⛔ WHAT NOT TO DO:**
- Don't update `PRIVACY_POLICY.md` locally and forget to push to GitHub — the live URL is what Google checks, not your local file

---

## 🟠 H7 — **NEW** — EAS `eas.json` `production` Profile Missing `NODE_ENV=production`

Without explicitly setting `NODE_ENV=production` in your EAS production build profile, some libraries (including React Native itself) will bundle in development-mode code paths. This bloats the APK and leaves debug warnings in the binary.

**✅ HOW TO FIX IT:**

In `eas.json`:
```json
{
  "build": {
    "production": {
      "android": {
        "buildType": "app-bundle",
        "gradleCommand": ":app:bundleRelease"
      },
      "env": {
        "NODE_ENV": "production",
        "EXPO_PUBLIC_ENV": "production"
      }
    }
  }
}
```

Also check `app.config.js` (if you use it instead of `app.json`) isn't accidentally exposing dev variables through `extra` fields.

---

## 🟠 H8 — **NEW** — `versionCode` Needs a Bump Strategy Before First Upload

`versionCode` must be a monotonically increasing integer — once you upload an AAB with a `versionCode`, you can never re-upload the same or lower number, even if you delete the release. If you upload a test build with `versionCode: 1` and then try to publish with `versionCode: 1`, Play Console will reject it.

**✅ HOW TO FIX IT — plan your version numbering now:**

```json
// app.json — recommended scheme
{
  "expo": {
    "version": "7.1.0",
    "android": {
      "versionCode": 710001
    }
  }
}
```

Using `MAJOR * 100000 + MINOR * 1000 + PATCH * 10 + BUILD_NUMBER` gives you room for 9 hotfix builds per version and clear human-readable structure. So v7.1.0 build 1 = `710001`, v7.1.0 build 2 = `710002`, v7.2.0 = `720001`.

Automate it in your EAS build hook to prevent forgetting to bump it:
```bash
# scripts/bump-version-code.sh
CURRENT=$(cat app.json | python3 -c "import json,sys; print(json.load(sys.stdin)['expo']['android']['versionCode'])")
NEW=$((CURRENT + 1))
sed -i "s/\"versionCode\": $CURRENT/\"versionCode\": $NEW/" app.json
echo "versionCode: $CURRENT → $NEW"
```

---

---

# PART 3 — SECURITY FIXES (WITH FULL CODE)

---

## 🔴 S1 — Session Tokens Never Expire

**✅ COMPLETE FIX for `butler_server.py`:**

```python
TOKEN_TTL_SECONDS = 86400  # 24 hours — adjust as needed

def verify_token(token):
    try:
        raw   = base64.urlsafe_b64decode(token + "==").decode()
        parts = raw.split(":")
        if len(parts) < 3: return None
        device_id, ts, sig = parts[0], parts[1], ":".join(parts[2:])
        
        # ✅ ADD THIS EXPIRY CHECK
        token_age = int(time.time()) - int(ts)
        if token_age > TOKEN_TTL_SECONDS:
            return None
        if token_age < 0:  # Clock skew / tampered timestamp
            return None
            
        msg      = f"{device_id}:{ts}".encode()
        expected = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected): return device_id
    except: pass
    return None
```

**Also update the reconnect flow in the app** (`services/serverConnection.ts`) to automatically call `/reconnect` when it receives a 401, which will get a fresh token using the saved deviceId.

**💡 UPGRADE IDEA:** Add a `/api/refresh` endpoint that issues a new token before the current one expires (e.g., when token is >20 hours old). The app's heartbeat engine can call this proactively, so users are never locked out mid-session.

**⛔ WHAT NOT TO DO:**
- Don't set TOKEN_TTL to something very short (e.g., 5 minutes) without implementing automatic refresh — users will get random 401 errors while using the app and think it's broken
- Don't use JWT libraries for this — the current HMAC approach is simpler and entirely sufficient for a local network tool

---

## 🔴 S2 — Unauthenticated Pairing (No PIN Required)

**✅ COMPLETE FIX — Add a display PIN to butler_server.py:**

```python
import random, string

# Generate a 6-digit PIN when server starts or is reset
def _gen_pin():
    return ''.join(random.choices(string.digits, k=6))

PAIRING_PIN   = _gen_pin()
PIN_EXPIRES   = time.time() + 300  # 5 minutes

@app.route("/api/pair/pin-info", methods=["GET"])
def pin_info():
    """Returns only whether a PIN is active — not the PIN itself."""
    return jsonify({"pinActive": True, "hint": "Check your PC terminal"})

@app.route("/pair", methods=["POST"])
def pair():
    global PAIRING_PIN, PIN_EXPIRES
    d = request.get_json(force=True) or {}
    device_id = d.get("deviceId", "")
    
    if not device_id or len(device_id) < 5:
        return jsonify({"error": "deviceId required"}), 400
    
    # ✅ PIN CHECK — skip only if already paired to this device
    if STATE["deviceId"] and STATE["deviceId"] == device_id:
        pass  # Allow reconnect from same device without PIN
    else:
        submitted_pin = d.get("pin", "")
        if time.time() > PIN_EXPIRES:
            PAIRING_PIN = _gen_pin()
            PIN_EXPIRES = time.time() + 300
            print(f"\n[Butler] PIN expired. New PIN: {PAIRING_PIN}\n")
        if submitted_pin != PAIRING_PIN:
            return jsonify({"error": "Invalid pairing PIN. Check your PC terminal."}), 403
        # Invalidate PIN after use
        PAIRING_PIN = _gen_pin()
        PIN_EXPIRES = time.time() + 300
        print(f"\n[Butler] Paired! Next PIN: {PAIRING_PIN}\n")
    
    STATE["deviceId"] = device_id
    STATE["lockedAt"] = time.time()
    save_state()
    token = make_token(device_id)
    return jsonify({"status": "ok", "sessionToken": token, "serverVersion": "7.0.0"})
```

Print the PIN prominently when the server starts:
```python
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════╗
║     Butler AI Server v7.0.0          ║
║     Local: http://{get_ip()}:{PORT}   ║
║     Pairing PIN: {PAIRING_PIN}                ║
║     (PIN expires in 5 minutes)        ║
╚══════════════════════════════════════╝
""")
```

**In the app** (pairing screen), add a PIN input field:
```typescript
// In your QR/manual pairing component
const [pin, setPin] = useState('');
// Add to the pair request body:
body: JSON.stringify({ deviceId, pin })
```

**💡 UPGRADE IDEA:** Show the PIN as a QR code alongside the IP:port QR code. The app can scan both in one shot — reading the IP/port from one QR and the PIN from another, or embed the PIN in the main QR payload as a third field.

**⛔ WHAT NOT TO DO:**
- Don't transmit the PIN over the network — it must be displayed on the PC's physical screen (terminal/console) so only someone with physical access or remote desktop access to the PC can see it
- Don't make the PIN permanent or configurable in a config file — a static PIN defeats the purpose of a PIN

---

## 🟠 S3 — Add Rate Limiting to Auth Endpoints

**✅ COMPLETE FIX — Simple in-memory rate limiter:**

```python
from collections import defaultdict
import time

_req_log: dict = defaultdict(list)

def rate_limit(ip: str, endpoint: str, max_req: int = 5, window: int = 60) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    key = f"{ip}:{endpoint}"
    now = time.time()
    # Prune old entries
    _req_log[key] = [t for t in _req_log[key] if now - t < window]
    if len(_req_log[key]) >= max_req:
        return False
    _req_log[key].append(now)
    return True

# Apply to the pair endpoint:
@app.route("/pair", methods=["POST"])
def pair():
    ip = request.remote_addr
    if not rate_limit(ip, "pair", max_req=5, window=60):
        return jsonify({"error": "Too many attempts. Wait 60 seconds."}), 429
    # ... rest of pair logic
```

**⛔ WHAT NOT TO DO:**
- Don't rate limit the `/health` endpoint — the app's auto-connect engine pings it every 6 seconds and will stop working
- Don't use IP-based blocking as the only mechanism — on some home networks (NAT hairpin), all devices share one internal IP

---

## 🟠 S4 — Add Server-Side Script Safety Check

The client-side safety guard is good but bypassable by direct HTTP calls. Add a minimal server-side mirror:

```python
import re

# Minimal server-side blocklist — not a full replacement for client guard
SERVER_BLOCK_PATTERNS = [
    (re.compile(r'shutil\.rmtree\s*\(\s*[\'\"]/[\'\"]', re.I), 'Root filesystem deletion'),
    (re.compile(r'format\s+[a-z]:\s*/[qQ]\s*/[yY]', re.I), 'Windows disk format'),
    (re.compile(r'dd\s+if=/dev/zero\s+of=/dev/', re.I), 'Disk wipe'),
    (re.compile(r':\(\)\{.*\}.*:', re.S), 'Fork bomb'),
    (re.compile(r'subprocess.*socket.*connect|socket.*connect.*subprocess', re.I|re.S), 'Reverse shell'),
    (re.compile(r'rm\s+-rf\s+/\s*$', re.I|re.M), 'Root recursive delete'),
]

def server_safety_check(script: str) -> tuple[bool, str]:
    for pattern, name in SERVER_BLOCK_PATTERNS:
        if pattern.search(script):
            return False, name
    return True, ""
```

---

## 🟠 S5 — **NEW** — `SECRET` Key Derivation is Weak

The server generates `SECRET` using `secrets.token_hex(32)` on first run and saves it to state. This is fine in isolation, but if `state.json` is deleted (e.g., during an update), all existing tokens become invalid and every device must re-pair. More critically, if `state.json` is ever world-readable on a multi-user system, the secret is exposed.

**✅ HOW TO FIX IT:**

Use a derived key that survives state resets, stored separately from the pairing state:

```python
import secrets, os, stat

SECRET_FILE = Path("butler_secret.key")

def load_or_create_secret() -> str:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    new_secret = secrets.token_hex(32)
    SECRET_FILE.write_text(new_secret)
    # Make owner-read-only: chmod 600
    os.chmod(SECRET_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return new_secret

SECRET = load_or_create_secret()
```

Add `butler_secret.key` to `.gitignore`:
```bash
echo "butler_secret.key" >> .gitignore
```

**⛔ WHAT NOT TO DO:**
- Don't hardcode the SECRET in source code — even if the repo is private today, it may not be tomorrow
- Don't derive the secret from the machine's hostname or MAC address — these can be spoofed

---

## 🟡 S6 — **NEW** — Flask Running in Debug Mode in Production

If `app.run(debug=True)` ever reaches a production user, the Werkzeug debugger exposes an interactive Python REPL on any exception — which is a complete remote code execution vulnerability. The PIN is found on the network interface page.

**✅ HOW TO FIX IT:**

```python
# Never hardcode debug=True
DEBUG = os.environ.get("BUTLER_DEBUG", "false").lower() == "true"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG, threaded=True)
```

Your setup script should never set `BUTLER_DEBUG=true` for end users.

Additionally, set `use_reloader=False` — the reloader spawns a second process that interferes with your state management and causes duplicate state saves:
```python
app.run(host="0.0.0.0", port=PORT, debug=DEBUG, threaded=True, use_reloader=False)
```

---

## 🟡 S7 — **NEW** — Script Execution Has No Timeout or Output Size Limit

`/api/execute` runs scripts via subprocess but doesn't cap how long they can run or how much output they can produce. A runaway script (or a malicious one) can hang the server indefinitely and flood memory with stdout.

**✅ HOW TO FIX IT:**

```python
import subprocess, resource

MAX_EXEC_SECONDS = 30
MAX_OUTPUT_BYTES = 1 * 1024 * 1024  # 1 MB

@app.route("/api/execute", methods=["POST"])
def execute():
    if not auth_device(): return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json(force=True) or {}
    script = d.get("script", "")
    timeout = min(int(d.get("timeout", 10)), MAX_EXEC_SECONDS)
    
    safe, reason = server_safety_check(script)
    if not safe:
        return jsonify({"error": f"Script blocked: {reason}", "blocked": True}), 400
    
    try:
        result = subprocess.run(
            ["python3", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        stderr = result.stderr[:MAX_OUTPUT_BYTES]
        
        if len(result.stdout) > MAX_OUTPUT_BYTES:
            stdout += "\n[OUTPUT TRUNCATED — exceeded 1MB limit]"
        
        return jsonify({
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": f"Script timed out after {timeout}s", "timeout": True}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

---

## 🟡 S8 — **NEW** — No CORS Restriction on the Flask Server

The server currently accepts requests from any `Origin`. While this doesn't matter for the React Native app (which doesn't send an `Origin` header), it means any website the user visits can make requests to `localhost:8766` via JavaScript `fetch()` — a technique known as localhost CSRF.

**✅ HOW TO FIX IT:**

```bash
pip install flask-cors
```

```python
from flask_cors import CORS

# Only allow requests from the Expo/RN app itself (no browser Origin)
# For local network tools, restricting to no-origin (native app) is sufficient
CORS(app, origins=[], allow_headers=["Content-Type", "X-Auth-Token"])
```

For tighter control, you can also add a custom header requirement:
```python
@app.before_request
def require_native_client():
    origin = request.headers.get("Origin", "")
    if origin and not origin.startswith("http://localhost"):
        return jsonify({"error": "Browser access not permitted"}), 403
```

---

---

# PART 4 — BUGS WITH FIXES

---

## 🔴 BUG1 — Onboarding Step Count Mismatch

App Access instructions say "6 welcome screens." The actual code has `TOTAL_STEPS = 10`. Reviewers will count to 6 and be confused.

**✅ FIX:** In your App Access instructions in Play Console, change to:
> *"Onboarding has 10 screens. Tap CONTINUE through each. All consent checkboxes must be ticked to proceed to the next screen."*

**Also fix the `STEP_LABELS` comment in welcome.tsx** — it says "10 steps" but the App Access instructions in app.json say 6. Make them match.

---

## 🔴 BUG2 — `saveAndFinish` Saves Consents Regardless of Whether User Accepted Them

In `welcome.tsx`, `saveAndFinish()` (called from Screen10) writes `'1'` for all consent keys including `CAMERA_CONSENT_KEY` and `REMOTE_EXEC_CONSENT_KEY` — even if the user skipped those optional checkboxes.

**✅ FIX:** Only write the keys that were actually accepted:
```typescript
const saveAndFinish = useCallback(async () => {
  const entries: [string, string][] = [
    [ONBOARDING_DONE_KEY, '1'],
    // Required — only save if actually consented
    ...(consents.age     ? [[AGE_CONFIRMED_KEY,        '1']] : []),
    ...(consents.tos     ? [[TERMS_ACCEPTED_KEY,       '1']] : []),
    ...(consents.privacy ? [[PRIVACY_ACCEPTED_KEY,     '1']] : []),
    ...(consents.lan     ? [[LAN_CONSENT_KEY,          '1']] : []),
    // Optional — only save if accepted
    ...(consents.camera  ? [[CAMERA_CONSENT_KEY,       '1']] : []),
    ...(consents.exec    ? [[REMOTE_EXEC_CONSENT_KEY,  '1']] : []),
    // Server privacy
    ...(serverAccepts.lan && serverAccepts.local && serverAccepts.install && serverAccepts.exec
        ? [[SERVER_PRIVACY_ACCEPTED_KEY, '1']] : []),
  ] as [string, string][];
  await AsyncStorage.multiSet(entries);
}, [consents, serverAccepts]);
```

**Add consent timestamps** (important for audit trail and Google compliance):
```typescript
await AsyncStorage.setItem('CONSENT_TIMESTAMP', new Date().toISOString());
await AsyncStorage.setItem('CONSENT_APP_VERSION', '7.1.0');
```

---

## 🔴 BUG3 — Metrics Endpoint Exposes Hostname Without Auth

`GET /api/metrics` and `/api/status/full` are **unauthenticated** and return `socket.gethostname()` and `sys.platform`. Anyone on the LAN can call this and get your PC's name and OS.

**✅ FIX:**
```python
@app.route("/api/metrics", methods=["GET", "POST"])
@app.route("/api/status/full", methods=["GET", "POST"])
def metrics():
    if not auth_device():
        return jsonify({"error": "Unauthorized"}), 401
    # ... rest of metrics logic
```

Keep `/health` unauthenticated but strip it to just:
```python
@app.route("/health")
def health():
    return jsonify({"status": "ok", "locked": bool(STATE["deviceId"])})
    # No version, no CPU, no RAM, no hostname
```

---

## 🟡 BUG4 — All 4 Legal Document Links in Onboarding Point to the Same URL

In `welcome.tsx`, Privacy Policy, Terms of Service, Data Safety Declaration, and Data Deletion Policy all link to `https://shawnjan-cmd.github.io/privacy-policy-/`. Google reviewers will tap each one expecting different documents and find the same page.

**✅ FIX — Create separate anchors or pages:**

Option A (Easiest) — Use URL fragments on the same page:
```tsx
const LEGAL_DOCS = [
  { title: 'Privacy Policy', url: 'https://shawnjan-cmd.github.io/privacy-policy-/#privacy' },
  { title: 'Terms of Service', url: 'https://shawnjan-cmd.github.io/privacy-policy-/#terms' },
  { title: 'Data Safety', url: 'https://shawnjan-cmd.github.io/privacy-policy-/#data-safety' },
  { title: 'Delete My Data', url: 'https://shawnjan-cmd.github.io/privacy-policy-/#delete' },
];
```
Then add matching `<a id="privacy">`, `<a id="terms">` etc. anchors to your GitHub Pages HTML.

Option B — Create separate pages: `privacy-policy.html`, `terms.html`, `data-safety.html`, `deletion.html`

**⛔ WHAT NOT TO DO:**
- Don't leave all four pointing to the same page — reviewers specifically check that ToS and Privacy Policy are separate documents

---

## 🟡 BUG5 — Screen 8 ("Server Privacy") Says HMAC Timestamp Validation Happens But It Doesn't

On Screen8ServerPrivacy, the card says: *"Replay attacks are prevented by timestamp validation."* This is currently FALSE — `verify_token()` never checks the timestamp (see Security fix S1 above).

**✅ FIX:**
Either implement the timestamp validation (fix S1 above, which you should do anyway) OR change the text to something accurate:
```tsx
body: 'Every request is signed with a shared HMAC-SHA256 secret. The server rejects requests with an invalid or tampered signature, preventing unauthorized execution.'
```

---

## 🟡 BUG6 — **NEW** — `useAutoReconnect` Exponential Backoff Has No Jitter

Your reconnect hook backs off exponentially (1s → 2s → 4s → 8s...) but without jitter. If multiple users (or multiple app instances) lose connection simultaneously — e.g., during server restart — they all retry at exactly the same intervals, causing a thundering herd that can crash the Flask server.

**✅ FIX:** Add random jitter to reconnect intervals:
```typescript
// In useAutoReconnect.js
const baseDelay = Math.min(1000 * Math.pow(2, attempt), 30000); // cap at 30s
const jitter = Math.random() * 1000; // up to 1s random jitter
const delay = baseDelay + jitter;
```

This is especially important once you have multiple users who may all be running the server on the same home network.

---

## 🟡 BUG7 — **NEW** — `contextManager.ts` Ollama Context Cap Can Cut Mid-Message

Your context manager caps at 20 messages or 12K characters, whichever comes first. But when it trims by character count it may cut in the middle of a message — passing a truncated JSON string or partial assistant response to Ollama, which causes garbled output.

**✅ FIX:** Always trim at message boundaries, never mid-message:
```typescript
// contextManager.ts
function trimContext(messages: Message[], maxChars: number): Message[] {
  let totalChars = 0;
  const result: Message[] = [];
  
  // Walk from newest to oldest, keeping whole messages
  for (let i = messages.length - 1; i >= 0; i--) {
    const msgChars = JSON.stringify(messages[i]).length;
    if (totalChars + msgChars > maxChars && result.length > 0) {
      break; // Stop before this message — we have at least one
    }
    result.unshift(messages[i]);
    totalChars += msgChars;
  }
  
  // Always keep at least the last 2 messages (user + assistant pair)
  if (result.length === 0 && messages.length > 0) {
    return messages.slice(-2);
  }
  return result;
}
```

---

## 🟡 BUG8 — **NEW** — `useChatHistory.ts` Debounced Write Can Drop Messages on App Backgrounding

Your debounced AsyncStorage write fires 500ms after the last message. If the user immediately backgrounds the app after sending a message (common: tap send, switch apps), the debounce timer is cancelled by React Native's component lifecycle and the message is never written to storage. The next session opens with the conversation missing the last message.

**✅ FIX:** Flush immediately on app state change to background:
```typescript
// In useChatHistory.ts — add this
import { AppState, AppStateStatus } from 'react-native';

useEffect(() => {
  const handleAppState = (state: AppStateStatus) => {
    if (state === 'background' || state === 'inactive') {
      // Cancel debounce and flush immediately
      debouncedSaveRef.current.cancel?.();
      saveHistoryNow(messages); // non-debounced version
    }
  };
  
  const sub = AppState.addEventListener('change', handleAppState);
  return () => sub.remove();
}, [messages]);
```

---

## 🟢 BUG9 — **NEW** — `ResponseMeta.tsx` Shows "0ms" on First Response

The response time calculation assumes `startTime` is set before the first API call, but if `startTime` isn't initialized until the first character arrives (streaming), the displayed time is always 0 for the first token.

**✅ FIX:** Set `startTime` at the moment `sendMessage` is called, not at first token arrival:
```typescript
// In ChatScreen.jsx or wherever streaming starts
const startTime = Date.now(); // Capture before awaiting anything
dispatch({ type: 'START_GENERATION', payload: { startTime } });
// Then pass startTime to ResponseMeta
```

---

---

# PART 5 — ONBOARDING: UPGRADES, TIPS & TRICKS

Your onboarding is genuinely well-built — 10 screens with consent gates, legal docs, Q&A, setup guide, animations, and haptics. Here's how to make it excellent.

---

## 🔴 ONBOARDING BUG — Screen 3 Consent Gate Mismatches Age Declaration

Screen 3 says "I am 18 years of age or older" but your store targets Teen 13+. Fix this first (see H3 above) — it's a blocker before anything else.

---

## 🟠 ONBOARDING UPGRADE — Add Consent Timestamps to Storage

Currently consents are saved as `'1'` with no timestamp. For Play Store compliance and user transparency, save with timestamp:

```typescript
// In saveAndFinish or when each consent is accepted:
const consentRecord = {
  accepted: true,
  timestamp: new Date().toISOString(),
  appVersion: '7.1.0',
  platform: Platform.OS,
};
await AsyncStorage.setItem('CONSENT_RECORD_V1', JSON.stringify(consentRecord));
```

---

## 🟠 ONBOARDING UPGRADE — Add a "Skip to App" Fast Path for Returning Users

Currently, returning users who already accepted everything have to tap through all 10 screens again (or most of them). You have the right idea with `allPreviouslyAccepted` — but it only changes the CTA text, not the flow.

**Better pattern:**
```typescript
// In WelcomeScreen's useEffect:
if (allPreviouslyAccepted) {
  // Show a 2-second summary splash then skip to tab
  setTimeout(() => router.replace('/(tabs)'), 2000);
}
```

Show a brief "Welcome back" screen with their accepted consents displayed as locked checkmarks, then auto-advance. This respects the returning user's time while still surfacing the consent state.

---

## 🟠 ONBOARDING UPGRADE — Add Progress Indicator

There's no visible step counter or progress bar. Users don't know how many screens remain. A simple "3 of 10" or a progress bar at the top dramatically reduces abandonment on long onboarding flows.

```tsx
function OnboardingProgress({ step, total }: { step: number; total: number }) {
  const progress = step / total;
  return (
    <View style={{ marginBottom: 16 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 }}>
        <Text style={{ fontSize: 10, color: C.textDim, fontFamily: MONO }}>
          STEP {step} OF {total}
        </Text>
        <Text style={{ fontSize: 10, color: C.textDim, fontFamily: MONO }}>
          {Math.round(progress * 100)}%
        </Text>
      </View>
      <View style={{ height: 2, backgroundColor: C.surface, borderRadius: 1 }}>
        <View style={{ height: 2, width: `${progress * 100}%`, backgroundColor: C.cyan, borderRadius: 1 }} />
      </View>
    </View>
  );
}
```

---

## 🟡 ONBOARDING UPGRADE — Consent Screen: Show What Happens If User Declines Optional Items

Screen 3 has optional checkboxes (camera, exec) but doesn't tell users what they miss out on if they don't accept. This increases anxiety and leads to blind "accept all."

**Add a "What if I skip this?" note to each optional consent:**
```tsx
<ConsentCheckbox
  checked={!!consents.camera}
  onToggle={() => toggle('camera')}
  label="Camera permission — QR code pairing only"
  sublabel="QR scan for instant pairing. Skip this: enter your PC's IP manually instead."
  color={C.purple}
/>
```

---

## 🟡 ONBOARDING UPGRADE — Screen 9 (Setup Guide): Add Direct Download Button

Screen 9 shows 5 setup steps and mentions `boter_setup.bat` / `boter_setup.sh` but provides no way to actually download them.

**✅ FIX:** Add a button that opens the GitHub release URL:
```tsx
<TouchableOpacity
  onPress={() => Linking.openURL('https://github.com/YOUR_USERNAME/butler-ai/releases/latest')}
  style={s.primaryBtn}
>
  <MaterialIcons name="download" size={18} color="#000" />
  <Text style={s.primaryBtnTxt}>OPEN DOWNLOAD PAGE</Text>
</TouchableOpacity>
```

---

## 🟡 ONBOARDING UPGRADE — Add a "What Your PC Needs" Checklist to Screen 9

The setup screen mentions Python 3.10+, but some users will have Python 2 or no Python at all. Add a pre-flight checklist:

```
✓ Windows 10/11, macOS 11+, or Ubuntu 20.04+
✓ Python 3.10 or newer (python.org)
✓ 100MB free disk space
✓ Phone and PC on the same Wi-Fi network
✓ Firewall allows port 8766 (the installer handles this)
```

---

## 🟡 ONBOARDING UPGRADE — Make Q&A Screen Searchable

Screen 7 has 12 Q&A items. On a small screen, users have to scroll through all of them. Add a simple text filter:

```tsx
const [qaFilter, setQaFilter] = useState('');
const filteredQAs = QAS.filter(qa =>
  qaFilter === '' ||
  qa.q.toLowerCase().includes(qaFilter.toLowerCase()) ||
  qa.a.toLowerCase().includes(qaFilter.toLowerCase())
);
```

---

## 🟢 ONBOARDING UPGRADE — Animate the "ALL DONE" Screen More

Screen 10 already has a pulsing launch button and check circle. Consider adding:
1. A small confetti burst when the screen first appears (use `react-native-reanimated` worklets)
2. A typewriter effect on "ALL DONE!"
3. The summary badges sliding in one-by-one

---

## 🟢 ONBOARDING TIP — Store Which Screens Were Completed, Not Just "Done"

Currently `ONBOARDING_DONE_KEY = '1'` is a binary. If onboarding crashes on Screen 7, the user has to start over. Store per-screen progress:

```typescript
// When each screen completes:
await AsyncStorage.setItem(`ONBOARDING_SCREEN_${step}_DONE`, '1');

// On restart, resume from last incomplete screen:
const lastCompleted = await findLastCompletedScreen();
setStep(lastCompleted + 1);
```

---

## 🟢 ONBOARDING TIP — Add a "This is a Developer Tool" Warning on Screen 1

Google reviewers appreciate explicit user-facing warnings for technical tools:

```tsx
<View style={{ borderWidth: 1.5, borderRadius: 10, borderColor: C.amber + '40',
  backgroundColor: C.amber + '08', padding: 12, marginBottom: 12 }}>
  <Text style={{ fontSize: 12, color: C.amber, fontFamily: MONO }}>
    ⚠️ DEVELOPER TOOL — For advanced users who run Python scripts on their own PC.
    Not a general-purpose AI assistant.
  </Text>
</View>
```

---

## 🟢 ONBOARDING TIP — **NEW** — Add a "Network Troubleshooting" Link on the Pairing Failure State

When pairing fails (the most common first-run failure), the app should show a link to a troubleshooting page rather than just "Connection failed." Users who hit this without guidance uninstall.

```tsx
// In your connection error state:
<TouchableOpacity onPress={() => Linking.openURL('https://github.com/YOUR_USERNAME/butler-ai/wiki/Troubleshooting')}>
  <Text style={{ color: C.cyan, fontSize: 12, fontFamily: MONO }}>
    → TROUBLESHOOTING GUIDE
  </Text>
</TouchableOpacity>
```

Content for that wiki page should cover: firewall rules, same-Wi-Fi check, Python not running, port 8766 blocked by router, Windows Defender blocking the script.

---

---

# PART 6 — STORE LISTING TIPS & TRICKS

---

## Screenshot Strategy (You Have 5, Should Have 8)

Your 5 screenshots cover: Homepage, Chat, QR, Scripts, Settings. Missing:
1. **Knowledge Base screen** — shows the AI learning system, a unique feature
2. **PC Health dashboard** — shows real-time CPU/RAM/Disk gauges, impressive
3. **Feature overview graphic** — a designed "hero" screenshot with text overlays showing "70+ Scripts · Local AI · No Cloud"

**Screenshot specs for Google Play:**
- Minimum 320px on shortest side, max 3840px on either side
- 16:9 aspect ratio recommended for phones (1080 × 1920 works perfectly)
- JPEG or 24-bit PNG, under 8 MB each
- Must accurately represent app content — no fake UI states

**Screenshot text overlay rules:**
- Max 20% of the screenshot can be text overlay
- Text must be legible at thumbnail size (minimum ~16pt equivalent)
- One clear message per screenshot — don't cram multiple features

**Screenshot 1 is the most important** — it shows in search results before users expand the listing. Make it show the most impressive or unique visual (the live CPU/RAM dashboard or the cyberpunk home screen) with a single bold line: *"Your PC. From Your Phone."*

---

## Description Keyword Placement

Google Play's search algorithm weights keywords by position. Put your most important keywords:
1. In the first 167 characters (visible without "Read more" expansion)
2. In the first 3 bullet points
3. In the app title (you already have this)

Most searched terms for this category: `remote desktop`, `python script`, `PC automation`, `local AI`, `terminal emulator`, `script runner`, `ollama android`.

---

## What's New / Release Notes

Google also indexes your "What's New" text for search. Write it as a feature list, not a changelog:
```
• Run Python, Bash, PowerShell from your phone
• Local AI chat with Ollama — 100% private, no API key
• 70+ built-in automation scripts
• QR code pairing — connect in seconds
• Real-time CPU, RAM, disk monitoring
```

---

## **NEW** — Localized Store Listings (Quick Win for Installs)

Play Console lets you create localized store listings for different regions. Even a basic Spanish and Portuguese translation of your title and short description can expand your addressable market by 40%+ (Latin America is a huge Android market).

Fastest approach: translate just the title + short description (80 chars max) using DeepL Pro. Don't translate the full description if you can't maintain it — a bad machine translation is worse than English.

Priority locales for your app category: `es-419` (Latin American Spanish), `pt-BR` (Brazilian Portuguese), `de-DE` (German), `fr-FR` (French).

---

---

# PART 7 — TRAPS AND ANTI-PATTERNS TO AVOID

---

### ⛔ Anti-Pattern 1: Adding Fake Review Deflection to Onboarding

Some developers add "If you're going to leave a low review, please email us first" screens in onboarding. Google explicitly bans this. It's called "review manipulation" and can get your developer account terminated.

---

### ⛔ Anti-Pattern 2: Putting "GOOGLE PLAY COMPLIANT" in Your App UI

Your Screen 1 has a `PlayStoreBadge` component that says "GOOGLE PLAY COMPLIANT" with a verified shield. **Do not ship this.** Google does not certify apps as compliant, and claiming Google endorsement of your app is a policy violation (misuse of brand). Remove this badge or change it to "Privacy First" or "No Cloud" or another claim you can substantiate.

---

### ⛔ Anti-Pattern 3: Using the Privacy Policy URL as the Developer Website

`playStoreDeveloperWebsite` in app.json points to the privacy policy URL. Google uses the developer website to assess developer legitimacy. A privacy policy URL is not a developer website. Create a simple landing page (even one HTML page on GitHub Pages at a different URL).

---

### ⛔ Anti-Pattern 4: Setting `usesCleartextTraffic: true` in BOTH app.json AND the network_security_config

You've done this — it's redundant. The `networkSecurityConfig` file overrides `usesCleartextTraffic` on Android 7+. Remove `"usesCleartextTraffic": true` from `app.json` and rely entirely on the `network_security_config.xml` which is already in place.

---

### ⛔ Anti-Pattern 5: Submitting Without Testing on a Real Clean Device

EAS builds in release mode behave differently from Expo Go in dev mode. Things that commonly break in release:
- Hermes JS engine disables some non-standard JS features
- ProGuard/R8 can mangle TypeScript class names used as string keys
- `expo-dev-client` must NOT be in the release build
- Metro bundler tree-shaking can remove code that side-effects were relying on

Before submitting: flash a clean Android device (factory reset), install only your release APK/AAB, and go through the entire onboarding + pairing flow manually.

---

### ⛔ Anti-Pattern 6: Using `console.log` in Production

ProGuard doesn't remove `console.log` calls. Release builds shipped with verbose logging leak internal state to anyone who connects a debugger or reads Logcat.

```typescript
// utils/logger.ts
const IS_PROD = process.env.NODE_ENV === 'production';
export const log = IS_PROD ? () => {} : console.log;
export const warn = IS_PROD ? () => {} : console.warn;
export const error = IS_PROD ? () => {} : console.error;
```

Replace all `console.log` with `log` from this module.

---

### ⛔ Anti-Pattern 7: Describing the App Differently in Different Places

Your app description in `app.json` says the app uses "local Ollama AI." Your `DATA_SAFETY.md` says chat goes to Google Gemini. Your `STORE_LISTING.md` doesn't mention Gemini at all. Your privacy policy mentions both. Google's reviewers cross-check all of these. Inconsistency signals that you don't understand your own app's data flows, which is a red flag.

Pick one source of truth for what the app does and replicate it consistently.

---

### ⛔ Anti-Pattern 8: Submitting to Production Before Closed Testing Is Complete

The production access questionnaire checks tester count at submission time. If you don't have 12 opted-in testers when you click "Apply," it fails and you have to wait and reapply. Get all 12 testers confirmed and active for 14 days first, then apply.

---

### ⛔ Anti-Pattern 9: Hardcoding the Demo Server IP in a Shipped Binary

If you add a demo server to help reviewers, do not hardcode the demo server's IP in the production APK. Keep the demo server IP in a remote config or make it user-configurable.

---

### ⛔ Anti-Pattern 10: Thinking Google Only Checks Your App on Submission

Google's Play Protect and policy engine does ongoing post-publish scans. The most common triggers for post-publish removal:
- A dependency update introducing a new SDK that collects data not in your Data Safety form
- A user report triggering a manual review
- A new Google policy that your app now violates
- Your privacy policy URL going dead

Check your Play Console account weekly after publishing.

---

### ⛔ Anti-Pattern 11 — **NEW** — Bundling Python or Node.js Interpreter in the APK

Several "PC remote execution" apps on the Play Store have been removed for bundling a Python interpreter inside the APK, because it allows executing arbitrary downloaded code — which violates Google's policy on device abuse. Your app doesn't do this (it runs Python on the PC), but make sure this is clear in your store description. If Google reviewers misunderstand and think the app runs scripts locally on the Android device, they may reject it.

Add a clarifying line to your description: *"All scripts run on your home PC. No code executes on your Android device."*

---

### ⛔ Anti-Pattern 12 — **NEW** — Storing the Session Token in AsyncStorage Without Encryption

`AsyncStorage` on Android is stored in plaintext in `/data/data/com.butlerai.pc.automation/databases/`. On a rooted device, any app with root access can read it. Your session token is what grants full script execution access to the PC server.

**Better approach:** Use `expo-secure-store` for sensitive values:
```bash
pnpm add expo-secure-store
```
```typescript
import * as SecureStore from 'expo-secure-store';

// Store token securely (uses Android Keystore / iOS Keychain)
await SecureStore.setItemAsync('session_token', token);
const token = await SecureStore.getItemAsync('session_token');
```

SecureStore uses the Android Keystore on Android 6+ and is significantly harder to extract even on rooted devices.

---

### ⛔ Anti-Pattern 13 — **NEW** — Not Handling the Case Where Ollama Isn't Running

The most common support request for any Ollama-based app is "why doesn't the chat work?" — and the answer is almost always "Ollama isn't running." Currently, the app sends a chat message to the server, the server calls `localhost:11434`, gets a connection refused error, and returns a 500 to the app.

The app should detect this specific case and show a helpful error:
```typescript
// In your error classifier (you already have one — extend it)
if (errorMessage.includes('11434') || errorMessage.includes('ollama')) {
  return {
    type: 'OLLAMA_NOT_RUNNING',
    userMessage: 'Ollama is not running on your PC. Open a terminal and run: ollama serve',
    actionLabel: 'LEARN HOW TO FIX',
    actionUrl: 'https://ollama.ai/download',
  };
}
```

---

---

# PART 8 — **NEW** — REACT NATIVE ARCHITECTURE & CODE QUALITY

---

## 🟠 RN1 — FlashList `estimatedItemSize` Should Be Measured, Not Guessed

Your `ChatScreen.jsx` uses `FlashList` which is great for performance. But `estimatedItemSize` is likely set to an arbitrary value (e.g., 80). If the actual average rendered height differs significantly from this value, FlashList's internal recycler will produce scroll position jumps and layout jank.

**✅ HOW TO FIX IT:**

Log the actual rendered sizes during development:
```tsx
<FlashList
  data={messages}
  renderItem={renderMessage}
  estimatedItemSize={100} // start here
  onLoad={({ elapsedTimeInMs }) => {
    // After first render, check Flipper or console for
    // "FlashList: estimatedItemSize mismatch" warnings
    console.log(`List rendered in ${elapsedTimeInMs}ms`);
  }}
/>
```

A practical approach: render 20 typical messages in dev mode, measure with `onLayout`, compute the average, and use that as your `estimatedItemSize`.

---

## 🟠 RN2 — `useReducer` in ChatScreen Creates New Object References on Every Action

If your `useReducer` in `ChatScreen.jsx` returns a new messages array on every dispatch (including `SET_STREAMING_TEXT` updates that fire ~10 times/second during generation), any child component subscribed to the messages array will re-render on every token.

**✅ HOW TO FIX IT:**

For streaming updates, update only the tail of the array in-place rather than spreading the whole array:
```typescript
case 'APPEND_TOKEN':
  // WRONG: creates new array on every token
  return { ...state, messages: [...state.messages.slice(0, -1), updatedLastMsg] };
  
  // BETTER: use immer or a ref for in-flight message
  // Keep the streaming message in a separate ref, only merge into state on completion
```

Consider using a `streamingMessageRef` (a React `useRef`) to accumulate tokens without triggering re-renders, and only dispatch to the reducer when the stream completes or at 200ms intervals.

---

## 🟠 RN3 — TypeScript Barrel Export (`utils/index.ts`) Needs Periodic Auditing

The barrel export pattern you adopted is good for preventing "export-but-never-import" bugs. But barrel files can also cause tree-shaking problems: if any import in `utils/index.ts` has a side effect (e.g., runs code at module initialization), importing ANY utility from that barrel will execute all side effects.

**✅ HOW TO FIX IT:**

Check your `utils/index.ts` for any exports that run code at import time:
```bash
# Find files that have top-level code (not just function/class/const declarations)
grep -n "^[^a-z]" utils/*.ts | grep -v "^.*:export\|^.*:import\|^.*:const\|^.*:function\|^.*:class\|^.*:type\|^.*:interface\|^.*://"
```

Any file with top-level side effects should NOT be in the barrel.

---

## 🟡 RN4 — Missing `keyExtractor` Stability Guarantee in Message List

If your `keyExtractor` for chat messages uses array index (`(_, index) => String(index)`) rather than a stable message ID, inserting or prepending messages will cause FlashList to re-render the entire visible window.

**✅ HOW TO FIX IT:**

Ensure every message has a stable ID:
```typescript
// When creating messages, always assign a unique ID
const newMessage: Message = {
  id: `msg_${Date.now()}_${Math.random().toString(36).slice(2)}`,
  role: 'user',
  content: text,
  timestamp: Date.now(),
};

// In FlashList:
keyExtractor={(item) => item.id}
```

---

## 🟡 RN5 — No Error Boundary Around the Chat Tab

If `ChatScreen.jsx` throws during render (e.g., a null message object from a corrupted AsyncStorage history), the entire app crashes with a white screen. There's no error boundary to catch this.

**✅ HOW TO FIX IT:**

```tsx
// components/ErrorBoundary.tsx
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  State
> {
  state: State = { hasError: false };
  
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info);
  }
  
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 }}>
          <Text style={{ color: '#ff4444', fontFamily: 'JetBrainsMono', fontSize: 14 }}>
            RENDER ERROR — {this.state.error?.message}
          </Text>
          <TouchableOpacity onPress={() => this.setState({ hasError: false })}>
            <Text style={{ color: '#00bcd4', marginTop: 16 }}>RETRY</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}
```

Wrap each tab screen:
```tsx
<ErrorBoundary>
  <ChatScreen />
</ErrorBoundary>
```

---

## 🟡 RN6 — No Deep Link / Universal Link Support

If someone shares a "butler://connect?ip=192.168.1.5&port=8766" link (e.g., via AirDrop-equivalent or NFC tag), the app can't handle it. Adding deep link support for the pairing flow would dramatically improve the UX for technically sophisticated users.

**✅ HOW TO FIX IT:**

In `app.json`:
```json
{
  "expo": {
    "scheme": "butler",
    "intentFilters": [
      {
        "action": "VIEW",
        "data": [{ "scheme": "butler" }],
        "category": ["BROWSABLE", "DEFAULT"]
      }
    ]
  }
}
```

In your app router:
```typescript
// In _layout.tsx or a useEffect:
import * as Linking from 'expo-linking';

const url = await Linking.getInitialURL();
if (url) {
  const { queryParams } = Linking.parse(url);
  if (queryParams?.ip && queryParams?.port) {
    // Auto-populate the manual pairing form
    navigation.navigate('Pairing', { ip: queryParams.ip, port: queryParams.port });
  }
}
```

---

## 🟢 RN7 — Consider Migrating from Expo Router File-Based Routing to Typed Routes

Expo Router v3+ supports typed routes via `expo-router/types`. This gives you TypeScript autocomplete on `router.push()` calls and catches routing mistakes at compile time rather than runtime.

```bash
pnpm add expo-router@latest
```

Enable in `app.json`:
```json
{
  "expo": {
    "experiments": {
      "typedRoutes": true
    }
  }
}
```

---

---

# PART 9 — **NEW** — SERVER PERFORMANCE & RELIABILITY

---

## 🟠 P1 — Flask's Single-Threaded Default Will Stall Under Concurrent Requests

Flask's built-in dev server is single-threaded by default. If `butler_server.py` runs a 10-second script AND the app simultaneously sends a `/api/metrics` poll, the metrics request queues behind the script and the app UI shows a fake "disconnected" state.

**✅ HOW TO FIX IT:**

You're already using `threaded=True` in `app.run()` — good. But also set a thread pool limit to prevent runaway script execution from consuming all threads:

```python
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import threading

# Allow max 4 concurrent script executions
_script_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="butler-exec")
_script_semaphore = threading.Semaphore(4)

@app.route("/api/execute", methods=["POST"])
def execute():
    if not auth_device(): return jsonify({"error": "Unauthorized"}), 401
    
    if not _script_semaphore.acquire(blocking=False):
        return jsonify({"error": "Server busy — max concurrent scripts running"}), 503
    
    try:
        # ... execute script
        pass
    finally:
        _script_semaphore.release()
```

**For production use**, consider replacing Flask's built-in server with `waitress` (cross-platform, production-grade WSGI):
```bash
pip install waitress
```
```python
# Replace app.run() with:
from waitress import serve
serve(app, host="0.0.0.0", port=PORT, threads=8)
```

`waitress` handles concurrent requests properly without any code changes to your routes.

---

## 🟠 P2 — State Save Race Condition on Concurrent Pair + Execute

Already flagged in previous sessions. Adding here for completeness with a complete fix:

```python
import threading
_state_lock = threading.Lock()

def save_state():
    with _state_lock:
        with open(STATE_FILE, "w") as f:
            json.dump(STATE, f, indent=2)

def load_state():
    with _state_lock:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}  # Corrupted state — return empty, don't crash
    return {}
```

---

## 🟠 P3 — No Graceful Shutdown Handler

If the user kills the server with Ctrl+C while a script is running, the subprocess is orphaned and continues running in the background. On the next server start, the port may be in use and the server fails to bind.

**✅ HOW TO FIX IT:**

```python
import signal, subprocess
_running_procs: list[subprocess.Popen] = []

def _shutdown_handler(sig, frame):
    print("\n[Butler] Shutting down...")
    for proc in _running_procs:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except:
            proc.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)
```

Track every subprocess you spawn in `_running_procs` and remove them when they complete.

---

## 🟡 P4 — Unbounded Rate-Limiter Dictionary (Memory Leak)

Already identified in previous sessions. The `_req_log` dictionary grows unboundedly. After days of uptime, it consumes significant memory.

**✅ FIX (complete version):**

```python
import time
from collections import defaultdict

_req_log: dict[str, list[float]] = defaultdict(list)
_req_log_last_prune: float = time.time()
_REQ_LOG_PRUNE_INTERVAL = 300  # Prune every 5 minutes

def rate_limit(ip: str, endpoint: str, max_req: int = 5, window: int = 60) -> bool:
    global _req_log_last_prune
    now = time.time()
    
    # Global prune pass every 5 minutes
    if now - _req_log_last_prune > _REQ_LOG_PRUNE_INTERVAL:
        expired_keys = [k for k, times in _req_log.items()
                       if not any(now - t < window for t in times)]
        for k in expired_keys:
            del _req_log[k]
        _req_log_last_prune = now
    
    key = f"{ip}:{endpoint}"
    _req_log[key] = [t for t in _req_log[key] if now - t < window]
    if len(_req_log[key]) >= max_req:
        return False
    _req_log[key].append(now)
    return True
```

---

## 🟡 P5 — No Health Check for Ollama Before Forwarding Chat

The server forwards chat requests to Ollama at `localhost:11434` without first checking if Ollama is responsive. If Ollama crashes or is OOM-killed mid-session, the server times out after 60+ seconds with no useful error.

**✅ HOW TO FIX IT:**

```python
import httpx  # or requests

def check_ollama() -> tuple[bool, str]:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, f"OK — {len(models)} model(s) loaded"
        return False, f"Ollama returned HTTP {r.status_code}"
    except Exception as e:
        return False, f"Ollama not reachable: {e}"

@app.route("/api/ollama/status", methods=["GET"])
def ollama_status():
    if not auth_device(): return jsonify({"error": "Unauthorized"}), 401
    ok, msg = check_ollama()
    return jsonify({"available": ok, "message": msg})
```

Call this before any `/api/chat` request on the server side, and surface a clear error to the app if Ollama is down.

---

## 🟡 P6 — SQLite KB Writes Block Flask Request Threads

Already covered in previous sessions (WAL mode, FTS5, thread-local connections). Checklist for completeness:

```python
# Required pragmas on every connection:
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA cache_size=-32000")  # 32MB page cache
conn.execute("PRAGMA busy_timeout=5000")  # 5s timeout before SQLITE_BUSY

# FTS5 table for fast search:
conn.execute("""
  CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
    title, content, content='kb_entries', content_rowid='id'
  )
""")
```

---

---

# PART 10 — **NEW** — POST-LAUNCH OPERATIONS

---

## 🟠 OPS1 — Set Up Firebase Crashlytics Before Launch

Once the app is live, crashes in production are invisible without a crash reporter. You'll only find out when users leave 1-star reviews saying "app crashes on startup."

**✅ HOW TO FIX IT:**

Expo has first-class Sentry integration (alternative to Crashlytics, easier with Expo):
```bash
pnpm add @sentry/react-native
npx sentry-wizard@latest -i reactNative
```

Initialize in `app/_layout.tsx`:
```typescript
import * as Sentry from '@sentry/react-native';

Sentry.init({
  dsn: 'YOUR_SENTRY_DSN',
  environment: process.env.NODE_ENV,
  // Don't send PII
  beforeSend(event) {
    delete event.user;
    return event;
  }
});
```

Sentry's free tier allows 5,000 errors/month — more than enough for a new app.

**Note:** Add Sentry to your Data Safety form — it collects crash data and device info.

---

## 🟠 OPS2 — Create a GitHub Release Workflow Before Launch

Users who find the server setup confusing will look for a GitHub release with pre-packaged server files. Currently there's no automated release process.

**✅ HOW TO FIX IT:**

Create `.github/workflows/release.yml`:
```yaml
name: Release
on:
  push:
    tags:
      - 'v*'

jobs:
  package-server:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Package server files
        run: |
          mkdir -p release/butler-server
          cp butler_server.py requirements.txt setup.bat setup.sh release/butler-server/
          cd release && zip -r butler-server-${{ github.ref_name }}.zip butler-server/
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: release/butler-server-*.zip
          generate_release_notes: true
```

Then when you tag a release (`git tag v7.1.0 && git push --tags`), users get a clean download link.

---

## 🟠 OPS3 — Plan for App Updates After Publication

Many first-time Play Store publishers don't realize that every code update requires:
1. Bumping `versionCode` (integer) and `version` (string) in `app.json`
2. Running `eas build --platform android --profile production` again
3. Uploading the new AAB to the Production track in Play Console
4. Going through Google's review again (typically 1–3 days, sometimes instant)

**Timeline planning for urgent fixes:** If you discover a critical bug post-launch, expect 1–3 days before the fix reaches users after submission. For a security critical fix, you can flag it in Play Console as "critical update" which sometimes speeds up review.

**Build a simple version bump script:**
```bash
#!/bin/bash
# scripts/bump.sh
CURRENT_VERSION=$(cat app.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['expo']['version'])")
CURRENT_CODE=$(cat app.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['expo']['android']['versionCode'])")
echo "Current: $CURRENT_VERSION (code $CURRENT_CODE)"
NEW_CODE=$((CURRENT_CODE + 1))
read -p "New version string (e.g. 7.2.0): " NEW_VERSION
python3 -c "
import json
with open('app.json') as f: d = json.load(f)
d['expo']['version'] = '$NEW_VERSION'
d['expo']['android']['versionCode'] = $NEW_CODE
with open('app.json', 'w') as f: json.dump(d, f, indent=2)
print('Updated app.json')
"
```

---

## 🟡 OPS4 — Monitor Your Privacy Policy URL

If your GitHub Pages URL ever goes dead (repository renamed, GitHub Pages disabled, account suspended), Google will detect that the privacy policy URL returns 404 and may remove your app from the store.

**✅ HOW TO FIX IT:**

Set up a free uptime monitor on the privacy policy URL:
- UptimeRobot (free, checks every 5 minutes, sends email on failure)
- BetterUptime (free tier available)

Also: do NOT use a GitHub Pages URL from a personal repository as your permanent policy URL. Personal accounts can delete repos. Consider buying a $10/year domain and hosting it there — gives your store listing far more credibility too.

---

## 🟡 OPS5 — Prepare a User-Facing Changelog Page

Google doesn't require this, but users who see "Bug fixes and performance improvements" in your "What's New" repeatedly stop trusting the developer. A public changelog (even a simple GitHub releases page with descriptions) builds trust and gets users to update faster.

Template for each release:
```
v7.1.0 — May 2026

✅ Fixed: Pairing PIN expiry sometimes triggered before 5 minutes
✅ Fixed: Chat history lost when backgrounding app mid-message
🆕 Added: Knowledge Base search is now full-text (FTS5)
🆕 Added: Server now shows Ollama model list at startup
⚡ Improved: Metrics polling now 40% more efficient
```

---

---

# PART 11 — **NEW** — iOS CONSIDERATIONS (IF YOU PLAN TO SHIP ON APP STORE)

Your app is Android-first but built in React Native, so iOS is a natural eventual target. Here's what's different:

---

## 🔴 iOS1 — Local Network Permission Required on iOS

On iOS, any app that scans the local network (for LAN discovery) must request `NSLocalNetworkUsageDescription`. Without it, the iOS networking stack silently blocks all local network access and the app appears broken.

**In `app.json`:**
```json
{
  "expo": {
    "ios": {
      "infoPlist": {
        "NSLocalNetworkUsageDescription": "Butler AI needs local network access to connect to your PC server.",
        "NSBonjourServices": ["_butler._tcp"]
      }
    }
  }
}
```

Apple's App Store review team manually checks that your stated usage description is accurate. "Needs local network access to connect to your PC server" is accurate and specific — good.

---

## 🔴 iOS2 — App Store Requires Privacy Manifest File (PrivacyInfo.xcprivacy)

As of May 2024, Apple requires a `PrivacyInfo.xcprivacy` file declaring all "required reason" API usage. React Native and several common SDKs use APIs on Apple's required-reason list.

**Create `ios/PrivacyInfo.xcprivacy`:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>NSPrivacyTracking</key>
  <false/>
  <key>NSPrivacyTrackingDomains</key>
  <array/>
  <key>NSPrivacyCollectedDataTypes</key>
  <array/>
  <key>NSPrivacyAccessedAPITypes</key>
  <array>
    <dict>
      <!-- UserDefaults (AsyncStorage uses this) -->
      <key>NSPrivacyAccessedAPIType</key>
      <string>NSPrivacyAccessedAPICategoryUserDefaults</string>
      <key>NSPrivacyAccessedAPITypeReasons</key>
      <array>
        <string>CA92.1</string>
      </array>
    </dict>
    <dict>
      <!-- File timestamp APIs -->
      <key>NSPrivacyAccessedAPIType</key>
      <string>NSPrivacyAccessedAPICategoryFileTimestamp</string>
      <key>NSPrivacyAccessedAPITypeReasons</key>
      <array>
        <string>C617.1</string>
      </array>
    </dict>
  </array>
</dict>
</plist>
```

Check every React Native dependency for their own privacy manifests — Expo SDK 50+ includes them for most core packages.

---

## 🟠 iOS3 — `expo-secure-store` Has Different Behavior on iOS vs Android

On Android, SecureStore uses Android Keystore. On iOS, it uses the iOS Keychain. The key difference: on iOS, Keychain items persist across app uninstalls by default. This means a user who deletes and reinstalls the app will still have their old session token — which may be expired — leading to confusing "token expired" errors on a fresh install.

**✅ FIX:**
```typescript
import * as SecureStore from 'expo-secure-store';

// On iOS, set accessible to WHEN_UNLOCKED_THIS_DEVICE_ONLY
// and delete on fresh install by checking an install marker
const IS_FRESH_INSTALL_KEY = '@butler_install_marker';
const marker = await AsyncStorage.getItem(IS_FRESH_INSTALL_KEY);
if (!marker) {
  // Fresh install — clear any stale keychain data
  await SecureStore.deleteItemAsync('session_token');
  await AsyncStorage.setItem(IS_FRESH_INSTALL_KEY, Date.now().toString());
}
```

---

## 🟡 iOS4 — Apple's Review Team Is Stricter About "Remote Execution" Apps

Apple's App Review team has historically been very cautious about apps that can execute arbitrary code remotely. Your app does this (it sends Python/Bash scripts to run on a PC). This is completely fine and legal, but you need to frame it correctly in your App Store review notes:

- Emphasize that all scripts run on the user's own PC, not on Apple's infrastructure
- Emphasize that the server software must be manually installed by the user on their own computer
- Include the demo mode (see B3) so reviewers can evaluate the full UI without a PC
- In the reviewer notes, explicitly state: *"Scripts execute on the user's home PC via a locally-installed Python server. The iOS app is a remote control interface only. No code runs on the iOS device."*

---

---

# PART 7 (EXTENDED) — ADDITIONAL ANTI-PATTERNS

---

### ⛔ Anti-Pattern 14 — **NEW** — Using `Math.random()` for Security-Sensitive IDs

If your `deviceId` generation uses `Math.random()`, it is NOT cryptographically random. On V8/Hermes, `Math.random()` is a deterministic PRNG seeded at startup — predictable by an attacker who knows the seed.

**✅ FIX:**
```typescript
// WRONG:
const deviceId = Math.random().toString(36).substring(2);

// RIGHT — use crypto-grade randomness:
import * as Crypto from 'expo-crypto';
const deviceId = await Crypto.randomUUID(); // Returns a cryptographically random UUID v4
```

---

### ⛔ Anti-Pattern 15 — **NEW** — Not Versioning Your AsyncStorage Schema

Currently, if you change the shape of any stored object (e.g., adding a field to a message object or changing the consent storage format), users who upgrade will have the old format in their storage. If your new code expects a field that doesn't exist in the old format, you get undefined errors or silent data corruption.

**✅ FIX:** Version your storage schema and run migrations on app startup:
```typescript
const STORAGE_SCHEMA_VERSION = 2;
const STORED_VERSION_KEY = '@butler_schema_version';

async function migrateStorage() {
  const stored = await AsyncStorage.getItem(STORED_VERSION_KEY);
  const version = stored ? parseInt(stored) : 0;
  
  if (version < 1) {
    // Migration from v0 → v1: add 'platform' field to consent record
    const consent = await AsyncStorage.getItem('CONSENT_RECORD');
    if (consent) {
      const parsed = JSON.parse(consent);
      await AsyncStorage.setItem('CONSENT_RECORD_V1', JSON.stringify({ ...parsed, platform: 'android' }));
    }
  }
  
  if (version < 2) {
    // Migration from v1 → v2: add message IDs to chat history
    // ...
  }
  
  await AsyncStorage.setItem(STORED_VERSION_KEY, String(STORAGE_SCHEMA_VERSION));
}

// Call in app startup, before rendering:
await migrateStorage();
```

---

---

# SUMMARY CHECKLIST (Print This)

## Blockers to Fix Before Building AAB
- [ ] Create 1024×500 Feature Graphic
- [ ] Fix port mismatch (server 8766 vs docs 5000)
- [ ] Fix `.gitignore` to include `.env` and purge history
- [ ] Add token expiry to `verify_token()` — 24h TTL
- [ ] Add PIN requirement to `/pair` endpoint
- [ ] Add auth to `/api/reset_pair`
- [ ] Add auth to `/api/metrics` and `/api/status/full`
- [ ] Change age gate from 18+ to 13+ (to match Teen rating)
- [ ] Canonicalize app name to "Butler AI: PC Automation" everywhere
- [ ] Remove: `@stripe/stripe-react-native`, `react-native-webrtc`, `expo-location`, `expo-contacts`, `expo-calendar`, `expo-screen-capture`, `@supabase/supabase-js`
- [ ] Update Privacy Policy to say v7.1.0
- [ ] Add demo mode OR set up a persistent demo server for reviewers
- [ ] Update consent `saveAndFinish` to respect which checkboxes were actually ticked
- [ ] Update App Access instructions with correct port and correct step count (10)
- [ ] Remove the "GOOGLE PLAY COMPLIANT" PlayStoreBadge component or rename it
- [ ] Set `NODE_ENV=production` in EAS production build profile **[NEW]**
- [ ] Lock and verify `applicationId` before first AAB upload **[NEW]**
- [ ] Plan `versionCode` strategy (recommend: MAJOR*100000+MINOR*1000+PATCH*10) **[NEW]**
- [ ] Migrate session token storage from AsyncStorage to `expo-secure-store` **[NEW]**
- [ ] Move `SECRET` key to separate `butler_secret.key` file, chmod 600 **[NEW]**
- [ ] Add Flask debug mode guard (`BUTLER_DEBUG` env var) **[NEW]**
- [ ] Add script execution timeout (max 30s) and output size cap (1MB) **[NEW]**
- [ ] Replace `Math.random()` deviceId generation with `expo-crypto` UUID **[NEW]**

## Before Submitting to Play Console
- [ ] 12 Closed Testing testers opted in for 14 consecutive days
- [ ] Feature Graphic uploaded (1024×500)
- [ ] Screenshots re-exported at 1080×1920 (all 8 slots filled)
- [ ] All 4 legal doc links point to different pages/anchors
- [ ] Data Safety form updated (Supabase/Gemini removed)
- [ ] Developer Website URL is separate from Privacy Policy URL
- [ ] Content rating: Teen 13+ (IARC questionnaire answered)
- [ ] Target Audience: Older teens and adults (not Children)
- [ ] Ads: No
- [ ] Tested on a real clean device in release mode end-to-end
- [ ] Description includes "All scripts run on your home PC. No code runs on your Android device." **[NEW]**
- [ ] Add Sentry (or equivalent crash reporter) before launch **[NEW]**
- [ ] GitHub Release workflow set up for server package downloads **[NEW]**
- [ ] UptimeRobot monitoring set up on privacy policy URL **[NEW]**

## After Launch (First 30 Days)
- [ ] Check Play Console daily for reviews and policy flags
- [ ] Verify crash rate < 1% in Android Vitals
- [ ] Check ANR (App Not Responding) rate < 0.47% (Play Store threshold)
- [ ] Respond to all reviews within 24 hours (affects store ranking)
- [ ] Ship at least one update in first 30 days (signals active maintenance)
- [ ] Set up UptimeRobot alert for privacy policy URL

---
*Total unique issues: 12 Blockers · 16 High · 22 Medium · 12 Low · 15 Anti-Patterns*
*New in v3: +2 Blockers · +4 High · +7 Medium · +4 Low · +5 Anti-Patterns · 4 new parts (React Native Architecture, Server Performance, Post-Launch Ops, iOS)*
