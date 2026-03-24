# Domoticz TinyTUYA Local Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuyalocal" name="TinyTUYA (Local Control)" author="Xenomes modified by jvdzande for Weatherstation" version="0.8" wikilink="" externallink="https://github.com/jvanderzande/Domoticz-TinyTUYA-Local-Plugin/tree/weatherstation">
    <description>
        <h2>TinyTUYA Plugin Local</h2><br/>
        <br/>
        <p>Plugin to get information from Tuya for below devices and send them to domoticz. This plugin is based on the TinyTUYA plugin from Xenomes.</p>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Weatherstation Nedis WIFIWEST500WT</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Inside Temp&Humidity</li>
            <li>Outside Temp&Humidity&Barometer</li>
            <li>Rain</li>
            <li>Wind</li>
        </ul>
    </description>
    <params>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic + Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections + Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
try:
    import DomoticzEx as Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
import tinytuya
# from tinytuya import Contrib
import subprocess
import platform
import os
import sys
import json
import ast
import time
import base64
import traceback
from datetime import datetime, timedelta


class BasePlugin:
    enabled = False
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Log('TinyTUYA ' + Parameters['Version'] + ' plugin started')
        Domoticz.Log('TinyTuya Version:' + tinytuya.version )

        global testData, DEBUGLEVEL
        DEBUGLEVEL = int(Parameters['Mode6'])
        if Parameters['Mode6'] != '0':
            Domoticz.Debugging(int(Parameters['Mode6']))
            # Domoticz.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()
        # Domoticz.Heartbeat(10)
        testData = False
        if os.path.isfile(Parameters['HomeFolder'] + '/testdata.on'):
            testData = True
            Domoticz.Error('!!! Warning Plugin overruled by local json file !!!')

        onCreateDevices()

    def onStop(self):
        Domoticz.Log('onStop called')

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log('onConnect called')

    def onMessage(self, Connection, Data):
        Domoticz.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        return

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        Domoticz.Log('onDisconnect called')

    def onHeartbeat(self):
        Domoticz.Debug('onHeartbeat called')
        # if time.time() - getConfigItem(DeviceID, 'last_update') < 10:
        #     Domoticz.Debug("onHeartbeat called skipped")
        #     return
        # Domoticz.Debug("onHeartbeat called last run: " + str(time.time() - last_update))
        onHandleThread(False)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


def onCreateDevices():
    try:
        global tuya, tuyadevsensors, last_update, result, tuya2domo
        last_update = time.time()
        tuyadevsensors = None
        if os.path.isfile(Parameters['HomeFolder'] + '/tuyadevices.json'):
            with open(Parameters['HomeFolder'] + '/tuyadevices.json') as dFile:
                tuyadevsensors = json.load(dFile)
    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())

    # Initialize/Update devices from TUYA API
    if tuyadevsensors is None:
        Domoticz.Error('tuyadevices.json is missing in the plugin folder!')
        exit

    try:
        tuya2domo = {}
        if os.path.isfile(Parameters['HomeFolder'] + '/tuya2domoticz.json'):
            with open(Parameters['HomeFolder'] + '/tuya2domoticz.json') as dFile:
                tuya2domo = json.load(dFile)
        # Domoticz.Debug('Devs: ' + str(tuyadevsensors))
        # Domoticz.Debug('Result: ' + str(result))

        Domoticz.Debug('Devices: ' + str(Devices))
        # Create devices
        for t2d_dhwid, units in tuya2domo.items():
            for t2d_dunitid, t2d_dunitinfo in units.items():
                # Domoticz.Log('Check for: ' + str(t2d_dhwid) + ' - ' + str(t2d_dunitid))
                if createDevice(t2d_dhwid, t2d_dunitid):
                    subType = t2d_dunitinfo.get('subType', 1)
                    Domoticz.Log(f"Create Name={t2d_dunitinfo['Name']},DeviceID={t2d_dhwid},Unit={t2d_dunitid},Type={t2d_dunitinfo['Type']}, Subtype={subType},Used=1")
                    Domoticz.Unit(
                        Name=t2d_dunitinfo['Name'],
                        DeviceID=str(t2d_dhwid),
                        Unit=int(t2d_dunitid),
                        Type=int(t2d_dunitinfo['Type']),  # Temp+Hum combined
                        Subtype=int(subType),
                        Used=1
                    ).Create()
    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())

    if tuya2domo is None:
        Domoticz.Error('tuya2domoticz.json is missing in the plugin folder!')
        exit


