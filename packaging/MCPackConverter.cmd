@echo off
rem MC Pack Converter. Double-click, or drag a pack onto this file.
rem
rem Runs through the signed python.exe on purpose: pip generates its console
rem and gui scripts as UNSIGNED .exe shims, which Windows Smart App Control
rem blocks -- the same reason this project no longer ships a bundled exe.
setlocal
python -m mc_pack_converter.gui %*
if errorlevel 1 (
  echo.
  echo MC Pack Converter exited with an error.
  echo Log: %LOCALAPPDATA%\MCPackConverter\last-run.log
  pause
)
