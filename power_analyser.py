import cli_walker
import re
import logging
import time

logger = logging.getLogger()

JUNIPER_CFP_RE = ('cfp_re', '^\s*Lane\s*(?P<laneNum>\d+).*?Laser\sbias\scurrent\s*:\s*(?P<current>[\d\.]*)\s*mA.*?Laser\soutput\s*power' \
                 '\s*:\s*(?P<TxmWPower>\S*)\s*\w*\s\/\s*(?P<TxdBPower>\S*)\s*dBm\n.*?\s*.*?Laser\sreceiver\spower\s*:\s*' \
                 '(?P<RxmWPower>\S*)\s*mW\s*\/\s*(?P<RxdBPower>\S*)\s\w*\n')
JUNIPER_QSFP_RE = ('qsfp_re', '^\s*Lane\s*(?P<laneNum>\d+).*?Laser\sbias\scurrent\s*:\s*(?P<current>[\d\.]*)\s*mA\n\s*Laser\s' \
                  'receiver\spower\s*:\s*(?P<RxmWPower>\S*)\s*mW\s*\/\s*(?P<RxdBPower>\S*)')

JUNIPER_GENERIC_RES = [JUNIPER_CFP_RE, JUNIPER_QSFP_RE]



def single_true(iterable):
    i = iter(iterable)
    return any(i) and not any(i)