def tuya_load_prev_state():
    global TuyaStateFile
    TuyaStateFile = Parameters['HomeFolder'] + '/tuya_state_combined.json'
    if os.path.exists(TuyaStateFile):
        try:
            with open(TuyaStateFile, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def tuya_save_state(state):
    with open(TuyaStateFile, "w") as f:
        json.dump(state, f, indent=2)

def tuya_update_state(new_data, device_id):
    state = tuya_load_prev_state()

    # Ensure device exists
    if device_id not in state:
        state[device_id] = {"dps": {}}

    # Merge DPS values
    state[device_id]["dps"].update(new_data.get("dps", {}))

    tuya_save_state(state)
    return state

def onHandleThread(startup):
    # Run for every device on startup and heartbeat
    try:
        # Update devices
        for t2d_dhwid, t2d_dhwinfo in tuya2domo.items():
            # Domoticz.Debug( 'Device name=' + str(tuyaunit['name']) + ' id=' + str(tuyaunit['id']) + ' ip=' + str(tuyaunit['ip']) + ' version=' + str(tuyaunit['version'])) # ' key=' + str(tuyaunit['key']) +

            tuyaunit = next((tuyaunit for tuyaunit in tuyadevsensors if tuyaunit['id'] == str(t2d_dhwid)), None)
            # Domoticz.Debug('t2d_dhwid:' + str(t2d_dhwid) + '   tdev:' + str(tdev))
            # Domoticz.Debug(str(code_list))
            tuyaunitdevices = tuyaunit['mapping']
            # update devices in Domoticz
            Domoticz.Debug('Update devices in Domoticz')
            tuya = tinytuya.Device(dev_id=str(tuyaunit['id']), address=str(tuyaunit['ip']), local_key=str(tuyaunit['key']), version=str(tuyaunit['version']))
            # tuya = tinytuya.Device(dev_id=str(tuyaunit['id']), address=str(tuyaunit['ip']), local_key=str(tuyaunit['key']), version=str(tuyaunit['version']), connection_timeout=5, connection_retry_limit=1)
            # tuya.detect_available_dps()
            # tuya.detect_available_dps() # Two times for detection bulb devices
            tuyastatus = tuya.status()
            # tuyastatus = tuya.status()

            # if DEBUGLEVEL > 0:
            #     # ---- save/merge tuya stateinfo in debug modes to tuya_state_combined.json ----
            #     tuya_update_state(tuyastatus, str(tuyaunit['id']))

            # save records
            # TuyaStateFile = Parameters['HomeFolder'] + '/tuya_state_records.json'
            # staterecord = {}
            # now = datetime.now()
            # staterecord[str(tuyaunit['id'])] = {}
            # staterecord[str(tuyaunit['id'])]["time"] = now.strftime("%Y%m%d-%H%M%S")
            # staterecord[str(tuyaunit['id'])]["data"] = tuyastatus
            # with open(TuyaStateFile, "a") as f:
            #     json.dump(staterecord, f)
            #     f.write("\n")


            last_update = getConfigItem(str(t2d_dhwid), 'last_update')
            if isinstance(last_update, dict):
                last_update = last_update.get('last_update', 0)

            if float(time.time()) > float(last_update) or testData:
                # Domoticz.Debug('tuyastatus: ' + str(tuyastatus))
                dps = tuyastatus.get('dps', {})
                for t2d_dunitid, t2d_dunitinfo in t2d_dhwinfo.items():
                    # Domoticz.Debug(Devices[str(t2d_dhwid)].Units[int(t2d_dunitid)])
                    try:
                        # Domoticz.Debug('process t2d_dunitid '+str(t2d_dunitid) + "  dtype:" + str(dtype))
                        svalue=""
                        for t2d_dunitseqnr, t2d_tunitid in t2d_dunitinfo["TuyaIDs"].items():  # loop through all entries/columns for this t2d_dunitid
                            # Domoticz.Debug('--> process '+str(t2d_dunitseqnr)+  " -> t2d_tunitid:" + str(t2d_tunitid))
                            # Domoticz.Debug('>dps '+ str(dps))
                            if t2d_tunitid == "0":
                                currentstatus = 0
                            else:
                                item_value = dps.get(t2d_tunitid, 0)   # t2d_tunitid is e.g., '101'
                                # Domoticz.Debug('>process t2d_tunitid '+ t2d_tunitid + '  item_value: ' + str(item_value))
                                # Get Tuya sensor info
                                tuyasubdev = tuyaunitdevices.get(t2d_tunitid)
                                # Domoticz.Debug('>process tuyasubdev: '+str(tuyasubdev))
                                currentstatus = get_scale(item_value, tuyasubdev, t2d_dunitinfo, t2d_dunitseqnr)

                            if svalue != "":
                                svalue+=";"
                            svalue += str(currentstatus)
                            Domoticz.Debug('+ process t2d_dunitid '+str(t2d_dunitid) + ' t2d_dunitseqnr:' + str(t2d_dunitseqnr) + '  t2d_tunitid:' + str(t2d_tunitid) + ' currentstatus:' + str(currentstatus) + ' new svalue:' + str(svalue))

                        Domoticz.Debug('< process t2d_dunitid '+str(t2d_dunitid)+ ' svalue:' + str(svalue))
                        UpdateDevice(str(t2d_dhwid), t2d_dunitid, str(svalue), 0, 0)
                    except Exception:
                        Domoticz.Error('device value error:\n' + traceback.format_exc())

    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())
    # except Exception as err:
    #     Domoticz.Error('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return

