"""Secure, platform-aware updater for Achan.

The updater reads only published GitHub Releases for this project. A release
must contain a platform-specific JSON manifest and the matching installer.
The downloaded installer is accepted only after its SHA-256 and byte count
match the manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

import requests


OWNER = "Amirfaraji86"
REPOSITORY = "Achan-Desktop"
APP_ID = "achan-desktop"
API_RELEASES_URL = "https://api.github.com/repos/{}/{}/releases?per_page=100".format(
    OWNER, REPOSITORY
)
USER_AGENT = "Achan-Desktop-Updater/1"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_INSTALLER_BYTES = 300 * 1024 * 1024


class UpdateError(RuntimeError):
    """Raised when update metadata or an installer cannot be trusted."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag: str
    platform: str
    installer_name: str
    installer_url: str
    sha256: str
    size_bytes: int
    release_notes: str


def parse_version(value: str) -> Tuple[int, int, int]:
    match = VERSION_RE.match(str(value or "").strip())
    if not match:
        raise UpdateError("فرمت شماره نسخه معتبر نیست.")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


class UpdateClient:
    """Find and download the newest compatible stable release."""

    def __init__(
        self,
        owner: str = OWNER,
        repository: str = REPOSITORY,
        session: Any = requests,
        timeout: Tuple[int, int] = (8, 30),
    ) -> None:
        self.owner = owner
        self.repository = repository
        self.session = session
        self.timeout = timeout
        self.api_url = "https://api.github.com/repos/{}/{}/releases?per_page=100".format(
            owner, repository
        )

    @staticmethod
    def platform_for_windows(major: int, minor: int) -> Tuple[str, str, str]:
        if (major, minor) == (6, 1):
            return (
                "windows-7-sp1-x64",
                "-win7",
                "Achan-Update-Windows-7-SP1.json",
            )
        if major >= 10:
            return (
                "windows-10-11-x64",
                "-win10-11",
                "Achan-Update-Windows-10-11.json",
            )
        raise UpdateError("این نسخه ویندوز در کانال به‌روزرسانی آچان پشتیبانی نمی‌شود.")

    @staticmethod
    def _safe_release_asset_url(url: str, owner: str, repository: str) -> bool:
        prefix = "https://github.com/{}/{}/releases/download/".format(owner, repository)
        return isinstance(url, str) and url.startswith(prefix) and ".." not in url

    def _get_json(self, url: str) -> Any:
        response = self.session.get(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()
        final_url = getattr(response, "url", None) or url
        parsed = urlparse(str(final_url))
        allowed_hosts = {
            "api.github.com",
            "github.com",
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
        }
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise UpdateError("پاسخ به‌روزرسانی از میزبان امن و مورد اعتماد GitHub دریافت نشد.")
        try:
            return response.json()
        except (ValueError, TypeError) as exc:
            raise UpdateError("پاسخ سرور به‌روزرسانی قابل خواندن نیست.") from exc

    def find_update(
        self, current_version: str, platform_info: Tuple[str, str, str]
    ) -> Optional[UpdateInfo]:
        current = parse_version(current_version)
        platform, suffix, manifest_name = platform_info
        releases = self._get_json(self.api_url)
        if not isinstance(releases, list):
            raise UpdateError("فهرست انتشارهای GitHub ساختار نامعتبر دارد.")

        candidates = []
        for release in releases:
            if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                continue
            tag = str(release.get("tag_name", ""))
            match = re.match(r"^v(\d+\.\d+\.\d+){}$".format(re.escape(suffix)), tag)
            if not match:
                continue
            version_text = match.group(1)
            try:
                version = parse_version(version_text)
            except UpdateError:
                continue
            if version > current:
                candidates.append((version, version_text, tag, release))

        candidates.sort(key=lambda row: row[0], reverse=True)
        for _version_tuple, version_text, tag, release in candidates:
            assets = release.get("assets") or []
            if not isinstance(assets, list):
                continue
            assets = [asset for asset in assets if isinstance(asset, dict)]
            manifest_asset = next(
                (asset for asset in assets if asset.get("name") == manifest_name), None
            )
            if not manifest_asset:
                continue
            try:
                manifest_size = int(manifest_asset.get("size", 0))
            except (TypeError, ValueError):
                raise UpdateError("اندازهٔ فایل مشخصات آپدیت در GitHub معتبر نیست.")
            if manifest_size <= 0 or manifest_size > 256 * 1024:
                raise UpdateError("اندازهٔ فایل مشخصات آپدیت از محدودهٔ مجاز خارج است.")
            manifest_url = manifest_asset.get("browser_download_url", "")
            if not self._safe_release_asset_url(manifest_url, self.owner, self.repository):
                raise UpdateError("نشانی فایل مشخصات آپدیت معتبر نیست.")
            manifest = self._get_json(manifest_url)
            if not isinstance(manifest, dict):
                raise UpdateError("فایل مشخصات آپدیت ساختار نامعتبر دارد.")
            if manifest.get("schema_version") != 1 or manifest.get("app_id") != APP_ID:
                raise UpdateError("نسخه قالب یا شناسه برنامه در manifest پشتیبانی نمی‌شود.")
            if manifest.get("platform") != platform:
                continue
            if manifest.get("tag") != tag or manifest.get("version") != version_text:
                raise UpdateError("نسخه manifest با برچسب انتشار GitHub یکسان نیست.")

            expected_installers = {
                "windows-7-sp1-x64": "Achan-Setup-Windows-7-SP1-x64.exe",
                "windows-10-11-x64": "Achan-Setup-Windows-10-11-x64.exe",
            }
            installer_name = manifest.get("installer")
            if installer_name != expected_installers.get(platform):
                raise UpdateError("نام نصب‌کننده در manifest با کانال رسمی ویندوز مطابقت ندارد.")
            if (
                not isinstance(installer_name, str)
                or Path(installer_name).name != installer_name
                or "/" in installer_name
                or "\\" in installer_name
            ):
                raise UpdateError("نام فایل نصب‌کننده نامعتبر است.")
            installer_asset = next(
                (asset for asset in assets if asset.get("name") == installer_name), None
            )
            if not installer_asset:
                raise UpdateError("نصب‌کنندهٔ متناظر با manifest در انتشار وجود ندارد.")
            installer_url = installer_asset.get("browser_download_url", "")
            if not self._safe_release_asset_url(installer_url, self.owner, self.repository):
                raise UpdateError("نشانی نصب‌کننده خارج از مخزن رسمی آچان است.")

            digest = str(manifest.get("sha256", "")).lower()
            if not SHA256_RE.match(digest):
                raise UpdateError("SHA-256 فایل نصب‌کننده در manifest معتبر نیست.")
            try:
                size = int(manifest.get("size_bytes"))
            except (TypeError, ValueError):
                raise UpdateError("اندازهٔ فایل نصب‌کننده در manifest معتبر نیست.")
            if size <= 0 or size > MAX_INSTALLER_BYTES:
                raise UpdateError("اندازهٔ فایل نصب‌کننده خارج از محدودهٔ مجاز است.")
            asset_size = installer_asset.get("size")
            if asset_size is not None:
                try:
                    parsed_asset_size = int(asset_size)
                except (TypeError, ValueError):
                    raise UpdateError("اندازهٔ فایل در اطلاعات GitHub معتبر نیست.")
                if parsed_asset_size != size:
                    raise UpdateError("اندازهٔ فایل در GitHub با manifest یکسان نیست.")

            return UpdateInfo(
                version=version_text,
                tag=tag,
                platform=platform,
                installer_name=str(installer_name),
                installer_url=installer_url,
                sha256=digest,
                size_bytes=size,
                release_notes=str(manifest.get("release_notes", release.get("body", "")))[:12000],
            )
        return None

    def check_for_update(
        self, current_version: str, windows_version: Tuple[int, int]
    ) -> Optional[UpdateInfo]:
        platform_info = self.platform_for_windows(*windows_version)
        return self.find_update(current_version, platform_info)

    def download_installer(
        self,
        info: UpdateInfo,
        destination_dir: Path,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        expected_installers = {
            "windows-7-sp1-x64": ("Achan-Setup-Windows-7-SP1-x64.exe", "-win7"),
            "windows-10-11-x64": ("Achan-Setup-Windows-10-11-x64.exe", "-win10-11"),
        }
        expected = expected_installers.get(info.platform)
        if expected is None:
            raise UpdateError("کانال ویندوز برای دانلود معتبر نیست.")
        expected_name, tag_suffix = expected
        try:
            parse_version(info.version)
        except UpdateError:
            raise UpdateError("شماره نسخهٔ دریافت‌شده معتبر نیست.")
        if info.tag != "v{}{}".format(info.version, tag_suffix):
            raise UpdateError("برچسب نسخه با پلتفرم و شماره نسخه یکسان نیست.")
        if (
            info.installer_name != expected_name
            or Path(info.installer_name).name != info.installer_name
            or "/" in info.installer_name
            or "\\" in info.installer_name
        ):
            raise UpdateError("نام فایل نصب‌کننده برای دانلود معتبر نیست.")
        if not self._safe_release_asset_url(info.installer_url, self.owner, self.repository):
            raise UpdateError("نشانی نصب‌کننده خارج از انتشار رسمی آچان است.")
        if not SHA256_RE.fullmatch(str(info.sha256 or "")):
            raise UpdateError("SHA-256 فایل نصب‌کننده معتبر نیست.")
        if not isinstance(info.size_bytes, int) or not 0 < info.size_bytes <= MAX_INSTALLER_BYTES:
            raise UpdateError("اندازهٔ فایل نصب‌کننده معتبر نیست.")
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / info.installer_name
        partial = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        received = 0
        try:
            response = self.session.get(
                info.installer_url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            final_url = getattr(response, "url", info.installer_url)
            parsed = urlparse(str(final_url))
            allowed_hosts = {
                "github.com",
                "release-assets.githubusercontent.com",
                "objects.githubusercontent.com",
            }
            if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
                raise UpdateError("دانلود به میزبان امن و مورد اعتماد GitHub منتقل نشد.")
            with open(str(partial), "wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    received += len(chunk)
                    if received > info.size_bytes or received > MAX_INSTALLER_BYTES:
                        raise UpdateError("حجم دانلود از اندازهٔ ثبت‌شده بیشتر شد.")
                    digest.update(chunk)
                    output.write(chunk)
                    if progress:
                        progress(received, info.size_bytes)
            if received != info.size_bytes:
                raise UpdateError("دانلود کامل نیست؛ اندازهٔ فایل با manifest تفاوت دارد.")
            if digest.hexdigest().lower() != info.sha256.lower():
                raise UpdateError("تأیید SHA-256 ناموفق بود؛ فایل نصب‌کننده اجرا نشد.")
            os.replace(str(partial), str(destination))
            return destination
        except Exception:
            try:
                partial.unlink()
            except OSError:
                pass
            raise


def installed_by_setup(app_dir: Path) -> bool:
    """Return True for an Inno Setup installation, including legacy 1.0.x.

    Portable ZIP folders do not contain the Inno Setup uninstaller, so they
    are deliberately excluded from silent self-installation.
    """
    try:
        app_dir = Path(app_dir).resolve()
        uninstaller = app_dir / "unins000.exe"
        return uninstaller.is_file()
    except (OSError, RuntimeError):
        return False
