# بسته آماده‌سازی انتشار Achan 1.2.0

این بسته، رابط Qt Quick نسخه v4 را به‌عنوان رابط رسمی Windows 10/11 آماده می‌کند و مسیر انتشار Windows 7 SP1 را حفظ می‌کند.

## نکته مهم سازگاری

Qt 6.12 برای Windows 10 نسخه 1809 (Build 17763) و Windows 11 پشتیبانی می‌شود. Windows 7 توسط Qt 6 پشتیبانی رسمی نمی‌شود؛ بنابراین نسخه Windows 7 SP1 با رابط قدیمی Tkinter و همان هسته شبکه منتشر خواهد شد. دو انتشار مستقل با tagهای `v1.2.0-win10-11` و `v1.2.0-win7` ساخته می‌شوند.

## محتویات

- `main_qt.py`: پل Qt/Python متصل به NetworkController و UpdateClient فعلی. نمونه‌برداری دائمی Ping/Download/Upload حذف شده و فقط سلامت پردازش تونل بررسی می‌شود.
- `qt_ui/main.qml`: رابط مدرن v4؛ بدون صفحه مانیتور شبکه و کارت وضعیت سرویس‌ها.
- `requirements-qt.txt`: وابستگی‌های ساخت نسخه Qt.
- `tools/validate_qml.py`: تست بارگذاری QML در CI.
- `scripts/prepare-modern-release.ps1`: آماده‌سازی workflow ویندوز 10/11 برای ساخت Qt Quick.
- `RELEASE_NOTES_FA.md`: یادداشت انتشار 1.2.0.

## نصب در مخزن محلی

1. این ZIP را در ریشه مخزن `Achan-Desktop` استخراج کن و فایل‌های هم‌نام را جایگزین کن.
2. PowerShell را در ریشه مخزن باز کن و اجرا کن:

```powershell
.\scripts\prepare-modern-release.ps1 -Version 1.2.0
```

3. تغییرات را بررسی کن:

```powershell
git diff -- .github/workflows/build-windows.yml main_qt.py qt_ui/main.qml requirements-qt.txt RELEASE_NOTES_FA.md
```

4. وقتی diff درست بود، انتشار هر دو کانال را با اسکریپت موجود پروژه انجام بده:

```powershell
.\scripts\publish-release.ps1 -Version 1.2.0 -CommitAndPush
```

اسکریپت انتشار موجود، `main.py`، `version_info.txt` و `installer/Achan.iss` را به نسخه 1.2.0 ارتقا می‌دهد و یک commit به `main` push می‌کند. سپس GitHub Actions دو Workflow را اجرا و دو Release مستقل را منتشر می‌کند.

## خروجی‌های GitHub Releases

برای هر سیستم‌عامل سه بسته ساخته می‌شود: Setup، Portable و Distribution. همچنین Manifest مخصوص آپدیت با اندازه و SHA-256 نصب‌کننده منتشر می‌شود.

- Windows 10/11 x64: نصب‌کننده مدرن Qt Quick.
- Windows 7 SP1 x64: نصب‌کننده سازگار Tkinter.

## تست محلی نسخه مدرن

بعد از نصب وابستگی‌های Qt:

```cmd
python -m pip install -r requirements-qt.txt
python tools\validate_qml.py
run-modern-demo.bat
```

حالت Demo هیچ تغییری در شبکه ایجاد نمی‌کند.
