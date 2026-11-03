# Fail closed: inspect SIDs and rights, never localized icacls text or account names.
$ErrorActionPreference = 'Stop'
# Python may inherit PS7's PSModulePath; Windows PowerShell must load its own system modules.
$env:PSModulePath = "$PSHOME\Modules"
try {
    $sidType = [System.Security.Principal.SecurityIdentifier]
    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    # Deploy user, SYSTEM, Administrators and the Windows servicing owner TrustedInstaller.
    $trusted = @($currentSid, 'S-1-5-18', 'S-1-5-32-544',
        'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')
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
        $deployProfileRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
        $insideProfile = $path.TrimEnd('\') -eq $deployProfileRoot.TrimEnd('\') -or
            $path.StartsWith($deployProfileRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
        $rights = $unsafeRights
        if (-not $insideProfile) {
            # Creating siblings is safe; replacing a protected child or changing its parent is not.
            $rights = [System.Security.AccessControl.FileSystemRights]::Delete -bor
                [System.Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
                [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
                [System.Security.AccessControl.FileSystemRights]::TakeOwnership
        }
        if ([System.IO.File]::Exists($path)) {
            # A read-only descriptor can acquire a byte-range lock; files must be private.
            $rights = $rights -bor [System.Security.AccessControl.FileSystemRights]::ReadData
        }
        foreach ($rule in $acl.GetAccessRules($true, $true, $sidType)) {
            if ($rule.IdentityReference.Value -eq 'S-1-3-4') {
                continue # OWNER RIGHTS is scoped to the object owner, verified as trusted above.
            }
            $inheritOnly = ($rule.PropagationFlags -band
                [System.Security.AccessControl.PropagationFlags]::InheritOnly) -ne 0
            if ($inheritOnly -and (-not $insideProfile -or $rule.IdentityReference.Value -eq 'S-1-3-0')) {
                continue # CREATOR OWNER applies only to descendants, whose owners are checked.
            }
            # Conservatively reject untrusted grants even when deny rules also exist.
            if ($rule.AccessControlType -eq 'Allow' -and
                $trusted -notcontains $rule.IdentityReference.Value -and
                ($rule.FileSystemRights -band $rights) -ne 0) {
                throw "Untrusted grant $($rule.IdentityReference.Value) ($($rule.FileSystemRights)) on lock path: $path"
            }
        }
    }
    Write-Output 'deployment-lock-acl-ok'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
