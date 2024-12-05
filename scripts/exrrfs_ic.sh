#!/usr/bin/env bash
declare -rx PS4='+ $(basename ${BASH_SOURCE[0]:-${FUNCNAME[0]:-"Unknown"}})[${LINENO}]${id}: '
set -x
cpreq=${cpreq:-cpreq}
if [[ -z "${ENS_INDEX}" ]]; then
  prefix=${EXTRN_MDL_SOURCE:-IC_EXTRN_MDL_SOURCE_not_defined}
  ensindexstr=""
else
  prefix=${EXTRN_MDL_SOURCE:-ENS_IC_EXTRN_MDL_SOURCE_not_defined}
  ensindexstr="/mem${ENS_INDEX}"
fi
cd ${DATA}
#
# genereate the namelist on the fly
# required variables: init_case, start_time, end_time, nvertlevels, nsoillevels, nfglevles, nfgsoillevels,
# prefix, inerval_seconds, zeta_levels, decomp_file_prefix
#
init_case=7
start_time=$(date -d "${CDATE:0:8} ${CDATE:8:2}" +%Y-%m-%d_%H:%M:%S)
end_time=${start_time}

# set default zeta_levels file
zeta_levels=${FIXrrfs}/meshes/L65.txt

if [[ "${prefix}" == "RAP" || "${prefix}" == "HRRR" ]]; then
  nfglevels=51
  nfgsoillevels=9
  nsoillevels=9
  zeta_levels=${FIXrrfs}/meshes/L62.txt
elif  [[ "${prefix}" == "RRFS" ]]; then
  nfglevels=66
  nfgsoillevels=9
  nsoillevels=9
elif  [[ "${prefix}" == "GFS" ]]; then
  nfglevels=58
  nfgsoillevels=4
  nsoillevels=4
elif  [[ "${prefix}" == "GEFS" ]]; then
  nfglevels=32
  nfgsoillevels=4
  nsoillevels=4
fi

ztop=$(tail -1 ${zeta_levels})
nvertlevels=$(( $(wc -l < ${zeta_levels}) - 1 ))

interval_seconds=3600 # just a place holder as we use metatask to run lbc hour by hour
decomp_file_prefix="${MESH_NAME}.graph.info.part."
#
physics_suite=${PHYSICS_SUITE:-'PHYSICS_SUITE_not_defined'}
file_content=$(< ${PARMrrfs}/${physics_suite}/namelist.init_atmosphere) # read in all content
eval "echo \"${file_content}\"" > namelist.init_atmosphere

#
# generate the streams file on the fly 
# using sed as this file contains "filename_template='lbc.$Y-$M-$D_$h.$m.$s.nc'"
#
sed -e "s/@input_stream@/static.nc/" -e "s/@output_stream@/init.nc/" \
    -e "s/@lbc_interval@/3/" ${PARMrrfs}/streams.init_atmosphere > streams.init_atmosphere
#
#prepare fix files and ungrib files for init_atmosphere
#
ln -snf ${UMBRELLA_DATA}${ensindexstr}/ungrib_ic/${prefix}:${start_time:0:13} .
${cpreq} ${FIXrrfs}/meshes/${MESH_NAME}.static.nc static.nc
${cpreq} ${FIXrrfs}/graphinfo/${MESH_NAME}.graph.info.part.${NTASKS} .

# run init_atmosphere_model
source prep_step
${cpreq} ${EXECrrfs}/init_atmosphere_model.x .
${MPI_RUN_CMD} ./init_atmosphere_model.x
export err=$?; err_chk
if [[ ! -s './init.nc' ]]; then
  echo "FATAL ERROR: failed to generate init.nc"
  err_exit
fi

# copy init.nc to COMOUT
${cpreq} ${DATA}/init.nc ${COMOUT}${ensindexstr}/ic/
