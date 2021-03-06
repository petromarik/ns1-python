#
# Copyright (c) 2014 NSONE, Inc.
#
# License under The MIT License (MIT). See LICENSE in project root.
#
from __future__ import absolute_import

from ns1.rest.transport.base import TransportBase
from ns1.rest.errors import (
    ResourceException,
    RateLimitException,
    AuthException,
)

try:
    import requests

    have_requests = True
except ImportError:
    have_requests = False


class RequestsTransport(TransportBase):
    def __init__(self, config):
        if not have_requests:
            raise ImportError("requests module required for RequestsTransport")
        TransportBase.__init__(self, config, self.__module__)
        self.REQ_MAP = {
            "GET": requests.get,
            "POST": requests.post,
            "DELETE": requests.delete,
            "PUT": requests.put,
        }
        self._timeout = self._config.get("timeout", None)
        if isinstance(self._timeout, list) and len(self._timeout) == 2:
            self._timeout = tuple(self._timeout)

    def _rateLimitHeaders(self, headers):
        return {
            "by": headers.get("X-RateLimit-By", "customer"),
            "limit": int(headers.get("X-RateLimit-Limit", 10)),
            "period": int(headers.get("X-RateLimit-Period", 1)),
            "remaining": int(headers.get("X-RateLimit-Remaining", 100)),
        }

    def send(
        self,
        method,
        url,
        headers=None,
        data=None,
        params=None,
        files=None,
        callback=None,
        errback=None,
    ):
        self._logHeaders(headers)
        resp = self.REQ_MAP[method](
            url,
            headers=headers,
            verify=self._verify,
            data=data,
            files=files,
            params=params,
            timeout=self._timeout,
        )

        response_headers = resp.headers
        rate_limit_headers = self._rateLimitHeaders(response_headers)
        self._rate_limit_func(rate_limit_headers)

        if resp.status_code < 200 or resp.status_code >= 300:
            if errback:
                errback(resp)
                return
            else:
                if resp.status_code == 429:
                    raise RateLimitException(
                        "rate limit exceeded",
                        resp,
                        resp.text,
                        by=rate_limit_headers["by"],
                        limit=rate_limit_headers["limit"],
                        period=rate_limit_headers["period"],
                        remaining=rate_limit_headers["remaining"],
                    )
                elif resp.status_code == 401:
                    raise AuthException("unauthorized", resp, resp.text)
                else:
                    raise ResourceException("server error", resp, resp.text)

        # TODO make sure json is valid if a body is returned
        if resp.text:
            try:
                jsonOut = resp.json()
            except ValueError:
                if errback:
                    errback(resp)
                    return
                else:
                    raise ResourceException(
                        "invalid json in response", resp, resp.text
                    )
        else:
            jsonOut = None

        if callback:
            return callback(jsonOut)
        else:
            return jsonOut


TransportBase.REGISTRY["requests"] = RequestsTransport
