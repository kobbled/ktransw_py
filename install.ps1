function ktransw_install {
    Write-Output "Installing ktransw ..."

    #install python dependencies
    pip3 install -r "$PSScriptRoot\requirements.txt"

    #add ktransw to path
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";" + "$PSScriptRoot" + ";" + "$PSScriptRoot" + "\deps\gpp", "User");
    Write-Output "Added to Path: $PSScriptRoot"
    Write-Output "Added to Path: $PSScriptRoot\deps\gpp"

}

#python environment
$penv=$args[0]

if ($penv) {
    $pactivate = $penv + "\Scripts\Activate.ps1"
    Write-Output $pactivate
    Invoke-Expression -Command $pactivate
}

#update pip
pip3 install --upgrade pip

#run ktransw install
ktransw_install

if ($penv) {
    deactivate
}
