#!/usr/bin/python3

import meraki
#import copy
import asyncio
import os
from time import *

from meraki import aio
import tqdm.asyncio

#import time
import get_keys as g
import datetime
#import random

#import click
#from deepdiff import DeepDiff

#import inspect 

log_dir = os.path.join(os.getcwd(), "Logs/")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


#Main dashboard object
db = meraki.DashboardAPI(
            api_key=g.get_api_key(), 
            base_url='https://api.meraki.com/api/v1/', 
            output_log=True,
            log_file_prefix=os.path.basename(__file__)[:-3],
            log_path='Logs/',
            print_console=False)

#Loads whilelist from disk if it's available, otherwise the script will span ALL organizations your API key has access to
orgs_whitelist = []
file_whitelist = 'org_whitelist.txt'
if os.path.exists(file_whitelist):
    f = open(file_whitelist)
    wl_orgs = f.readlines()
    for o in wl_orgs:
        if len(o.strip()) > 0:
            orgs_whitelist.append(o.strip())

### ASYNC SECTION

async def getOrg_Networks(aio, org_id):
    result = await aio.organizations.getOrganizationNetworks(org_id,perPage=1000, total_pages='all')
    return org_id, "networks", result

async def getOrg_Devices(aio, org_id):
    result = await aio.organizations.getOrganizationDevicesStatuses(org_id,perPage=1000, total_pages='all')
    return org_id, "devices", result

async def getOrg_Templates(aio, org_id):
    result = await aio.organizations.getOrganizationConfigTemplates(org_id)
    return org_id, "templates", result

async def getSwitchStatuses_Device(aio, serial):
    result = await aio.switch.getDeviceSwitchPortsStatuses(serial)
    return serial, "statuses", result

async def getSwitchPorts_Device(aio, serial):
    result = await aio.switch.getDeviceSwitchPorts(serial)
    return serial, "switchports", result


async def getEverything():
    async with meraki.aio.AsyncDashboardAPI(
                api_key=g.get_api_key(),
                base_url="https://api.meraki.com/api/v1",
                output_log=True,
                log_file_prefix=os.path.basename(__file__)[:-3],
                log_path='Logs/',
                maximum_concurrent_requests=10,
                maximum_retries= 100,
                nginx_429_retry_wait_time=60,
                wait_on_rate_limit=True,
                print_console=False,
                
        ) as aio:
            orgs_raw = await aio.organizations.getOrganizations()
            orgs = {}
            for o in orgs_raw:
                if len(orgs_whitelist) == 0:
                    if o['api']['enabled']:
                        orgs[o['id']] = o
                elif o['id'] in orgs_whitelist:
                    orgs[o['id']] = o
            
            org_networks = {}
            org_devices = {}
            org_templates = {}
            getTasks = []
            for o in orgs:
                getTasks.append(getOrg_Networks(aio, o))
                getTasks.append(getOrg_Devices(aio, o))
                #getTasks.append(getOrg_Templates(aio, o))

            for task in tqdm.tqdm(asyncio.as_completed(getTasks), total=len(getTasks), colour='green'):
                oid, action, result = await task
                if action == "devices":
                    org_devices[oid] = result
                elif action == "networks":
                    org_networks[oid] = result
                elif action == "templates":
                    org_templates[oid] = result

            
            print("DONE")
            return org_devices, org_networks, org_templates
    return

async def getEverythingDevice(device_list):
    async with meraki.aio.AsyncDashboardAPI(
                api_key=g.get_api_key(),
                base_url="https://api.meraki.com/api/v1",
                output_log=True,
                log_file_prefix=os.path.basename(__file__)[:-3],
                log_path='Logs/',
                maximum_concurrent_requests=10,
                maximum_retries= 100,
                wait_on_rate_limit=True,
                print_console=False,
                
        ) as aio:
            getTasks = []
            for d in device_list:
                #getTasks.append(getSwitchPorts_Device(aio, d['serial']))
                getTasks.append(getSwitchStatuses_Device(aio, d['serial']))
                

            switches_statuses = {}
            switches_switchports = {}
            for task in tqdm.tqdm(asyncio.as_completed(getTasks), total=len(getTasks), colour='green'):
                serial, action, result = await task
                if action == 'statuses':
                    switches_statuses[serial] = result
                elif action == 'switchports':
                    switches_switchports[serial] = result
                    
                
            
            print("DONE")
            return switches_switchports, switches_statuses

### /ASYNC SECTION   


orgs = db.organizations.getOrganizations()

### This section returns all Devices, Networks and Templates in all the orgs you have access to
loop = asyncio.get_event_loop()
start_time = time()
org_devices, org_networks, org_templates = loop.run_until_complete(getEverything())
end_time = time()
elapsed_time = round(end_time-start_time,2)

print(f"Loaded Everything took [{elapsed_time}] seconds")
print()
### end-of Devices/Networks/Templates

def getDevice(serial):
    for o in org_devices:
        devs = org_devices[o]
        for d in devs:
            if serial == d['serial']:
                return d
    return

