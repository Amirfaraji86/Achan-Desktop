# ساخت ابری آچان

این پوشه سورس و فرایند ساخت ویندوزی آچان است. فایل‌های workflow در `.github/workflows` قرار دارند.

## ساخت نسخه Windows 10/11

1. در GitHub وارد زبانه **Actions** شو.
2. Workflow با نام **Build Achan for Windows** را باز کن.
3. بعد از Push کردن Tag نسخه با الگوی `v*`، ساخت به‌صورت خودکار انجام می‌شود؛ اجرای دستی هم از **Run workflow** ممکن است.
4. خروجی در بخش **Artifacts** و در Release همان نسخه قرار می‌گیرد.

## ساخت نسخه Windows 7 SP1

1. ابتدا Release نسخه موردنظر را با Workflow اصلی بساز.
2. در **Actions**، Workflow با نام **Build Achan for Windows 7** را باز کن.
3. روی **Run workflow** کلیک کن و Tag همان Release، مانند `v1.0.3`، را وارد کن.
4. پس از پایان موفق، سه فایل Windows 7 به Artifact و به Release انتخاب‌شده اضافه می‌شوند.

## نکته فنی

در Build ویندوز ۷ از Python 3.8.10 و وابستگی‌های قفل‌شده `requirements-win7.txt` استفاده می‌شود. Python فقط ابزار Build است و روی رایانه مقصد لازم نیست. نصب‌کننده Visual C++ 2015–2019 Runtime را همراه خود دارد.

Windows 7 باید SP1 x64 باشد و به‌روزرسانی‌های SHA-2 مایکروسافت KB4474419 و KB4490628 را داشته باشد. این دو به‌روزرسانی قبل از نصب باید نصب شده باشند و پس از آن سیستم Restart شود.
