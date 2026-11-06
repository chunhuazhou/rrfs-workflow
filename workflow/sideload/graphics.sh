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
file_tmpl="${NET}.t${cyc}z.prslev.f0{FCST_TIME:02d}.${UPP_DOMAIN}grib2"
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
fhr1=0
fhr2=${fcst_len_hrs_thiscyc}
wait_minutes=${WAIT_MINUTES:-180}
#
# generate the graphics
#
graphics_type="maps"
extra_args=()
if [[ "${DO_ENSEMBLE^^}" == "TRUE" || "${WGF,,}" == "enkf" || "${WGF,,}" == "ens" ]]; then
  graphics_type="enspanel"
  image_list="${pygrafdir}/image_lists/rrfs_ens.yml"
  [[ ! -f "${image_list}" ]] && image_list="${pygrafdir}/image_lists/regional_mpas_subset.yml"
  grib2_dir="${COMOUT}/upp"
  file_tmpl="${WGF:-enkf}/mem{mem:03d}/${NET}.t${cyc}z.prslev.f{FCST_TIME:03d}.${UPP_DOMAIN}grib2"
  ens_size=${ENS_SIZE:-10}
  extra_args+=(--ens_size "${ens_size}")

  # Search OBSPATH_NSSLMOSAIC for the MRMS file closest to cycle valid time
  if [[ -n "${OBSPATH_NSSLMOSAIC}" && -d "${OBSPATH_NSSLMOSAIC}" ]]; then
    obs_file=$(python3 -c '
import os, sys, glob, re
from datetime import datetime

obspath = os.getenv("OBSPATH_NSSLMOSAIC", "")
cdate_str = os.getenv("CDATE", "")
if obspath and cdate_str:
    try:
        target_dt = datetime.strptime(cdate_str[:10], "%Y%m%d%H")
        pdy = cdate_str[:8]
        candidates = []
        for sdir in [obspath, os.path.join(obspath, pdy)]:
            if os.path.isdir(sdir):
                candidates.extend(glob.glob(os.path.join(sdir, f"*{pdy}*.grib2*")))
        best_file, best_diff = None, float("inf")
        ts_pattern = re.compile(r"(\d{8})[-_](\d{6})")
        for f in set(candidates):
            m = ts_pattern.search(os.path.basename(f))
            if m:
                try:
                    fdt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
                    diff = abs((fdt - target_dt).total_seconds())
                    if diff < best_diff:
                        best_diff, best_file = diff, f
                except Exception:
                    continue
        if best_file:
            print(best_file)
    except Exception:
        pass
')
    if [[ -n "${obs_file}" && -f "${obs_file}" ]]; then
      extra_args+=(--obs_file_path "${obs_file}")
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
