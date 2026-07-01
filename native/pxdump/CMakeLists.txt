cmake_minimum_required(VERSION 3.20)
project(pxdump CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
  minhook
  GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
  GIT_TAG master
)
FetchContent_MakeAvailable(minhook)

add_library(pxdump SHARED src/dllmain.cpp)
target_link_libraries(pxdump PRIVATE minhook)
target_compile_definitions(pxdump PRIVATE _CRT_SECURE_NO_WARNINGS)
