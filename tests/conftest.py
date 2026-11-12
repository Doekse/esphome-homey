"""Test bootstrap.

The app's code imports the Homey SDK, which only exists on a Homey. Provide
the few classes the imports need, and register the app root as the
``app`` package, the way the Homey runtime loads it.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Generic, TypeVar

_DriverT = TypeVar("_DriverT")


def _install_homey_stub() -> None:
    try:
        import homey.device  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        return

    class Device(Generic[_DriverT]):
        def get_name(self) -> str:
            return self._name

    class Driver:
        pass

    homey = types.ModuleType("homey")
    device = types.ModuleType("homey.device")
    discovery = types.ModuleType("homey.discovery_result")
    mdns = types.ModuleType("homey.discovery_result_mdns_sd")
    driver = types.ModuleType("homey.driver")
    pair = types.ModuleType("homey.pair_session")
    device.Device = Device
    discovery.DiscoveryResult = type("DiscoveryResult", (), {})
    mdns.DiscoveryResultMDNSSD = type("DiscoveryResultMDNSSD", (), {})
    driver.Driver = Driver
    pair.PairSession = type("PairSession", (), {})
    homey.device = device
    homey.discovery_result = discovery
    homey.discovery_result_mdns_sd = mdns
    homey.driver = driver
    homey.pair_session = pair
    sys.modules.update(
        {
            "homey": homey,
            "homey.device": device,
            "homey.discovery_result": discovery,
            "homey.discovery_result_mdns_sd": mdns,
            "homey.driver": driver,
            "homey.pair_session": pair,
        }
    )


_install_homey_stub()


def _install_app_package() -> None:
    # Homey imports the app root as the ``app`` package; mirror that here.
    root = Path(__file__).resolve().parents[1]
    app = types.ModuleType("app")
    app.__path__ = [str(root)]
    sys.modules.setdefault("app", app)


_install_app_package()
