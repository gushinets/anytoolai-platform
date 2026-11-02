# Fail closed: inspect SIDs and rights, never localized icacls text or account names.
$ErrorActionPreference = 'Stop'
try {
    $sidType = [System.Security.Principal.SecurityIdentifier]
    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $trusted = @($currentSid, 'S-1-5-18', 'S-1-5-32-544') # User, SYSTEM, Administrators.
    $unsafeRights = [System.Security.AccessControl.FileSystemRights]::Write -bor
        [System.Security.AccessControl.FileSystemRights]::Delete -bor
        [System.Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
        [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [System.Security.AccessControl.FileSystemRights]::TakeOwnership
    $paths = ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd())
    foreach ($path in $paths) {
        $acl = Get-Acl -LiteralPath $path
        if ($trusted -notcontains $acl.GetOwner($sidType).Value) {
            throw "Untrusted lock path owner: $path"
        }
        $raw = [System.Security.AccessControl.RawSecurityDescriptor]::new(
            $acl.GetSecurityDescriptorBinaryForm(), 0)
        if ($null -eq $raw.DiscretionaryAcl) {
            throw "Unrestricted lock path DACL: $path"
        }
        foreach ($rule in $acl.GetAccessRules($true, $true, $sidType)) {
            # Conservatively reject untrusted write grants even when deny rules also exist.
            if ($rule.AccessControlType -eq 'Allow' -and
                $trusted -notcontains $rule.IdentityReference.Value -and
                ($rule.FileSystemRights -band $unsafeRights) -ne 0) {
                throw "Untrusted write/delete/ownership grant on lock path: $path"
            }
        }
    }
    Write-Output 'deployment-lock-acl-ok'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
