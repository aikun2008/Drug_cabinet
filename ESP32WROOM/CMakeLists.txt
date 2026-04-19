# For more information about build system see
# https://docs.espressif.com/projects/esp-idf/en/latest/api-guides/build-system.html
# The following five lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

# 设置使用自定义分区表
set(PARTITION_TABLE_CUSTOM_FILENAME "partitions.csv")
set(PARTITION_TABLE_TYPE "custom")

# 从config.h文件中提取版本号
file(READ ${CMAKE_SOURCE_DIR}/main/config.h CONFIG_H_CONTENTS)
string(REGEX MATCH "#define FIRMWARE_VERSION \"([0-9.]+)\"" _ ${CONFIG_H_CONTENTS})
set(FIRMWARE_VERSION ${CMAKE_MATCH_1})

# 设置项目名称包含版本号
set(PROJECT_NAME_WITH_VERSION "mqtt_v${FIRMWARE_VERSION}")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(${PROJECT_NAME_WITH_VERSION})

