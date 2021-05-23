import cli_walker
import re
import logging
import time

logging.basicConfig(level=logging.DEBUG)
class endpointRegister():
    def __init__(self):
        self.interface_register = {}
        self.link_register = []
        self.host_details = {}
        self.walker = None
        self.auth_init = False
        self.sleep_timer = 2


    def update_interface_register(self, device, interface):
        if not self.interface_register.get(device):
            self.interface_register[device] = {}

        if self.interface_register[device].get(interface):
            raise Exception('Duplicate interface detected: {} {}. Check the link register'.format(device, interface))
        else:
            self.interface_register[device][interface] = {'ifname': interface}


    def update_link_register(self, nodeA, ifaceA, nodeB, ifaceB, **kwargs):
        self.link_register.append({
            'nodeA': nodeA,
            'ifaceA': ifaceA,
            'nodeB': nodeB,
            'ifaceB': ifaceB,
            **kwargs})


    def walker_init(self, host_details):
        self.host_details = host_details
        self.walker = cli_walker.walker(host_details)
        self.auth_init = True


    def get_interface_details(self, host, interface):
        show_interface_command = 'show interface {}'.format(interface)
        interface_details = self.walker.execute(host, show_interface_command)
        return interface_details


    def iface_status_assessment(self, line):
        detected_statuses = []
        valid_statutes = ['up', 'down', 'administratively down']
        for status in valid_statutes:
            if status in line:
                detected_statuses.append(status)
        if len(detected_statuses) == 1:
            return detected_statuses[0]
        elif len(detected_statuses) == 2:
            if detected_statuses == ['down', 'administratively down']:
                return 'administratively down'
            else:
                raise Exception('cannot detect interface status: {}'.format(line))


    def get_iface_status(self, host, interface):
        output = self.get_interface_details(host, interface)
        magic_line = output.split('\n')[3]
        status = self.iface_status_assessment(magic_line)
        return status


    def get_controllers_details(self, host, interface):
        show_controllers_command = 'show controllers {}'.format(interface)
        controllers_data = self.walker.execute(host, show_controllers_command)
        return controllers_data


    def get_controllers_phy_details(self, host, interface):
        show_controllers_command = 'show controllers {} phy'.format(interface)
        controllers_data = self.walker.execute(host, show_controllers_command)
        return controllers_data


    def perLane_transformer(self, data, direction):
        result = {}
        for line in iter(data):
            if line[1] == direction:
                result[line[0]] = {
                         'dBm': line[3],
                         'mW': line[2]
                }
        return result


    def safe_re_getter(self, re_match_object, target_group):
        if re_match_object:
            try:
                return re_match_object.group(target_group)
            except:
                return None
        else:
            return None


    def _simplified_power_summariser(self, data, direction):
        import math
        print('Landed in a simplified power summariser')
        print(data)
        lane_mW_data = []
        for line in iter(data):
            if direction == 'Tx':
                lane_mW_data.append(line[2])
            elif direction == 'Rx':
                lane_mW_data.append(line[4])
            else:
                raise Exception('unknown direction: {}'. format(direction))
        float_data = [float(x) for x in lane_mW_data]
        total_mW = sum(float_data)
        total_dBm = 10*math.log10(total_mW/0.001)
        return {'dBm':total_dBm, 'mW': total_mW}


    def _simplified_perLane_transformer(self, data, direction):
        print('Started the per lane power transformer')
        print(data)
        result = {}
        for line in iter(data):
            result[line[0]] = {}
            if direction == 'Tx':
                result[line[0]] = {
                    'dBm': line[2],
                    'mW': line[3]
                }
            elif direction == 'Rx':
                result[line[0]] = {
                    'dBm': line[3],
                    'mW': line[4]
                }
            else:
                raise Exception('unknown direction: {}'. format(direction))
        print(result)
        return result


    def xr_precise_controllers_parsing(self, data):
        txTotalre = '^Total Tx power:\s(?P<mWTxPower>\S*)\s*\S*\s\(\s*(?P<dBmTxPower>[\-\d\.]*)\sdBm\)'
        rxTotalre = '^Total Rx power:\s(?P<mWRxPower>\S*)\s*\S*\s\(\s*(?P<dBmRxPower>[\-\d\.]*)\sdBm\)'
        perLanere = '^\s*Lane\s(?P<lane>\d)\s(?P<direction>\S*)\spower:\s(?P<mWpower>\S*)\s\S*\s*\(\s*(?P<dBmPower>[\d\.\-]*)\sdBm\)'
        txTotal_data = re.search(txTotalre, data, re.MULTILINE)
        rxTotal_data = re.search(rxTotalre, data, re.MULTILINE)
        perLane_data = re.findall(perLanere, data, re.MULTILINE)

        transformed_data = {
            'Tx':
                {'total':
                     {
                         'dBm': self.safe_re_getter(txTotal_data, 'dBmTxPower'),
                         'mW': self.safe_re_getter(txTotal_data, 'mWTxPower')},
                'per_lane': self.perLane_transformer(perLane_data, 'Tx')},
            'Rx':
                {'total':
                    {
                        'dBm': self.safe_re_getter(rxTotal_data,'dBmRxPower'),
                        'mW': self.safe_re_getter(rxTotal_data, 'mWRxPower')},
            'per_lane': self.perLane_transformer(perLane_data, 'Rx')}
        }
        return transformed_data

    def xr_simplified_controllers_parsing(self, data):
        perLanere = '^\s*(?P<laneNumber>\d)\s+\S*\s+(?P<dBmTxPower>[\d\.\-]*)\s+(?P<mWTxPower>[\d\.\-]*)\s+(?P<dBmRxPower>[\d\.\-]+)\s*(?P<mWRxPower>[\d\.\-]+)\s+(?P<laserBias>[\d\.\-]+)'
        perLane_data = re.findall(perLanere, data, re.MULTILINE)
        print(perLane_data)
        transformed_data = {
            'Tx':
                {'total': self._simplified_power_summariser(perLane_data, 'Tx'),
                'per_lane': self._simplified_perLane_transformer(perLane_data, 'Tx')},
            'Rx':
                {'total': self._simplified_power_summariser(perLane_data, 'Rx'),
                'per_lane': self._simplified_perLane_transformer(perLane_data, 'Rx')}
        }
        return transformed_data

    def _simplified_xr_power_extractor(self, device, interface):
        ddata = self.get_controllers_details(device, interface)
        power_data = self.xr_simplified_controllers_parsing(ddata)
        return power_data

    def _precise_xr_power_extractor(self, device, interface):
        ddata = self.get_controllers_phy_details(device, interface)
        power_data = self.xr_precise_controllers_parsing(ddata)
        return power_data

    def interface_processor_selector(self, device_trait):
        local_function_register = {
            'simplified': self._simplified_xr_power_extractor,
            'precise': self._precise_xr_power_extractor
        }
        return local_function_register[device_trait]


    def interface_power_getter(self):
        for device in self.interface_register.keys():
            device_phy_capabilities = self.host_details[device]['phy_capabilities']
            device_interface_processor = self.interface_processor_selector(device_phy_capabilities)
            for interface in self.interface_register[device]:
                logging.info('Investigating: {} {}'.format(device, interface))
                power_data = device_interface_processor(device, interface)
                self.interface_register[device][interface]['power_data'] = power_data
                time.sleep(self.sleep_timer)


    def _unidirectional_attenuation_calculator(self, Tx_data, Rx_data):
        assert bool(Tx_data['total']) == bool(Rx_data['total'])
        assert len(Tx_data['per_lane']) == len(Rx_data['per_lane'])
        total_attenuation_dB = float(Tx_data['total']['dBm']) - float(Rx_data['total']['dBm'])
        total_attenuation_mW = float(Tx_data['total']['mW']) - float(Rx_data['total']['mW'])
        per_lane_attenuation = {}
        for laneNum in Tx_data['per_lane'].keys():
            per_lane_attenuation_dBm = float(Tx_data['per_lane'][laneNum]['dBm']) - float(Rx_data['per_lane'][laneNum]['dBm'])
            per_lane_attenuation_mW = float(Tx_data['per_lane'][laneNum]['mW']) - float(Rx_data['per_lane'][laneNum]['mW'])
            per_lane_attenuation[laneNum]= {'dBm': per_lane_attenuation_dBm,
                                            'mW': per_lane_attenuation_mW,
                                            }
        return {'total':
                    {'dB': total_attenuation_dB,
                    'mW': total_attenuation_mW},
                'per_lane': per_lane_attenuation
                }

    def _per_link_attenuation_caliculator(self, link_data):
        nodeATx = self.interface_register[link_data['nodeA']][link_data['ifaceA']]['power_data']['Tx']
        nodeBRx = self.interface_register[link_data['nodeB']][link_data['ifaceB']]['power_data']['Rx']
        link_data['attenuation'] = {}
        link_data['attenuation']['AtoB'] = self._unidirectional_attenuation_calculator(nodeATx, nodeBRx)

        nodeBTx = self.interface_register[link_data['nodeB']][link_data['ifaceB']]['power_data']['Tx']
        nodeARx = self.interface_register[link_data['nodeA']][link_data['ifaceA']]['power_data']['Rx']
        link_data['attenuation']['BtoA'] = self._unidirectional_attenuation_calculator(nodeBTx, nodeARx)



    def attenuation_calculator(self):
        for i in self.link_register:
            self._per_link_attenuation_caliculator(i)


    def reporter(self):
        for link in self.link_register:
            print('############')
            print('Endpoint A: {} {}'. format(link['nodeA'], link['ifaceA']))
            print('Endpoint B: {} {}'. format(link['nodeB'], link['ifaceB']))
            print('#####')
            print('Total attenuation across lanes :')
            print('from A to B:     {:4s} dB'.format(str(round(link['attenuation']['AtoB']['total']['dB']))))
            print('from B to A:     {:4s} dB'.format(str(round(link['attenuation']['BtoA']['total']['dB']))))
            print('delta:           {:4s} dB'.format(str(abs(round(link['attenuation']['AtoB']['total']['dB'] -
                                                                   link['attenuation']['BtoA']['total']['dB'], 2)))))



