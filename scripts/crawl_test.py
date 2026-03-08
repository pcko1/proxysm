"""Crawl 10 websites 10 times each through the proxy rotator."""
import concurrent.futures
import time
import subprocess

PROXY = "http://crawl-test:wCDbmkI_wP6UzgSc3DS92EhUiTM9Wm7-a4Wk4imeIWw@localhost:9080"

TARGETS = [
    "http://httpbin.org/ip",
    "http://httpbin.org/headers",
    "http://example.com",
    "http://jsonplaceholder.typicode.com/posts/1",
    "http://jsonplaceholder.typicode.com/users/1",
    "http://wttr.in/?format=3",
    "http://ifconfig.me/ip",
    "http://icanhazip.com",
    "http://checkip.amazonaws.com",
    "http://api.ipify.org",
]

REPS = 10
CONCURRENCY = 5

results = {"success": 0, "fail": 0, "status_codes": {}}
timings = []
errors = []
lock = __import__("threading").Lock()


def fetch(url: str, rep: int):
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-x", PROXY, "--max-time", "15", url],
            capture_output=True, text=True, timeout=20,
        )
        elapsed = round((time.monotonic() - t0) * 1000)
        code = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
        with lock:
            results["status_codes"][code] = results["status_codes"].get(code, 0) + 1
            timings.append(elapsed)
            if 200 <= code < 400:
                results["success"] += 1
            else:
                results["fail"] += 1
        print(f"  [{rep+1:2d}/10] {url:<50s} -> {code} ({elapsed}ms)")
    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000)
        with lock:
            results["fail"] += 1
            errors.append(f"{url}: {type(e).__name__}")
        print(f"  [{rep+1:2d}/10] {url:<50s} -> ERR {type(e).__name__} ({elapsed}ms)")


def main():
    total = len(TARGETS) * REPS
    print(f"Crawling {len(TARGETS)} sites x {REPS} reps = {total} requests")
    print(f"Proxy: localhost:9080 (proxy rotator)")
    print(f"Concurrency: {CONCURRENCY}\n")

    t_start = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = []
        for url in TARGETS:
            for rep in range(REPS):
                futures.append(pool.submit(fetch, url, rep))
        concurrent.futures.wait(futures)

    total_time = round(time.monotonic() - t_start, 1)
    total_req = results["success"] + results["fail"]

    print(f"\n{'='*60}")
    print(f"RESULTS: {total_req} requests in {total_time}s")
    print(f"  Success: {results['success']}  |  Failed: {results['fail']}")
    print(f"  Success rate: {results['success']/max(total_req,1)*100:.1f}%")
    if timings:
        timings.sort()
        print(f"  Avg latency: {sum(timings)//len(timings)}ms")
        print(f"  P50: {timings[len(timings)//2]}ms  |  P95: {timings[int(len(timings)*0.95)]}ms")
    print(f"\n  Status codes:")
    for code, count in sorted(results["status_codes"].items()):
        print(f"    {code}: {count}")
    if errors:
        unique = list(set(errors))
        print(f"\n  Errors ({len(unique)} unique):")
        for e in unique[:10]:
            print(f"    - {e}")


if __name__ == "__main__":
    main()
