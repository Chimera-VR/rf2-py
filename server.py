
"""
Inherit Python mapping of The Iron Wolf's rF2 Shared Memory Tools
and add access functions to it.
"""
# pylint: disable=invalid-name

import psutil

try:
    from . import rF2data
except ImportError:
    import rF2data

def getAll():
    """ Find all rFactor servers """
    serverPids = []

    for pid in psutil.pids():
        try:
            p = psutil.Process(pid)
        except psutil.NoSuchProcess:
            continue
        if p.name().lower().startswith('rfactor2 dedicated.exe'):
            serverPids.append(pid)
            break
    return serverPids

def Cbytestring2Python(bytestring):
    """
    C string to Python string
    """
    try:
        return bytes(bytestring).partition(b'\0')[0].decode('utf_8').rstrip()
    except BaseException:
        pass
    try:    # Codepage 1252 includes Scandinavian characters
        return bytes(bytestring).partition(b'\0')[0].decode('cp1252').rstrip()
    except BaseException:
        pass
    try:    # OK, struggling, just ignore errors
        return bytes(bytestring).partition(b'\0')[
            0].decode('utf_8', 'ignore').rstrip()
    except Exception as e:
        print('Trouble decoding a string')
        print(e)

class Pod(rF2data.ServerInfo):
    """
    API for rF2 shared memory
    """
    __HELP = "\nShared Memory is installed by Crew Chief or you can install it yourself.\n" \
        "Please update rFactor2SharedMemoryMapPlugin64.dll, see\n" \
        "https://forum.studio-397.com/index.php?threads/rf2-shared-memory-tools-for-developers.54282/"

    sharedMemoryVerified = False
    minimumSupportedVersionParts = ['3', '6', '0', '0']
    rf2_pid = None          # Once we've found rF2 running
    rf2_pid_counter = 0     # Counter to check if running
    rf2_running = False

    def __init__(self, pid):
        rf2_pid = pid
        rF2data.ServerInfo.__init__(self, pid)
        self.versionCheckMsg = self.versionCheck()

    def versionCheck(self):
        """
        Lifted from
        https://gitlab.com/mr_belowski/CrewChiefV4/blob/master/CrewChiefV4/RF2/RF2GameStateMapper.cs
        and translated.
        """
        self.sharedMemoryVerified = False    # Verify every time it is called.

        versionStr = Cbytestring2Python(self.Rf2Ext.mVersion)
        msg = ''

        if versionStr == '':
            msg = "\nrFactor 2 Shared Memory not present." + self.__HELP
            return msg

        versionParts = versionStr.split('.')
        if len(versionParts) != 4:
            msg = "Corrupt or leaked rFactor 2 Shared Memory.  Version string: " \
                + versionStr + self.__HELP
            return msg

        smVer = 0
        minVer = 0
        partFactor = 1
        for i in range(3, -1, -1):
            versionPart = 0
            try:
                versionPart = int(versionParts[i])
            except BaseException:
                msg = "Corrupt or leaked rFactor 2 Shared Memory version.  Version string: " \
                    + versionStr + self.__HELP
                return msg

            smVer += (versionPart * partFactor)
            minVer += (int(self.minimumSupportedVersionParts[i]) * partFactor)
            partFactor *= 100

        if smVer < minVer:
            minVerStr = ".".join(self.minimumSupportedVersionParts)
            msg = "Unsupported rFactor 2 Shared Memory version: " \
                + versionStr \
                + "  Minimum supported version is: " \
                + minVerStr + self.__HELP
        else:
            msg = "\nrFactor 2 Shared Memory\nversion: " + versionStr + " 64bit."
            if self.Rf2Ext.mDirectMemoryAccessEnabled:
                if self.Rf2Ext.mSCRPluginEnabled:
                    msg += "  Stock Car Rules plugin enabled. (DFT:%d" % \
                        self.Rf2Ext.mSCRPluginDoubleFileType
                else:
                    msg += "  DMA enabled."
            if self.Rf2Ext.is64bit == 0:
                msg += "\nOnly 64bit version of rFactor 2 is supported."
            else:
                self.sharedMemoryVerified = True

        return msg

    def isRF2running(self, find_counter=200, found_counter=5):
        """
        Both "rFactor 2 Launcher" and "rf2" processes are found
        whether it's the launcher or the game that's running BUT
        rfactor2.exe is only present if the game is running.
        Beacuse this takes some time, control how often it's checked using:
        find_counter: how often to check if rF2 is not running
        found_counter: how often to check once rF2 is running
        """
        if self.rf2_pid_counter == 0:  # first time
            self.rf2_pid_counter = find_counter
        if self.isSharedMemoryAvailable():
            # No need to check if Shared Memory is OK!
            self.rf2_running = True
        if self.rf2_pid_counter >= found_counter:
            self.rf2_pid_counter = 0
            try:
                p = psutil.Process(self.rf2_pid)
            except psutil.NoSuchProcess:
                self.rf2_pid = None
                return False
            if p.name().lower().startswith('rfactor2 dedicated.exe'):
                self.rf2_running = True
        self.rf2_pid_counter += 1
        return self.rf2_running
    
    def isSharedMemoryAvailable(self):
        """
        True: The correct memory map is loaded
        """
        self.versionCheck()
        return self.sharedMemoryVerified

    def isTrackLoaded(self):
        """
        True: rF2 is running and the track is loaded
        """
        started = self.Rf2Ext.mSessionStarted
        return started != 0

    def getDrivers(self):
        """
        Return array of drivers
        """
        return self.Rf2Scor.mVehicles

    def playersVehicleTelemetry(self):
        """
        Return telemetry
        """
        return self.Rf2Tele.mVehicles

    def close(self):
        # This didn't help with the errors
        try:
            self._rf2_tele.close()
            self._rf2_scor.close()
            self._rf2_ext.close()
        except BufferError:  # "cannot close exported pointers exist"
            pass

    def __del__(self):
        self.close()
