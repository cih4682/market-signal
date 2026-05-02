@echo off
chcp 65001 >nul
title Market Signal - 설치

echo.
echo ============================================
echo          Market Signal 설치 시작
echo ============================================
echo.

REM Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python이 설치되어 있지 않습니다.
    echo.
    echo     1. https://www.python.org/downloads/ 접속
    echo     2. 최신 Python 3.11 또는 3.12 다운로드
    echo     3. 설치 시 "Add Python to PATH" 반드시 체크 ^^!
    echo     4. 설치 완료 후 이 setup.bat을 다시 실행
    echo.
    pause
    exit /b
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] Python %PYVER% 확인 완료

REM 가상환경 생성
echo.
echo [*] 가상환경 준비 중...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 (
        echo [X] 가상환경 생성 실패. Python 설치 상태를 확인하세요.
        pause
        exit /b
    )
    echo [OK] 가상환경 생성 완료
) else (
    echo [OK] 가상환경 이미 존재
)

REM 가상환경 활성화
call .venv\Scripts\activate.bat

REM pip 업그레이드
echo.
echo [*] pip 업그레이드...
python -m pip install --upgrade pip --quiet

REM 의존성 설치
echo.
echo [*] 패키지 설치 중... (3~5분, 인터넷 속도에 따라 더 길어질 수 있음)
echo     streamlit / pandas / lxml / curl_cffi 등
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [X] 패키지 설치 실패
    echo     - 인터넷 연결 확인
    echo     - 회사 보안망이면 관리자에게 PyPI 접근 허용 요청
    pause
    exit /b
)

echo.
echo ============================================
echo            설치 완료!
echo ============================================
echo.
echo  실행:  run.bat 더블클릭
echo  종료:  검은 창에서 Ctrl + C
echo.
pause
