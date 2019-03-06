@echo off

IF NOT EXIST build (
mkdir build
)

pushd build
rem cmake.exe -G "NMake Makefiles" -DDynamoRIO_DIR=%DYNAMORIO_HOME%\cmake -Dtest=ON ..
cmake -G "Visual Studio 15" -Dtest=1 -DDynamoRIO_DIR=%DYNAMORIO_HOME%\cmake ..
popd
