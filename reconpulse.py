#!/usr/bin/env python3
"""ReconPulse — Automated Bug Bounty Reconnaissance Pipeline"""
import sys, json, subprocess, argparse, time, re, os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BANNER = "\033[1;32m╔══════════════════════════════════════════════════════════╗\n║  ReconPulse — Automated Bug Bounty Recon Pipeline v1.0   ║\n╚══════════════════════════════════════════════════════════╝\033[0m"

OUTPUT_DIR = "./recon_output"
TIMEOUT = 5
THREADS = 20

def log(msg, level="INFO"):
    colors = {"INFO": "\033[1;36m", "OK": "\033[1;32m", "WARN": "\033[1;33m", "ERR": "\033[1;31m"}
    print(f"{colors.get(level, '')}[{level}]\033[0m {msg}")

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return "", 1

def subfinder_enum(domain):
    log(f"Enumerating subdomains for {domain}...")
    out, _ = run_cmd(f"subfinder -d {domain} -silent -max-time 30 2>/dev/null", timeout=35)
    subs = [s for s in out.split('\n') if s]
    log(f"Found {len(subs)} subdomains", "OK")
    return subs

def probe_host(host):
    try:
        cmd = f"curl -sk -m {TIMEOUT} -o /dev/null -w '%{{http_code}}|%{{size_download}}' 'https://{host}'"
        out, _ = run_cmd(cmd, timeout=TIMEOUT+2)
        parts = out.split('|')
        if len(parts) == 2 and parts[0].isdigit():
            return {"host": host, "status": int(parts[0]), "size": int(parts[1])}
    except: pass
    return None

def probe_tech(host):
    try:
        cmd = f"curl -sk -m {TIMEOUT} -D- 'https://{host}' -o /dev/null"
        headers, _ = run_cmd(cmd, timeout=TIMEOUT+2)
        tech = []
        for h in ['x-powered-by', 'server']:
            m = re.search(rf'(?i){h}:\s*(.+)', headers)
            if m: tech.append(m.group(1).strip())
        return {'host': host, 'tech': tech}
    except: return None

def extract_js(host):
    try:
        html, _ = run_cmd(f"curl -sk -m {TIMEOUT} 'https://{host}'", timeout=TIMEOUT+2)
        js_files = re.findall(r'src="([^"]*\.js)"', html)
        endpoints = re.findall(r'https?://[a-zA-Z0-9._-]+/[a-zA-Z0-9/._?=&%-]{5,200}', html)
        return {'host': host, 'js_count': len(js_files), 'js_files': js_files[:10], 'endpoints': endpoints[:20]}
    except: return None

def scan(target):
    log(f"Starting ReconPulse scan on {target}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    subs = subfinder_enum(target) or [target]
    
    log(f"Probing {len(subs)} hosts")
    results = []
    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        for f in as_completed([ex.submit(probe_host, s) for s in subs]):
            r = f.result()
            if r and r['status'] in [200, 301, 302, 401, 403]: results.append(r)
    
    live = [r for r in results if r['status'] == 200]
    log(f"Live hosts: {len(live)}/{len(subs)}", "OK")
    
    tech_results, js_results = [], []
    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        for f in as_completed([ex.submit(probe_tech, r['host']) for r in live]):
            r = f.result()
            if r: tech_results.append(r)
        for f in as_completed([ex.submit(extract_js, r['host']) for r in live]):
            r = f.result()
            if r: js_results.append(r)
    
    log(f"Technology fingerprints: {len(tech_results)}", "OK")
    log(f"JS bundles analyzed: {sum(len(r.get('js_files',[])) for r in js_results)}", "OK")
    
    report = {
        "scan_time": datetime.now().isoformat(), "target": target,
        "total_subdomains": len(subs), "live_hosts": len(live),
        "results": [{"host": r['host'], "status": r['status'],
                      "tech": next((t['tech'] for t in tech_results if t['host']==r['host']), [])}
                     for r in results],
        "js_findings": js_results
    }
    
    path = os.path.join(OUTPUT_DIR, f"recon_{target}_{int(time.time())}.json")
    with open(path, 'w') as f: json.dump(report, f, indent=2)
    log(f"Report saved to {path}", "OK")
    _summary(report)

def report():
    files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.startswith('recon_')])
    if not files: return log("No reports found", "WARN")
    with open(os.path.join(OUTPUT_DIR, files[-1])) as f: _summary(json.load(f))

def _summary(r):
    print(f"\n\033[1;35m═══ SCAN SUMMARY ═══\033[0m")
    print(f"  Target: {r['target']}  |  Subs: {r['total_subdomains']}  |  Live: {r['live_hosts']}")
    for h in r['results'][:10]:
        t = ', '.join(h.get('tech', [])) or 'unknown'
        print(f"  \033[1;32m{h['host']}\033[0m [{h['status']}] — {t}")

def main():
    print(BANNER)
    p = argparse.ArgumentParser(description='ReconPulse — Automated Recon Pipeline')
    p.add_argument('command', choices=['scan', 'report', 'monitor'])
    p.add_argument('-t', '--target', help='Target domain')
    p.add_argument('-o', '--output', default='./recon_output')
    p.add_argument('--threads', type=int, default=20)
    args = p.parse_args()
    global OUTPUT_DIR, THREADS
    OUTPUT_DIR, THREADS = args.output, args.threads
    
    if args.command == 'scan':
        if not args.target: return log("Target required: -t example.com", "ERR")
        scan(args.target)
    elif args.command == 'report': report()
    elif args.command == 'monitor':
        log("Monitor mode — 60s intervals")
        while True:
            scan(args.target) if args.target else report()
            time.sleep(60)

if __name__ == '__main__': main()
