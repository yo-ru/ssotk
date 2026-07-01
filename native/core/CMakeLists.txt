cmake_minimum_required(VERSION 3.20)
project(ssotk_core CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(ssotk_core STATIC
  src/vocab.cpp
  src/nebula.cpp
  src/text.cpp
)
target_include_directories(ssotk_core PUBLIC include)
target_compile_definitions(ssotk_core PRIVATE _CRT_SECURE_NO_WARNINGS)

include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG v2.13.6
)
FetchContent_MakeAvailable(pybind11)

pybind11_add_module(_core src/bindings.cpp)
target_link_libraries(_core PRIVATE ssotk_core)

# Static-link the C++ runtime so wheels don't depend on external DLLs.
if(WIN32 AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  target_link_options(_core PRIVATE -static)
  target_link_options(ssotk_core PRIVATE -static)
endif()

if(MSVC)
  set_property(TARGET _core PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")
  set_property(TARGET ssotk_core PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")
endif()

install(TARGETS _core
  LIBRARY DESTINATION ssotk
  RUNTIME DESTINATION ssotk
)
