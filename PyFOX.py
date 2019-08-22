import numpy as np
from datetime import timedelta
import pandas as pd
import xarray as xr

# OS interaction
import os
import yaml
import tkinter as tk  # For the dialog that lets you choose your config file
from tkinter import filedialog
import copy
import csv
import sys

# UBT's package for handling dts data
import btmm_process

# Ignore the future compatibility warnings
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=RuntimeWarning)

# -----------------------------------------------------------------------------
# Configuration file
# -----------------------------------------------------------------------------
# Quick fix for us to do local debugging.
try:
    filename_configfile_KL = '/Users/karllapo/Desktop/proj/DarkMix_Voitsumra/love_dts/outer_array_flyfox_190722.yml'
    filename_configfile_AF = '/home/anita/Schreibtisch/python_programme/config_files/LOVE/rim_unheated_190711_all.yml'
    if os.path.exists(filename_configfile_KL):
        filename_configfile = filename_configfile_KL
    elif os.path.exists(filename_configfile_AF):
        filename_configfile = filename_configfile_AF
    else:
        print('config file not found.')

# Expected, non-debugging behavior.
except NameError:

    # Test if a file was provided to the script from the terminal.
    try:
        filename_configfile = sys.argv[1]
        if not os.path.exists(filename_configfile):
            print('Config file' + sys.argv[1] + 'not found.')

    # Prompt the user for the config file.
    except IndexError:
        # Open the config file
        root = tk.Tk()
        # to close this stupid root window that doesn't let itself be closed.
        root.withdraw()
        filename_configfile = filedialog.askopenfilename()
        ftypes = [
            ('yaml configuration file', '*.yml'),
            ]
        filename_configfile = filedialog.askopenfilename(filetypes=ftypes)

with open(filename_configfile, 'r') as stream:
    config_user = yaml.load(stream)

try:
    remote_dir = config_user['directories']['remote']['remote_directories']
except KeyError:
    remote_dir = []

