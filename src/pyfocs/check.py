import os
import yaml
from pyfocs import yamlDict
import copy
import numpy as np


def config(fn_cfg, ignore_flags=False):
    '''
    Function checks the basic integrity of a configuration file and returns the
    config dictionary, location library, and physical locations dictionary
    expected by pyfocs.
    '''

    # The internal config file and location library are handed back to pyfocs
    in_cfg = {}
    lib = {}

    # This yaml syntax requires pyyaml v5.1
    try:
        cfg = yamlDict(fn_cfg)
    # The parse error appears to be raised a couple different ways. Try to
    # catch both methods of reporting a ParserError.
    except yaml.parser.ParserError as exc:
        print('The config yaml file is not properly formatted.')
        print('Examine the following bad line(s):')
        print(exc)

        return None, None
        # Example output:
        # while parsing a block mapping
        # in "fine_name.yml", line 2, column 1

    # -------------------------------------------------------------------------
    # Look through the configuration file and prepare
    experiment_names = cfg['directories']['experiment_names']
    mess = 'experiment_names should be a list (e.g., all items start with a dash)'
    assert isinstance(cfg['directories']['experiment_names'], list), experiment_names
    in_cfg['experiment_names'] = experiment_names

    # Verify that the flags exist and are booleans.

    # Remove deprecated flags.
    try:
        del cfg['flags']['cal_mode']
        in_cfg['flags'] = cfg['flags']
    except KeyError:
        in_cfg['flags'] = cfg['flags']

    # Catch an old name for the "final" flag.
    if 'processed_flag' in in_cfg['flags']:
        in_cfg['flags']['final_flag'] = in_cfg['flags']['processed_flag']
        del in_cfg['processed_flag']

    flags = ['write_mode', 'archiving_flag', 'archive_read_flag',
             'calibrate_flag', 'final_flag']
    if not all([fl in in_cfg['flags'] for fl in flags]):
        missing_flags = [fl for fl in in_cfg['flags'] if fl not in flags]
        raise KeyError('Not all flags were found:\n' + '\n'.join(missing_flags))

    # This flag will trigger true if calibration is on and requests labeling
    # the data with physical locations (label_data: True)
    label_data_flag = False

    # --------
    # Check paths that do not vary between experiments.

    # Directories located locally.
    try:
        dir_pre_local = cfg['directories']['local']['dir_pre']
    except KeyError:
        dir_pre_local = ''

    # List of directories located remotely.
    try:
        remote_dir = cfg['directories']['remote']['remote_directories']
    except KeyError:
        remote_dir = []
    # Remote path for running on a server.
    try:
        dir_pre_remote = cfg['directories']['remote']['dir_pre']
    except KeyError:
        dir_pre_remote = ''

    # Handling for relative paths
    if dir_pre_local == '.':
        dir_pre_local = os.getcwd()
    if dir_pre_remote == '.':
        dir_pre_remote = os.getcwd()

    # External data directory
    try:
        dir_ext = cfg['directories']['external']
        # Handling for relative paths
        if dir_ext == '.':
            dir_ext = os.getcwd()
        # Check for empty yaml lists (assigned NoneType)
        if dir_ext is not None:
            # check if the external data directory exists, error if not
            if (not os.path.exists(dir_ext)):
                raise FileNotFoundError('External data directory not found at\n'
                                        + dir_ext)
    except KeyError:
        dir_ext = None

    # Resampling time
    try:
        dt = cfg['dataProperties']['resampling_time']
    except KeyError:
        dt = None
    in_cfg['resampling_time'] = dt

    # -------------------------------------------------------------------------
    # Integrity of caibration parameters
    if in_cfg['flags']['calibrate_flag'] or ignore_flags:
        probe_names = []
        cal = cfg['calibration']

        # Label the LAFs using the physical locations library. Will trigger
        # checking the location library.
        if 'label_data' in cal and cal['label_data']:
            label_data_flag = True

        # External data stream for reference probes
        if 'external_fields' in cal and cal['external_fields']:
            # Verify if the external data was provided and exists
            if dir_ext:
                ext_fname = os.path.join(dir_ext,
                                         cfg['directories']['filename_external'])
                if os.path.isfile(ext_fname):
                    # Make sure the file is a netcdf
                    if not ext_fname.endswith('.nc'):
                        mess = ('Config file indicates to use external data, '
                                'but a netcdf was not found at: ' + ext_fname)
                        raise FileNotFoundError()

                    # Build the path to the file.
                    in_cfg['external_data'] = os.path.join(dir_ext, ext_fname)

                    probe_names.extend(cal['external_fields'])
                    cal['external_flag'] = True

                else:
                    mess = ('Config file indicates to use external data, but no file '
                            'was found at: ' + ext_fname)
                    print(mess)
                    raise FileNotFoundError()
            # Both situations mean that no external data should be processed.
            else:
                cal['external_flag'] = False
        else:
            cal['external_flag'] = False

        # Check for built-in probes
        if cal['builtin_probe_names']['probe1Temperature']:
            probe_names.append(cal['builtin_probe_names']['probe1Temperature'])
            cal['builtin_flag'] = True
        if cal['builtin_probe_names']['probe2Temperature']:
            probe_names.append(cal['builtin_probe_names']['probe2Temperature'])
            cal['builtin_flag'] = True
        if (not cal['builtin_probe_names']['probe1Temperature'] and
                not cal['builtin_probe_names']['probe2Temperature']):
            cal['builtin_flag'] = False

        if not cal['builtin_flag'] and not cal['external_flag']:
            print('No reference data was provided for calibration. Exiting.')
            return None, None

        # Valid options
        # Single-ended methods
        single_methods = ['ols single',
                          'wls single',
                          'matrix',
                          ]
        # Double ended methods
        double_methods = ['ols double',
                          'wls double',
                          'temp_matching']
        # List of all valid methods
        valid_meths = copy.deepcopy(single_methods)
        valid_meths.extend(double_methods)

        # Only two valid ways of labeling a bath
        valid_bath_types = ['calibration', 'validation']

        # Method must be supported
        if cal['method'] not in valid_meths:
            mess = ('The calibration method, {cm}, is not in the list of '
                    'supported calibration methods: {vmeths}')
            raise KeyError(mess.format(cm=cal['method'], vmeths=valid_meths))

        if cal['method'] in single_methods:
            cal['double_ended'] = False
        elif cal['method'] in double_methods:
            cal['double_ended'] = True
            if 'bw_channel' not in cal:
                mess = ('Double ended methods require a backwards channel.')
                raise KeyError(mess)
            if not dt:
                mess = ('A resampling time must be provided when performing '
                        'a double ended calibration.')
                raise ValueError(mess)
            if 'fixed_shift' in cal:
                if not isinstance(cal['fixed_shift'], int):
                    try:
                        cal['fixed_shift'] = int(cal['fixed_shift'])
                    except TypeError as te:
                        print('fixed_shift could not be coerced into an int')
                        cal['fixed_shift'] = None
            else:
                cal['fixed_shift'] = None

        # Single-ended explicit matrix inversion only accepts 3 calibration baths.
        if cal['method'] == 'matrix':
            cal_baths = [c for c in cal['library'] if cal['library'][c]['type'] == 'calibration']
            if not len(cal_baths) == 3:
                mess = ('The explicit matrix inversion for the single-ended '
                        'fibers must have exactly three reference sections '
                        'of type "calibration". Found: \n{cref}')
                raise ValueError(mess.format(cref=cal_baths))

        # Check integrity of each calibration section
        # Error messages
        miss_ref_sen_mess = ('The reference sensor, {r}, for {cl} was '
                             'not in the list of provided sensors: '
                             '{slist}')
        unkn_cal_mess = ('The calibration type, {ct}, for {cl} is not '
                         'recognized. Valid options are {valopt}')
        missing_mess = ('LAF for {cl} was not defined by pair of LAF, '
                        'Found intsead: {lib}')

        for cloc in cal['library']:
            # Get details for this section
            calsect = cal['library'][cloc]
            refsen = calsect['ref_sensor']
            bath_type = calsect['type']

            # The reference sensor must be listed in the built-in probes or
            # external sensors list.
            if refsen not in probe_names:
                raise KeyError(miss_ref_sen_mess.format(r=refsen,
                                                        cl=cloc,
                                                        slist=probe_names))
            # Bath types must be valid
            if bath_type not in valid_bath_types:
                raise KeyError(unkn_cal_mess.format(ct=bath_type,
                                                    cl=cloc,
                                                    valopt=valid_bath_types))

            # All locations are defined by a pair of LAFs.
            assert 'LAF' in calsect, 'No LAFs provided for ' + cloc
            assert len(calsect['LAF']) == 2, missing_mess.format(cl=cloc,
                                                                 lib=calsect)
            if any(np.isnan(calsect['LAF'])):
                del cal['library'][cloc]
                print(cloc + ' will not be labeled due to NaNs in LAF. Check library.')
                continue

         # Calibration field
        in_cfg['calibration'] = copy.deepcopy(cal)

    # -------------------------------------------------------------------------
    # Prepare each requested experiment.
    for exp_name in experiment_names:
        # Check the experiment name:
        if '_' in exp_name:
            mess = ('Experiment names cannot contain underscores. '
                    'This character is reserved by the pyfocs naming scheme.')
            raise ValueError(mess)

        # Create directories if they don't exist and
        # errors if needed data are not found.

        # --------
        # Raw xml files
        if 'raw_xml' in remote_dir:
            dir_raw_xml = os.path.join(dir_pre_remote,
                                       exp_name, cfg['directories']['raw'])
        else:
            dir_raw_xml = os.path.join(dir_pre_local,
                                       exp_name, cfg['directories']['raw_xml'])

        # Throw an error if raw files should be read but directory isn't found
        if (not os.path.exists(dir_raw_xml)) and (cfg['flags']['archiving_flag']):
            mess = ('Creating archived data is on but the raw xml data '
                    'directory was not found at ' + dir_raw_xml)
            raise FileNotFoundError(mess)

        # --------
        # Archived tar.gz of xmls
        if 'archive' in remote_dir:
            dir_archive = os.path.join(dir_pre_remote,
                                       exp_name, cfg['directories']['archive'])
        else:
            dir_archive = os.path.join(dir_pre_local,
                                       exp_name, cfg['directories']['archive'])

        if (not os.path.exists(dir_archive)):
            # create the folder for the archived files if it doesn't already
            # exist and archived files will be created
            if cfg['flags']['archiving_flag']:
                os.makedirs(dir_archive)
                print('Archived directory not found. Created a new one at ' + dir_archive)
            # throw error if archived files are needed but neither found nor created
            elif cfg['flags']['archive_read_flag']:
                mess = ('Reading archived data is on but the archived data '
                        'directory was not found at ' + dir_archive)
                raise FileNotFoundError(mess)

        # --------
        # Raw xmls in netcdf format
        if 'raw_netcdf' in remote_dir:
            dir_raw_netcdf = os.path.join(dir_pre_remote,
                                          exp_name, cfg['directories']['raw_netcdf'])
        else:
            dir_raw_netcdf = os.path.join(dir_pre_local,
                                          exp_name, cfg['directories']['raw_netcdf'])

        if not os.path.exists(dir_raw_netcdf):
            # Create the folder for the raw netcdf files if it doesn't already
            # exist and raw netcdf files will be created.
            if cfg['flags']['archive_read_flag']:
                os.makedirs(dir_raw_netcdf)
                print('Calibrated directory not found. Created a new one at ' + dir_raw_netcdf)
            # throw error if raw netcdf files are needed but neither found
            # nor created
            elif cfg['flags']['calibrate_flag']:
                mess = ('Calibration is on but the raw netcdf data '
                        'directory was not found at ' + dir_raw_netcdf)
                raise FileNotFoundError(mess)
        # --------
        # Calibrated temperature
        if 'calibrated' in remote_dir:
            dir_cal = os.path.join(dir_pre_remote,
                                   exp_name, cfg['directories']['calibrated'])
        else:
            dir_cal = os.path.join(dir_pre_local,
                                   exp_name, cfg['directories']['calibrated'])

        if not os.path.exists(dir_cal):
            # create the folder for the calibrated files if it doesn't already
            # exist and calibrated files will be created
            if cfg['flags']['calibrate_flag']:
                os.makedirs(dir_cal)
                print('Calibrated directory not found. Created a new one at '
                      + dir_cal)
            elif cfg['flags']['final_flag']:
                mess = ('Finalizing is on but the calibrated data '
                        'directory was not found at ' + dir_cal)
                raise FileNotFoundError(mess)

        # --------
        # Final data (converted into just the labeled segments with
        # a physical location)
        if 'final' in remote_dir:
            dir_final = os.path.join(dir_pre_remote,
                                     exp_name, cfg['directories']['final'])
        else:
            dir_final = os.path.join(dir_pre_local,
                                     exp_name, cfg['directories']['final'])

        # Create the folder for the final files if it doesn't already exist
        if ((not os.path.exists(dir_final))
                and ((cfg['flags']['calibrate_flag'])
                     or (cfg['flags']['final_flag']))):
            os.makedirs(dir_final)
            print('Final directory not found. Created a new one at ' + dir_final)

        # --------
        # Graphics folder
        if 'graphics' in remote_dir:
            dir_graphics = os.path.join(dir_pre_remote,
                                        exp_name, cfg['directories']['graphics'])
        else:
            dir_graphics = os.path.join(dir_pre_local,
                                        exp_name, cfg['directories']['graphics'])

        # assemble internal config for each dts folder within the
        # experiment folder
        in_cfg[exp_name] = {}
        in_cfg[exp_name]['archive'] = copy.deepcopy(cfg['archive'])
        in_cfg[exp_name]['archive']['channelName'] = cfg['directories']['channelName']
        in_cfg[exp_name]['archive']['sourcePath'] = dir_raw_xml
        in_cfg[exp_name]['archive']['targetPath'] = dir_archive
        in_cfg[exp_name]['directories'] = copy.deepcopy(cfg['directories'])
        in_cfg[exp_name]['directories']['dirArchive'] = dir_archive
        in_cfg[exp_name]['directories']['dirRawNetcdf'] = dir_raw_netcdf
        in_cfg[exp_name]['directories']['dirCalibrated'] = dir_cal
        in_cfg[exp_name]['directories']['dirFinal'] = dir_final
        in_cfg[exp_name]['directories']['dirGraphics'] = dir_graphics

    # -------------------------------------------------------------------------
    # Integrity of the location library

    # Remind the user that multicore fibers are no longer supported
    if 'coretype' in in_cfg:
        raise ValueError('Multicore fibers are no longer supported.')

    # -------------------------------------------------------------------------
    # Labeling sections and physical coordinates
    # Prepare relevant parameters for finalizing
    if in_cfg['flags']['final_flag'] or label_data_flag or ignore_flags:
        # Indicate that we need to check the integrity of the location library.
        check_loc_library = True
        if 'phys_locs_labeling' in cfg['dataProperties']:
            if cfg['dataProperties']['phys_locs_labeling'] == 'stacked':
                stacked = True
        else:
            stacked = False

        if not dt:
            mess = 'A resampling time must be provided when finalizing the data.'
            raise KeyError(mess)

        # Make sure the physical locations exist.
        try:
            phys_locs = cfg['dataProperties']['phys_locs']
            in_cfg['phys_locs'] = phys_locs
        except KeyError as kerr:
            mess = ('The phys_locs field in dataProperties is empty but '
                    'labeling physical coordinates is turned on.')
            print(mess)
            raise kerr

        # Remind the user that documenting the calibration has changed.
        if 'calibration' in phys_locs:
            mess = ('Including the calibration locations in the location '
                    'library is no longer supported.')
            print(mess)
    else:
        check_loc_library = False

    # Error messages for the assert statements.
    missing_mess = ('Coordinates for {ploc} were not defined by pairs of LAF, '
                    'x, y, and z in the location library. Found intsead:\n'
                    '{lib}')

    # Check the integrity of the location library.
    if check_loc_library and not stacked:
        for loc_type_cur in phys_locs:
            lib[loc_type_cur] = {}
            for l in cfg['location_library']:
                if loc_type_cur == cfg['location_library'][l]['loc_type']:
                    lib[loc_type_cur][l] = cfg['location_library'][l]

                    # All locations are defined by a pair of LAFs.
                    assert 'LAF' in lib[loc_type_cur][l], 'No LAFs provided for ' + l
                    assert len(lib[loc_type_cur][l]['LAF']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                    if any(np.isnan(lib[loc_type_cur][l]['LAF'])):
                        del lib[loc_type_cur][l]
                        print(l + ' will not be labeled due to NaNs in LAF. Check library.')
                        continue

                    # All physical coordinates are defined by pairs of x, y, z
                    if (cfg['flags']['final_flag']
                            and loc_type_cur in phys_locs):
                        assert 'x_coord' in lib[loc_type_cur][l], missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                        assert 'y_coord' in lib[loc_type_cur][l], missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                        assert 'z_coord' in lib[loc_type_cur][l], missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])

                        assert len(lib[loc_type_cur][l]['x_coord']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                        assert len(lib[loc_type_cur][l]['y_coord']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                        assert len(lib[loc_type_cur][l]['z_coord']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])

            if not bool(lib[loc_type_cur]):
                print(loc_type_cur + ' was not found in location library.')

        # Asserts that lib is an iterable list with stuff in it.
        mess = 'No items found in location library.'
        # Returns False if it is emtpy, True if is not.
        assert bool(lib), mess

    elif check_loc_library and stacked:
        for loc_type_cur in phys_locs:
            lib[loc_type_cur] = {}
            for l in cfg['location_library'][loc_type_cur]:
                lib[loc_type_cur][l] = cfg['location_library'][loc_type_cur][l]

                # All locations are defined by a pair of LAFs.
                assert 'LAF' in lib[loc_type_cur][l], 'No LAFs provided for ' + l
                assert len(lib[loc_type_cur][l]['LAF']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                if any(np.isnan(lib[loc_type_cur][l]['LAF'])):
                    del lib[loc_type_cur][l]
                    print(l + ' will not be labeled due to NaNs in LAF. Check library.')
                    continue

                # All physical coordinates are defined by pairs of x, y, z
                if (cfg['flags']['final_flag']
                        and loc_type_cur in phys_locs):
                    assert 'x_coord' in lib[loc_type_cur][l], missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                    assert 'y_coord' in lib[loc_type_cur][l], missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                    assert 'z_coord' in lib[loc_type_cur][l], missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])

                    assert len(lib[loc_type_cur][l]['x_coord']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                    assert len(lib[loc_type_cur][l]['y_coord']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])
                    assert len(lib[loc_type_cur][l]['z_coord']) == 2, missing_mess.format(ploc=l, lib=lib[loc_type_cur][l])

            if not bool(lib[loc_type_cur]):
                print(loc_type_cur + ' was not found in location library.')

        # Asserts that lib is an iterable list with stuff in it.
        mess = 'No items found in location library.'
        # Returns False if it is emtpy, True if is not.
        assert bool(lib), mess

    # -------------------------------------------------------------------------
    # Further variables to assess.

    # Step loss corrections
    if ('step_loss_LAF' in cfg['dataProperties']
            and 'step_loss_correction' in cfg['dataProperties']):
        in_cfg['step_loss'] = {}
        steploss_laf = np.atleast_1d(cfg['dataProperties']['step_loss_LAF']).astype('float')
        steploss_corr = np.atleast_1d(cfg['dataProperties']['step_loss_correction']).astype('float')
        for sl_laf, sl_co in zip(steploss_laf, steploss_corr):
            # Make sure the step loss corrections are numeric
            if np.isnan(sl_laf) or np.isnan(sl_co):
                step_loss_flag = False
                in_cfg['step_loss'] = {}
                break

            else:
                step_loss_flag = True
        in_cfg['step_loss']['flag'] = step_loss_flag
        in_cfg['step_loss']['LAF'] = steploss_laf
        in_cfg['step_loss']['correction'] = steploss_corr
    else:
        step_loss_flag = False
        in_cfg['step_loss'] = {}
        in_cfg['step_loss']['flag'] = step_loss_flag

    # Fiber limits
    if 'fiber_limits' in cfg['dataProperties']:
        if cfg['dataProperties']['fiber_limits']['min_limit']:
            in_cfg['min_fiber_limit'] = cfg['dataProperties']['fiber_limits']['min_limit']
        else:
            in_cfg['min_fiber_limit'] = 0

        if cfg['dataProperties']['fiber_limits']['max_limit']:
            in_cfg['max_fiber_limit'] = cfg['dataProperties']['fiber_limits']['max_limit']
        else:
            in_cfg['max_fiber_limit'] = -1

    # Determine if a file suffix was provided.
    if 'suffix' in cfg['directories']:
        in_cfg['outname_suffix'] = cfg['directories']['suffix']
        if '_' in in_cfg['outname_suffix']:
            mess = ('File suffixes cannot contain underscores. '
                    'This character is reserved by the pyfocs naming scheme.')
            raise ValueError(mess)
    else:
        in_cfg['outname_suffix'] = None

    if ('fiber_limits' in cfg['dataProperties']
            and not in_cfg['outname_suffix']):
        warn = ('Fiber limits were provided without a suffix. This may cause '
                'issues with overwriting data for multicore fibers.')
        print(warn)

    if 'min_fiber_limit' not in in_cfg:
        in_cfg['min_fiber_limit'] = 0
    if 'max_fiber_limit' not in in_cfg:
        in_cfg['max_fiber_limit'] = -1

    # Determine write mode:
    try:
        write_mode = cfg['flags']['write_mode']
    except KeyError:
        write_mode = 'overwrite'
    # Add check here that write_mode has an expected value.
    in_cfg['write_mode'] = write_mode

    # Channels to process -- this should be on the outside of the script
    in_cfg['channelNames'] = cfg['directories']['channelName']

    return in_cfg, lib
