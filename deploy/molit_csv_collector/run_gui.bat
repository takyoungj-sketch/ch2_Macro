@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================
echo  국토부 실거래 CSV 수집기
echo  폴더: %CD%
echo ========================================
echo.

REM Python 찾기 (py 우선, 없으면 python)
set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [오류] Python을 찾을 수 없습니다.
  echo        python.org 에서 설치하거나 PATH에 추가하세요.
  goto :fail
)

echo Python: 
%PY% --version
if errorlevel 1 goto :fail
echo.

if not exist "molit_csv_collector\__main__.py" (
  echo [오류] molit_csv_collector 패키지 폴더가 없습니다.
  echo        zip을 풀 때 run_gui.bat 와 같은 폴더에
  echo        molit_csv_collector\ 하위폴더가 있어야 합니다.
  goto :fail
)

if not exist "requirements.txt" (
  echo [오류] requirements.txt 파일이 없습니다.
  goto :fail
)

echo 의존성 확인 중...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [오류] pip install 실패
  goto :fail
)
echo.

echo tkinter 확인...
%PY% -c "import tkinter" 2>nul
if errorlevel 1 (
  echo [오류] tkinter 없음. Python 설치 관리자에서 tcl/tk 를 포함해 재설치하세요.
  goto :fail
)
echo.

echo GUI 시작...
%PY% "%~dp0run_collector.py"
if errorlevel 1 goto :fail

endlocal
exit /b 0

:fail
echo.
echo 실행이 중단되었습니다. 위 메시지를 확인하세요.
pause
endlocal
exit /b 1