# -----------------------------------------------------------------------------
# Look through the configuration file and prepare
# -----------------------------------------------------------------------------
#%% loop through the experiment_names
experiment_names = config_user['directories']['experiment_names']
internal_config = {}
for exp_name in experiment_names:
    #%% Get paths for the directories of the different processing steps.
    # Create directories if they don't exist and errors if needed data aren't
    # found.

    # --------
    # External data
    try:
        dir_ext = config_user['directories']['external']
        # Check for empty yaml lists (assigned NoneType)
        if dir_ext is not None:
            # check if the external data directory exists, error if not
            if (not os.path.exists(dir_ext)) and (config_user['flags']['ref_temp_option']):
                raise FileNotFoundError('External data directory not found')
    except KeyError:
        dir_ext = None

    #%%
    # --------
    # Raw xml files
    if 'raw_xml' in remote_dir:
        dir_raw_xml = os.path.join(config_user['directories']['remote']['dir_pre'],
                                   exp_name, config_user['directories']['raw'])
    else:
        dir_raw_xml = os.path.join(config_user['directories']['local']['dir_pre'],
                                   exp_name, config_user['directories']['raw_xml'])

    # Throw an error if raw files should be read but directory isn't found
    if (not os.path.exists(dir_raw_xml)) and (config_user['flags']['archiving_flag']):
        raise FileNotFoundError('Raw data directory not found')

    #%%
    # --------
    # Archived tar.gz of xmls
    if 'archive' in remote_dir:
        dir_archive = os.path.join(config_user['directories']['remote']['dir_pre'],
                                   exp_name, config_user['directories']['archive'])
    else:
        dir_archive = os.path.join(config_user['directories']['local']['dir_pre'],
                                   exp_name, config_user['directories']['archive'])

    if (not os.path.exists(dir_archive)):
        # create the folder for the archived files if it doesn't already exist and archived files will be created
        if config_user['flags']['archiving_flag']:
            os.makedirs(dir_archive)
            print('Archived directory not found. Created a new one at ' + dir_archive)
        # throw error if archived files are needed but neither found nor created
        elif config_user['flags']['archive_read_flag']:
            raise FileNotFoundError('Archived data directory not found')

    #%%
    # --------
    # Raw xmls in netcdf format
    if 'raw_netcdf' in remote_dir:
        dir_raw_netcdf = os.path.join(config_user['directories']['remote']['dir_pre'],
                                      exp_name, config_user['directories']['raw_netcdf'])
    else:
        dir_raw_netcdf = os.path.join(config_user['directories']['local']['dir_pre'],
                                      exp_name, config_user['directories']['raw_netcdf'])

    if not os.path.exists(dir_raw_netcdf):
        # Create the folder for the raw netcdf files if it doesn't already
        # exist and raw netcdf files will be created.
        if config_user['flags']['archive_read_flag']:
            os.makedirs(dir_raw_netcdf)
            print('Calibrated directory not found. Created a new one at ' + dir_raw_netcdf)
        # throw error if raw netcdf files are needed but neither found nor created
        elif config_user['flags']['processed_flag']:
            raise FileNotFoundError('Raw netcdf data directory not found')

    #%%
    # --------
    # Processed netcdfs (labeling, initial data cleanup and
    # prep for calibration)
    if 'processed' in remote_dir:
        dir_processed = os.path.join(config_user['directories']['remote']['dir_pre'],
                                     exp_name, config_user['directories']['processed'])
    else:
        dir_processed = os.path.join(config_user['directories']['local']['dir_pre'],
                                     exp_name, config_user['directories']['processed'])

    if not os.path.exists(dir_processed):
        # Create the folder for the processed files if it doesn't already
        # exist and processed files will be created.
        if config_user['flags']['processed_flag']:
            os.makedirs(dir_processed)
            print('Processed directory not found. Created a new one at '
                  + dir_processed)
        # Throw error if processed files are needed but neither
        # found nor created.
        elif config_user['flags']['calibrate_flag']:
            raise FileNotFoundError('Processed data directory not found')


    #%%
    # --------
    # Calibrated temperature (full matrix inversion)
    if 'calibrated' in remote_dir:
        dir_cal = os.path.join(config_user['directories']['remote']['dir_pre'],
                               exp_name, config_user['directories']['calibrated'])
    else:
        dir_cal = os.path.join(config_user['directories']['local']['dir_pre'],
                               exp_name, config_user['directories']['calibrated'])

    if not os.path.exists(dir_cal):
        # create the folder for the calibrated files if it doesn't already
        # exist and calibrated files will be created
        if config_user['flags']['calibrate_flag']:
            os.makedirs(dir_cal)
            print('Calibrated directory not found. Created a new one at '
                  + dir_cal)
        elif config_user['flags']['final_flag']:
            raise FileNotFoundError('Calibrated data directory not found')

    #%%
    # --------
    # Final data (converted into just the labeled segments with
    # a physical location)
    if 'final' in remote_dir:
        dir_final = os.path.join(config_user['directories']['remote']['dir_pre'],
                                 exp_name, config_user['directories']['final'])
    else:
        dir_final = os.path.join(config_user['directories']['local']['dir_pre'],
                                 exp_name, config_user['directories']['final'])

    # Create the folder for the final files if it doesn't already exist
    if (not os.path.exists(dir_final)) and (config_user['flags']['calibrate_flag']):
        os.makedirs(dir_final)
        print('Final directory not found. Created a new one at ' + dir_final)

    #%%
    # --------
    # Graphics folder (currently unused)
    if 'graphics' in remote_dir:
        dir_graphics = os.path.join(config_user['directories']['remote']['dir_pre'],
                                    exp_name, config_user['directories']['graphics'])
    else:
        dir_graphics = os.path.join(config_user['directories']['local']['dir_pre'],
                                    exp_name, config_user['directories']['graphics'])

    # assemble internal config for each dts folder within the experiment folder
    internal_config[exp_name] = {}
    internal_config[exp_name] = copy.deepcopy(config_user)
    internal_config[exp_name]['archive']['channelName'] = config_user['directories']['channelName']
    internal_config[exp_name]['archive']['sourcePath'] = dir_raw_xml
    internal_config[exp_name]['archive']['targetPath'] = dir_archive
    internal_config[exp_name]['directories']['dirArchive'] = dir_archive
    internal_config[exp_name]['directories']['dirRawNetcdf'] = dir_raw_netcdf
    internal_config[exp_name]['directories']['dirProcessed'] = dir_processed
    internal_config[exp_name]['directories']['dirCalibrated'] = dir_cal
    internal_config[exp_name]['directories']['dirFinal'] = dir_final

    # Make sure the prefix/suffix fields exist
    try:
        internal_config[exp_name]['directories']['fileName']['prefix'] = config_user['directories']['raw_xml'] + '_' + exp_name
    except KeyError:
        internal_config[exp_name]['directories']['fileName'] = {}
        internal_config[exp_name]['directories']['fileName']['prefix'] = config_user['directories']['raw_xml'] + '_' + exp_name

   # Determine fiber type
    coretype = internal_config[exp_name]['dataProperties']['fiber_type']
    if coretype == 'multicore':
        cores = internal_config[exp_name]['dataProperties']['cores']
    else:
        cores = None

    # Determine the list of location types
    try:
        loc_type = config_user['dataProperties']['all_locs']
    except KeyError:
        loc_type = []
        for l in config_user['location_library']:
            loc_type.append(config_user['location_library'][l]['loc_type'])
        loc_type = np.unique(loc_type).tolist()

