"""Real scanner with a simulated fallback for CTF environments."""

try:
    import nmap
    HAS_NMAP = True
except ImportError:
    HAS_NMAP = False


def run_scan(target_ip, scan_profile, verbose=False):
    """
    Perform a network scan.
    Returns a formatted result string.
    """
    if not target_ip or target_ip == "0.0.0.0":
        return "[ERROR] No target IP provided."

    # Map profile to nmap arguments
    profiles = {
        "Standard Scan": "-sV -T4",
        "Deep Analysis": "-A -T4",
        "Custom": "-sC -sV -O",
    }
    args = profiles.get(scan_profile, "-sV")

    if HAS_NMAP:
        try:
            nm = nmap.PortScanner()
            result = nm.scan(hosts=target_ip, arguments=args)
            output = _format_nmap_output(nm, target_ip)
            if verbose:
                output += f"\n[VERBOSE] Raw command: nmap {args} {target_ip}"
            return output
        except Exception as e:
            return f"[ERROR] Scan failed: {e}"
    else:
        # Simulated scan for environments without nmap
        import random, time
        time.sleep(1.2)  # fake delay
        ports = [22, 80, 443, 8080]
        open_ports = random.sample(ports, k=random.randint(1, 3))
        return (
            f"[SIMULATED SCAN] Nmap not installed.\n"
            f"Target: {target_ip}\n"
            f"Profile: {scan_profile}\n"
            f"Open ports: {', '.join(map(str, open_ports))}"
            + ("\nVerbose: ON" if verbose else "")
        )


def _format_nmap_output(nm, host):
    """Convert nmap scan result into a readable string."""
    try:
        host_info = nm[host]
        lines = [f"Scan report for {host}"]
        for proto in host_info.all_protocols():
            lport = list(host_info[proto].keys())
            for port in sorted(lport):
                state = host_info[proto][port]['state']
                name = host_info[proto][port].get('name', 'unknown')
                lines.append(f"{port}/{proto} {state} ({name})")
        return "\n".join(lines)
    except Exception:
        return "[INFO] Scan completed but could not parse results."

