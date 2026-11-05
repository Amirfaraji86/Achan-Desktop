# انتشار نسخه آچان در GitHub Releases

## انتشار خودکار (روش پیشنهادی)

1. تغییرات نسخه را روی شاخه `main` قرار بده.
2. در پوشه اصلی پروژه اجرا کن:

```powershell
git add .
git commit -m "Release Achan 1.0.2"
git push origin main
git tag v1.0.2
git push origin v1.0.2
```

3. در GitHub وارد **Actions → Build Achan for Windows** شو و اجرای مربوط به tag را بررسی کن.
4. پس از سبز شدن job، صفحه **Releases** را باز کن. Workflow سه فایل را به Release نسخه `v1.0.2` پیوست می‌کند:
   - `Achan-Setup-1.0.2.exe` (نصب‌کننده پیشنهادی)
   - `Achan-Portable-Win64.zip` (نسخه بدون نصب)
   - `Achan-Distribution-Win64.zip` (بسته کامل به‌همراه راهنما و SHA256)

## دانلود برای کاربران

در صفحه مخزن، **Releases → Latest** را باز کن و از بخش **Assets** فایل نصب‌کننده را دانلود کن. فایل Source code ZIP که GitHub خودش می‌سازد، برنامه آماده اجرا نیست؛ باید یکی از فایل‌های سه‌گانه بالا را از Assets بگیری.

## نکته مهم

اجرای دستی `workflow_dispatch` فقط Artifact در بخش Actions می‌سازد؛ انتشار عمومی در Releases با push کردن tag با الگوی `v*` فعال می‌شود. چون مخزن خصوصی است، فقط افرادی که دسترسی خواندن دارند می‌توانند Release و فایل‌ها را ببینند. برای دانلود عمومی، مخزن باید Public باشد یا فایل‌ها از یک محل عمومی دیگر ارائه شوند.
