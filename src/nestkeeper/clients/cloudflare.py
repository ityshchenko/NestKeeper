"""Cloudflare Email Routing destination-address client."""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr, TypeAdapter, ValidationError

from nestkeeper.http import HttpClient, HttpError
from nestkeeper.models.cloudflare import ApiError, ApiResponse, DestinationAddress

API_BASE = "https://api.cloudflare.com/client/v4"
PER_PAGE = 50
MAX_PAGES = 100

_ADDRESS_LIST = TypeAdapter(list[DestinationAddress])


class CloudflareError(Exception):
    def __init__(self, status: int, errors: list[ApiError]) -> None:
        detail = "; ".join(f"{e.code}: {e.message}" for e in errors) or "no details"
        super().__init__(f"Cloudflare API error (HTTP {status}): {detail}")
        self.status = status
        self.errors = errors


class CloudflareClient:
    def __init__(self, http: HttpClient, account_id: str, token: SecretStr) -> None:
        self._http = http
        self._base = f"{API_BASE}/accounts/{account_id}/email/routing/addresses"
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token.get_secret_value()}"}

    async def _request(self, method: str, url: str, body: Any = None) -> ApiResponse:
        response = await self._http.request(method, url, headers=self._headers(), json_body=body)
        try:
            parsed = ApiResponse.model_validate(response.json_body())
        except (ValueError, ValidationError) as exc:
            raise HttpError(f"Cloudflare: unexpected response (HTTP {response.status})") from exc
        if not parsed.success:
            raise CloudflareError(response.status, parsed.errors)
        return parsed

    async def create_destination(self, email: str) -> DestinationAddress:
        """Create a destination address; Cloudflare e-mails a verification link to it."""
        parsed = await self._request("POST", self._base, {"email": email})
        try:
            return DestinationAddress.model_validate(parsed.result)
        except ValidationError as exc:
            raise HttpError("Cloudflare: invalid result for create_destination") from exc

    async def list_destinations(self) -> list[DestinationAddress]:
        addresses: list[DestinationAddress] = []
        for page in range(1, MAX_PAGES + 1):
            url = f"{self._base}?page={page}&per_page={PER_PAGE}"
            parsed = await self._request("GET", url)
            try:
                batch = _ADDRESS_LIST.validate_python(parsed.result or [])
            except ValidationError as exc:
                raise HttpError("Cloudflare: invalid destination list") from exc
            addresses.extend(batch)
            info = parsed.result_info
            total_pages = info.total_pages if info and info.total_pages else None
            if total_pages is not None:
                if page >= total_pages:
                    break
            elif len(batch) < PER_PAGE:
                break
        return addresses

    async def find_destination(self, email: str) -> DestinationAddress | None:
        target = email.lower()
        for address in await self.list_destinations():
            if address.email.lower() == target:
                return address
        return None
