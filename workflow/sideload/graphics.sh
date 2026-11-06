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
tile=${TILE:-'full'}
model=${GRAPHICS_MODEL:-${NET}}
ntasks=${NTASKS:-12}
zipdir="${COMOUT}/nclprd"
wait_minutes=${WAIT_MINUTES:-180}

# Determine if running for ensemble or deterministic
is_ensemble=false
if [[ "${DO_ENSEMBLE^^}" == "TRUE" || "${WGF,,}" == "enkf" || "${WGF,,}" == "ens" || "${GRAPHICS_TYPE,,}" == "enspanel" ]]; then
  is_ensemble=true
fi

if [[ -n "${GRAPHICS_TYPE}" ]]; then
  graphics_type="${GRAPHICS_TYPE}"
elif [[ "${is_ensemble}" == "true" ]]; then
  graphics_type="enspanel"
else
  graphics_type="maps"
fi

if [[ "${is_ensemble}" == "true" ]]; then
  image_list="${GRAPHICS_IMAGE_LIST:-"${pygrafdir}/image_lists/rrfs_ens.yml"}"
  [[ ! -f "${image_list}" ]] && image_list="${pygrafdir}/image_lists/regional_mpas_subset.yml"
  grib2_dir="${GRAPHICS_GRIB2_DIR:-"${COMOUT}/upp"}"
  file_tmpl="${GRAPHICS_FILE_TMPL:-"${WGF:-enkf}/mem{mem:03d}/${NET}.t${cyc}z.prslev.f{FCST_TIME:03d}.${UPP_DOMAIN}grib2"}"
else
  image_list="${GRAPHICS_IMAGE_LIST:-"${pygrafdir}/image_lists/regional_mpas_subset.yml"}"
  grib2_dir="${GRAPHICS_GRIB2_DIR:-"${COMOUT}/upp/det"}"
  file_tmpl="${GRAPHICS_FILE_TMPL:-"${NET}.t${cyc}z.prslev.f0{FCST_TIME:02d}.${UPP_DOMAIN}grib2"}"
fi

workdir="${COMOUT}/graphics/${WGF}/${tile}"
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

extra_args=()
if [[ "${is_ensemble}" == "true" ]]; then
  ens_size=${ENS_SIZE:-10}
  extra_args+=(--ens_size "${ens_size}")

  if [[ -n "${GRAPHICS_HAS_DET}" ]]; then
    if [[ "${GRAPHICS_HAS_DET^^}" == "TRUE" ]]; then
      extra_args+=(--has_det)
    else
      extra_args+=(--no_det)
    fi
  fi

  if [[ -n "${GRAPHICS_DET_TMPL}" ]]; then
    extra_args+=(--det_tmpl "${GRAPHICS_DET_TMPL}")
  fi

  obs_file="${GRAPHICS_OBS_FILE:-}"
  if [[ -z "${obs_file}" ]]; then
    cand_obs=(
      "${COMOUT}/ioda_mrms_refl/${WGF}/mrms_radr.t${cyc}z.grib2"
      "${COMOUT}/ioda_mrms_refl/det/mrms_radr.t${cyc}z.grib2"
      "${COMOUT}/obs/mrms_radr.t${cyc}z.grib2"
      "${OBSPATH_NSSLMOSAIC:-/dev/null}/${PDY}/mrms_radr.t${cyc}z.grib2"
    )
    for co in "${cand_obs[@]}"; do
      if [[ -f "${co}" ]]; then
        obs_file="${co}"
        break
      fi
    done
  fi

  # If not found, search OBSPATH_NSSLMOSAIC for the file closest to cycle valid time
  if [[ -z "${obs_file}" && -n "${OBSPATH_NSSLMOSAIC}" && -d "${OBSPATH_NSSLMOSAIC}" ]]; then
    obs_file=$(python3 -c '
import os, sys, glob, re
from datetime import datetime

obspath = os.getenv("OBSPATH_NSSLMOSAIC", "")
cdate_str = os.getenv("CDATE", "")
if not (obspath and cdate_str):
    sys.exit(0)

try:
    target_dt = datetime.strptime(cdate_str[:10], "%Y%m%d%H")
except Exception:
    sys.exit(0)

pdy = cdate_str[:8]
search_dirs = [obspath, os.path.join(obspath, pdy)]
candidates = []
for sdir in search_dirs:
    if os.path.isdir(sdir):
        for pattern in (f"*{pdy}*.grib2", f"*{pdy}*.grib2.gz"):
            candidates.extend(glob.glob(os.path.join(sdir, pattern)))

best_file = None
best_diff = float("inf")
ts_pattern = re.compile(r"(\d{8})[-_](\d{6})")

for f in set(candidates):
    m = ts_pattern.search(os.path.basename(f))
    if m:
        try:
            fdt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            diff = abs((fdt - target_dt).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_file = f
        except Exception:
            continue

if best_file:
    print(best_file)
')
  fi

  if [[ -n "${obs_file}" && -f "${obs_file}" ]]; then
    extra_args+=(--obs_file_path "${obs_file}")
  fi
fi

if [[ "${GRAPHICS_ZIP^^}" == "TRUE" ]]; then
  mkdir -p "${zipdir}"
  extra_args+=(-z "${zipdir}")
fi

python create_graphics.py "${graphics_type}" --all_leads \
    -d "${grib2_dir}" \
    -f "${fhr1}" "${fhr2}" \
    --file_type prs \
    --file_tmpl "${file_tmpl}" \
    -m "${model}" \
    --images "${image_list}" "${GRAPHICS_IMAGE_SECTION:-hourly}" \
    -n "${ntasks}" \
    -o "${workdir}" \
    -s "${CDATE}" \
    --tiles ${tile} \
    -w "${wait_minutes}" \
    "${extra_args[@]}"
export err=$?; err_chk
exit 0
