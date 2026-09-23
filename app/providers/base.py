"""
AEGIS UNIFIED DATA CORE - Base Provider Interface
Every external data source implements this common contract.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import httpx
from backend.app.core.ssrf import SSRFGuard
from backend.app.core.config import settings
from backend.app.schemas.unified import UnifiedObservation


class ProviderFetchResult:
    def __init__(
        self,
        success: bool,
        raw_data: Any = None,
        status_code: Optional[int] = None,
        response_time_ms: float = 0.0,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.raw_data = raw_data
        self.status_code = status_code
        self.response_time_ms = response_time_ms
        self.error_message = error_message


class BaseProvider(ABC):
    def __init__(
        self,
        name: str,
        provider_code: str,
        base_url: str,
        endpoint: str = "",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        self.name = name
        self.provider_code = provider_code
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint if endpoint.startswith("/") or not endpoint else f"/{endpoint}"
        self.api_key = api_key
        self.headers = headers or {}
        self.params = params or {}
        self.timeout_seconds = timeout_seconds

    def get_full_url(self) -> str:
        return f"{self.base_url}{self.endpoint}"

    async def fetch(self, custom_params: Optional[Dict[str, Any]] = None, custom_headers: Optional[Dict[str, str]] = None) -> ProviderFetchResult:
        """Executes secure, SSRF-validated outbound HTTP request."""
        url = self.get_full_url()
        
        # 1. SSRF Safety Gate
        is_safe, error = SSRFGuard.validate_url(url, allow_local_in_dev=settings.DEBUG)
        if not is_safe:
            return ProviderFetchResult(success=False, error_message=f"SSRF Check Failed: {error}")

        merged_params = {**self.params, **(custom_params or {})}
        merged_headers = {**self.headers, **(custom_headers or {})}

        import time
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
                res = await client.get(url, params=merged_params, headers=merged_headers)
                elapsed_ms = (time.time() - start_time) * 1000.0

                if res.is_success:
                    try:
                        data = res.json()
                    except Exception:
                        data = res.text
                    return ProviderFetchResult(
                        success=True,
                        raw_data=data,
                        status_code=res.status_code,
                        response_time_ms=elapsed_ms
                    )
                else:
                    return ProviderFetchResult(
                        success=False,
                        status_code=res.status_code,
                        response_time_ms=elapsed_ms,
                        error_message=f"HTTP Error {res.status_code}: {res.text[:200]}"
                    )
        except httpx.TimeoutException:
            return ProviderFetchResult(
                success=False,
                error_message="Connection timed out while querying external provider."
            )
        except Exception as exc:
            return ProviderFetchResult(
                success=False,
                error_message=f"Network dispatch error: {str(exc)}"
            )

    @abstractmethod
    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Extracts structured raw records from provider response."""
        pass

    @abstractmethod
    def normalize(self, parsed_record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        """Maps parsed record into standard UnifiedObservation format."""
        pass

    @abstractmethod
    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        """Performs domain & boundary validation on normalized observation."""
        pass
