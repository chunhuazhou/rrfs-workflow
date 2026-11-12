#!/usr/bin/env bash
# shellcheck disable=all
declare -rx PS4='+${SECONDS}s $(basename ${BASH_SOURCE[0]:-${FUNCNAME[0]:-"Unknown"}})[${LINENO}]: '
set -x
date
#
export HOMErrfs=${HOMErrfs} #comes from the workflow at runtime
export EXECrrfs=${EXECrrfs:-${HOMErrfs}/exec}
export FIXrrfs=${FIXrrfs:-${HOMErrfs}/fix}
export PARMrrfs=${PARMrrfs:-${HOMErrfs}/parm}
export USHrrfs=${USHrrfs:-${HOMErrfs}/ush}
#
pygrafdir="${HOMErrfs}/workflow/sideload/pygraf"
image_list="${pygrafdir}/image_lists/regional_mpas_subset.yml"
file_tmpl="${NET}.t${cyc}z.prslev.f{FCST_TIME:03d}.${UPP_DOMAIN}grib2"
model=${GRAPHICS_MODEL:-${NET}}
ntasks=${NTASKS:-12}
grib2_dir="${COMOUT}/upp/det"
tile=${TILE:-'full'}
workdir="${COMOUT}/graphics/${WGF}/${tile}"
zipdir="${COMOUT}/nclprd"
rm -rf "${workdir}"
mkdir -p "${workdir}"
cd "${pygrafdir}" || exit 1
#
# find forecst length for this cycle
#
fcst_len_hrs_cycles=${FCST_LEN_HRS_CYCLES:-"01 01"}
fcst_len_hrs_thiscyc=$( "${USHrrfs}/find_fcst_length.sh"  "${fcst_len_hrs_cycles}"  "${cyc}" )
echo "forecast length for this cycle is ${fcst_len_hrs_thiscyc}"
fhr1=${FHR1:-0}
fhr2=${fcst_len_hrs_thiscyc}
wait_minutes=${WAIT_MINUTES:-180}
#
# generate the graphics
#
graphics_type="maps"
extra_args=()
if [[ "${DO_ENSEMBLE^^}" == "TRUE" ]]; then
  graphics_type="enspanel"
  image_list="${pygrafdir}/image_lists/rrfs_ens.yml"
  [[ ! -f "${image_list}" ]] && image_list="${pygrafdir}/image_lists/regional_mpas_subset.yml"
  grib2_dir="${COMOUT}/upp"
  file_tmpl="${WGF:-enkf}/mem{mem:03d}/${NET}.t${cyc}z.prslev.f{FCST_TIME:03d}.${UPP_DOMAIN}grib2"
  ens_size=${GRAPHICS_ENS_SIZE:-${ENS_SIZE:-10}}
  if (( ens_size > 10 )); then
    ens_size=10
  fi
  extra_args+=(--ens_size "${ens_size}")

  # Ensure mem000 points to det so upstream pygraf finds member 0 directly
  [[ -d "${COMOUT}/upp/det" && ! -e "${COMOUT}/upp/${WGF:-enkf}/mem000" ]] && ln -snf "${COMOUT}/upp/det" "${COMOUT}/upp/${WGF:-enkf}/mem000"

  # Resolve MRMS composite reflectivity observation file matching the forecast valid time
  if [[ -n "${OBSPATH_MRMS_COMPOSITE}" ]]; then
    vtime=$(python3 -c "import datetime; print((datetime.datetime.strptime('${CDATE}', '%Y%m%d%H') + datetime.timedelta(hours=${fhr1})).strftime('%Y%m%d-%H'))" 2>/dev/null)
    obs_file=""
    if [[ -n "${vtime}" ]]; then
      vdate="${vtime%%-*}"
      obs_file=$(ls ${OBSPATH_MRMS_COMPOSITE}/*MergedReflectivityQCComposite*${vtime}*.grib2* \
                    ${OBSPATH_MRMS_COMPOSITE}/${vdate}/*MergedReflectivityQCComposite*${vtime}*.grib2* 2>/dev/null | head -n 1)
    fi
    if [[ -f "${obs_file}" ]]; then
      echo "Found MRMS observation file matching valid time ${vtime}: ${obs_file}"
      extra_args+=(--obs_file_path "${obs_file}")
    elif [[ -f "${OBSPATH_MRMS_COMPOSITE}" ]]; then
      extra_args+=(--obs_file_path "${OBSPATH_MRMS_COMPOSITE}")
    else
      echo "Notice: No MRMS observation file found matching valid time ${vtime} in ${OBSPATH_MRMS_COMPOSITE}"
    fi
  fi
fi

if [[ "${GRAPHICS_ZIP^^}" == "TRUE" ]]; then
  mkdir -p "${zipdir}"
  extra_args+=(-z "${zipdir}")
fi

python create_graphics.py "${graphics_type}" --all_leads -d "${grib2_dir}" -f "${fhr1}" "${fhr2}" --file_type prs --file_tmpl "${file_tmpl}" -m "${model}" \
    --images "${image_list}" hourly -n "${ntasks}" -o "${workdir}" -s "${CDATE}" --tiles "${tile}" -w "${wait_minutes}" "${extra_args[@]}"
export err=$?; err_chk
exit 0
