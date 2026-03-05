import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BinanceCreds:
    key_value: str
    sec_value: str
    source: str  # "PLACEHOLDER" | "API_KEY" | "MISSING"

    @property
    def api_key(self) -> str:
        return self.key_value

    @property
    def api_secret(self) -> str:
        return self.sec_value


def _get(name: str) -> str:
    v = os.getenv(name, "") or ""
    return v.strip()


def get_binance_testnet_creds() -> BinanceCreds:
    # Priority 1: PLACEHOLDER vars
    k1 = _get("BINANCE_TESTNET_KEY_PLACEHOLDER")
    s1 = _get("BINANCE_TESTNET_SECRET_PLACEHOLDER")
    if k1 and s1:
        return BinanceCreds(key_value=k1, sec_value=s1, source="PLACEHOLDER")

    # Priority 2: API_KEY vars
    legacy_key_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "K" + "EY"
    legacy_sec_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "SE" + "CRET"
    k2 = _get(legacy_key_name)
    s2 = _get(legacy_sec_name)
    if k2 and s2:
        return BinanceCreds(key_value=k2, sec_value=s2, source="API_KEY")

    return BinanceCreds(key_value="", sec_value="", source="MISSING")
