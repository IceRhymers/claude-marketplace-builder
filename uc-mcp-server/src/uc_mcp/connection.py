"""UC Connection proxy for HTTP via Databricks connections."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ExternalFunctionRequestHttpMethod

logger = logging.getLogger(__name__)

_METHOD_MAP: dict[str, ExternalFunctionRequestHttpMethod] = {
    "GET": ExternalFunctionRequestHttpMethod.GET,
    "POST": ExternalFunctionRequestHttpMethod.POST,
    "PUT": ExternalFunctionRequestHttpMethod.PUT,
    "PATCH": ExternalFunctionRequestHttpMethod.PATCH,
    "DELETE": ExternalFunctionRequestHttpMethod.DELETE,
}


@dataclass
class UCResponse:
    """Response from a UC connection HTTP request."""

    status_code: int
    body: dict[str, Any] | str
    headers: dict[str, str]
    raw_contents: str


class UCConnection:
    """Proxies HTTP requests through a Databricks UC connection."""

    def __init__(self, connection_name: str, client: Optional[WorkspaceClient] = None):
        self._connection_name = connection_name
        self._client = client if client is not None else WorkspaceClient()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        query_params: Optional[dict[str, Any]] = None,
    ) -> UCResponse:
        """Execute an HTTP request through the UC connection."""
        # ServingEndpointsExt.http_request uses:
        #   conn: str, method: enum, path: str,
        #   headers: Optional[Dict], json: Optional[Dict], params: Optional[Dict]
        # Returns: requests.Response
        kwargs: dict[str, Any] = {
            "conn": self._connection_name,
            "method": _METHOD_MAP[method],
            "path": path,
        }

        if headers:
            kwargs["headers"] = headers

        if body is not None:
            kwargs["json"] = body

        if query_params:
            kwargs["params"] = query_params

        response = self._client.serving_endpoints.http_request(**kwargs)

        # Response is requests.Response
        raw = response.text if hasattr(response, "text") else str(response)
        status_code = response.status_code if hasattr(response, "status_code") else 200

        try:
            parsed_body: dict[str, Any] | str = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            parsed_body = raw

        resp_headers = {}
        if hasattr(response, "headers"):
            resp_headers = dict(response.headers)

        return UCResponse(
            status_code=status_code,
            body=parsed_body,
            headers=resp_headers,
            raw_contents=raw,
        )
