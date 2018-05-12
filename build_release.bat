git rev-parse HEAD > git_rev.txt
set /p git_rev=<git_rev.txt
del git_rev.txt

set "release=releases\release-%git_rev:~0,5%"

mkdir %release%
mkdir %release%\manage_packages
mkdir %release%\work


REM pyinstaller-generated EXEs break because of ifstools using Pool apparently
REM pyinstaller manage_packages.spec
REM copy /Y dist\manage_packages.exe %release%\manage_packages
xcopy /Y /E /I tools %release%\manage_packages\tools
copy /Y manage_packages.py %release%\manage_packages
copy /Y manage_packages.bat %release%\manage_packages
copy /Y requirements-manage_packages.txt %release%\manage_packages
copy /Y tmpfile.py %release%\manage_packages\tools
copy /Y ifs.py %release%\manage_packages\tools
rmdir /S /Q %release%\manage_packages\__pycache__


REM Prepare actual work tools for custom charters
copy /Y adpcmwavetool.exe %release%\work
copy /Y xa.exe %release%\work

xcopy /Y /E /I plugins %release%\work\plugins
copy /Y adpcmwave.py %release%\work
copy /Y audio.py %release%\work
copy /Y create_gst.py %release%\work
copy /Y eamxml.py %release%\work
copy /Y event.py %release%\work
copy /Y helper.py %release%\work
copy /Y ifs.py %release%\work
copy /Y manage_packages.py %release%\work
copy /Y mdb.py %release%\work
copy /Y seqtool.py %release%\work
copy /Y tmpfile.py %release%\work
copy /Y vas3tool.py %release%\work
copy /Y wavbintool.py %release%\work
copy /Y wavfile.py %release%\work
copy /Y requirements.txt %release%\work
rmdir /S /Q %release%\work\plugins\__pycache__
rmdir /S /Q %release%\work\__pycache__
