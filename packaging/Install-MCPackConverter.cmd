@echo off
rem One-time install. Re-run it any time to update to the latest build.
rem Needs Python 3.11+ -- the Microsoft Store build is signed, so Smart App
rem Control allows it.
setlocal
echo Installing MC Pack Converter...
python -m pip install --upgrade "mc-pack-converter[gui] @ https://github.com/M8SON/mc-pack-converter/archive/refs/heads/master.zip"
echo.
echo Done. Run MCPackConverter.cmd to start it.
pause
