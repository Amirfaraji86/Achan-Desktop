# ساخت ابری و انتشار خودکار Achan

دو Workflow مجزا در `.github/workflows` هستند:

- `build-windows.yml`: Windows 10/11 x64، Python 3.13 و PyInstaller فعلی.
- `build-windows7.yml`: Windows 7 SP1 x64، Python 3.8.10، وابستگی‌های قفل‌شده و PyInstaller 5.13.2.

## انتشار نسخه جدید

شماره `APP_VERSION` در `main.py` و نسخه منابع اجرایی در `version_info.txt` را هماهنگ افزایش بده، تغییرات را به `main` Push کن و وضعیت هر دو Workflow را در Actions ببین. Workflowها شماره نسخه Commit جاری را با Commit قبلی مقایسه می‌کنند. اگر تغییر کرده باشد، خروجی Setup، Portable، Distribution و Manifest JSON مخصوص همان سیستم‌عامل را می‌سازند و در همان Workflow، Tag و Release مختص سیستم‌عامل را ایجاد و منتشر می‌کنند.

الگوی نام‌گذاری:

- `vX.Y.Z-win10-11` برای Windows 10/11.
- `vX.Y.Z-win7` برای Windows 7 SP1.

به‌دلیل Immutable شدن Release پس از انتشار، فایل‌ها در چند مرحله به یک Release اضافه نمی‌شوند؛ همه Assetها در یک دستور ایجاد Release بارگذاری می‌شوند. برای اصلاح یک نسخه منتشرشده، شماره نسخه را افزایش بده.

## اجرای دستی

از Actions می‌توان Workflow را دستی اجرا کرد. اجرای دستی Build همان نسخه فعلی است؛ این روش را برای تست ابزار ساخت استفاده کن، نه برای بازنویسی Release Immutable.

## اجزای Updater

`core/update_client.py` انتشار مخصوص ویندوز را از GitHub API پیدا می‌کند، manifest را می‌خواند، نام فایل و نسخه و اندازه را کنترل می‌کند و Setup را دریافت می‌کند. سپس SHA-256 و تعداد بایت‌ها بررسی می‌شود. `AchanUpdater.exe` یک برنامه کمکی مستقل است که پس از خروج GUI، نصب‌کننده را اجرا و آچان را دوباره باز می‌کند.

Manifestها در Release به‌صورت `Achan-Update-Windows-10-11.json` و `Achan-Update-Windows-7-SP1.json` منتشر می‌شوند.

## پیش‌نیازهای Windows 7

نسخه Win7 از Python 3.8.10 و `requirements-win7.txt` استفاده می‌کند. برای ران‌تایم به Windows 7 SP1 x64 و به‌روزرسانی‌های SHA-2 مایکروسافت KB4474419 و KB4490628 نیاز است. نصب‌کننده Visual C++ 2015–2019 Runtime را نیز همراه خود دارد. این سازگاری باید روی یک VM یا دستگاه واقعی Windows 7 SP1 x64 تست شود.
