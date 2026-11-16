#Requires -Version 5.1

[CmdletBinding()]
param(
    [string] $GameRoot = 'D:\Games\Wargaming.net\World_of_Tanks_EU'
)

$ErrorActionPreference = 'Stop'

function ConvertTo-PythonPathLiteral([string] $Path) {
    $json = ConvertTo-Json -InputObject $Path -Compress
    # PyRun_SimpleString receives an ANSI string, so keep the Python source ASCII.
    [regex]::Replace($json, '[^\x00-\x7f]', {
        param($Match)
        '\u{0:x4}' -f [int][char]$Match.Value
    })
}

function Publish-Package([string] $Staging, [string] $Destination) {
    if ([IO.File]::Exists($Destination)) {
        [IO.File]::Replace($Staging, $Destination, [NullString]::Value)
    } else {
        [IO.File]::Move($Staging, $Destination)
    }
}

function Get-StatusLabels([string] $Catalog) {
    $labels = @{ 'status/online' = 'Online'; 'status/offline' = 'Offline' }
    if (Test-Path -LiteralPath $Catalog) {
        $bytes = [IO.File]::ReadAllBytes($Catalog)
        if ([BitConverter]::ToInt32($bytes, 0) -ne -1794895138) {
            throw "Unsupported messenger translation catalog at '$Catalog'."
        }
        $count = [BitConverter]::ToInt32($bytes, 8)
        $keys = [BitConverter]::ToInt32($bytes, 12)
        $translations = [BitConverter]::ToInt32($bytes, 16)
        $utf8 = [Text.Encoding]::UTF8
        for ($i = 0; $i -lt $count; $i++) {
            $keyEntry = $keys + 8 * $i
            $key = $utf8.GetString($bytes, [BitConverter]::ToInt32($bytes, $keyEntry + 4),
                [BitConverter]::ToInt32($bytes, $keyEntry))
            if ($labels.ContainsKey($key)) {
                $valueEntry = $translations + 8 * $i
                $value = $utf8.GetString($bytes, [BitConverter]::ToInt32($bytes, $valueEntry + 4),
                    [BitConverter]::ToInt32($bytes, $valueEntry))
                if ($value) { $labels[$key] = $value }
            }
        }
    }
    $labels
}

