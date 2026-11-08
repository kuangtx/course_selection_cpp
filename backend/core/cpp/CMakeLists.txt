cmake_minimum_required(VERSION 3.18)
project(course_selection_planner LANGUAGES CXX)

add_library(course_selection_planner STATIC planner.cpp)
target_include_directories(course_selection_planner PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(course_selection_planner PUBLIC cxx_std_17)
set_target_properties(course_selection_planner PROPERTIES
  CXX_EXTENSIONS OFF
  POSITION_INDEPENDENT_CODE ON
)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(course_selection_planner PRIVATE -O3 -Wall -Wextra -Wpedantic)
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_planner bindings.cpp)
target_link_libraries(_planner PRIVATE course_selection_planner)
target_compile_features(_planner PRIVATE cxx_std_17)
set_target_properties(_planner PROPERTIES CXX_EXTENSIONS OFF)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(_planner PRIVATE -Wall -Wextra -Wpedantic)
endif()
