@echo off
rem MC Pack Converter. Drag a 1.8.9 resource pack onto this file.
rem
rem This is the ONLY file a user needs. It installs itself the first time it
rem runs, keeps itself current after that, and converts whatever is dropped on
rem it. There used to be a separate Install-MCPackConverter.cmd; two files with
rem near-identical names meant downloading both by hand out of the GitHub tree
rem and running the wrong one did nothing useful.
rem
rem Everything runs through the signed python.exe on purpose: pip generates its
rem console scripts as UNSIGNED .exe shims, which Windows Smart App Control
rem blocks -- the same reason this project ships no bundled exe.
setlocal
title MC Pack Converter

rem --- 1. Python -------------------------------------------------------------
rem Without Python installed, `python` hits the Windows App Execution Alias,
rem which opens the Microsoft Store and says nothing about why. Ask first, and
rem ask for the version we actually need rather than merely for a python.
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :nopython

rem --- 2. Install, the first time -------------------------------------------
python -c "import mc_pack_converter" >nul 2>&1
if errorlevel 1 (
  echo Installing MC Pack Converter. This takes about a minute...
  call :install || goto :installfailed
  echo Done.
  echo.
)

rem --- 3. Keep it current ----------------------------------------------------
rem --check exits 1 only when a newer build is proven to exist. Offline, rate
rem limited, or nothing recorded all answer "no", so a launch with no network
rem never turns into a one-minute wait. Bounded by update.py's 2s timeout.
python -m mc_pack_converter.webui.update --check >nul 2>&1
if errorlevel 1 (
  echo A newer version is available. Updating, about a minute...
  call :install || goto :installfailed
  echo Done.
  echo.
)

rem --- 4. Convert ------------------------------------------------------------
python -m mc_pack_converter.gui %*
set "EC=%ERRORLEVEL%"
rem Exit 2 covers two ordinary cases, not a crash: a bare double-click (no pack
rem dropped) and a rejected pack. gui.main already printed its own message to
rem stderr for both, so just hold the window open to show it -- echoing "error"
rem on top would be wrong for the double-click case.
if "%EC%"=="0" goto :eof
if "%EC%"=="2" (
  pause
  goto :eof
)
echo.
echo MC Pack Converter crashed ^(exit code %EC%^).
pause
goto :eof


:install
rem --force-reinstall is not caution, it is the whole mechanism. --upgrade
rem compares VERSION NUMBERS, and pyproject pins 0.1.0 with no per-commit bump,
rem so against a moving master branch pip fetches the zip, finds the same
rem version installed, prints "Requirement already satisfied" and installs
rem nothing. That once left a build three and a half hours old in place.
rem --no-cache-dir is the same failure from the other end: the URL names a
rem branch, so its contents change while its name does not, and a cached
rem archive is a stale build wearing the right address.
rem --quiet because pip's resolver chatter reads as an error wall to the
rem audience this file exists for, and --disable-pip-version-check because
rem --quiet does NOT suppress pip advertising its own upgrade, which leaked
rem through a real Windows install. Failures still print.
python -m pip install --quiet --disable-pip-version-check --no-cache-dir --force-reinstall "mc-pack-converter @ https://github.com/M8SON/mc-pack-converter/archive/refs/heads/master.zip"
if errorlevel 1 exit /b 1
rem Record which build this is, AFTER the install and never before: a SHA
rem written first and then a failed pip is a file that lies, and it lies in the
rem direction of staying quiet.
python -m mc_pack_converter.webui.update >nul 2>&1
exit /b 0


:nopython
echo.
echo MC Pack Converter needs Python, and it is not installed.
echo.
echo Get it from the Microsoft Store -- search for "Python 3.12", or open:
echo   https://apps.microsoft.com/detail/9NCVDN91XZQP
echo.
echo Use the Store version. It is signed by Microsoft, so Windows allows it;
echo other builds can be blocked by Smart App Control.
echo.
echo Then run this file again.
echo.
pause
goto :eof


:installfailed
echo.
echo MC Pack Converter could not install itself.
echo The reason should be printed just above this line.
echo.
echo Most often this is no internet connection. Check that, then run this
echo file again.
echo.
pause
goto :eof
