
####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was osqp-config.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)

####################################################################################

# CMake 2.6.4 and before didn't support ON in if() statements, so to ensure compatibility
# add some temp variables indicating the build options.
SET( OSQP_HAVE_SHARED_LIB ON )
SET( OSQP_HAVE_STATIC_LIB ON )

if( ${OSQP_HAVE_SHARED_LIB} )
    include( "${CMAKE_CURRENT_LIST_DIR}/osqp-targets.cmake" )
endif()

if( ${OSQP_HAVE_STATIC_LIB} )
    # Add the dependencies for the static library
    if( EXISTS "${CMAKE_CURRENT_LIST_DIR}/osqp-findAlgebraDependency.cmake" )
        include( "${CMAKE_CURRENT_LIST_DIR}/osqp-findAlgebraDependency.cmake" )
    endif()

    include( "${CMAKE_CURRENT_LIST_DIR}/osqpstatic-targets.cmake" )

    # Modify the language to include CXX if CUDA is included,
    # otherwise the linker stage will fail because CUDA uses some C++ elements.
    get_property( interface_languages
                  TARGET osqp::osqpstatic
                  PROPERTY IMPORTED_LINK_INTERFACE_LANGUAGES_NOCONFIG)

    foreach( LANG in ${interface_languages} )
        if( ${LANG} STREQUAL "CUDA" )
            set_target_properties( osqp::osqpstatic PROPERTIES
                                   IMPORTED_LINK_INTERFACE_LANGUAGES_NOCONFIG "${interface_languages};CXX" )
        endif()
    endforeach()
endif()
