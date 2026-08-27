@echo off
powershell -NoProfile -Command "try { Invoke-RestMethod -Method Post http://127.0.0.1:8888/shutdown | Out-Null } catch {}"
