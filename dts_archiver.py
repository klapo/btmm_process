import os
import subprocess
import datetime
import sys
import glob

# Script to tar and gzip the Ultima data

# ------------------------------------------------------------------------------
# System stuff
# ------------------------------------------------------------------------------
# Path of the python file
def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))
scriptPath = get_script_path()

# Path to unison.exe
unisonPath = os.path.join(scriptPath, 'Unison', 'Unison-2.40.61 Text.exe')

# Add the unison-required libraries to the path
unisonLibs = os.path.join(scriptPath, 'libs', 'gtk-runtime-2.16.6.0', 'Gtk', 'bin')
if unisonLibs not in sys.path:
    sys.path.append(unisonLibs)
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# Define paths here. Use single quotes as python expects strings.
# ------------------------------------------------------------------------------
# Mode to run the script in
mode = 'archiving'
# Path to search for local data.
sourcePath = '/Users/karllapo/Desktop/software/DTS_archive'
# Path to where you want the data to end up
targetPath = '/Users/karllapo/Desktop/archive'
# Root variables for the unison command. rootLocal is where to find the
# local archive. rootBackup is where to find the backup drive. rootMobile is
# where to find removable disk. Both back up locations may not be needed. In
# that case leave the unneeded path as an empty string, e.g., ''. Logfiles are
# where you want the log of the synchronisation to be written.
rootLocal = targetPath
rootMobile = '/Users/karllapo/Desktop/proj/test_archive'
logfileMobile = rootMobile + '_logfile.txt'
# Names of the channels. The script will search for targetPath/channel_X.
channel_1 = 'channel 1'
channel_2 = 'channel 2'
channel_3 = 'channel 3'
channel_4 = 'channel 4'
channels = [channel_1, channel_2, channel_3, channel_4]

# ------------------------------------------------------------------------------
# Sub function -- actually zips and archives data
# ------------------------------------------------------------------------------
def archiveTool(outFile, sourceFile):
    '''
    This helper function creates the command to tar.gz the DTS XML files.
    INPUT:
        outFile = Name of the tar.gz file to create
        sourceFile = Name of the source files to compress. It MUST terminate with a
            wildcare (*) (I think).
    OUTPUT:
        flag = True if the archive was sucessfully created. False if an error was
            detected.
    '''
    # Check that the directory actually exists.
    if os.path.isdir(sourcePath):
        print('Source files: ' + sourceFile)
        print('Archiving to: ' + outFile)

        # We are on a windows machine (likely the Ultimas/XT)
        if os.name == 'nt':
            mergeCommand = ['bsdtar', '-czf', outFile] + (glob.glob(sourceFile))
            subprocess.check_output(['bsdtar -czf ' + outFile + ' ' + sourceFile])
            try:
                p = subprocess.check_output(mergeCommand)
            # The tar command indicated an error.
            except subprocess.CalledProcessError:
                print('tar failed with non-zero exit.')
                return(False)

        # We are on a unix system (likely archiving post-sampling)
        elif os.name == 'posix':
            mergeCommand = ['tar', '-zcvf', outFile] + (glob.glob(sourceFile))
            try:
                p = subprocess.check_output(mergeCommand)
            # The tar command indicated an error.
            except subprocess.CalledProcessError:
                print('tar failed with non-zero exit.')
                return(False)
        print('')
#         print('Deleting original files...')
#         sys('del /Q ' + sourceFile)
        return(True)

    # No files were found, exit and notify.
    else:
        print('Could not find files in specified paths. Please check sourcePath')
        return(False)


# ------------------------------------------------------------------------------
# Archive data
# ------------------------------------------------------------------------------
for ch in channels:
    channelPath = os.path.join(sourcePath, ch)

    ########
    # Active: Meant to be run with a cron job and uses the current time.
    if mode == 'active':
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
        outFile = os.path.join(targetPath, channel_1 + '_' + dateFileName + '.tar.gz')
        sourceFile = os.path.join(sourcePath, channel_1, channel_1 + '_' + dateFileName + '*')

        # zip the data and move to archive
        archiveTool(outFile, sourceFile)

    ########
    # Archive: To archive previously aquired data.
    elif mode == 'archiving':
        # Check if the channel directory exists.
        if os.path.isdir(channelPath):
            contents = os.listdir(channelPath)
        # If it doesn't, move on to the next channel
        else:
            continue
        # Only select xml files
        contents = [c for c in contents if '.xml' in c]
        # Sort the file list alphabetically.
        contents.sort()

        # First datetimes
        t = contents[0]
        t = t.split('_')[-1]
        t = t.split('.')[0]
        year = t[0:4]
        month = t[4:6]
        day = t[6:8]
        hour = t[8:10]
        dtInit = datetime.datetime(int(year), int(month), int(day), int(hour), 0)

        # Last datetime
        t = contents[-1]
        t = t.split('_')[-1]
        t = t.split('.')[0]
        year = t[0:4]
        month = t[4:6]
        day = t[6:8]
        hour = t[8:10]
        dtFinal = datetime.datetime(int(year), int(month), int(day), int(hour), 0)

        # Span the time found in the specified directory
        dt = dtInit
        while dt <= dtFinal:
            yyyy = dt.year
            mm = dt.month
            dd = dt.day

            # Hours require special attention
            hh = dt.hour
            if hh < 10:
                hh = '0' + str(hh)
            else:
                hh = str(hh)

            # Create file names for this hour
            dateFileName = '_' + str(yyyy) + str(mm) + str(dd) + '-' + hh
            outFile = os.path.join(targetPath, channel_1 + '_' + str(yyyy) +
                str(mm) + str(dd) + '-' + hh + '.tar.gz')
            sourceFile = os.path.join(sourcePath, channel_1,
                channel_1 + '_' + str(yyyy) + str(mm) + str(dd) + hh + '*')
            # Zip and archive this time period
            archiveTool(outFile, sourceFile)

            # Iterate the time
            dt = dt + datetime.timedelta(hours=1)

    print('Done with ' + ch + '. Backup files in: ' + targetPath)
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Sync to the mobile backup drive.
if os.path.isdir(rootMobile):
    print('Backing up archives to mobile drive')
    print('Syncing ' + rootLocal + ' to ' + rootMobile)

    # Check the os. Unix = rsync; Windos = Unison.
    if os.name == 'nt':
        mergeCommand = [unisonPath, rootLocal, rootMobile,
                        '-logfile ' + logfileMobile, ' -force ' + rootLocal,
                        ' -batch -nodeletion ' + rootMobile]
        subprocess.check_output(mergeCommand)
        try:
            p = subprocess.check_output(mergeCommand)
        # The tar command indicated an error.
        except subprocess.CalledProcessError:
            print('Warning: syncing to the mobile backup failed.')

    elif os.name == 'posix':
        # Add a trailing backslash to make rsync behave as expected.
        if not rootMobile[-1] == '/':
            rootMobile = rootMobile + '/'
        if not rootLocal[-1] == '/':
            rootLocal = rootLocal + '/'
        mergeCommand = ['rsync', '-az', rootLocal, rootMobile]
        try:
            p = subprocess.check_output(mergeCommand)
        # The tar command indicated an error.
        except subprocess.CalledProcessError:
            print('Warning: syncing to the mobile backup failed.')

else:
    print('Warning: Mobile back-up was not found in the specified path.')
# ------------------------------------------------------------------------------
