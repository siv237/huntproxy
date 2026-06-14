import pytest
import hunt


class TestCustomProxies:
    def test_create_and_get_custom_proxy(self, state):
        data = {
            "id": "my-proxy",
            "name": "My Proxy",
            "protocol": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
            "username": "user",
            "password": "pass",
            "test_url": "https://example.com",
        }
        created = state.create_custom_proxy(data)
        assert created is not None
        assert created["id"] == "my-proxy"
        assert created["name"] == "My Proxy"
        assert created["host"] == "1.2.3.4"
        assert created["port"] == 1080

        fetched = state.get_custom_proxy("my-proxy")
        assert fetched is not None
        assert fetched["name"] == "My Proxy"

    def test_create_custom_proxy_missing_fields(self, state):
        assert state.create_custom_proxy({"id": "x", "name": "x"}) is None

    def test_update_custom_proxy(self, state):
        state.create_custom_proxy({
            "id": "my-proxy",
            "name": "My Proxy",
            "protocol": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
        })
        updated = state.update_custom_proxy("my-proxy", {"name": "Renamed Proxy", "port": 1081})
        assert updated is not None
        assert updated["name"] == "Renamed Proxy"
        assert updated["port"] == 1081

    def test_delete_custom_proxy(self, state):
        state.create_custom_proxy({
            "id": "my-proxy",
            "name": "My Proxy",
            "protocol": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
        })
        assert state.delete_custom_proxy("my-proxy") is True
        assert state.get_custom_proxy("my-proxy") is None

    def test_toggle_custom_proxy(self, state):
        state.create_custom_proxy({
            "id": "my-proxy",
            "name": "My Proxy",
            "protocol": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
        })
        original = state.get_custom_proxy("my-proxy")["enabled"]
        state.toggle_custom_proxy("my-proxy")
        updated = state.get_custom_proxy("my-proxy")
        assert updated["enabled"] != original

    def test_custom_proxy_password_masking(self, state):
        state.create_custom_proxy({
            "id": "my-proxy",
            "name": "My Proxy",
            "protocol": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
            "password": "secret",
        })
        # get_custom_proxy should mask password
        fetched = state.get_custom_proxy("my-proxy")
        assert fetched["password"] != "secret"
        # update with mask should keep old password
        state.update_custom_proxy("my-proxy", {"password": "****"})
        updated = state.get_custom_proxy("my-proxy")
        assert updated["password"] != "secret"  # still masked

    def test_list_custom_proxies(self, state):
        state.create_custom_proxy({
            "id": "p1",
            "name": "Proxy 1",
            "protocol": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
        })
        state.create_custom_proxy({
            "id": "p2",
            "name": "Proxy 2",
            "protocol": "http",
            "host": "5.6.7.8",
            "port": 8080,
        })
        proxies = state.get_custom_proxies()
        assert len(proxies) == 2
        ids = {p["id"] for p in proxies}
        assert ids == {"p1", "p2"}