# -----------------------------------------------------------------------------
# Archive and create raw netcdfs
# -----------------------------------------------------------------------------
#%% Archive/read the raw xml files
for exp_name in experiment_names:
    print('-------------')
    print(exp_name)
    print('-------------')

    # archiving
    if config_user['flags']['archiving_flag']:
        print('-------------')
        print('Archiving raw xml files.')
        print(' ')
        print('archiving ', exp_name)
        btmm_process.archiver(internal_config[exp_name])

    # write raw netCDF
    if config_user['flags']['archive_read_flag']:
        print('-------------')
        print('Writing netcdfs from raw xml files.')
        print(' ')
        print('creating raw netcdf for experiment: ', exp_name)
        btmm_process.archive_read(internal_config[exp_name])

# -----------------------------------------------------------------------------
# Process DTS files
# -----------------------------------------------------------------------------
for exp_name in experiment_names:

    if config_user['flags']['processed_flag']:
        #%% Open the raw saved as netcdf
        print('-------------')
        print('Processing DTS data: labeling, cleaning, separating cores, adding external reference data.')
        print(' ')

        # Get the external data to add if we are not using the instrument PT100s
        if internal_config[exp_name]['flags']['ref_temp_option'] == 'external':
            # Get the metdata
            os.chdir(dir_ext)
            ref_data = xr.open_mfdataset('*.nc').to_dataframe()

            probe1_name = internal_config[exp_name]['dataProperties']['probe1Temperature']
            probe2_name = internal_config[exp_name]['dataProperties']['probe2Temperature']

            probe1_cols = np.atleast_1d(internal_config[exp_name]['dataProperties']['probe1_value'])
            probe2_cols = np.atleast_1d(internal_config[exp_name]['dataProperties']['probe2_value'])

            probe1 = xr.DataArray.from_series(ref_data_df[probe1_cols].mean(axis=1))
            probe2 = xr.DataArray.from_series(ref_data_df[probe2_cols].mean(axis=1))


        # Find all 'raw' netcdfs within the processed directory,
        # sort them (by date), and process each individually.
        os.chdir(internal_config[exp_name]['directories']['dirRawNetcdf'])
        contents = os.listdir()
        ncfiles = [file for file in contents if '.nc' in file and 'raw' in file]
        ncfiles.sort()
        ntot = np.size(ncfiles)

        for nraw, raw_nc in enumerate(ncfiles):
            os.chdir(internal_config[exp_name]['directories']['dirRawNetcdf'])

            # Name of the output file for this archive chunk
            try:
                outname_suffix = config_user['directories']['fileName']['suffix']
            except KeyError:
                outname_suffix = ''
            outname_date = '_'.join(raw_nc.split('.')[0].split('_')[1:])
            print('Processing ' + outname_date + ' (' + str(nraw + 1)
                  + ' of ' + str(ntot) + ')')

            # Open up raw file for this interval.
            dstemp = xr.open_dataset(raw_nc)

            # Resample to a common time stamp interval with the reference/bath
            # instruments. Do this using a linear interpolation.

            # Round to the nearest time interval
            delta_t = config_user['dataProperties']['resampling_time']
            dt_start = pd.Timestamp(dstemp.time.values[0]).round(delta_t)
            dt_end = pd.Timestamp(dstemp.time.values[-1]).round(delta_t)

            # Create a regular interval time stamp index
            reg_time_pd = pd.date_range(start=dt_start, end=dt_end, freq=delta_t)
            dstemp = dstemp.interp(time=reg_time_pd,
                                   kwargs={'fill_value': 'extrapolate'})

            # Add a delta t attribute
            dstemp.attrs['dt'] = config_user['dataProperties']['resampling_time']


            # Add in external reference data here
            if internal_config[exp_name]['flags']['ref_temp_option'] == 'external':
                probe1_temp = probe1.reindex_like(dstemp.time,
                                                  method='nearest',
                                                  tolerance=1)

                probe2_temp = probe2.reindex_like(dstemp.time,
                                                  method='nearest',
                                                  tolerance=1)
                dstemp[probe1_name] = probe1_temp
                dstemp[probe2_name] = probe2_temp

            # Finish processing the fiber by labeling it and splitting up multicore fibers
            os.chdir(internal_config[exp_name]['directories']['dirProcessed'])
            # Split up multicore data
            if coretype == 'multicore':
                for c in cores:
                    dstemp_core = dstemp

                    # Drop the unnecessary negative LAF indices
                    core_LAF_start = config_user['dataProperties']['cores'][c]['LAF'][0]
                    core_LAF_end = config_user['dataProperties']['cores'][c]['LAF'][-1]
                    dstemp_core = dstemp_core.sel(LAF=((dstemp_core['LAF'] > core_LAF_start)
                                                        & (dstemp_core['LAF'] < core_LAF_end)))
                    dstemp_core.attrs['LAF_beg'] = core_LAF_start
                    dstemp_core.attrs['LAF_end'] = core_LAF_end

                    # Location labels
                    for loc_type_cur in loc_type:
                        location = {}
                        for l in config_user['location_library']:
                            if loc_type_cur == config_user['location_library'][l]['loc_type']:
                                location[l] = config_user['location_library'][l]['LAF'][c]
                        dstemp_core = btmm_process.labelLoc_additional(dstemp_core,
                                                                       location,
                                                                       loc_type_cur)
                    # Converting to a netcdf ruins this step unfortunately.
                    # dstemp_core.attrs['loc_general_long'] = dict((l, config_user['loc_general'][l]['long name'])

                    # Label the core
                    dstemp_core.coords['core'] = c
                    # Output this core
                    outname = exp_name + '_proc_' + outname_date + outname_suffix + '_' + c + '.nc'
                    dstemp_core.to_netcdf(outname)

            elif coretype == 'singlecore':
                # Drop the unnecessary negative LAF indices
                dstemp = dstemp.sel(LAF=dstemp['LAF'] > 0)
                dstemp.attrs['LAF_beg'] = dstemp.LAF.values[0]

                # Location labels
                for loc_type_cur in loc_type:
                    location = {}
                    for l in config_user['location_library']:
                        if loc_type_cur == config_user['location_library'][l]['loc_type']:
                            location[l] = config_user['location_library'][l]['LAF']
                    dstemp_core = btmm_process.labelLoc_additional(dstemp,
                                                                   location,
                                                                   loc_type_cur)

                outname = exp_name + '_proc_' + outname_date + outname_suffix + '.nc'
                dstemp.to_netcdf(outname)

