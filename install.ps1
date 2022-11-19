function ktransw_install {

    #install python dependencies
    python -m pip install -r requirements.txt

    #add ktransw to path
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";" + "$PWD" + ";" + "$PWD" + "\deps\gpp", "User");
    Write-Output "Added to Path: $PWD"
    Write-Output "Added to Path: $PWD\deps\gpp"

    }

#update pip
python -m pip install --upgrade pip
#run install
ktransw_install
