@echo off
rem Instala o J.A.R.V.I.S. neste PC (duplo clique). Detalhes no README.md.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