# -----------------------------------------------------------------------------
# Calibrate the temperature data
# -----------------------------------------------------------------------------
#%% Construct dataset with all experiments/over all the measurement duration
if config_user['flags']['calibrate_flag']:
    print('-------------')
    print('Calibrating DTS data: full matrix inversion.')
    print(' ')
    for exp_name in experiment_names:
        # Find all 'processed' netcdfs within the processed directory,
        # sort them by date and core name, and process each individually.
        os.chdir(internal_config[exp_name]['directories']['dirProcessed'])
        contents = os.listdir()
        ncfiles = [file for file in contents if '.nc' in file and 'proc' in file]
        ncfiles.sort()
        ntot = np.size(ncfiles)
        for nproc, proc_nc in enumerate(ncfiles):
            # Name of the output file for this archive chunk
            try:
                outname_suffix = config_user['directories']['fileName']['suffix']
            except KeyError:
                outname_suffix = ''
            outname_date = '_'.join(proc_nc.split('.')[0].split('_')[1:])

            print('Calibrating ' + proc_nc + ' (' + str(nproc + 1)
                  + ' of ' + str(ntot) + ')')

            os.chdir(internal_config[exp_name]['directories']['dirProcessed'])
            dstemp = xr.open_dataset(proc_nc)

            # Step loss corrections if they are provided.
            if 'step_loss_LAF' in config_user['dataProperties'] and 'step_loss_correction' in config_user['dataProperties']:
                splice_LAF = np.atleast_1d(config_user['dataProperties']['step_loss_LAF'])
                step_loss_corrections = np.atleast_1d(config_user['dataProperties']['step_loss_correction'])

                # Make sure these are not NaNs
                if splice_LAF and step_loss_corrections:
                    # Calculate the log power of the stokes/anti-stokes scattering
                    dstemp['logPsPas'] = np.log(dstemp.Ps / dstemp.Pas)
                    # Correct for any step-losses due to splicing.
                    for spl_num, spl_LAF in enumerate(splice_LAF):
                        dstemp['logPsPas'] = dstemp.logPsPas.where((dstemp.LAF < spl_LAF),
                                                                   dstemp.logPsPas + step_loss_corrections[spl_num])

           # Calibrate the temperatures. If the bath pt100s and dts do not line up
            # in time, do not calibrate.
            if (np.size(np.flatnonzero(~np.isnan(dstemp.temp.values))) > 0):
                dstemp, _, _, _ = btmm_process.matrixInversion(dstemp, internal_config[exp_name])
            else:
                # Notify the user.
                print('PT100 and DTS data do not line up in time for ' + exp_name)
                print('The cal_temp field will not be returned.')

            # Rename the instrument reported temperature field
            dstemp = dstemp.rename({'temp': 'instr_temp'})

            # Output the calibrated data'
            if coretype == 'multicore':
                core = proc_nc.split('_')[-1].split('.')[0]
                dstemp.coords['core'] = core
            else:
                core = None
            outname_channel = proc_nc.split('.')[0].split('_')[-3]
            outname_date = proc_nc.split('.')[0].split('_')[-2]
            outname_core = proc_nc.split('.')[0].split('_')[-1]
            outname = '_'.join(filter(None, [exp_name, 'cal', outname_channel, outname_date, outname_suffix, outname_core])) + '.nc'

            os.chdir(internal_config[exp_name]['directories']['dirCalibrated'])
            dstemp.to_netcdf(outname, engine='netcdf4')

            print('')

