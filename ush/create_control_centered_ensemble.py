#!/usr/bin/env python3
"""
Create a control-centered ensemble by replacing selected variables
in each ensemble member with:

    X_new(m) = X_control + [X_member(m) - X_ensemble_mean]

All variables not listed in PERTURB_VARS are taken directly from
the control file.

The original member files are replaced in-place only after the
new file has been successfully written.

Environment variables:

    UMBRELLA_PREP_IC_DATA
        Directory containing memXXX/init.nc

    UMBRELLA_PREP_CONTROL_IC_DATA
        Directory containing det/mpasout.nc

    ENS_SIZE
        Ensemble size, default 30

    PERTURB_VARS
        Comma- or whitespace-separated list of variables to perturb.
        Example:
            qv
        or:
            qv,u,v,theta

    NONNEGATIVE_VARS
        Variables that must be >= 0.
        Example:
            qv

    CLIP_NEGATIVE
        TRUE  -> clip negative values to zero
        FALSE -> abort if negative values are found
"""


import os
import shutil
import sys
from pathlib import Path

import numpy as np
import xarray as xr


# ======================================================================
# Helpers
# ======================================================================

def parse_varlist(value):
    """Parse comma/whitespace-separated variable list."""
    if not value:
        return []

    value = value.replace(",", " ")

    return [
        item.strip()
        for item in value.split()
        if item.strip()
    ]


def check_dimensions(member_ds, control_ds, var, member_name):
    """Check that a perturbed variable is compatible with the control."""

    if var not in member_ds:
        raise RuntimeError(
            f"{member_name}: variable '{var}' is not present "
            f"in the ensemble member"
        )

    if var not in control_ds:
        raise RuntimeError(
            f"Control: variable '{var}' is not present "
            f"in the control file"
        )

    member_dims = member_ds[var].dims
    control_dims = control_ds[var].dims

    if member_dims != control_dims:
        raise RuntimeError(
            f"{member_name}: dimension mismatch for '{var}':\n"
            f"  member : {member_dims}\n"
            f"  control: {control_dims}"
        )

    if member_ds[var].shape != control_ds[var].shape:
        raise RuntimeError(
            f"{member_name}: shape mismatch for '{var}':\n"
            f"  member : {member_ds[var].shape}\n"
            f"  control: {control_ds[var].shape}"
        )


def finite_min_max(da):
    """Return finite minimum and maximum."""

    data = da.values

    finite = np.isfinite(data)

    if not np.any(finite):
        return np.nan, np.nan

    return (
        float(np.min(data[finite])),
        float(np.max(data[finite])),
    )


# ======================================================================
# Configuration
# ======================================================================

ENS_SIZE = int(
    os.environ.get("ENS_SIZE", "30")
)

PERTURB_VARS = parse_varlist(
    os.environ.get("PERTURB_VARS", "qv")
)

NONNEGATIVE_VARS = parse_varlist(
    os.environ.get("NONNEGATIVE_VARS", "qv")
)

CLIP_NEGATIVE = (
    os.environ.get("CLIP_NEGATIVE", "FALSE").upper()
    == "TRUE"
)

PREP_IC_DATA = Path(
    os.environ["UMBRELLA_PREP_IC_DATA"]
)

PREP_CONTROL_DATA = Path(
    os.environ["UMBRELLA_PREP_CONTROL_IC_DATA"]
)

DATA = Path(
    os.environ["DATA"]
)

print("=" * 72)
print("CONTROL-CENTERED ENSEMBLE")
print("=" * 72)
print(f"ENS_SIZE          = {ENS_SIZE}")
print(f"PERTURB_VARS      = {PERTURB_VARS}")
print(f"NONNEGATIVE_VARS  = {NONNEGATIVE_VARS}")
print(f"CLIP_NEGATIVE     = {CLIP_NEGATIVE}")
print(f"PREP_IC_DATA      = {PREP_IC_DATA}")
print(f"CONTROL_DATA      = {PREP_CONTROL_DATA}")
print(f"DATA              = {DATA}")
print("=" * 72)


if not PERTURB_VARS:
    raise RuntimeError(
        "PERTURB_VARS is empty. At least one variable must be specified."
    )


# ======================================================================
# Locate input ensemble
# ======================================================================

member_files = []

for member_number in range(1, ENS_SIZE + 1):

    member = f"mem{member_number:03d}"

    filename = (
        PREP_IC_DATA
        / member
        / "init.nc"
    )

    if not filename.is_file():
        raise RuntimeError(
            f"Missing ensemble file:\n  {filename}"
        )

    member_files.append(filename)


# ======================================================================
# Locate control
# ======================================================================

control_file = (
    PREP_CONTROL_DATA
    / "mpasout.nc"
)

if not control_file.is_file():

    # Keep compatibility with the possibility that the control
    # preparation produces init.nc instead.
    alternate_control = (
        PREP_CONTROL_DATA
        / "init.nc"
    )

    if alternate_control.is_file():
        control_file = alternate_control
    else:
        raise RuntimeError(
            "Cannot find control file:\n"
            f"  {PREP_CONTROL_DATA / 'mpasout.nc'}\n"
            f"  {alternate_control}"
        )


print(f"Control file: {control_file}")


# ======================================================================
# Open control
# ======================================================================

print("Opening control file...")

control = xr.open_dataset(
    control_file,
    engine="netcdf4",
)


# ======================================================================
# Open original ensemble members
#
# IMPORTANT:
# Only PERTURB_VARS are loaded. We do not need complete ensemble
# members to calculate the perturbations.
# ======================================================================

print("Opening ensemble members...")

member_datasets = []

