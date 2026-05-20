import re
from collections import defaultdict

LOG_FILE = "/var/log/auth.log"
THRESHOLD = 3

def parse_failed_logins(filepath):
    pattern = re.compile(r'(\w+\s+\d+\s+\d+:\d+:\d+).*Failed password.*from (\d+\.\d+\.\d+\.\d+)')
    failures = defaultdict(list)
    with open(filepath, "r") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                timestamp = match.group(1)
                ip = match.group(2)
                failures[ip].append(timestamp)
    return failures

def generate_report(failures):
    flagged = 0
    for ip, times in failures.items():
        count = len(times)
        if count >= THRESHOLD:
            flagged += 1
            print(f"[ALERT] IP: {ip} | Attempts: {count}")
    if flagged == 0:
        print("No suspicious activity detected.")
    print(f"Total IPs flagged: {flagged}")

failures = parse_failed_logins(LOG_FILE)
generate_report(failures)