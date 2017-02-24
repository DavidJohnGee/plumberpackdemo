"""Stuff."""

# See ../requirements.txt

import uuid
import pdb
import json
import requests
from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.v2_0 import client
from requests.auth import HTTPBasicAuth
from st2reactor.sensor.base import PollingSensor


class PlumbingSensor(PollingSensor):
    """Stuff."""

    TRIGGER = 'plumbpack.new_vrouter'

    def __init__(self, sensor_service, config=None, poll_interval=None):
        """Stuff."""
        super(PlumbingSensor, self).__init__(sensor_service, config,
                                             poll_interval)

        self._logger = self._sensor_service.get_logger(__name__)

        self._compute = self._config.get('compute', "")
        self._neutron = self._config.get('neutron', "")
        self._flask = self._config.get('flask', "")
        self._flaskuser = self._config.get('flaskuser', "")
        self._flaskpass = self._config.get('flaskpass', "")
        self._computeuser = self._config.get('computeuser', "")
        self._computepass = self._config.get('computepass', "")
        self._neutronuser = self._config.get('neutronuser', "")
        self._neutronpass = self._config.get ('neutronpass', "")

    def setup(self):
        """Stuff."""
        pass

    def poll(self):
        """
        Execute the awful script every 20 seconds.

        An unmapped interface sends a trigger with the info.
        """
        self._logger.debug('[PlumbingSensor]: Entering into listen mode ...')

        # THING = {'vlan': "1", 'iface': "1"}

        trace_tag = uuid.uuid4().hex
        
        r = SensorExecute()

        self._logger.debug('[PlumbingSensor]: %s ' % r)
        
        if r:
            for k in r:
                # print thing['vlan']
                # print thing['iface']
                BODY = {'vlan': k['vlan'], 'iface': k['iface']}
                
                self.sensor_service.dispatch(trigger=self.TRIGGER,
                                             payload=BODY, trace_tag=trace_tag)

    def cleanup(self):
        """Stuff."""
        pass

    def add_trigger(self, trigger):
        """Stuff."""
        pass

    def update_trigger(self, trigger):
        """Stuff."""
        pass

    def remove_trigger(self, trigger):
        """Stuff."""
        pass


def SensorExecute():
    username='admin'
    password='brocade101'
    project_name='admin'
    auth_url='http://192.168.100.100:5000/v2.0'
    auth = identity.Password(auth_url=auth_url,
                                username=username,
                                password=password,
                                project_name=project_name)

    sess = session.Session(auth=auth)

    neutron = client.Client(session=sess)

    # Get router list from Neutron
    dset1 = neutron.list_routers()
    jset1 = json.dumps(dset1)

    # Get port list from Neutron
    dset2 = neutron.list_ports()
    jset2 = json.dumps(dset2)

    # Create vRouter dict
    RTRS = {}

    # Iterate through jset from neutron.list_routers()
    for rtr in dset1['routers']:
        test = rtr['external_gateway_info']
        RTR = {}
        # Create dict with key as router devID
        if test is not False:
            RTR["devid"] = rtr['id']

            if 'external_gateway_info' in rtr:
                t1 = rtr['external_gateway_info']
                if 'ip_address' in t1['external_fixed_ips'][0]:
                    t2 = t1['external_fixed_ips'][0]['ip_address']
                    RTR["address"] = t2
                    RTR["vlan"] = t2.split(".")[2]
                    RTRS[rtr['id']] = RTR
                else:
                    return []
            else:
                return []

    # Iterate through Neutron ports
    ports = dset2['ports']
    for port in ports:
        if 'network:router_gateway' in port['device_owner']:
            if port['device_id'] in RTRS:
                RTRS[port['device_id']]['mac'] = port['mac_address']

    # Now we have a list of RTRS with MAC addresses. Let's add the port-ID to that list
    r = requests.get('http://192.168.100.101:5000/macs',
                       auth=HTTPBasicAuth('admin', 'admin'))

    controllerInts = r.json()

    # For each router, get the MAC address of an external_gateway interface and
    # find the relevant TAP interface in the controllerInts JSON array

    # print RTRS
    # print controllerInts

    for r in RTRS:
        # get five nibbles of MAC due to MAC being broken on Neutron
        m = RTRS[r]['mac']
        mn = m.split(":")[1:6]
        for c in controllerInts:
            cn = c['address'].split(":")[1:6]
            if mn == cn:
                RTRS[r]['iface'] = c['name']

    # Now let's get the list of bridges on the compute node and associated ports

    r = requests.get('http://192.168.100.101:5000/bridges',
                        auth=HTTPBasicAuth('admin', 'admin'))

    lbridges = r.json()

    vRouterDump = """{"f8e098c2-4fcd-4608-8257-e0d1a0ca6c9b": {"mac": "fa:16:3e:58:68:c1", "devid": "f8e098c2-4fcd-4608-8257-e0d1a0ca6c9b", "iface": "tapb2331f17-f7", "vlan": "122", "address": "10.10.122.18"}, "09303a9e-b634-4d36-a895-66eaebef1239": {"mac": "fa:16:3e:55:d4:d0", "devid": "09303a9e-b634-4d36-a895-66eaebef1239", "iface": "tap2615e53a-2f", "vlan": "123", "address": "10.10.123.18"}}"""

    # For each vRouter iterate over Bridges and check for tap ports on br<x>

    # ST2 Trigger Stuff
    triggerDicts = []

    for vR in RTRS:
        riface = RTRS[vR]['iface']
        rvlan = RTRS[vR]['vlan']

        # Now run through each bridge and check for existance
        _found = False
        for bridge in lbridges:
            for siface in lbridges[bridge]:
                if riface == siface:
                    _found = True

        if _found == False:
            # print("Did not find external bridge port for {0} and VLAN {1}".format(riface, rvlan))
            triggerDict = {}
            triggerDict['vlan'] = rvlan
            triggerDict['iface'] = riface
            triggerDicts.append(triggerDict)

    # print triggerDicts
    return triggerDicts

