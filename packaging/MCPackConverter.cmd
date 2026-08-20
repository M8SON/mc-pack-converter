@echo off
rem MC Pack Converter. Double-click, or drag a pack onto this file.
rem
rem Runs through the signed python.exe on purpose: pip generates its console
rem and gui scripts as UNSIGNED .exe shims, which Windows Smart App Control
rem blocks -- the same reason this project no longer ships a bundled exe.
setlocal
python -m mc_pack_converter.gui %*
set "EC=%ERRORLEVEL%"
rem Exit 2 covers two ordinary cases, not a crash: a bare double-click (no
rem pack dropped) and a rejected pack. gui.main already printed its own
rem message to stderr for both, so just hold the window open to show it --
rem echoing "error" on top would be wrong for the double-click case, and
rem there is no log to point at any more: last-run.log was written by _diag,
rem which was deleted with the pywebview window.
if "%EC%"=="0" goto :eof
if "%EC%"=="2" (
  pause
  goto :eof
)
echo.
echo MC Pack Converter crashed ^(exit code %EC%^).
pause
