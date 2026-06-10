@echo off
title SentimentSwipe V2 Dashboard
cd /d %~dp0
echo =============================================
echo   SentimentSwipe V2 - AI Trading Dashboard
echo =============================================
echo.
echo Starting Flask dashboard on http://localhost:5000
echo Press Ctrl+C to stop
echo.
python "%~dp0sentimentswipe\dashboard\app.py"
pause