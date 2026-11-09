# آماده‌سازی رابط مدرن آچان برای Windows 7

هدف این بسته، ساخت نسخه Windows 7 SP1 با همان طراحی رابط مدرن Qt Quick نسخه Windows 10/11 است؛ بدون تغییر در فایل‌ها و فرایند ساخت Windows 10/11.

## طرح فنی

- Windows 10/11: بدون تغییر؛ همچنان PySide6 / Qt 6.12 و فایل‌های فعلی را استفاده می‌کند.
- Windows 7 SP1: از PySide2 5.15.2.1 / Qt 5.15.2 و Python 3.8.10 استفاده می‌کند.
- فایل QML نسخه Windows 7 از روی همان `qt_ui/main.qml` ساخته می‌شود و فقط importهای Qt 6 به API سازگار Qt 5.15 تبدیل می‌شوند؛ طراحی، رنگ‌ها، صفحات و انیمیشن‌ها حفظ می‌شوند.
- چون انتشار Win7 با برچسب `v1.2.0-win7` قبلاً وجود دارد، نسخه مستقل Win7 روی `1.2.1` قرار می‌گیرد تا فایل‌های انتشار قبلی بازنویسی نشوند.
- کد و هسته شبکه مشترک آچان حفظ می‌شود.

## نحوه استفاده

1. از مخزن نسخه پشتیبان یا یک شاخه Git جداگانه داشته باش.
2. این ZIP را در ریشه مخزن استخراج کن؛ فایل اسکریپت در مسیر `scripts\prepare-win7-qt.ps1` قرار می‌گیرد.
3. در CMD و از ریشه مخزن اجرا کن:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\prepare-win7-qt.ps1" -Version "1.2.1"
```

اسکریپت از روی فایل‌های موجود پروژه، نسخه مستقل Win7 را می‌سازد و فقط `.github/workflows/build-windows7.yml` را تغییر می‌دهد. فایل‌های Win10 از جمله `main_qt.py`، `qt_ui/main.qml`، `requirements-qt.txt`، `version_info.txt` و `.github/workflows/build-windows.yml` را ویرایش نمی‌کند.

## بررسی پس از اجرا

```bat
git status --short
git diff --check
git diff -- .github/workflows/build-windows7.yml
python -m py_compile main_qt_win7.py tools\validate_qml_win7.py
```

برای تست QML محلی باید Python 3.8.10 x64 نصب باشد. اگر لانچر Python آن را می‌شناسد، در CMD از `py -3.8` استفاده کن (Python 3.13 فعلی برای PySide2 مناسب نیست):

```bat
py -3.8 -m pip install -r requirements-win7-qt.txt
set QT_QPA_PLATFORM=offscreen
set QT_QUICK_BACKEND=software
py -3.8 tools\validate_qml_win7.py
```

اگر Python 3.8 روی سیستم نصب نیست، بسته‌های Win7 را روی Python 3.13 نصب نکن؛ تست Python 3.8 و PySide2 در GitHub Actions انجام می‌شود.

برای پاک‌کردن متغیرهای موقت:

```bat
set QT_QPA_PLATFORM=
set QT_QUICK_BACKEND=
```

## مهم

این بسته یک **اسکریپت آماده‌سازی** است، نه فایل نصب نهایی. هنوز روی دستگاه واقعی Windows 7 اجرا و تأیید نشده است. ابتدا باید QML smoke test و GitHub Actions ساخت Win7 موفق شوند؛ سپس نصب‌کننده را روی Windows 7 SP1 x64 آزمایش کن. تا آن زمان Commit/Push یا انتشار را تأیید نکن.

در Qt 5.15، عملیات جابه‌جایی و تغییر اندازه پنجره از طریق API بومی `QWindow` در Bridge پایتون فراخوانی می‌شود؛ چون Wrapper مربوط به QML این متدها را فقط در Qt 6.8 در اختیار QML می‌گذارد. ظاهر نوار عنوان و نواحی drag/resize همان طراحی نسخه مدرن باقی می‌ماند.