def UpdateDevice(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate = 0):
    Unit = int(Unit)
    #update sensors each minute when not changed
    update_due = False
    try:
        last_update = datetime.strptime(Devices[ID].Units[Unit].LastUpdate, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_update > timedelta(minutes=1):
            update_due = True
    except Exception:
        update_due = False

    # Domoticz.Debug('? Update device value: ' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    if update_due or str(Devices[ID].Units[Unit].sValue) != str(sValue) or str(Devices[ID].Units[Unit].nValue) != str(nValue) or str(Devices[ID].TimedOut) != str(TimedOut) or AlwaysUpdate == 1:
        if sValue == None:
            sValue = Devices[ID].Units[Unit].sValue
        if type(sValue) == int or type(sValue) == float:
            Devices[ID].Units[Unit].LastLevel = sValue
        elif type(sValue) == dict:
            Devices[ID].Units[Unit].Color = json.dumps(sValue)

        Devices[ID].Units[Unit].sValue = str(sValue)
        Devices[ID].Units[Unit].nValue = nValue
        Devices[ID].TimedOut = TimedOut
        Devices[ID].Units[Unit].Update(Log=True)

        Domoticz.Debug('Update device value: ' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    return

def searchCode(Item, Functions):
    for OneItem in Functions:
        if Item == OneItem:
            return True
        else:
            return False
    # Domoticz.Debug("searchCodeActualFunction unable to find " + str(Item) + " in " + str(Function))
    return

def createDevice(ID, Unit):
    if ID in Devices:
        if Unit in Devices[ID].Units:
            value = False
        else:
            if int(Unit) in Devices[ID].Units:
                value = False
            else:
                value = True
    else:
        value = True

    return value


def get_scale(raw, tuyasubdev, t2d_dunitinfo, t2d_dunitseqnr):
    scale = 0
    max_value = 0

    # Check if raw is a valid number (int, float, or numeric string)
    if not isinstance(raw, (list, tuple, dict, set, bool, complex, bytes, str)) or (isinstance(raw, str) and raw.isnumeric()):
        # Convert numeric strings to floats
        raw = float(raw) if isinstance(raw, str) else raw
        result = raw
        try:
            t2d_dunitid = ''
            # Domoticz.Debug('Raw Value: ' + str(raw) + '  Type: ' + str(type(raw)))
            # Domoticz.Debug('Item Values: ' + str(tuyasubdev['values']))
            if 'scale' in tuyasubdev['values']:
                scale = tuyasubdev['values'].get('scale')

            if 'unit' in tuyasubdev['values']:
                t2d_dunitid = tuyasubdev['values'].get('unit')

            if 'max' in tuyasubdev['values']:
                max_value = tuyasubdev['values'].get('max')

            Domoticz.Debug(f'-> raw: {raw}  scale:{scale} t2d_dunitid:{t2d_dunitid}  max_value:{max_value}')

            if scale == 0:
                if t2d_dunitid == 'V' and len(str(max_value)) >= 4:
                    result = raw / 10
                elif t2d_dunitid == 'W' and len(str(max_value)) >= 5:
                    result = raw / 10
                else:
                    result = int(raw)
            elif scale == 1:
                result = raw / 10
                Domoticz.Debug(f'1 raw: {raw}  scale:{scale} result {result}')
            elif scale == 2:
                result = raw / 100
                Domoticz.Debug(f'2 raw: {raw}  scale:{scale} result {result}')
            elif scale == 3:
                result = raw / 1000
                Domoticz.Debug(f'3 raw: {raw}  scale:{scale} result {result}')
            else:
                result = int(raw)
                Domoticz.Debug(f'else raw: {raw}  scale:{scale} result {result}')

        except Exception as err:
            Domoticz.Error('get_scale error:\n' + traceback.format_exc())
            result = raw
    else:
        # If raw is not numeric, return it unmodified
        result = raw
        Domoticz.Debug('Non-numeric input, returning raw value: ' + str(result))

    try:
        # process defined factor or range translate in tuya2domoticz.json
        factor = 1
        if "factor" in t2d_dunitinfo:
            if t2d_dunitseqnr in t2d_dunitinfo["factor"]:
                factor = float(t2d_dunitinfo["factor"][t2d_dunitseqnr])
        #factor == 0 means use content as-is
        Domoticz.Debug('> process t2d_dunitseqnr '+ t2d_dunitseqnr + '  raw: ' + str(raw) + '  result: ' + str(result) + '  factor: ' + str(factor))
        if factor != 0:
            # check if there is a range defined to which we need to translate the string to itemnumber
            if "range" in tuyasubdev["values"]:
                range_list = tuyasubdev["values"]["range"]
                try:
                    # translate string to itemnumber
                    result = range_list.index(result)
                    Domoticz.Debug('x range-> t2d_dunitseqnr '+ t2d_dunitseqnr + '  raw: ' + str(raw) + '  result: ' + str(result) + '  factor: ' + str(factor))
                except ValueError:
                    result = 1  # or some default
            # apply the found factor in case not 1
            if factor != 1:
                result = round(result * factor, 2)
            Domoticz.Debug('<process t2d_dunitseqnr '+ t2d_dunitseqnr + '  raw: ' + str(raw) + '  result: ' + str(result) + '  factor: ' + str(factor))
    except Exception as err:
        Domoticz.Error('factor-translate error:\n' + traceback.format_exc())

    return result





    # Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            # Domoticz.Debug(Config[Key][Values])
            Value = Config[Key][Values]  # only return requested key if there was one
        else:
            Value = Config      # return the whole configuration if no key
    except KeyError:
        Value = {}
    except Exception as inst:
        Domoticz.Error('Domoticz.Configuration read failed: ' + str(inst))
    return Value


def version(v):
    return tuple(map(int, (v.split("."))))