@echo off
echo ========================================
echo    EPUB 转 DOCX 转换器
echo ========================================
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

pip install -r requirements.txt

python main.py

if errorlevel 1 (
    echo.
    echo 转换过程中出现错误，请检查错误信息。
    pause
)