for number, filename in enumerate(member_files, start=1):

    member = f"mem{number:03d}"

    print(f"  {member}: {filename}")

    ds = xr.open_dataset(
        filename,
        engine="netcdf4",
    )

    for var in PERTURB_VARS:
        check_dimensions(
            ds,
            control,
            var,
            member,
        )

    member_datasets.append(ds)


# ======================================================================
# Verify that all ensemble members have compatible dimensions
# ======================================================================

print("Checking ensemble dimensions...")

for var in PERTURB_VARS:

    reference = member_datasets[0][var]

    for number, ds in enumerate(
        member_datasets[1:],
        start=2,
    ):

        member = f"mem{number:03d}"

        if ds[var].dims != reference.dims:
            raise RuntimeError(
                f"{member}: dimension mismatch for '{var}'"
            )

        if ds[var].shape != reference.shape:
            raise RuntimeError(
                f"{member}: shape mismatch for '{var}'"
            )


# ======================================================================
# Calculate ensemble means
# ======================================================================

print("Calculating ensemble means...")

ensemble_mean = {}

for var in PERTURB_VARS:

    print(f"  mean({var})")

    # Use xarray directly rather than loading the entire 30-member
    # ensemble into a separate array.
    stack = xr.concat(
        [
            ds[var]
            for ds in member_datasets
        ],
        dim="ensemble_member",
    )

    ensemble_mean[var] = stack.mean(
        dim="ensemble_member"
    )

    # Force the mean to be computed while all original member files
    # are still untouched.
    ensemble_mean[var].load()

    del stack


# ======================================================================
# Create new members
# ======================================================================

for number, (member_file, member_ds) in enumerate(
    zip(member_files, member_datasets),
    start=1,
):

    member = f"mem{number:03d}"

    print()
    print("=" * 72)
    print(f"Creating {member}")
    print("=" * 72)

    # --------------------------------------------------------------
    # Start with the COMPLETE control state.
    # --------------------------------------------------------------

    new_member = control.copy(deep=False)

    # --------------------------------------------------------------
    # Apply perturbations to selected variables.
    # --------------------------------------------------------------

    for var in PERTURB_VARS:

        print(f"Applying perturbation: {var}")

        perturbation = (
            member_ds[var]
            - ensemble_mean[var]
        )

        updated = (
            control[var]
            + perturbation
        )

        # ----------------------------------------------------------
        # Make the updated variable concrete before replacing the
        # original file. This also allows us to perform the
        # non-negative check.
        # ----------------------------------------------------------

        updated = updated.load()

        # ----------------------------------------------------------
        # Check finite values.
        # ----------------------------------------------------------

        if not np.all(np.isfinite(updated.values)):

            raise RuntimeError(
                f"{member}: {var} contains NaN or Inf "
                "after applying perturbation"
            )

        # ----------------------------------------------------------
        # Moisture / non-negative constraint.
        # ----------------------------------------------------------

        if var in NONNEGATIVE_VARS:

            minimum = float(
                updated.min().values
            )

            negative_count = int(
                (updated < 0).sum().values
            )

            print(
                f"  {var}: minimum={minimum:.8e}, "
                f"negative_count={negative_count}"
            )

            if negative_count > 0:

                if CLIP_NEGATIVE:

                    print(
                        f"  WARNING: clipping "
                        f"{negative_count} negative "
                        f"{var} values to zero"
                    )

                    updated = updated.clip(
                        min=0.0
                    )

                else:

                    raise RuntimeError(
                        f"{member}: {var} contains "
                        f"{negative_count} negative values; "
                        f"minimum={minimum:.8e}. "
                        "Set CLIP_NEGATIVE=TRUE if clipping "
                        "is intended."
                    )

        new_member[var] = updated

    # --------------------------------------------------------------
    # Temporary output file.
    #
    # It is deliberately placed beside init.nc so os.replace()
    # can perform the final replacement on the same filesystem.
    # --------------------------------------------------------------

    temp_file = Path(
        str(member_file) + ".recenter_tmp"
    )

    if temp_file.exists():
        temp_file.unlink()

    print(f"Writing temporary file:")
    print(f"  {temp_file}")

    try:

        new_member.to_netcdf(
            temp_file,
            engine="netcdf4",
        )

        # ----------------------------------------------------------
        # Verify that the temporary file exists and is non-empty.
        # ----------------------------------------------------------

        if not temp_file.is_file():
            raise RuntimeError(
                f"Temporary output was not created: {temp_file}"
            )

        if temp_file.stat().st_size == 0:
            raise RuntimeError(
                f"Temporary output is empty: {temp_file}"
            )

        # ----------------------------------------------------------
        # Validate that the temporary NetCDF file can be reopened.
        # ----------------------------------------------------------

        print("Validating temporary NetCDF file...")

        with xr.open_dataset(
            temp_file,
            engine="netcdf4",
        ) as test_ds:

            for var in PERTURB_VARS:

                if var not in test_ds:
                    raise RuntimeError(
                        f"{temp_file}: missing variable {var}"
                    )

        # ----------------------------------------------------------
        # Only now replace the original init.nc.
        # ----------------------------------------------------------

        print(
            f"Replacing original:\n"
            f"  {member_file}"
        )

        os.replace(
            temp_file,
            member_file,
        )

    except Exception:

        if temp_file.exists():
            temp_file.unlink()

        raise

    print(f"{member} completed successfully")


# ======================================================================
# Cleanup
# ======================================================================

for ds in member_datasets:
    ds.close()

control.close()


print()
print("=" * 72)
print("CONTROL-CENTERED ENSEMBLE COMPLETED SUCCESSFULLY")
print("=" * 72)
