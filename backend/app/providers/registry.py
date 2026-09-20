"""
AEGIS UNIFIED DATA CORE - Provider Registry
Instantiates and manages all active data provider adapters.
"""
from typing import Dict, Optional, List, Any
from backend.app.providers.base import BaseProvider
from backend.app.providers.adapters.open_meteo import OpenMeteoProvider
from backend.app.providers.adapters.usgs import USGSSeismologyProvider
from backend.app.providers.adapters.imd import IMDProvider
from backend.app.providers.adapters.cwc import CWCFloodProvider
from backend.app.providers.adapters.incois import INCOISOceanProvider
from backend.app.providers.adapters.nasa_firms import NASAFIRMSProvider
from backend.app.providers.adapters.cpcb import CPCBAirQualityProvider
from backend.app.providers.adapters.geographic import GeographicLocationProvider
from backend.app.providers.adapters.custom_http import CustomHttpProvider


class ProviderRegistry:
    _BUILTIN_PROVIDERS: Dict[str, Any] = {
        "open_meteo": OpenMeteoProvider,
        "usgs": USGSSeismologyProvider,
        "imd": IMDProvider,
        "cwc": CWCFloodProvider,
        "incois": INCOISOceanProvider,
        "nasa_firms": NASAFIRMSProvider,
        "cpcb": CPCBAirQualityProvider,
        "geographic": GeographicLocationProvider,
    }

    @classmethod
    def get_provider(
        cls,
        provider_code: str,
        name: str,
        base_url: str,
        endpoint: str = "",
        category: str = "WEATHER",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        field_mappings: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 15.0
    ) -> BaseProvider:
        """Instantiates provider adapter matching provider_code or creates dynamic CustomHttpProvider."""
        code = provider_code.lower()
        if code in cls._BUILTIN_PROVIDERS:
            provider_cls = cls._BUILTIN_PROVIDERS[code]
            return provider_cls(
                name=name,
                base_url=base_url,
                endpoint=endpoint,
                api_key=api_key,
                headers=headers,
                params=params,
                timeout_seconds=timeout_seconds
            )
        
        # Universal fallback for custom / arbitrary admin-configured REST endpoints
        return CustomHttpProvider(
            name=name,
            base_url=base_url,
            endpoint=endpoint,
            category=category,
            api_key=api_key,
            headers=headers,
            params=params,
            field_mappings=field_mappings,
            timeout_seconds=timeout_seconds
        )

    @classmethod
    def list_supported_providers(cls) -> List[Dict[str, str]]:
        return [
            {"code": "open_meteo", "name": "Open-Meteo Meteorological Service", "category": "WEATHER"},
            {"code": "usgs", "name": "USGS Earthquake Hazards Program", "category": "EARTHQUAKE"},
            {"code": "imd", "name": "India Meteorological Department", "category": "CYCLONE"},
            {"code": "cwc", "name": "Central Water Commission", "category": "FLOOD"},
            {"code": "incois", "name": "INCOIS Tsunami & Ocean Early Warning", "category": "STORM"},
            {"code": "nasa_firms", "name": "NASA FIRMS Wildfire Thermal Satellite", "category": "WILDFIRE"},
            {"code": "cpcb", "name": "CPCB Air Quality Index Network", "category": "AIR_QUALITY"},
            {"code": "custom_http", "name": "Custom External REST / HTTP API", "category": "OTHER"},
        ]
