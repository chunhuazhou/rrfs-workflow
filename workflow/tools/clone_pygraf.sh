#!/bin/bash
# shellcheck disable=all
pygraf_repo=${PYGRAF_REPO:-"https://github.com/chunhuazhou/pygraf.git"}
pygraf_branch=${PYGRAF_BRANCH:-"fix-enspanel-mpas-det-obs"}
pygraf_hash=${PYGRAF_HASH:-""}
#
toolsdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "${toolsdir}/../sideload"
if [[ -d pygraf ]]; then
  echo "pygraf/ already cloned, no actions."
else
  which git-lfs 2>/dev/null ||  module load git-lfs
  set -x
  if [[ -n "${pygraf_hash}" ]]; then
    GIT_LFS_SKIP_SMUDGE=1 git clone "${pygraf_repo}" pygraf
    cd pygraf
    git checkout "${pygraf_hash}" &> /dev/null
  else
    GIT_LFS_SKIP_SMUDGE=1 git clone -b "${pygraf_branch}" "${pygraf_repo}" pygraf
  fi
fi
