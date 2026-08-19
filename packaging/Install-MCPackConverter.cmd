@echo off
rem One-time install. Re-run it any time to update to the latest build.
rem Needs Python 3.11+ -- the Microsoft Store build is signed, so Smart App
rem Control allows it.
rem --force-reinstall is not caution, it is the whole mechanism. --upgrade
rem compares VERSION NUMBERS, and pyproject pins 0.1.0 with no per-commit
rem bump, so against a moving master branch pip fetches the zip, finds the
rem same version already installed, prints "Requirement already satisfied"
rem and installs nothing. Re-running the installer looked like it worked and
rem changed nothing for three and a half hours.
rem --no-cache-dir is the same failure from the other end: the URL names a
rem branch, so its contents change while its name does not, and a cached
rem archive is a stale build wearing the right address.
rem The cost is that dependencies reinstall too, so this takes a minute.
setlocal
echo Installing MC Pack Converter...
python -m pip install --no-cache-dir --force-reinstall "mc-pack-converter[gui] @ https://github.com/M8SON/mc-pack-converter/archive/refs/heads/master.zip"
rem Record which build this is, so the window can tell you when it is stale.
rem AFTER the install, never before: a SHA written first and then a failed pip
rem is a file that lies, and it lies in the direction of staying quiet.
python -m mc_pack_converter.webui.update
echo.
echo Done. Run MCPackConverter.cmd to start it.
pause
