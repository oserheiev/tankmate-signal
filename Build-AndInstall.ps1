#Requires -Version 7.0

[CmdletBinding()]
param(
    [string] $GameRoot = 'D:\Games\Wargaming.net\World_of_Tanks_EU'
)

$ErrorActionPreference = 'Stop'

$modsRoot = Join-Path $GameRoot 'mods'
$latestFolder = Get-ChildItem -LiteralPath $modsRoot -Directory |
    Where-Object { [version]::TryParse($_.Name, [ref] $null) } |
    Sort-Object -Property { [version] $_.Name } -Descending |
    Select-Object -First 1

if ($null -eq $latestFolder) {
    throw "No numbered World of Tanks mod folders were found in '$modsRoot'."
}

$pythonDll = (Get-Item -LiteralPath (Join-Path $GameRoot 'win64/python27.dll')).FullName
$probeRoot = Join-Path $PSScriptRoot 'probe'
$moduleName = 'mod_tankmate_signal'
$source = Join-Path $probeRoot "$moduleName.py"
$packageName = 'tankmate-signal.wotmod'
$package = Join-Path $probeRoot $packageName
$destination = Join-Path $latestFolder.FullName $packageName

if (-not ('WotProbePython' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class WotProbePython
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr LoadLibrary(string path);

    [DllImport("kernel32.dll", ExactSpelling = true)]
    private static extern IntPtr GetProcAddress(IntPtr library, string name);

    [DllImport("kernel32.dll")]
    private static extern bool FreeLibrary(IntPtr library);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void Initialize(int installSignals);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int RunScript([MarshalAs(UnmanagedType.LPStr)] string script);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void FinalizePython();

    private static IntPtr Export(IntPtr library, string name)
    {
        IntPtr address = GetProcAddress(library, name);
        if (address == IntPtr.Zero)
            throw new EntryPointNotFoundException(name);
        return address;
    }

    public static void Run(string dll, string script)
    {
        IntPtr library = LoadLibrary(dll);
        if (library == IntPtr.Zero)
            throw new Win32Exception(Marshal.GetLastWin32Error());

        try
        {
            var initialize = Marshal.GetDelegateForFunctionPointer<Initialize>(Export(library, "Py_InitializeEx"));
            var run = Marshal.GetDelegateForFunctionPointer<RunScript>(Export(library, "PyRun_SimpleString"));
            var finalize = Marshal.GetDelegateForFunctionPointer<FinalizePython>(Export(library, "Py_Finalize"));
            Marshal.WriteInt32(Export(library, "Py_NoSiteFlag"), 1);
            Marshal.WriteInt32(Export(library, "Py_IgnoreEnvironmentFlag"), 1);
            initialize(0);

            try
            {
                if (run(script) != 0)
                    throw new InvalidOperationException("Python 2.7 could not compile the mod.");
            }
            finally
            {
                finalize();
            }
        }
        finally
        {
            FreeLibrary(library);
        }
    }
}
'@
}

$bytecode = [IO.Path]::GetTempFileName()
$buildStaging = "$package.$([guid]::NewGuid().ToString('N')).tmp"
$installStaging = "$destination.$([guid]::NewGuid().ToString('N')).tmp"
try {
    $sourceLiteral = ConvertTo-Json -InputObject $source -Compress -EscapeHandling EscapeNonAscii
    $bytecodeLiteral = ConvertTo-Json -InputObject $bytecode -Compress -EscapeHandling EscapeNonAscii
    [WotProbePython]::Run($pythonDll, @"
import imp
import marshal

with open(u$sourceLiteral, 'rb') as source:
    code = compile(source.read().replace('\r\n', '\n'), '$moduleName.py', 'exec')
with open(u$bytecodeLiteral, 'wb') as bytecode:
    bytecode.write(imp.get_magic() + '\x00' * 4)
    marshal.dump(code, bytecode)
"@)

    $archive = [IO.Compression.ZipFile]::Open($buildStaging, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $meta = $archive.CreateEntry('meta.xml', [IO.Compression.CompressionLevel]::NoCompression)
        $writer = [IO.StreamWriter]::new($meta.Open())
        try {
            $writer.Write(@'
<root>
    <id>local.friendpresence.probe</id>
    <version>0.1.16</version>
    <name>Tankmate Signal</name>
    <description>World of Tanks friend presence notifications</description>
</root>
'@)
        } finally {
            $writer.Dispose()
        }
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive, $bytecode, "res/scripts/client/gui/mods/$moduleName.pyc",
            [IO.Compression.CompressionLevel]::NoCompression
        )
        foreach ($texture in 'tankmate-plate.dds', 'tankmate-plate-offline.dds') {
            [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, (Join-Path $probeRoot $texture),
                "res/gui/maps/icons/tankmate_signal/$texture",
                [IO.Compression.CompressionLevel]::NoCompression
            )
        }
    } finally {
        $archive.Dispose()
    }

    [IO.File]::Move($buildStaging, $package, $true)
    [IO.File]::Copy($package, $installStaging)
    try {
        [IO.File]::Move($installStaging, $destination, $true)
    } catch {
        if ($_.Exception.InnerException -is [IO.IOException] -and
            ($_.Exception.InnerException.HResult -band 65535) -in 32, 33) {
            throw "World of Tanks is using '$destination'. Close the game and rerun this script."
        }
        throw
    }
    Write-Output "Packaged $package"
    Write-Output "Installed $destination"
} finally {
    foreach ($temporaryFile in $bytecode, $buildStaging, $installStaging) {
        if (Test-Path -LiteralPath $temporaryFile) {
            Remove-Item -LiteralPath $temporaryFile
        }
    }
}
