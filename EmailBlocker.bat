@echo off
%@Try%
    cd EmailBlocker
    @start "Email Blocker - By Crozzo" "EmailBlocker.exe"
%@EndTry%
:@Catch
    cd ..
    echo Error loading the EmailBlocker. Make sure you have run the setup.bat file first
    pause
:@EndCatch