import os
import datetime
import glob
import tarfile
import dirsync


# ------------------------------------------------------------------------------
# make_tarfile -- actually zips and archives data
def make_tarfile(tarName, filesToZip):
    '''
    This helper function creates the command to tar.gz the DTS XML files.
    INPUT:
        tarName = Name of the tar.gz file to create
        filesToZip = List with the name of the source files to compress.
    '''

    print('Archiving ' + tarName)

    # Open the tarball and prepare it for writing
    # and compress the xml files
    with tarfile.open(tarName, "w:gz") as tar:
        for f in filesToZip:
            tar.add(f, arcname=os.path.basename(f))


# ------------------------------------------------------------------------------
# backup_sync -- sync to an external backup drive.
def backup_sync(dirMobile, dirLocal, logfile):

    if os.path.isdir(dirMobile):
        os.chdir(dirMobile)
        print('Backing up archives to mobile drive')
        print('Syncing ' + dirLocal + ' to ' + dirMobile)

        dirsync.sync(dirLocal, dirMobile, 'diff')
        dirsync.sync(dirLocal, dirMobile, 'sync')

    else:
        print('Warning: Mobile back-up was not found in the specified path.')

    return()


# ------------------------------------------------------------------------------
# Rounds a datetime object to the nearest minute delta
def round_dt(dt, delta, type='floor'):
    '''
    dt - datetime object
    delta - rounding interval in minutes (e.g., nearest 15, delta=15)
    type - specifies if we round up or down
    '''
    if type == 'floor':
        dt = dt - datetime.timedelta(minutes=dt.minute % delta,
                                     seconds=dt.second,
                                     microseconds=dt.microsecond)
    elif type == 'ceil':
        dt = dt + datetime.timedelta(minutes=delta - dt.minute % delta - 1,
                                     seconds=60 - dt.second - 1,
                                     microseconds=10**6 - dt.microsecond)
    else:
        raise ValueError('Unrecognized dt rounding type. Valid options are'
                         'floor and ceil.')
    return(dt)


