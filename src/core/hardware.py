"""Hardware acceleration detection and capabilities."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HardwareCapabilities:
    """
    Detects and reports available hardware acceleration capabilities.

    Checks for:
    - VAAPI (Intel/AMD)
    - NVENC (NVIDIA)
    - QSV (Intel Quick Sync)
    - AMF (AMD Advanced Media Framework)
    """

# TODO: Loads these 2 lists from a config file or external source (that can be updated easily wihthout code changes)
    # PCI vendor IDs
    VENDOR_INTEL = "8086"
    VENDOR_NVIDIA = "10de"
    VENDOR_AMD = "1002"

    # PCI device classes
    CLASS_VGA = "0300"
    CLASS_DISPLAY = "0380"

    def __init__(self):
        self._pci_devices = self._get_pci_devices()
        self.vaapi_available = self._check_vaapi()
        self.nvidia_available = self._check_nvidia()
        self.amd_available = self._check_amd()
        self.intel_qsv_available = self._check_intel_qsv()

    def _get_pci_devices(self) -> list[dict]:
        """
        Get PCI devices using lspci.

        Returns:
            List of dicts with vendor, device_class, and description
        """
        devices = []
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    # Parse format: "00:02.0 VGA compatible controller [0300]: Intel... [8086:xxxx]"
                    match = re.search(r"\[([0-9a-f]{4})\].*\[([0-9a-f]{4}):", line)
                    if match:
                        device_class = match.group(1)
                        vendor = match.group(2)
                        devices.append({
                            "vendor": vendor,
                            "class": device_class,
                            "description": line,
                        })
        except FileNotFoundError:
            logger.debug("lspci command not found")
        except Exception as e:
            logger.debug(f"Failed to get PCI devices: {e}")

        return devices

    def _has_gpu_vendor(self, vendor_id: str) -> bool:
        """Check if GPU from specific vendor exists."""
        for device in self._pci_devices:
            if device["vendor"] == vendor_id:
                device_class = device["class"]
                # Check if it's a VGA or display controller
                if device_class.startswith(self.CLASS_VGA[:2]):
                    return True
        return False

    def _check_vaapi(self) -> bool:
        """
        Check if VAAPI (Video Acceleration API) is available.

        VAAPI is used by Intel and AMD GPUs on Linux.
        """
        # Check for render nodes
        if not Path("/dev/dri").exists():
            logger.debug("VAAPI: /dev/dri not found")
            return False

        render_devices = list(Path("/dev/dri").glob("renderD*"))
        if not render_devices:
            logger.debug("VAAPI: No render devices found")
            return False

        # Verify with vainfo if available
        try:
            result = subprocess.run(
                ["vainfo"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Check for VAProfile in output (indicates working VAAPI)
            if result.returncode == 0:
                profile_count = result.stdout.count("VAProfile")
                if profile_count > 0:
                    logger.info(f"VAAPI available: {profile_count} profiles, {len(render_devices)} device(s)")
                    return True
        except FileNotFoundError:
            # vainfo not installed, but render nodes exist
            logger.debug("VAAPI: vainfo not found, but render devices exist")
            return True  # Assume available if render devices exist
        except subprocess.TimeoutExpired:
            logger.warning("VAAPI: vainfo timed out")
        except Exception as e:
            logger.debug(f"VAAPI check failed: {e}")

        return False

    def _check_nvidia(self) -> bool:
        """
        Check if NVIDIA GPU with NVENC is available.
        """
        # First check PCI devices
        if not self._has_gpu_vendor(self.VENDOR_NVIDIA):
            logger.debug("NVIDIA: No NVIDIA GPU in PCI devices")
            return False

        # Verify with nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "-L"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                gpu_count = len([l for l in result.stdout.splitlines() if l.strip()])
                if gpu_count > 0:
                    logger.info(f"NVIDIA GPU available: {gpu_count} GPU(s)")
                    return True
        except FileNotFoundError:
            logger.debug("NVIDIA: nvidia-smi command not found")
        except subprocess.TimeoutExpired:
            logger.warning("NVIDIA: nvidia-smi timed out")
        except Exception as e:
            logger.debug(f"NVIDIA check failed: {e}")

        return False

    def _check_amd(self) -> bool:
        """
        Check if AMD GPU is available.

        AMD GPUs can use VAAPI or AMF for hardware acceleration.
        """
        # Check PCI devices for AMD GPU
        if not self._has_gpu_vendor(self.VENDOR_AMD):
            logger.debug("AMD: No AMD GPU in PCI devices")
            return False

        logger.info("AMD GPU detected")

        # Try to get more info with rocm-smi if available
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.debug("AMD: ROCm available")
        except FileNotFoundError:
            logger.debug("AMD: rocm-smi not found (ROCm not installed)")
        except Exception as e:
            logger.debug(f"AMD rocm-smi check failed: {e}")

        return True

    def _check_intel_qsv(self) -> bool:
        """
        Check if Intel Quick Sync Video is available.

        QSV is available on Intel CPUs with integrated graphics.
        """
        # Check PCI devices for Intel GPU
        if not self._has_gpu_vendor(self.VENDOR_INTEL):
            logger.debug("Intel QSV: No Intel GPU in PCI devices")
            return False

        logger.info("Intel GPU detected (QSV likely available)")
        return True

    def get_recommended_accel(self) -> Optional[str]:
        """
        Get recommended hardware acceleration method.

        Priority: NVENC > QSV > VAAPI (AMD) > VAAPI (Intel)

        Returns:
            Recommended accel method or None if no hardware accel available
        """
        if self.nvidia_available:
            return "nvenc"
        elif self.intel_qsv_available:
            return "qsv"
        elif self.amd_available:
            return "vaapi"  # AMD uses VAAPI on Linux
        elif self.vaapi_available:
            return "vaapi"
        return None

    def get_summary(self) -> dict:
        """
        Get summary of hardware capabilities.

        Returns:
            Dict with hardware capabilities and recommended accel
        """
        return {
            "vaapi": self.vaapi_available,
            "nvidia_nvenc": self.nvidia_available,
            "amd_gpu": self.amd_available,
            "intel_qsv": self.intel_qsv_available,
            "recommended": self.get_recommended_accel(),
        }

    def __repr__(self):
        summary = self.get_summary()
        available = [k for k, v in summary.items() if v and k != "recommended"]
        return f"HardwareCapabilities(available={available}, recommended={summary['recommended']})"


def detect_hardware_accel() -> list[str]:
    """
    Detect available hardware acceleration methods.

    Returns:
        List of available acceleration methods (e.g., ["vaapi", "nvenc"])
    """
    hw = HardwareCapabilities()
    available = []

    if hw.vaapi_available:
        available.append("vaapi")
    if hw.nvidia_available:
        available.append("nvenc")
    if hw.amd_available and not hw.vaapi_available:
        # AMD detected but VAAPI not working - might still work with AMF
        available.append("amf")
    if hw.intel_qsv_available:
        available.append("qsv")

    return available


def get_gpu_info() -> dict:
    """
    Get detailed GPU information for all vendors.

    Returns:
        Dict with GPU info for each vendor
    """
    info = {
        "nvidia": None,
        "amd": None,
        "intel": None,
    }

    # NVIDIA
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if lines:
                parts = [p.strip() for p in lines[0].split(",")]
                if len(parts) >= 3:
                    info["nvidia"] = {
                        "name": parts[0],
                        "driver_version": parts[1],
                        "memory_total": parts[2],
                    }
    except Exception:
        pass

    # AMD (ROCm)
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Parse GPU name from output
            for line in result.stdout.splitlines():
                if "GPU" in line:
                    info["amd"] = {"name": line.strip()}
                    break
    except Exception:
        pass

    # Intel (lspci fallback)
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "VGA" in line and "Intel" in line:
                    # Extract Intel GPU name
                    match = re.search(r"Intel.*", line)
                    if match:
                        info["intel"] = {"name": match.group(0)}
                        break
    except Exception:
        pass

    return info


def get_vaapi_profiles() -> list[str]:
    """
    Get VAAPI supported profiles.

    Returns:
        List of supported VAProfile names
    """
    try:
        result = subprocess.run(
            ["vainfo"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            profiles = []
            for line in result.stdout.splitlines():
                # Look for VAProfile lines
                match = re.match(r"\s*(VAProfile\w+)", line)
                if match:
                    profiles.append(match.group(1))
            return profiles
    except Exception as e:
        logger.debug(f"Failed to get VAAPI profiles: {e}")

    return []
