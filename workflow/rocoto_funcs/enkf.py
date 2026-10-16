#!/usr/bin/env python
import os
from rocoto_funcs.base import xml_task, get_cascade_env

# begin of enkf ---------------------------------------------------------------


def enkf(xmlFile, expdir, taskType=""):
    nocoldda = os.getenv('COLDSTART_CYCS_DO_DA', 'TRUE').upper() == 'FALSE'
    if nocoldda:
        cycledefs = 'da_nocold'
    else:
        cycledefs = 'prod'
    # Task-specific EnVars beyond the task_common_vars
    extrn_mdl_source = os.getenv('IC_EXTRN_MDL_NAME', 'IC_PREFIX_not_defined')
    physics_suite = os.getenv('PHYSICS_SUITE', 'PHYSICS_SUITE_not_defined')
    lsm_scheme = os.getenv('LSM_SCHEME', 'sf_ruc')
    recenter_cycs = os.getenv('RECENTER_CYCS', '99')
    analysis_variables = os.getenv('ANALYSIS_VARIABLES', '0')
    save_anl = os.getenv('SAVE_ENKF_ANL', os.getenv('SAVE_GETKF_ANL', 'FALSE')).upper()
    enkf_algo = 'LETKF' if taskType.upper() == 'LETKF' else os.getenv('ENKF_TYPE', os.getenv('ENS_DA_TYPE', os.getenv('ENKF_SOLVER', 'GETKF'))).upper()
    is_onestep = 'TRUE' if taskType.upper() == 'LETKF' or enkf_algo == 'LETKF' else os.getenv('ENKF_ONESTEP', os.getenv('GETKF_ONESTEP', 'false')).upper()
    sub_type = '' if taskType.upper() == 'LETKF' else taskType.lower()

    dcTaskEnv = {
        'EXTRN_MDL_SOURCE': f'{extrn_mdl_source}',
        'PHYSICS_SUITE': f'{physics_suite}',
        'LSM_SCHEME': f'{lsm_scheme}',
        'NSOIL_LEVELS': os.getenv('NSOIL_LEVELS', '9'),
        'REFERENCE_TIME': '@Y-@m-@dT@H:00:00Z',
        'DO_RADAR_REF': os.getenv('DO_RADAR_REF', 'FALSE').upper(),
        'YAML_GEN_METHOD': os.getenv('YAML_GEN_METHOD', '1'),
        'COLDSTART_CYCS_DO_DA': os.getenv('COLDSTART_CYCS_DO_DA', 'TRUE').upper(),
        'SAVE_ENKF_ANL': save_anl,
        'SAVE_GETKF_ANL': save_anl,
        'ENS_SIZE': os.getenv("ENS_SIZE", '5'),
        'ENKF_TYPE': enkf_algo,
        'ENKF_TASK_TYPE': sub_type,
        'GETKF_TYPE': sub_type,
        'USE_CONV_SAT_INFO': os.getenv('USE_CONV_SAT_INFO', 'TRUE').upper(),
        'SAT_USELIST': os.getenv('SAT_USELIST', ''),
        'EMPTY_OBS_SPACE_ACTION': os.getenv('EMPTY_OBS_SPACE_ACTION', 'skip output'),
        'ENKF_ONESTEP': is_onestep,
        'GETKF_ONESTEP': is_onestep,
        'PIO_STRIDE': os.getenv('PIO_STRIDE', '')
    }

    if taskType.upper() == "OBSERVER":
        task_id = "enkf_observer"
    elif taskType.upper() == "SOLVER":
        task_id = "enkf_solver"
    elif taskType.upper() == "POST":
        task_id = "enkf_post"
    else:  # "OBSERVER_SOLVER", "LETKF", or default single task
        task_id = "enkf"
    if analysis_variables != '0':
        dcTaskEnv['ANALYSIS_VARIABLES'] = analysis_variables

    dcTaskEnv['KEEPDATA'] = get_cascade_env(f"KEEPDATA_{task_id}".upper()).upper()
    # dependencies
    timedep = ""
    realtime = os.getenv("REALTIME", "false")
    if realtime.upper() == "TRUE":
        starttime = get_cascade_env(f"STARTTIME_{task_id}".upper())
        timedep = f'\n    <timedep><cyclestr offset="{starttime}">@Y@m@d@H@M00</cyclestr></timedep>'
    if taskType.upper() in ["OBSERVER", "OBSERVER_SOLVER", "LETKF", ""]:
        if os.getenv("DO_IODA", "FALSE").upper() == "TRUE":
            iodadep = '<taskdep task="ioda_bufr"/>'
            dcTaskEnv['IODA_BUFR_WGF'] = 'enkf'
        else:
            iodadep = f'<datadep age="00:01:00"><cyclestr>&COMROOT;/&NET;/&rrfs_ver;/&RUN;.@Y@m@d/@H/ioda_bufr/det/ioda_aircar.nc</cyclestr></datadep>'
            dcTaskEnv['IODA_BUFR_WGF'] = 'det'

        final_recenterdep = ""
        spaces = " " * 4
        if os.getenv("DO_RECENTER", "FALSE").upper() == "TRUE":
            recenterhrs = recenter_cycs.split(' ')
            recenterdep = f'<taskdep task="recenter"/>'
            streqs_rec = "<or>"
            strneqs_rec = "<and>"
            for hr in recenterhrs:
                hr = f"{int(hr):02d}"
                streqs_rec += '\n' + spaces + f'  <streq><left><cyclestr>@H</cyclestr></left><right>{hr}</right></streq>'
                strneqs_rec += '\n' + spaces + f'  <strneq><left><cyclestr>@H</cyclestr></left><right>{hr}</right></strneq>'
            streqs_rec += '\n      </or>'
            strneqs_rec += '\n    </and>'
            final_recenterdep = f'''
    <or>
    {strneqs_rec}
    <and>
      {streqs_rec}
      {recenterdep}
    </and>
    </or>'''

        dependencies = f'''
  <dependency>
  <and>{timedep}
    <taskdep task="prep_ic"/>
    {iodadep}{final_recenterdep}
  </and>
  </dependency>'''
    elif taskType.upper() == "SOLVER":
        dependencies = f'''
  <dependency>
  <and>{timedep}
    <taskdep task="enkf_observer"/>
  </and>
  </dependency>'''
    #
    elif taskType.upper() == "POST":
        dependencies = f'''
  <dependency>
  <and>{timedep}
   <or>
    <taskdep task="enkf_solver"/>
    <taskdep task="enkf"/>
   </or>
  </and>
  </dependency>'''
    #
    xml_task(xmlFile, expdir, task_id, cycledefs, dcTaskEnv=dcTaskEnv, dependencies=dependencies, command_id="ENKF")
# end of enkf -----------------------------------------------------------------


def getkf(xmlFile, expdir, taskType=""):
    enkf(xmlFile, expdir, taskType=taskType)


def letkf(xmlFile, expdir):
    enkf(xmlFile, expdir, taskType="LETKF")
