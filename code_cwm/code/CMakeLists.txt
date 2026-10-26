cmake_minimum_required(VERSION 3.15)
project(CWM LANGUAGES CXX)

# ------------------------------------------------------------------------------
# Compiler setup
# ------------------------------------------------------------------------------
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_compile_options(-Wall -Wextra -Wpedantic)

include_directories(${CMAKE_SOURCE_DIR}/lib)

# ------------------------------------------------------------------------------
# External dependencies (fetched at configure time)
# ------------------------------------------------------------------------------
include(FetchContent)

FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
    GIT_SHALLOW TRUE
)
set(JSON_BuildTests OFF CACHE INTERNAL "")
set(JSON_Install OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(nlohmann_json)

FetchContent_Declare(
    robin_hood
    GIT_REPOSITORY https://github.com/martinus/robin-hood-hashing.git
    GIT_TAG 3.11.5
    GIT_SHALLOW TRUE
)
set(RH_STANDALONE_PROJECT OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(robin_hood)

# Treat fetched dependency headers as system headers so their warnings are silenced.
foreach(_dep nlohmann_json robin_hood)
    if(TARGET ${_dep})
        get_target_property(_dep_inc ${_dep} INTERFACE_INCLUDE_DIRECTORIES)
        if(_dep_inc)
            set_target_properties(${_dep} PROPERTIES
                INTERFACE_SYSTEM_INCLUDE_DIRECTORIES "${_dep_inc}")
        endif()
    endif()
endforeach()

# ------------------------------------------------------------------------------
# Release optimization flags (shared by every project target)
# ------------------------------------------------------------------------------
add_library(project_release_flags INTERFACE)
target_compile_options(project_release_flags INTERFACE
    $<$<AND:$<OR:$<CXX_COMPILER_ID:GNU>,$<CXX_COMPILER_ID:Clang>,$<CXX_COMPILER_ID:AppleClang>>,$<CONFIG:Release>>:
        -O3 -DNDEBUG -march=native -mtune=native
        -flto -ffast-math -fassociative-math
        -fomit-frame-pointer -fno-math-errno
        -fno-trapping-math -fno-signed-zeros
    >
    # -frename-registers is GCC-only; Clang/AppleClang reject it with a warning.
    $<$<AND:$<CXX_COMPILER_ID:GNU>,$<CONFIG:Release>>:
        -frename-registers
    >
    $<$<AND:$<CXX_COMPILER_ID:MSVC>,$<CONFIG:Release>>:
        /O2 /GL /DNDEBUG /arch:AVX2
    >
)

include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_supported OUTPUT ipo_msg)
if(NOT ipo_supported)
    message(WARNING "IPO not supported: ${ipo_msg}")
endif()

function(apply_project_build_settings target)
    target_link_libraries(${target} PRIVATE project_release_flags)
    if(ipo_supported)
        set_property(TARGET ${target} PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
    endif()
endfunction()

# ------------------------------------------------------------------------------
# Library: CaWoSchedLib
# ------------------------------------------------------------------------------
file(GLOB_RECURSE LIB_SOURCES "${CMAKE_SOURCE_DIR}/lib/*.cpp")

add_library(CaWoSchedLib STATIC ${LIB_SOURCES})
target_link_libraries(CaWoSchedLib PUBLIC
    nlohmann_json::nlohmann_json
    robin_hood::robin_hood
)
apply_project_build_settings(CaWoSchedLib)

# ------------------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------------------
set(APP_SOURCES
    app/main.cpp
    app/heft_mapping.cpp
    app/setup_for_CaWoSched.cpp
    app/solve_cwm.cpp
)

foreach(src ${APP_SOURCES})
    get_filename_component(exec_name ${src} NAME_WE)
    add_executable(${exec_name} ${src})
    target_link_libraries(${exec_name} PRIVATE CaWoSchedLib)
    apply_project_build_settings(${exec_name})
endforeach()

# ------------------------------------------------------------------------------
# Tests (using GoogleTest)
# ------------------------------------------------------------------------------
#
#enable_testing()
#
#FetchContent_Declare(
#    googletest
#    URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
#)
#FetchContent_MakeAvailable(googletest)
#
#file(GLOB TEST_SOURCES "${CMAKE_SOURCE_DIR}/tests/*.cpp")
#
#add_executable(CaWoSchedTests ${TEST_SOURCES})
#target_link_libraries(CaWoSchedTests PRIVATE CaWoSchedLib GTest::gtest_main)
#
#include(GoogleTest)
#gtest_discover_tests(CaWoSchedTests)

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
message(STATUS "")
message(STATUS "================ Build Configuration ================")
message(STATUS "Project Name:        ${PROJECT_NAME}")
message(STATUS "C++ Standard:        ${CMAKE_CXX_STANDARD}")
message(STATUS "Build Type:          ${CMAKE_BUILD_TYPE}")
message(STATUS "IPO Supported:       ${ipo_supported}")
message(STATUS "Source Directory:    ${CMAKE_SOURCE_DIR}")
message(STATUS "=====================================================")
message(STATUS "")
