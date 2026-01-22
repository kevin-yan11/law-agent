"""Tests for URL fetcher SSRF protection."""

import pytest
from app.utils.url_fetcher import is_safe_url, ALLOWED_HOSTS


class TestSSRFProtection:
    """Test SSRF protection in URL validation."""

    def test_blocks_localhost(self):
        """Should block localhost URLs."""
        assert is_safe_url("http://localhost/secret") is False
        assert is_safe_url("http://localhost:8000/admin") is False
        assert is_safe_url("https://localhost/api") is False

    def test_blocks_loopback_ip(self):
        """Should block 127.0.0.1 loopback."""
        assert is_safe_url("http://127.0.0.1/") is False
        assert is_safe_url("http://127.0.0.1:3000/api") is False

    def test_blocks_private_ip_ranges(self):
        """Should block private IP ranges (10.x, 172.16-31.x, 192.168.x)."""
        # 10.0.0.0/8
        assert is_safe_url("http://10.0.0.1/internal") is False
        assert is_safe_url("http://10.255.255.255/") is False

        # 172.16.0.0/12
        assert is_safe_url("http://172.16.0.1/") is False
        assert is_safe_url("http://172.31.255.255/") is False

        # 192.168.0.0/16
        assert is_safe_url("http://192.168.1.1/router") is False
        assert is_safe_url("http://192.168.0.1/") is False

    def test_blocks_aws_metadata(self):
        """Should block AWS metadata endpoint."""
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_ipv6_localhost(self):
        """Should block IPv6 localhost."""
        assert is_safe_url("http://[::1]/") is False

    def test_blocks_non_http_schemes(self):
        """Should block non-HTTP(S) schemes."""
        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("ftp://example.com/file") is False
        assert is_safe_url("gopher://example.com/") is False

    def test_blocks_zero_ip(self):
        """Should block 0.0.0.0."""
        assert is_safe_url("http://0.0.0.0/") is False

    def test_handles_malformed_urls(self):
        """Should safely handle malformed URLs."""
        assert is_safe_url("") is False
        assert is_safe_url("not-a-url") is False
        assert is_safe_url("http://") is False
        assert is_safe_url("://missing-scheme.com") is False

    def test_blocks_localhost_with_ports(self):
        """Should block localhost regardless of port."""
        assert is_safe_url("http://localhost:3000/") is False
        assert is_safe_url("http://127.0.0.1:8080/") is False


class TestAllowlistBehavior:
    """Test allowlist enforcement when ALLOWED_HOSTS is configured."""

    def test_allowlist_is_configured(self):
        """Verify that ALLOWED_HOSTS is configured in test environment."""
        # This test documents expected behavior - allowlist should be set
        # If this fails, the .env file may not be loaded
        assert len(ALLOWED_HOSTS) > 0, (
            "ALLOWED_HOSTS should be configured. "
            "Set ALLOWED_DOCUMENT_HOSTS in backend/.env"
        )

    def test_blocks_non_allowlisted_hosts_when_allowlist_configured(self):
        """When allowlist is configured, non-allowlisted public hosts are blocked."""
        if not ALLOWED_HOSTS:
            pytest.skip("ALLOWED_HOSTS not configured")

        # These are public hosts but not in allowlist
        assert is_safe_url("https://example.com/document.pdf") is False
        assert is_safe_url("https://evil.com/malware.pdf") is False
        assert is_safe_url("http://random-site.org/file.pdf") is False

    def test_allows_supabase_domain_if_in_allowlist(self):
        """Should allow configured Supabase domain."""
        if not ALLOWED_HOSTS:
            pytest.skip("ALLOWED_HOSTS not configured")

        # Check if supabase.co is in allowlist
        has_supabase = any("supabase.co" in h for h in ALLOWED_HOSTS)
        if not has_supabase:
            pytest.skip("Supabase not in allowlist")

        # Find the exact supabase domain
        supabase_host = next((h for h in ALLOWED_HOSTS if "supabase.co" in h), None)
        if supabase_host:
            test_url = f"https://{supabase_host}/storage/v1/object/public/documents/test.pdf"
            assert is_safe_url(test_url) is True
