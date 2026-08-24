#!/usr/bin/env bash
# shellcheck disable=SC2154,SC1091
declare -rx PS4='+${SECONDS}s $(basename ${BASH_SOURCE[0]:-${FUNCNAME[0]:-"Unknown"}})[${LINENO}]: '
set -x

cpreq=${cpreq:-cpreq}

#-----------------------------------------------------------------------
# Enter run directory
#-----------------------------------------------------------------------
cd "${DATA}" || exit 1

#-----------------------------------------------------------------------
# Check whether this is a recenter cycle
#-----------------------------------------------------------------------
if [[ " ${RECENTER_CYCS:-99} " != *" ${cyc} "* ]]; then
  echo "INFO: No recentering at this cycle - ${cyc}"
  exit 0
fi

#-----------------------------------------------------------------------
# Configuration
#-----------------------------------------------------------------------
export ENS_SIZE="${ENS_SIZE:-30}"
#export PERTURB_VARS="${PERTURB_VARS:-qv}"
#export NONNEGATIVE_VARS="${NONNEGATIVE_VARS:-qv}"
export PERTURB_VARS="rho qv theta u"
export NONNEGATIVE_VARS="qv"
export CLIP_NEGATIVE="${CLIP_NEGATIVE:-FALSE}"

echo "============================================================"
echo "RRFS CONTROL-CENTERED ENSEMBLE"
echo "============================================================"
echo "ENS_SIZE          = ${ENS_SIZE}"
echo "PERTURB_VARS      = ${PERTURB_VARS}"
echo "NONNEGATIVE_VARS  = ${NONNEGATIVE_VARS}"
echo "CLIP_NEGATIVE     = ${CLIP_NEGATIVE}"
echo "============================================================"

#-----------------------------------------------------------------------
# Verify ensemble input
#
if [[ -s "${UMBRELLA_PREP_IC_DATA}/mem001/init.nc" ]]; then
  initial_file='init.nc'
else
  initial_file='mpasout.nc'
fi

for i in $(seq -w 001 "${ENS_SIZE}"); do
  member_file="${UMBRELLA_PREP_IC_DATA}/mem${i}/${initial_file}"
    if [[ ! -s "${member_file}" ]]; then
        echo "ERROR: Missing ensemble member:"
        echo "  ${member_file}"
        exit 1
    fi
done

#-----------------------------------------------------------------------
# Determine control file
#-----------------------------------------------------------------------
controlfile_init="${UMBRELLA_PREP_CONTROL_IC_DATA}/init.nc"
controlfile_mpasout="${UMBRELLA_PREP_CONTROL_IC_DATA}/mpasout.nc"
if [[ -s "${controlfile_init}" ]] ; then
  controlfile="${controlfile_init}"
elif [[ -s "${controlfile_mpasout}" ]] ; then
  controlfile="${controlfile_mpasout}"
else
  echo "! Warning: Cannot find control background: ${controlfile_init} or ${controlfile_mpasout}"
  exit 0
fi


echo "Control file: ${controlfile}"

#-----------------------------------------------------------------------
# Run Python control-centered ensemble generator
#-----------------------------------------------------------------------

export pgm="create_control_centered_ensemble.py"

python3 "${HOMErrfs}/ush/${pgm}"

export err=$?
err_chk

#-----------------------------------------------------------------------
# Verify that all output member files still exist
#-----------------------------------------------------------------------
for i in $(seq -w 001 "${ENS_SIZE}"); do
  member_file="${UMBRELLA_PREP_IC_DATA}/mem${i}/init.nc"
  if [[ ! -s "${member_file}" ]]; then
    echo "ERROR: Output member missing after recenter:"
    echo "  ${member_file}"
    exit 1
  fi
done

echo "============================================================"
echo "RRFS CONTROL-CENTERED ENSEMBLE COMPLETED"
echo "============================================================"

exit 0
