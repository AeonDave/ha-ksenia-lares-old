from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from xml.etree import ElementTree

from .const import *
from .outputs import OutputStatus, parse_outputs_description, parse_outputs_status

_LOGGER = logging.getLogger(__name__)

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)


class LaresBase:
    """HTTP client for the Ksenia Lares < v4 XML web server."""

    def __init__(self, data: dict[str, Any], session: aiohttp.ClientSession | None = None) -> None:
        self._ip: str = data["host"]
        self._port: str = str(data["port"])
        self._schema = "http://"
        self._host = f"{self._schema}{self._ip}:{self._port}"
        self._auth = aiohttp.BasicAuth(data["username"], data["password"])
        self._session = session

    async def general_info(self) -> dict[str, str] | None:
        root = await self.get(GENERAL_INFO)
        if root is None:
            return None
        try:
            name = _text(root, "productName")
            return {
                "mac": "",
                "id": f"{self._ip}:{self._port}",
                "name": name,
                "info": _text(root, "info1"),
                "version": _text(root, "productHighRevision"),
                "revision": _text(root, "productLowRevision"),
                "build": _text(root, "productBuildRevision"),
            }
        except (LookupError, AttributeError) as err:
            _LOGGER.error("Error parsing general info: %s", err)
            return None

    async def basis_info(self) -> dict[str, str] | None:
        root = await self.get(BASIS_INFO)
        if root is None:
            return None
        try:
            return {
                "askPin": _text(root, "askPIN"),
                "PINToUse": _text(root, "PINToUse"),
                "PINTimeout": _text(root, "PINTimeout"),
                "startFromMap": _text(root, "startFromMap"),
            }
        except (LookupError, AttributeError) as err:
            _LOGGER.error("Error parsing basis info: %s", err)
            return None

    async def device_info(self) -> dict[str, Any] | None:
        general = await self.general_info()
        if general is None:
            return None
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, general["id"])},
            "name": general["name"],
            "manufacturer": general["info"] or MANUFACTURER,
            "model": general["name"],
            "sw_version": f'{general["version"]}.{general["revision"]}.{general["build"]}',
            "lares_version": general["name"].split()[-1],
        }
        if general["mac"]:
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(general["mac"]))}
        return info

    async def _get_versioned_bytes(self, prefix: str, device_info: dict[str, Any]) -> bytes | None:
        version = device_info.get("lares_version") or ""
        if version:
            payload = await self.get_bytes(f"{prefix}{version}.xml")
            if payload is not None:
                return payload
            _LOGGER.warning(
                "Versioned XML %s%s.xml unavailable, trying unversioned path",
                prefix,
                version,
            )
        return await self.get_bytes(f"{prefix}.xml")

    async def outputs_descriptions(self, device_info: dict[str, Any]) -> dict[int, str] | None:
        xml = await self._get_versioned_bytes(OUTPUTS_DESCRIPTION, device_info)
        if xml is None:
            return None
        try:
            descriptions = parse_outputs_description(xml)
        except ElementTree.ParseError as err:
            _LOGGER.error("Invalid outputs description XML: %s", err)
            return None
        if not descriptions:
            _LOGGER.error("No outputs found in description XML (unexpected document)")
            return None
        return descriptions

    async def outputs_status(self, device_info: dict[str, Any]) -> list[OutputStatus] | None:
        xml = await self._get_versioned_bytes(OUTPUTS_STATUS, device_info)
        if xml is None:
            return None
        try:
            statuses = parse_outputs_status(xml)
        except ElementTree.ParseError as err:
            _LOGGER.error("Invalid outputs status XML: %s", err)
            return None
        if not statuses:
            _LOGGER.error("No outputs found in status XML (unexpected document)")
            return None
        return statuses

    async def command_output(self, pin: str, idx: str, value: str) -> bool:
        path = f"{GET_COMMAND}?cmd=setOutput&pin={pin}&outputId={idx}&outputValue={value}"
        response = await self.get(path)
        if response is None:
            _LOGGER.error("Output command failed for outputId=%s", idx)
            return False
        return True

    async def get(self, path: str) -> ElementTree.Element | None:
        xml = await self.get_bytes(path)
        if xml is None:
            return None
        try:
            return ElementTree.fromstring(xml)
        except ElementTree.ParseError as xml_err:
            _LOGGER.warning("Host %s path %s returned invalid XML: %s", self._host, path.split("?", 1)[0], xml_err)
            return None

    async def get_bytes(self, path: str) -> bytes | None:
        url = f"{self._host}/xml/{path}"
        safe_path = path.split("?", 1)[0]
        try:
            if self._session is None:
                async with aiohttp.ClientSession(auth=self._auth, timeout=_HTTP_TIMEOUT) as session:
                    return await self._fetch(session, url, safe_path)
            return await self._fetch(self._session, url, safe_path)
        except aiohttp.ClientResponseError as cre:
            _LOGGER.warning("Host %s path %s responded with HTTP %s", self._host, safe_path, cre.status)
        except (aiohttp.ClientError, TimeoutError) as conn_err:
            _LOGGER.warning("Host %s path %s connection error: %s", self._host, safe_path, conn_err)
        except ElementTree.ParseError as xml_err:
            _LOGGER.warning("Host %s path %s returned invalid XML: %s", self._host, safe_path, xml_err)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Host %s path %s: unexpected error: %s", self._host, safe_path, ex)
        return None

    async def _fetch(
        self, session: aiohttp.ClientSession, url: str, safe_path: str
    ) -> bytes:
        async with session.get(url=url, auth=self._auth, timeout=_HTTP_TIMEOUT) as response:
            response.raise_for_status()
            xml = await response.read()
            if b"FileNotFound" in xml[:800]:
                raise ElementTree.ParseError(f"Lares FileNotFound for {safe_path}")
            return xml


def _text(root: ElementTree.Element, tag: str) -> str:
    value = root.findtext(tag)
    if value is None:
        raise LookupError(tag)
    return value.strip()
