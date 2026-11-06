#!/usr/bin/env python
# this file hosts all tasks that will not be needed by NCO
import os
import textwrap
from rocoto_funcs.base import xml_task, get_cascade_env

# begin of graphics --------------------------------------------------------


def graphics(xmlFile, expdir, do_ensemble=False):
    meta_id = 'graphics'
    task_id = f'{meta_id}_#tile#'
    tiles = os.getenv('GRAPHICS_TILES', 'full')
    meta_bgn = f'''
<metatask name="{meta_id}">
<var name="tile">{tiles}</var>'''
    meta_end = f'</metatask>\n'
    cycledefs = 'prod'
    #
    # Task-specific EnVars beyond the task_common_vars
    dcTaskEnv = {
        'FCST_LEN_HRS_CYCLES': os.getenv('FCST_LEN_HRS_CYCLES', '03 03'),
        'TILE': '#tile#',
        'GRAPHICS_ZIP': os.getenv('GRAPHICS_ZIP', 'FALSE').upper(),
        'GRAPHICS_MODEL': os.getenv('GRAPHICS_MODEL', ''),
        'UPP_DOMAIN': os.getenv('UPP_DOMAIN', 'conus.'),
        'DO_ENSEMBLE': 'TRUE' if do_ensemble else 'FALSE',
        'GRAPHICS_TYPE': os.getenv('GRAPHICS_TYPE', 'enspanel' if do_ensemble else 'maps'),
    }
    if do_ensemble:
        dcTaskEnv['ENS_SIZE'] = os.getenv('ENS_SIZE', '10')
        obspath = os.getenv('OBSPATH_NSSLMOSAIC', '')
        if obspath:
            dcTaskEnv['OBSPATH_NSSLMOSAIC'] = f'<cyclestr>{obspath}</cyclestr>'
    # dependencies
    timedep = ""
    realtime = os.getenv("REALTIME", "false")
    if realtime.upper() == "TRUE":
        starttime = get_cascade_env(f"STARTTIME_{task_id}".upper())
        timedep = f'\n    <timedep><cyclestr offset="{starttime}">@Y@m@d@H@M00</cyclestr></timedep>'
    #
    ngroup = int(os.getenv('POST_GROUP_TOT_NUM', '1') or 1)
    if not do_ensemble:
        taskdep = '\n<taskdep task="upp_g00"/>'
        for i in range(1, ngroup):
            taskdep += f'''
<or>
  <not><taskvalid task="upp_g{i:02d}"/></not>
  <taskdep task="upp_g{i:02d}"/>
</or>'''
    else:
        taskdep = '\n<metataskdep metatask="upp_g00"/>'
        for i in range(1, ngroup):
            taskdep += f'''
<or>
  <not><taskvalid task="upp_g{i:02d}_m001"/></not>
  <metataskdep metatask="upp_g{i:02d}"/>
</or>'''

    taskdep = textwrap.indent(taskdep, '    ')
    #
    # Optional data dependency on deterministic UPP grib2 file
    det_datadep = ""
    if do_ensemble and os.getenv("GRAPHICS_WAIT_DET", "false").upper() == "TRUE":
        domain = os.getenv('UPP_DOMAIN', 'conus.')
        det_file = os.getenv('GRAPHICS_DET_FILE', f'&COMROOT;/&NET;/&rrfs_ver;/&RUN;.@Y@m@d/@H/upp/det/&RUN;.t@Hz.prslev.f001.{domain}grib2')
        det_datadep = f'\n    <datadep age="00:00:10"><cyclestr>{det_file}</cyclestr></datadep>'

    dependencies = f'''
  <dependency>
  <and>{timedep}{taskdep}{det_datadep}
  </and>
  </dependency>'''

    #
    xml_task(xmlFile, expdir, task_id, cycledefs, dcTaskEnv, dependencies, True, meta_id, meta_bgn, meta_end, "GRAPHICS")

# end of graphics --------------------------------------------------------