class endpointRegister():
    def __init__(self):
        self.interface_register = {}
        self.link_register = []
        self.host_details = {}
        self.walker = None
        self.auth_init = False
        self.sleep_timer = 2


    def update_interface_register(self, device, interface):
        logger.info('updating interface register: {} {}'. format(device, interface))
        if not self.interface_register.get(device):
            self.interface_register[device] = {}

        if self.interface_register[device].get(interface):
            raise Exception('Duplicate interface detected: {} {}. Check the link register'.format(device, interface))
        else:
            self.interface_register[device][interface] = {'ifname': interface}


    def update_link_register(self, nodeA, ifaceA, nodeB, ifaceB, **kwargs):

        logger.info('updating link register: {} {}, {} {}'.format(nodeA, ifaceA, nodeB, ifaceB, ))
        logger.info('aux data: {}'.format(kwargs))
        self.link_register.append({
            'nodeA': nodeA,
            'ifaceA': ifaceA,
            'nodeB': nodeB,
            'ifaceB': ifaceB,
            **kwargs})


    def walker_init(self, host_details: dict):
        self.host_details = host_details
        self.walker = cli_walker.walker(host_details)
        self.auth_init = True


    def get_interface_details(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show interface: {}'. format(host, interface))
        show_interface_command = 'show interface {}'.format(interface)
        interface_details = self.walker.execute(host, show_interface_command)
        return interface_details


    def iface_status_assessment(self, line: str) -> str:
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


    def get_iface_status(self, host: str, interface: str) -> str:
        output = self.get_interface_details(host, interface)
        magic_line = output.split('\n')[3]
        status = self.iface_status_assessment(magic_line)
        return status


    def get_xrcontrollers_details(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show controllers: {} {}'. format(host, interface))
        show_controllers_command = 'show controllers {}'.format(interface)
        controllers_data = self.walker.execute(host, show_controllers_command)
        return controllers_data


    def get_xrcontrollers_phy_details(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show controllers phy: {}'. format(host, interface))
        show_controllers_command = 'show controllers {} phy'.format(interface)
        controllers_data = self.walker.execute(host, show_controllers_command)
        return controllers_data


    def get_junos_disgnostics_details(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show controllers phy: {}'.format(host, interface))
        show_controllers_command = 'show interfaces diagnostics optics {}'.format(interface)
        controllers_data = self.walker.execute(host, show_controllers_command)
        return controllers_data


    def perLane_transformer(self, data, direction: str) -> dict:
        logger.info('Extracting per lane power details in direction: {}'. format(direction))
        logger.debug('Raw_data: {}'. format(data))
        result = {}
        for line in iter(data):
            if line[1] == direction:
                result[line[0]] = {
                         'dBm': line[3],
                         'mW': line[2]
                }
        logger.debug('Transformed data: {}'. format(result))
        return result


    def safe_re_getter(self, re_match_object, target_group):
        if re_match_object:
            try:
                return re_match_object.group(target_group)
            except:
                return None
        else:
            return None


    def _simplified_power_summariser(self, data: list, direction: str) -> dict:
        import math
        logger.info('Landed in a simplified power summariser')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'. format(direction))
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
        total_dBm = 10*math.log10(total_mW)
        logger.debug('total_mW: {}'. format(total_mW))
        logger.debug('total_dBm: {}'. format(total_dBm))
        return {'dBm':str(round(total_dBm, 2)), 'mW': str(round(total_mW, 4))}


    def lane_notation_mode_selector(self, lane_numbers: list) ->str:
        int_numbers = [int(x) for x in lane_numbers]
        int_numbers.sort()
        if int_numbers[0] == 0:
            return 'from_zero'
        elif int_numbers[0] == 1:
            return 'from_one'
        else:
            raise Exception('Unaccounted lane numbering: {}'.format(lane_numbers))


    def lane_num_equaliser(self, lane_num, mode):
        if mode == 'from_zero':
            return lane_num
        elif mode == 'from_one':
            return str(int(lane_num) - 1)
        else:
            raise Exception('Bad mode: {}'.format(mode))


    def _simplified_perLane_transformer(self, data: list, direction: str) -> dict:
        logger.info('Started the per lane power transformer')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'.format(direction))
        result = {}
        lane_numbers = [x[0] for x in iter(data)]
        lane_notation_mode = self.lane_notation_mode_selector(lane_numbers)
        for line in iter(data):
            # we count lanes from 0. Some cisco software is inconsistent. Normalizing now.
            lane_num = self.lane_num_equaliser(line[0], lane_notation_mode)
            result[lane_num] = {}
            if direction == 'Tx':
                result[lane_num] = {
                    'dBm': line[1],
                    'mW': line[2]
                }
            elif direction == 'Rx':
                result[lane_num] = {
                    'dBm': line[3],
                    'mW': line[4]
                }
            else:
                raise Exception('unknown direction: {}'. format(direction))
        logger.debug('Transformed_result: {}'.format(result))
        return result


    def _junos_perLane_transformet(self, data: list, direction: str):
        pass

    def xr_precise_controllers_parsing(self, data: str) -> dict:
        logger.debug('Starting a precise parsing process')
        logger.debug('raw data:{}'. format(data))
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

    def xr_simplified_controllers_parsing(self, data) -> dict:
        logger.debug('Starting a simplified parsing process')
        logger.debug('raw data:{}'. format(data))
        perLanere = '^\s*(?P<laneNumber>\d)\s+\S+\s+(?P<dBmTxPower>[\d\.\-]*)\s+(?P<mWTxPower>[\d\.\-]*)\s+(?P<dBmRxPower>[\d\.\-]+)\s*(?P<mWRxPower>[\d\.\-]+)\s+(?P<laserBias>[\d\.\-]{3,})'
        perLane_data = re.findall(perLanere, data, re.MULTILINE)
        transformed_data = {
            'Tx':
                {'total': self._simplified_power_summariser(perLane_data, 'Tx'),
                'per_lane': self._simplified_perLane_transformer(perLane_data, 'Tx')},
            'Rx':
                {'total': self._simplified_power_summariser(perLane_data, 'Rx'),
                'per_lane': self._simplified_perLane_transformer(perLane_data, 'Rx')}
        }
        logger.debug('final_data: {}'.format(transformed_data))
        return transformed_data

    def iterator_to_dict(self, iterator):
        data = []
        for item in iterator:
            data.append(item.groupdict())
        return data

    def junos_generic_diagnostics_optics_parsing(self, data: str) -> dict:
        logger.debug('Starting a juniper generic parsing process')
        logger.debug('raw data:{}'. format(data))
        extracted_data = []
        #doing the initial match against all juniper diagnostics patters
        for juniper_re in JUNIPER_GENERIC_RES:
            re_name = juniper_re[0]
            pattern = juniper_re[1]
            extract = re.finditer(pattern, data, re.MULTILINE|re.DOTALL)
            extracted_data.append(self.iterator_to_dict(extract))
        re_match_array = [bool(x) for x in extracted_data]
        if single_true(re_match_array):
            element_num = [i for i, x in enumerate(re_match_array) if x][0]
            return extracted_data[element_num]
        else:
            raise Exception('Junos diagnostics output matched too many regexes')


    def _generic_junos_power_extractor(self, device: str, interface: str) -> dict:
        ddata = self.get_junos_disgnostics_details(device, interface)
        power_data = self.junos_generic_diagnostics_optics_parsing(ddata)
        return power_data


    def _simplified_xr_power_extractor(self, device: str, interface: str) -> dict:
        ddata = self.get_xrcontrollers_details(device, interface)
        power_data = self.xr_simplified_controllers_parsing(ddata)
        return power_data


    def _precise_xr_power_extractor(self, device: str, interface: str) -> dict:
        ddata = self.get_xrcontrollers_phy_details(device, interface)
        power_data = self.xr_precise_controllers_parsing(ddata)
        return power_data


    def interface_processor_selector(self, device_trait: str):
        local_function_register = {
            'xrsimplified': self._simplified_xr_power_extractor,
            'xrprecise': self._precise_xr_power_extractor,
            'junos_generic': self._generic_junos_power_extractor
        }
        return local_function_register[device_trait]


    def interface_power_getter(self) -> None:
        for device in self.interface_register.keys():
            device_phy_capabilities = self.host_details[device]['phy_capabilities']
            device_interface_processor = self.interface_processor_selector(device_phy_capabilities)
            for interface in self.interface_register[device]:
                logging.info('Investigating: {} {}'.format(device, interface))
                power_data = device_interface_processor(device, interface)
                self.interface_register[device][interface]['power_data'] = power_data
                time.sleep(self.sleep_timer)


    def _unidirectional_attenuation_calculator(self, Tx_data: dict, Rx_data: dict) -> dict:
        assert bool(Tx_data['total']) == bool(Rx_data['total'])
        assert len(Tx_data['per_lane']) == len(Rx_data['per_lane'])
        logger.debug('Calculating attenuation')
        logger.debug('Tx_data: {}'. format(Tx_data))
        logger.debug('Rx_data: {}'. format(Rx_data))
        total_attenuation_dB = str(round(float(Tx_data['total']['dBm']) - float(Rx_data['total']['dBm']), 2))
        total_attenuation_mW = str(round(float(Tx_data['total']['mW']) - float(Rx_data['total']['mW']), 4))
        per_lane_attenuation = {}
        for laneNum in Tx_data['per_lane'].keys():
            per_lane_attenuation_dBm = str(round(float(Tx_data['per_lane'][laneNum]['dBm']) -
                                             float(Rx_data['per_lane'][laneNum]['dBm']), 2))
            per_lane_attenuation_mW = str(round(float(Tx_data['per_lane'][laneNum]['mW']) -
                                            float(Rx_data['per_lane'][laneNum]['mW']), 4))
            per_lane_attenuation[laneNum]= {'dB': per_lane_attenuation_dBm,
                                            'mW': per_lane_attenuation_mW,
                                            }
        result = {'total':
                    {'dB': total_attenuation_dB,
                    'mW': total_attenuation_mW},
                'per_lane': per_lane_attenuation
                }
        logger.debug('result: {}'. format(result))
        return result


    def _per_link_attenuation_calculator(self, link_data: dict) -> None:
        nodeATx = self.interface_register[link_data['nodeA']][link_data['ifaceA']]['power_data']['Tx']
        nodeBRx = self.interface_register[link_data['nodeB']][link_data['ifaceB']]['power_data']['Rx']
        link_data['attenuation'] = {}
        link_data['attenuation']['AtoB'] = self._unidirectional_attenuation_calculator(nodeATx, nodeBRx)
        nodeBTx = self.interface_register[link_data['nodeB']][link_data['ifaceB']]['power_data']['Tx']
        nodeARx = self.interface_register[link_data['nodeA']][link_data['ifaceA']]['power_data']['Rx']
        link_data['attenuation']['BtoA'] = self._unidirectional_attenuation_calculator(nodeBTx, nodeARx)


    def attenuation_calculator(self) -> None:
        for i in self.link_register:
            self._per_link_attenuation_calculator(i)