function Write-StatusTexture([string] $Text, [Drawing.Color] $Color, [string] $Path) {
    $bitmap = [Drawing.Bitmap]::new(320, 44)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $font = [Drawing.Font]::new('Segoe UI', 15, [Drawing.GraphicsUnit]::Pixel)
    $brush = [Drawing.SolidBrush]::new($Color)
    try {
        $graphics.ScaleTransform(2, 2)
        $graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
        $format = [Drawing.StringFormat]::GenericTypographic
        try {
            $graphics.DrawString($Text, $font, $brush, 0, 2, $format)
        } finally { $format.Dispose() }
        $bitmap.Save($Path, [Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $brush.Dispose()
        $font.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

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
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

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

    // The WoT mod loader requires ZIP method 0. .NET Framework emits method 8
    // even when ZipArchive is given CompressionLevel.NoCompression.
    public static void WritePackage(string path, string manifest, string modulePath, string bytecodePath,
        string onlineImage, string offlineImage, string onlinePlate, string offlinePlate)
    {
        byte[][] names = { Encoding.ASCII.GetBytes("meta.xml"), Encoding.ASCII.GetBytes(modulePath),
            Encoding.ASCII.GetBytes("res/gui/maps/icons/tankmate_signal/status-online.png"),
            Encoding.ASCII.GetBytes("res/gui/maps/icons/tankmate_signal/status-offline.png"),
            Encoding.ASCII.GetBytes("res/gui/maps/icons/tankmate_signal/tankmate-plate.dds"),
            Encoding.ASCII.GetBytes("res/gui/maps/icons/tankmate_signal/tankmate-plate-offline.dds") };
        byte[][] contents = { Encoding.UTF8.GetBytes(manifest), File.ReadAllBytes(bytecodePath),
            File.ReadAllBytes(onlineImage), File.ReadAllBytes(offlineImage),
            File.ReadAllBytes(onlinePlate), File.ReadAllBytes(offlinePlate) };
        uint[] offsets = new uint[names.Length];
        uint[] checksums = new uint[names.Length];
        using (var writer = new BinaryWriter(File.Open(path, FileMode.CreateNew)))
        {
            for (int i = 0; i < names.Length; ++i)
            {
                offsets[i] = (uint)writer.BaseStream.Position;
                checksums[i] = Crc32(contents[i]);
                writer.Write(0x04034b50u);
                WriteZipEntryHeader(writer, names[i], contents[i], checksums[i]);
                writer.Write(names[i]);
                writer.Write(contents[i]);
            }

            uint directoryOffset = (uint)writer.BaseStream.Position;
            for (int i = 0; i < names.Length; ++i)
            {
                writer.Write(0x02014b50u);
                writer.Write((ushort)20); // version made by
                WriteZipEntryHeader(writer, names[i], contents[i], checksums[i]);
                writer.Write((ushort)0); // comment length
                writer.Write((ushort)0); // starting disk
                writer.Write((ushort)0); // internal attributes
                writer.Write(0u); // external attributes
                writer.Write(offsets[i]);
                writer.Write(names[i]);
            }

            uint directorySize = (uint)writer.BaseStream.Position - directoryOffset;
            writer.Write(0x06054b50u);
            writer.Write(0u); // both disk numbers
            writer.Write((ushort)names.Length);
            writer.Write((ushort)names.Length);
            writer.Write(directorySize);
            writer.Write(directoryOffset);
            writer.Write((ushort)0); // archive comment length
        }
    }

    private static void WriteZipEntryHeader(BinaryWriter writer, byte[] name, byte[] contents, uint checksum)
    {
        writer.Write((ushort)20); // version needed
        writer.Write((ushort)0); // flags
        writer.Write((ushort)0); // stored compression method
        writer.Write((ushort)0); // DOS time
        writer.Write((ushort)33); // DOS date, January 1, 1980
        writer.Write(checksum);
        writer.Write((uint)contents.Length); // compressed size
        writer.Write((uint)contents.Length); // uncompressed size
        writer.Write((ushort)name.Length);
        writer.Write((ushort)0); // extra field length
    }

    private static uint Crc32(byte[] contents)
    {
        uint crc = uint.MaxValue;
        foreach (byte value in contents)
        {
            crc ^= value;
            for (int bit = 0; bit < 8; ++bit)
            {
                crc = (crc >> 1) ^ ((crc & 1u) != 0 ? 0xedb88320u : 0u);
            }
        }
        return ~crc;
    }
}
'@
}

$bytecode = [IO.Path]::GetTempFileName()
$onlineImage = [IO.Path]::GetTempFileName()
$offlineImage = [IO.Path]::GetTempFileName()
$buildStaging = "$package.$([guid]::NewGuid().ToString('N')).tmp"
$installStaging = "$destination.$([guid]::NewGuid().ToString('N')).tmp"
try {
    if ($PSVersionTable.PSEdition -eq 'Desktop') {
        Add-Type -AssemblyName System.Drawing
    } else {
        Add-Type -AssemblyName System.Drawing.Common
    }
    $labels = Get-StatusLabels (Join-Path $GameRoot 'res/text/lc_messages/messenger.mo')
    Write-StatusTexture $labels['status/online'] ([Drawing.Color]::FromArgb(156, 194, 128)) $onlineImage
    Write-StatusTexture $labels['status/offline'] ([Drawing.Color]::FromArgb(225, 109, 93)) $offlineImage

    $sourceLiteral = ConvertTo-PythonPathLiteral $source
    $bytecodeLiteral = ConvertTo-PythonPathLiteral $bytecode
    [WotProbePython]::Run($pythonDll, @"
import imp
import marshal

with open(u$sourceLiteral, 'rb') as source:
    code = compile(source.read().replace('\r\n', '\n'), '$moduleName.py', 'exec')
with open(u$bytecodeLiteral, 'wb') as bytecode:
    bytecode.write(imp.get_magic() + '\x00' * 4)
    marshal.dump(code, bytecode)
"@)

    $manifest = @'
<root>
    <id>local.friendpresence.probe</id>
    <version>0.1.21</version>
    <name>Tankmate Signal</name>
    <description>World of Tanks friend presence notifications</description>
</root>
'@
    [WotProbePython]::WritePackage($buildStaging, $manifest, "res/scripts/client/gui/mods/$moduleName.pyc",
        $bytecode, $onlineImage, $offlineImage,
        (Join-Path $probeRoot 'tankmate-plate.dds'), (Join-Path $probeRoot 'tankmate-plate-offline.dds'))

    Publish-Package $buildStaging $package
    [IO.File]::Copy($package, $installStaging)
    try {
        Publish-Package $installStaging $destination
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
    foreach ($temporaryFile in $bytecode, $onlineImage, $offlineImage, $buildStaging, $installStaging) {
        if (Test-Path -LiteralPath $temporaryFile) {
            Remove-Item -LiteralPath $temporaryFile
        }
    }
}