# ------------------------------------------------------------------------------
# Formats a datetime object into its components pieces or a string
def dt_strip(dt, str_convert=False):
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    sec = dt.second
    msec = dt.microsecond

    if str_convert:
        year = str(dt.year)

        if month < 10:
            month = '0' + str(month)
        else:
            month = str(month)

        if day < 10:
            day = '0' + str(day)
        else:
            day = str(day)

        if hour < 10:
            hour = '0' + str(hour)
        else:
            hour = str(hour)

        if minute < 10:
            minute = '0' + str(minute)
        else:
            minute = str(minute)

        if sec < 10:
            sec = '0' + str(sec)
        else:
            sec = str(sec)

        if msec < 10:
            msec = '0' + str(msec)
        else:
            msec = str(msec)

    return(year, month, day, hour, minute, sec, msec)
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# Archive data
# ------------------------------------------------------------------------------
def archiver(cfg):
    '''
    Script to tar and gzip the Ultima data.
    Requires a configuration file to run.
    '''

    # Read the configure file for the archiver arguments
    mode = cfg['archive']['mode']
    for ch in cfg['archive']:
        channels = cfg['archive']['channelName']
    sourcePath = cfg['archive']['sourcePath']
    targetPath = cfg['archive']['targetPath']
    delta_minutes = cfg['archive']['archiveInterval']

    # Determine if we are backing up to an external directory
    try:
        dirBackUp = cfg['archive']['dirBackUp']
        if os.path.isdir(dirBackUp):
            externalBackUp = True
            logfile = cfg['archive']['logfile']
        else:
            externalBackUp = False
            logfile = []
    except KeyError:
        print('No backup directory provided.')
        externalBackUp = False
        logfile = []

    # Determine if the archiver should clean up the original data directory
    try:
        cleanup_flag = cfg['archive']['cleanup_flag']
    except KeyError:
        cleanup_flag = False

    for ch in channels:
        channelPath = os.path.join(sourcePath, ch)

        ########
        # Active: Meant to be run with a cron job and uses the current time.
        if mode == 'active':
            print('WARNING: active mode has not been tested!'
                  + ' It will probably crash. Sorry :(')
            now = datetime.datetime.now()
            yyyy = now.year
            mm = now.month
            dd = now.dd

            # Hours require special attention
            hh = now.hour
            if hh < 10:
                hh = '0' + str(hh)

            # Date to zip and archive
            dateFileName = '_' + yyyy + mm + dd + '-' + hh

            # Define file names using current time
            outFile = os.path.join(targetPath, ch + '_'
                                   + dateFileName + '.tar.gz')
            sourceFile = os.path.join(sourcePath, ch, ch + '_'
                                      + dateFileName + '*')

            # zip the data and move to archive
            make_tarfile(outFile, sourceFile)

        ########
        # Archive: To archive previously aquired data.
        elif mode == 'archiving':
            # Check if the channel directory exists.
            if os.path.isdir(channelPath):
                contents = os.listdir(channelPath)
            # If it doesn't, move on to the next channel
            else:
                print('Did not find ' + ch)
                continue
            # Only select xml files
            contents = [c for c in contents if '.xml' in c]
            # Sort the file list alphabetically.
            contents.sort()

            # First datetime of the raw data
            t = contents[0]
            t = t.split('_')[-1]
            t = t.split('.')[0]
            year = t[0:4]
            month = t[4:6]
            day = t[6:8]
            hour = t[8:10]
            minute = t[10:12]
            sec = t[12:14]
            msec = t[14:16]
            dtInit = datetime.datetime(int(year), int(month),
                                       int(day), int(hour),
                                       int(minute), int(sec),
                                       int(msec) * 1000)

            # First datetime of the raw data
            t = contents[-1]
            t = t.split('_')[-1]
            t = t.split('.')[0]
            year = t[0:4]
            month = t[4:6]
            day = t[6:8]
            hour = t[8:10]
            minute = t[10:12]
            sec = t[12:14]
            msec = t[14:16]
            dtFinal = datetime.datetime(int(year), int(month),
                                        int(day), int(hour),
                                        int(minute), int(sec),
                                        int(msec) * 1000)

            # First time step interval
            dt1 = round_dt(dtInit, delta_minutes, type='floor')
            dt2 = round_dt(dtInit, delta_minutes, type='ceil')

            # Round up to the nearest interval for the end
            dtFinal = round_dt(dtFinal, delta_minutes, type='ceil')
            # Empty container for the files in this interval
            interval_contents = []

            # Iterate through the (date) sorted list of raw xml files
            for xml_counts, c in enumerate(contents):
                # Split the file name string into the datetime components
                t = c.split('_')[-1]
                t = t.split('.')[0]
                year = t[0:4]
                month = t[4:6]
                day = t[6:8]
                hour = t[8:10]
                minute = t[10:12]
                sec = t[12:14]

                if len(t) > 14:
                    msec = t[14:16]
                else:
                    msec = 0

                # Convert the file name into a datetime object
                dt = datetime.datetime(int(year), int(month),
                                       int(day), int(hour),
                                       int(minute), int(sec),
                                       int(msec))

                if dt < dt2 and dt > dt1:
                    interval_contents.append(os.path.join(sourcePath, ch, c))

                # We have spanned this interval, save the data and move on
                elif dt > dt2:
                    # Create file names for this hour
                    year, month, day, hour, minute, _, _ = dt_strip(dt1, str_convert=True)

                    dateFileName = '_' + year + month + day + '-' + hour + minute
                    outFile = os.path.join(targetPath, ch + dateFileName + '.tar.gz')

                    # Check if any files fall within the interval
                    if len(interval_contents) == 0:
                        print('No xml files in the interval: ' + str(dt1))
                    else:
                        make_tarfile(outFile, interval_contents)

                    dt1 = dt2
                    dt2 = dt2 + datetime.timedelta(minutes=delta_minutes)

                    # Determine if the xml files should be removed
                    if cleanup_flag:
                        print('Cleaning up the raw xml files...')
                        for f in sourceFile:
                            os.remove(f)

                    interval_contents = []

                # We reached the end of the file list, save and exit.
                if xml_counts == len(contents) - 1:
                    # Create file names for this hour
                    year, month, day, hour, minute, _, _ = dt_strip(dt1, str_convert=True)

                    dateFileName = '_' + year + month + day + '-' + hour + minute
                    outFile = os.path.join(targetPath, ch + dateFileName + '.tar.gz')
                    sourceFile = interval_contents
                    make_tarfile(outFile, sourceFile)

                    # Determine if the xml files should be removed
                    if cleanup_flag:
                        print('Cleaning up the raw xml files...')
                        for f in sourceFile:
                            os.remove(f)

                    print('Done with ' + ch + '.')

    ########
    # Back up to the external drive if specified.
    if externalBackUp:
        backup_sync(dirBackUp, targetPath, logfile)
# ------------------------------------------------------------------------------
