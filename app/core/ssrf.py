"""
AEGIS UNIFIED DATA CORE - Strict SSRF (Server-Side Request Forgery) Protection
Guards against malicious administrator inputs targeting internal infrastructure,
localhost, loopback devices, private subnets, and cloud metadata endpoints.
"""
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Tuple


BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),        # Private RFC 1918
    ipaddress.ip_network('100.64.0.0/10'),     # Carrier-grade NAT
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('169.254.0.0/16'),    # Link-local & AWS/GCP Cloud Metadata
    ipaddress.ip_network('172.16.0.0/12'),     # Private RFC 1918
    ipaddress.ip_network('192.0.0.0/24'),      # IETF Protocol Assignments
    ipaddress.ip_network('192.0.2.0/24'),      # TEST-NET-1
    ipaddress.ip_network('192.168.0.0/16'),    # Private RFC 1918
    ipaddress.ip_network('198.18.0.0/15'),     # Benchmarking
    ipaddress.ip_network('198.51.100.0/24'),   # TEST-NET-2
    ipaddress.ip_network('203.0.113.0/24'),    # TEST-NET-3
    ipaddress.ip_network('224.0.0.0/4'),       # Multicast
    ipaddress.ip_network('240.0.0.0/4'),       # Reserved
    ipaddress.ip_network('255.255.255.255/32'),# Broadcast
    # IPv6 blocks
    ipaddress.ip_network('::1/128'),           # IPv6 Loopback
    ipaddress.ip_network('::/128'),            # IPv6 Unspecified
    ipaddress.ip_network('fc00::/7'),          # Unique Local Address (ULA)
    ipaddress.ip_network('fe80::/10'),         # IPv6 Link-Local
]


class SSRFProtectionError(ValueError):
    """Raised when an external URL fails SSRF safety checks."""
    pass


class SSRFGuard:
    @staticmethod
    def validate_url(url: str, allow_local_in_dev: bool = False) -> Tuple[bool, str]:
        """
        Validates an outbound API URL for SSRF vulnerabilities.
        Returns (is_valid, error_message).
        """
        if not url:
            return False, "URL cannot be empty."

        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"Malformed URL: {str(e)}"

        # 1. Scheme check (Only HTTP/HTTPS allowed)
        if parsed.scheme.lower() not in ('http', 'https'):
            return False, f"Unsupported scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

        hostname = parsed.hostname
        if not hostname:
            return False, "URL must contain a valid hostname."

        # 2. Block direct localhost / loopback names
        lower_host = hostname.lower()
        if lower_host in ('localhost', 'localhost.localdomain', 'ip6-localhost', 'ip6-loopback'):
            if not allow_local_in_dev:
                return False, f"Host '{hostname}' resolves to a local/loopback address."

        # 3. Resolve DNS and inspect all resolved IP addresses
        try:
            addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
            for family, socktype, proto, canonname, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)

                # Check if IP is in any blocked network
                for net in BLOCKED_IP_NETWORKS:
                    if ip_obj in net:
                        if not allow_local_in_dev:
                            return False, f"Host '{hostname}' resolved to blocked private/loopback IP: {ip_str} ({net})"
        except socket.gaierror:
            # If DNS resolution fails, allow if it looks like a valid domain format, or fail safely
            if not allow_local_in_dev and '.' not in hostname:
                return False, f"Unable to resolve host: '{hostname}'"

        return True, ""
