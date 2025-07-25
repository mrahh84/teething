@echo off
echo ==========================================
echo     ATTENDANCE ANALYSIS REPORT GENERATOR
echo ==========================================
echo.
echo This will generate the complete attendance analysis report.
echo Looking for Excel file and processing...
echo.

REM Check if virtual environment exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Using system Python...
)

REM Check if config file exists
if not exist config.ini (
    echo ERROR: config.ini file not found!
    echo Please ensure the configuration file exists in the application folder.
    pause
    exit /b 1
)

REM Check if the original folder exists and has Excel files
if not exist original\ (
    echo Creating original folder...
    mkdir original
    echo.
    echo Please place your Excel files ^(REPORT_*.xlsx^) in the 'original' folder
    echo and run this script again.
    pause
    exit /b 1
)

dir original\*.xlsx >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: No Excel files found in the 'original' folder!
    echo Please place your Excel files ^(REPORT_*.xlsx^) in the 'original' folder
    echo.
    set /p continue="Continue anyway? (y/n): "
    if /i not "%continue%"=="y" (
        exit /b 1
    )
)

echo Starting attendance analysis...
echo.
python run_analysis.py --force

REM Check if the analysis was successful
if errorlevel 1 (
    echo.
    echo ERROR: Analysis failed! Please check the error messages above.
    echo Check analysis.log for detailed error information.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo     ANALYSIS COMPLETED SUCCESSFULLY!
echo ==========================================
echo.
echo Results have been generated in the following folders:
echo   - analysis\     ^(Main reports and charts^)
echo   - final\        ^(Consolidated data^)
echo.
echo Key reports generated:
echo   - attendance_analysis_results.csv
echo   - monthly_summary_report.csv
echo   - comprehensive_attendance_report.csv
echo   - Interactive HTML charts
echo.
echo You can find detailed logs in 'analysis.log'
echo.
pause
