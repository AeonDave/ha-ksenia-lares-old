import asyncio
import logging
from typing import Optional

import aiohttp
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from lxml import etree

from .const import *

_LOGGER = logging.getLogger(__name__)

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)


class LaresBase:

    def __init__(self, data) -> None:
        self._ip: str = data["host"]
        self._port: str = str(data["port"])
        self._schema: str = "http://"
        self._host: str = f"{self._schema}{self._ip}:{self._port}"
        self._auth: aiohttp.BasicAuth = aiohttp.BasicAuth(data["username"], data["password"])

    async def general_info(self) -> Optional[dict[str, str]]:
        response = await self.get(GENERAL_INFO)
        if response is None:
            return None

        try:
            name = response.xpath(XPATH_GENERAL_INFO_NAME)[0].text.strip()
            info = {
                "mac": "",
                "id": f"{self._ip}:{self._port}",
                "name": name,
                "info": response.xpath(XPATH_GENERAL_INFO_INFO)[0].text.strip(),
                "version": response.xpath(XPATH_GENERAL_INFO_VERSION)[0].text.strip(),
                "revision": response.xpath(XPATH_GENERAL_INFO_REVISION)[0].text.strip(),
                "build": response.xpath(XPATH_GENERAL_INFO_BUILD)[0].text.strip(),
            }
        except (IndexError, AttributeError) as err:
            _LOGGER.error("Error parsing general info: %s", err)
            return None

        return info

    async def basis_info(self) -> Optional[dict[str, str]]:
        response = await self.get(BASIS_INFO)
        if response is None:
            return None

        try:
            info = {
                "askPin": response.xpath(XPATH_BASIS_INFO_ASKPIN)[0].text,
                "PINToUse": response.xpath(XPATH_BASIS_INFO_PINTOUSE)[0].text,
                "PINTimeout": response.xpath(XPATH_BASIS_INFO_PINTIMEOUT)[0].text,
                "startFromMap": response.xpath(XPATH_BASIS_INFO_STARTFROMMAP)[0].text,
            }
        except (IndexError, AttributeError) as err:
            _LOGGER.error("Error parsing basis info: %s", err)
            return None

        return info

    async def device_info(self) -> Optional[dict[str, str]]:
        device_info = await self.general_info()
        if device_info is None:
            return None

        info = {
            "identifiers": {(DOMAIN, device_info["id"])},
            "name": device_info["name"],
            "manufacturer": device_info["info"],
            "model": device_info["name"],
            "sw_version": f'{device_info["version"]}.{device_info["revision"]}.{device_info["build"]}',
            "lares_version": device_info["name"].split()[-1],
        }
        if device_info["mac"]:
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(device_info["mac"]))}

        return info

    async def _get_versioned_xml(self, prefix: str, device_info: dict[str, str]):
        version = device_info.get("lares_version") or ""
        if version:
            response = await self.get(f"{prefix}{version}.xml")
            if response is not None:
                return response
            _LOGGER.warning(
                "Versioned XML %s%s.xml unavailable, trying unversioned path",
                prefix,
                version,
            )
        return await self.get(f"{prefix}.xml")

    async def outputs_descriptions(self, device_info: dict[str, str]) -> Optional[dict[int, str]]:
        response = await self._get_versioned_xml(OUTPUTS_DESCRIPTION, device_info)
        if response is None:
            return None

        outputs = response.xpath(XPATH_OUTPUTS_DESCRIPTION)
        if not outputs:
            _LOGGER.error("No outputs found in description XML (unexpected document)")
            return None

        outputs_dict: dict[int, str] = {}
        for i, output in enumerate(outputs):
            if output.text:
                outputs_dict[i] = output.text
        return outputs_dict

    async def zone_descriptions(self, device_info: dict[str, str]) -> Optional[list[str]]:
        response = await self._get_versioned_xml(ZONES_DESCRIPTION, device_info)
        if response is None:
            return None

        zones = response.xpath(XPATH_ZONES_DESCRIPTION)
        return [zone.text for zone in zones if zone.text]

    async def outputs_status(self, device_info: dict[str, str]) -> Optional[list[dict[str, str]]]:
        response = await self._get_versioned_xml(OUTPUTS_STATUS, device_info)
        if response is None:
            return None

        outputs = response.xpath(XPATH_OUTPUTS_STATUS)
        if not outputs:
            _LOGGER.error("No outputs found in status XML (unexpected document)")
            return None

        status_list: list[dict[str, str]] = []
        for output in outputs:
            try:
                status_list.append({
                    "status": output.find("status").text,
                    "type": output.find("type").text,
                    "value": output.find("value").text,
                    "noPIN": output.find("noPIN").text,
                    "remoteControl": output.find("remoteControl").text,
                })
            except AttributeError as err:
                _LOGGER.error("Error parsing outputs_status: %s", err)
        return status_list

    async def zones_status(self, device_info: dict[str, str]) -> Optional[list[dict[str, str]]]:
        response = await self._get_versioned_xml(ZONES_STATUS, device_info)
        if response is None:
            return None

        zones = response.xpath(XPATH_ZONES_STATUS)
        status_list: list[dict[str, str]] = []
        for zone in zones:
            try:
                status_list.append({
                    "status": zone.find("status").text,
                    "bypass": zone.find("bypass").text,
                    "alarm": zone.find("alarm").text,
                })
            except AttributeError as err:
                _LOGGER.error("Error parsing zones_status: %s", err)
        return status_list

    async def command_output(self, pin: str, idx: str, value: str) -> Optional[list[str]]:
        url_command = f"{GET_COMMAND}?cmd=setOutput&pin={pin}&outputId={idx}&outputValue={value}"
        response = await self.get(url_command)
        if response is None:
            _LOGGER.error("Output command failed for outputId=%s", idx)
            return None
        return []

    async def get(self, path) -> Optional[etree.Element]:
        url = f"{self._host}/xml/{path}"
        safe_path = path.split("?", 1)[0]
        try:
            async with aiohttp.ClientSession(auth=self._auth, timeout=_HTTP_TIMEOUT) as session:
                async with session.get(url=url) as response:
                    response.raise_for_status()
                    xml = await response.read()
                    return etree.fromstring(xml)
        except aiohttp.ClientResponseError as cre:
            _LOGGER.warning("Host %s path %s responded with HTTP %s", self._host, safe_path, cre.status)
        except (aiohttp.ClientError, aiohttp.ClientConnectorError, asyncio.TimeoutError) as conn_err:
            _LOGGER.warning("Host %s path %s connection error: %s", self._host, safe_path, conn_err)
        except etree.XMLSyntaxError as xml_err:
            _LOGGER.warning("Host %s path %s returned invalid XML: %s", self._host, safe_path, xml_err)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Host %s path %s: unexpected error: %s", self._host, safe_path, ex)
        return None
