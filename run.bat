@echo off
chcp 65001 >nul
title Market Signal

REM 가상환경 확인
if not exist ".venv\Scripts\activate.bat" (
    echo [X] 가상환경이 없습니다.
    echo     먼저 setup.bat 을 더블클릭해서 설치를 진행하세요.
    pause
    exit /b
)

REM 가상환경 활성화
call .venv\Scripts\activate.bat

echo.
echo ============================================
echo          Market Signal 시작 중...
echo ============================================
echo.
echo  잠시 후 브라우저가 자동으로 열립니다.
echo  ( http://localhost:8501 )
echo.
echo  종료하려면 이 창에서 Ctrl + C 또는 창 닫기.
echo.

REM Streamlit 실행 (자동으로 브라우저 열림)
streamlit run app.py
