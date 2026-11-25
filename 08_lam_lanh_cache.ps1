# =====================================================================
# Lam lanh cache truoc moi lan do "cache lanh" (bat buoc doc du lieu tu dia).
# PHAI chay trong PowerShell mo bang "Run as Administrator".
#
#   cd D:\BTL_DBM
#   powershell -ExecutionPolicy Bypass -File .\08_lam_lanh_cache.ps1 -Target mysql
#   powershell -ExecutionPolicy Bypass -File .\08_lam_lanh_cache.ps1 -Target mongo
#
# Script lam:
#   MySQL : dung service -> xoa file ib_buffer_pool (de MySQL KHONG nap lai cac trang
#           cu luc khoi dong) -> xoa cache file cua Windows -> bat lai service.
#           (InnoDB tren Windows dung innodb_flush_method=unbuffered nen khong di qua
#            cache file cua Windows; restart la buffer pool trong rong.)
#   Mongo : dung service -> xoa cache file cua Windows (WiredTiger DOC QUA cache nay,
#           restart thoi la chua du) -> bat lai service -> dat lai cache 2 GB.
#
# Xoa cache file cua Windows can RAMMap64.exe (Sysinternals, mien phi cua Microsoft):
#   tai https://learn.microsoft.com/sysinternals/downloads/rammap , giai nen
#   RAMMap64.exe vao D:\BTL_DBM\tools\
# =====================================================================
#Requires -RunAsAdministrator
param(
    [ValidateSet('mysql', 'mongo', 'all')]
    [string]$Target = 'all'
)
$ErrorActionPreference = 'Stop'

$mysqlService = 'MYSQL80'
$mongoService = 'MongoDB'
$mysqlDataDir = 'C:\ProgramData\MySQL\MySQL Server 8.0\Data'
$ramMap       = Join-Path $PSScriptRoot 'tools\RAMMap64.exe'

function Clear-WindowsFileCache {
    if (Test-Path $ramMap) {
        & $ramMap -accepteula -Et | Out-Null
        Start-Sleep -Seconds 2
        Write-Host '  Da xoa cache file cua Windows (standby list).'
    } else {
        Write-Warning "Khong thay $ramMap. Cache file cua Windows CHUA duoc xoa."
        Write-Warning 'MySQL van lanh (unbuffered), nhung MongoDB se KHONG lanh hoan toan.'
    }
}

function Wait-Port([int]$port) {
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $c = New-Object System.Net.Sockets.TcpClient
            $c.Connect('127.0.0.1', $port); $c.Close(); return
        } catch { Start-Sleep -Milliseconds 500 }
    }
    throw "Service tren cong $port khong len sau 30 giay."
}

$doMysql = $Target -in @('mysql', 'all')
$doMongo = $Target -in @('mongo', 'all')

Write-Host "== Lam lanh cache: $Target =="
if ($doMysql) { Stop-Service $mysqlService; Write-Host "  Da dung $mysqlService" }
if ($doMongo) { Stop-Service $mongoService; Write-Host "  Da dung $mongoService" }

if ($doMysql) {
    $dump = Join-Path $mysqlDataDir 'ib_buffer_pool'
    if (Test-Path $dump) { Remove-Item $dump -Force; Write-Host '  Da xoa ib_buffer_pool' }
}

Clear-WindowsFileCache

if ($doMysql) { Start-Service $mysqlService; Wait-Port 3306; Write-Host "  $mysqlService da chay lai" }
if ($doMongo) {
    Start-Service $mongoService; Wait-Port 27017; Write-Host "  $mongoService da chay lai"
    py -3.12 -c "from pymongo import MongoClient; r = MongoClient('mongodb://127.0.0.1:27017').admin.command('setParameter', 1, wiredTigerEngineRuntimeConfig='cache_size=2G'); print('  Mongo cache_size=2G, ok =', r['ok'])"
}
Write-Host '== Xong. Ket noi lai Workbench/Compass va chay DUNG 1 truy van, chi 1 lan. =='
