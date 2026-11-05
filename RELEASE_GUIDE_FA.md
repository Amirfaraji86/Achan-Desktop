# انتشار نسخه آچان در GitHub Releases

## انتشار نسخه اصلی

1. تغییرات نسخه را روی شاخه `main` قرار بده.
2. در پوشه اصلی پروژه اجرا کن:

```powershell
git add .
git commit -m "Release Achan 1.0.3"
git push origin main
git tag v1.0.3
git push origin v1.0.3
```

3. در GitHub وارد **Actions → Build Achan for Windows** شو و اجرای مربوط به Tag را بررسی کن.
4. پس از پایان موفق، Release نسخه `v1.0.3` شامل این فایل‌هاست:
   - `Achan-Setup-1.0.3.exe` (نصب‌کننده Windows 10/11)
   - `Achan-Portable-Win64.zip` (نسخه قابل‌حمل Windows 10/11)
   - `Achan-Distribution-Win64.zip` (بسته کامل به‌همراه راهنما و SHA256)

## ساخت نسخه Windows 7

بعد از ساخته شدن Release نسخه `v1.0.3`:

1. وارد **Actions → Build Achan for Windows 7** شو.
2. روی **Run workflow** بزن.
3. در فیلد `release_tag` مقدار `v1.0.3` را وارد کن.
4. بعد از موفقیت، فایل‌های مخصوص Windows 7 به همان Release اضافه می‌شوند:
   - `Achan-Setup-1.0.3-Win7-x64.exe`
   - `Achan-Portable-Win7-x64.zip`
   - `Achan-Distribution-Win7-x64.zip`

## دانلود برای کاربران

در صفحه مخزن، **Releases → Latest** را باز کن و از بخش **Assets** فایل متناسب با سیستم‌عامل را بگیر. فایل Source code ZIP که GitHub خودش می‌سازد، برنامه آماده اجرا نیست.

## نکته مهم

نسخه Windows 7 فقط برای Windows 7 SP1 x64 ساخته می‌شود و به‌روزرسانی‌های SHA-2 مایکروسافت (KB4474419 و KB4490628) را لازم دارد. مخزن خصوصی است؛ فقط افرادی که دسترسی خواندن دارند می‌توانند Release و فایل‌ها را ببینند.