def getNetwork(netID):
    for o in org_networks:
        nets = org_networks[o]
        for n in nets:
            if netID == n['id']:
                return n
    return

def getOrg(orgID):
    for o in orgs:
        if orgID == o['id']:
            return o
    return

### This section returns all SwitchPorts and SwitchPort Statuses
MS_online = []
for o in org_devices:
    for d in org_devices[o]:
        if d['status'] == 'online' and 'MS' in d['model'][:2]:
            d['org_id'] = o
            MS_online.append(d)


start_time = time()
switches_switchports, switches_statuses = loop.run_until_complete(getEverythingDevice(MS_online))
end_time = time()
elapsed_time = round(end_time-start_time,2)
print()
print(f"Loaded Everything took [{elapsed_time}] seconds")
print()
### end-of SwitchPorts / Statuses


def showBadPorts(switch_statuses):
    for p in switch_statuses:
        if len(p['errors']) > 0 or len(p['warnings']) > 0:
            print(p)

def getBadPorts(switch_statuses):
    errors = {}
    for s in switch_statuses:
        if len(s['errors']) > 0 or len(s['warnings']) > 0:
            errors[s['portId']] = s
    return errors

def getUplinks(switch_statuses):
    uplinks = {}
    for s in switch_statuses:
        if "isUplink" in s and s['isUplink'] == True:
        #if "MS" in str(s):
            uplinks[s['portId']] = s
    return uplinks

def getUnique(list_source):
    result = []
    for l in list_source:
        if not l in result: result.append(l)
    return result


#Find switches alerting
switches_erroring = []
switches_alerting = []
for s in switches_statuses:
    ports = switches_statuses[s]
    for p in ports:
        if 'Port disconnected' in p['errors']: p['errors'].remove('Port disconnected')
        if 'Port disabled' in p['errors']: p['errors'].remove('Port disabled')
        if len(p['errors']) > 0:
            if not s in switches_erroring:
                switches_erroring.append(s)
            
        if len(p['warnings']) > 0:
            if not s in switches_alerting:
                switches_alerting.append(s)


date_string = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

bad_switches = {}
for sn in switches_statuses:
    #ports = switches_switchports[sn]
    stats = switches_statuses[sn]
    uplinks = getUplinks(stats) #find the uplink ports based on connected MS's
    bad_ports = getBadPorts(stats)
    bad_uplinks = {}
    if len(bad_ports) > 0:
        print(f"Switch[{sn}] has bad ports!!!")
        for bp in bad_ports:
            if bp in uplinks:
                bad_uplinks[bp] = bad_ports[bp]
        print(bad_ports.keys())
    if len(bad_uplinks) > 0:
        print(f"Switch[{sn}] has bad uplinks!!!")
        bad_switches[sn] = bad_uplinks
    
        print(f"Switch[{sn}] Number of bad ports[{len(bad_ports)}], number of uplinks[{len(uplinks)}]")
    #print(bad_ports)
        print()

f = open(f"switch_bad_errors_{date_string}.txt", 'w')
for s in bad_switches:
    f.write(f"{s}: {str(bad_switches[s])}\n")
f.close()

crc = []
for b in bad_switches:
    ports = bad_switches[b]
    for p in ports:
        if "CRC" in str(ports[p]['errors']) or "CRC" in str(ports[p]['warnings']):
            crc.append(b)

#Build a dict of orgs, networks and devices impacted
org_networks_devices = {}
for sn in crc:
    d = getDevice(sn)
    if not d['org_id'] in org_networks_devices:
        org_networks_devices[d['org_id']] = {}
    if not d['networkId'] in org_networks_devices[d['org_id']]:
        org_networks_devices[d['org_id']][d['networkId']] = []

    org_networks_devices[d['org_id']][d['networkId']].append(sn)

f = open(f"switch_CRC_errors_{date_string}.txt", 'w')
for o in org_networks_devices:
    org = getOrg(o)
    print(f"Organization[{org['name']}] orgID[{o}]")
    f.write(f"Organization[{org['name']}] orgID[{o}]\n")
    for n in org_networks_devices[o]:
        net = getNetwork(n)
        print(f"  Network[{net['name']}] netID[{n}] URL[{net['url']}] ")
        f.write(f"  Network[{net['name']}] netID[{n}] URL[{net['url']}]\n")
        devices = org_networks_devices[o][n]
        for d in devices:
            dev = getDevice(d)
            port_list = []
            for p in bad_switches[d].keys():
                port_list.append(p)
            alertsP = []
            for p in bad_switches[d]:
                alertsP = alertsP + bad_switches[d][p]['errors']
                alertsP = alertsP + bad_switches[d][p]['warnings']
            alertsP = getUnique(alertsP)
            print(f"\tDevice [{d}] Name[{dev['name']}] Ports{port_list} Alerts{alertsP}")
            f.write(f"\tDevice [{d}] Name[{dev['name']}] Ports{port_list} Alerts{alertsP}\n")
    print()
    f.write('\n')
f.close()

f = open(f"switch_CRC_errors_{date_string}.json", 'w')
f.writelines(str(org_networks_devices))
f.close()