# -----------------------------------------------------------------------------
# Finalize with physical coordinates
# -----------------------------------------------------------------------------
#%% Final preparation of the DTS dataset

if config_user['flags']['final_flag']:
    print('-------------')
    print('Final preparation: assigning physical coordinates, dropping unused fields and locations')
    print(' ')

    # Locations to physically label
    phys_locs = config_user['dataProperties']['phys_locs']

    # List of finished files so we can skip files when handling multicore fibers.
    finished_files = []

    for exp_name in experiment_names:
        # Find all 'calibrated' netcdfs within the calibrated directory,
        # sort them by date and core name, and process each individually.
        os.chdir(internal_config[exp_name]['directories']['dirCalibrated'])
        contents = os.listdir()
        ncfiles = [file for file in contents if '.nc' in file and 'cal' in file]
        ncfiles.sort()
        ntot = np.size(ncfiles)
        for ncal, cal_nc in enumerate(ncfiles):
            # Name of the output file for this archive chunk
            try:
                outname_suffix = config_user['directories']['fileName']['suffix']
            except KeyError:
                outname_suffix = ''
            name_components = cal_nc.split('.')[0].split('_')
            outname_channel = name_components[-3]
            outname_date = name_components[-2]

            print('Finalizing ' + cal_nc + ' (' + str(ncal + 1)
                  + ' of ' + str(ntot) + ')')

            # Location dictionary to pass to the physical coordinates function.
            location = {}

            # Deal with multicore fibers differently than single core fibers.
            if coretype == 'multicore':
                os.chdir(internal_config[exp_name]['directories']['dirCalibrated'])
                # Check if we already handled this core.
                if cal_nc in finished_files:
                    continue
                nc_cal_core_name = '_'.join(name_components[:-1])
                nc_cal_core = [file for file in ncfiles if nc_cal_core_name in file and 'cal' in file]
                dstemp_out = {}

                # Assign physical coordinates. Each core is appended to a list to be merged later.
                for c in nc_cal_core:
                    dstemp = xr.open_dataset(c)
                    dstemp = dstemp.drop(['Ps', 'Pas', 'instr_temp'])
                    # Reformat the config locations to specify just a single core
                    core = str(dstemp.core.values)

                    for l in config_user['location_library']:
                        location[l] = copy.deepcopy(config_user['location_library'][l])
                        location[l]['LAF'] = config_user['location_library'][l]['LAF'][core]

                    for ploc in config_user['dataProperties']['phys_locs']:
                        if not ploc in dstemp_out:
                            dstemp_out[ploc] = []
                        # Find all the locations to label in this location type
                        temp_loc = {loc:location[loc] for loc in location if ploc in location[loc]['loc_type']}
                        dstemp_out[ploc].append(btmm_process.labeler.dtsPhysicalCoords_3d(dstemp, temp_loc))

                # Merge the cores
                for ploc in config_user['dataProperties']['phys_locs']:
                    for nc, c in enumerate(dstemp_out[ploc]):
                        # Make the assumption that the specific core is
                        # not important as they should be identical within
                        # the physical resolution of the DTS.
                        if nc == 0:
                            interp_to = c
                        else:
                            dstemp_out[ploc][nc] = dstemp_out[ploc][nc].interp(xyz=interp_to.xyz)

                    dstemp_out[ploc] = xr.concat(dstemp_out[ploc], dim='core')

                    # Output each location type as a separate final file.
                    outname = '_'.join(name_components[:-1]).replace('cal', 'final') + '_' + ploc + '.nc'
                    os.chdir(internal_config[exp_name]['directories']['dirFinal'])
                    dstemp_out[ploc].to_netcdf(outname)

                # Make sure we don't reprocess files.
                finished_files.extend(nc_cal_core)

            # Deal with the single core fiber.
            else:
                # Open each calibrated file.
                os.chdir(internal_config[exp_name]['directories']['dirCalibrated'])
                dstemp = xr.open_dataset(cal_nc)
                dstemp = dstemp.drop(['Ps', 'Pas', 'instr_temp'])

                location = {}
                for l in config_user['location_library']:
                    location[l] = copy.deepcopy(config_user['location_library'][l])
                    location[l]['LAF'] = config_user['location_library'][l]['LAF']

                for ploc in config_user['dataProperties']['phys_locs']:
                    temp_loc = {loc:location[loc] for loc in location if ploc in location[loc]['loc_type']}
                    dstemp_out = btmm_process.labeler.dtsPhysicalCoords_3d(dstemp, temp_loc)
                    os.chdir(internal_config[exp_name]['directories']['dirFinal'])
                    outname = cal_nc.split('.')[0].replace('cal', 'final') + '_' + ploc + '.nc'
                    dstemp_out.to_netcdf(outname)
