#!/usr/bin/env python
import os
import sys
try:
    import hifiyaml as hy
    import yamltools4jedi as yj
except ImportError:
    import hifiyaml4rrfs as hy
    import yamltools4rrfs as yj


def smart_superyaml(HOMErrfs, ytype, mesh, getkf_onestep=False):
    # make sure no "main.yaml" under parm/observers before further actions
    fmain = f'{HOMErrfs}/parm/observers/main.yaml'
    if os.path.islink(fmain):
        os.unlink(fmain)
    elif os.path.isfile(fmain):
        os.remove(fmain)
    # ~~~~
    fheader = f'../{ytype}_header.yaml'  # use a relative link
    os.symlink(fheader, fmain)
    #
    dirname = f'{HOMErrfs}/parm/observers'
    fpacked = f'{HOMErrfs}/parm/{ytype}.yaml'
    yj.pack(dirname, fpacked)
    #
    # -----------------------------------------------------------
    #  Modifications for different use cases or applications
    # -----------------------------------------------------------
    #
    data = hy.load(fpacked)
    #
    #  getkf and letkf need to set "io pool/max pool size" to 80
    #
    if ytype in ["getkf", "letkf"]:
        dcObs = yj.get_all_obs(data, shallow=True)
        # process in reverse order of pos1 so line insertions do not invalidate earlier offsets
        for name, observer in sorted(dcObs.items(), key=lambda x: x[1]["pos1"], reverse=True):
            p1 = observer["pos1"]
            p2 = observer["pos2"]
            tmp = data[p1:p2]

            pos, errmsg = hy.get_start_pos(tmp, "io pool/max pool size")
            if errmsg is None:
                absolute_pos = p1 + pos
                data[absolute_pos] = data[absolute_pos].replace("max pool size: 1", "max pool size: 80")

            # GETKF observer_solver or LETKF: change observer distribution to Halo
            if getkf_onestep or ytype == "letkf":
                for i, line in enumerate(tmp):
                    if line.strip() == "distribution:":
                        indent = line[:len(line) - len(line.lstrip())]
                        halo_val = "50e3" if name == "refl10cm" else "500e3"
                        if i + 2 < len(tmp) and "halo size:" in tmp[i + 2]:
                            if name != "refl10cm":
                                halo_val = tmp[i + 2].split("halo size:")[1].strip()
                            data[p1 + i : p1 + i + 3] = [
                                f"{indent}use data frame container: true",
                                f"{indent}redistribution:",
                                f"{indent}  name: Halo",
                                f"{indent}  halo size: {halo_val}",
                            ]
                        else:
                            data[p1 + i : p1 + i + 2] = [
                                f"{indent}use data frame container: true",
                                f"{indent}redistribution:",
                                f"{indent}  name: Halo",
                            ]
                        break

            # LETKF: inject observation vertical localization anchors
            if ytype == "letkf":
                vert_anchor = None
                if name == "refl10cm":
                    vert_anchor = "Refl10mVertObsLoc"
                elif name.startswith("adpsfc_uv") or name.startswith("sfcshp_uv") or name.startswith("msonet_uv"):
                    vert_anchor = "SfcWindVertObsLoc"
                elif name.startswith("adpsfc_") or name.startswith("sfcshp_") or name.startswith("msonet_"):
                    vert_anchor = "SfcVertObsLoc"
                elif any(name.startswith(p) for p in ["adpupa_", "aircft_", "aircar_", "proflr_", "rassda_", "satwnd_", "vadwnd_"]):
                    vert_anchor = "HeightVertObsLoc"

                if vert_anchor:
                    cur_obs = data[p1:]
                    loc_pos, err = hy.get_start_pos(cur_obs, "obs localizations")
                    if err is None:
                        target_idx = None
                        for j in range(loc_pos + 1, min(loc_pos + 20, len(cur_obs))):
                            if "lengthscale:" in cur_obs[j]:
                                target_idx = j
                                break
                        if target_idx is not None:
                            if vert_anchor == "SfcWindVertObsLoc":
                                indent = data[p1 + target_idx][:len(data[p1 + target_idx]) - len(data[p1 + target_idx].lstrip())]
                                data[p1 + target_idx] = f"{indent}lengthscale: 50e3"
                            abs_insert = p1 + target_idx + 1
                            vert_line = f"         - <<: *{vert_anchor}"
                            data.insert(abs_insert, vert_line)

    elif ytype == "jedivar" and mesh in {"conus12km", "na12km"}:  # temporary fix until GSIBEC is updated
        hy.modify(data, 'regional nn fill distance in km', 'regional nn fill distance in km: 5000')
    #
    # insert correct domain-specific polygon configuration
    if os.getenv("JEDI_POLYGON_FILTER", "TRUE") == "TRUE":
        fpolygon = f'{HOMErrfs}/fix/{mesh}/{mesh}.polygon.yaml'
        polygon = hy.load(fpolygon)
        data[0:0] = polygon  # insert at the beginning
    else:
        # remove polyogn filters from all observers
        yj.removefilter(data, "PolygonCheck")
    # ------------------------------------------------------------------------
    # dump out the final yaml file
    hy.dump(data, fpath=fpacked)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} HOMErrfs <getkf|letkf|jedivar> conus12km")
        sys.exit(1)
    smart_superyaml(sys.argv[1], sys.argv[2], sys.argv[3])
