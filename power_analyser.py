
import cli_walker
import re
import logging
import time
import power_handling_functions


logger = logging.getLogger()

JUNIPER_CFP_RE = ('cfp_re', r'^\s*Lane\s*(?P<laneNum>\d+).*?Laser\sbias\scurrent\s*:\s*(?P<current>[\d\.]*)\s*mA.*?Laser\soutput\s*power' \
                 r'\s*:\s*(?P<TxmWPower>\S*)\s*\w*\s\/\s*(?P<TxdBPower>\S*)\s*dBm\n.*?\s*.*?Laser\sreceiver\spower\s*:\s*' \
                 r'(?P<RxmWPower>\S*)\s*mW\s*\/\s*(?P<RxdBPower>\S*)\s\w*\n')
JUNIPER_QSFP_RE = ('qsfp_re', r'^\s*Lane\s*(?P<laneNum>\d+).*?Laser\sbias\scurrent\s*:\s*(?P<current>[\d\.]*)\s*mA\n\s*Laser\s' \
                  r'receiver\spower\s*:\s*(?P<RxmWPower>\S*)\s*mW\s*\/\s*(?P<RxdBPower>\S*)')
JUNIPER_SFP_RE = ('sfp_re',r'Laser\sbias\scurrent\s*:\s*(?P<current>[\d\.]*)\s*mA.*?Laser\soutput\s*power\s*:\s*'
                           r'(?P<TxmWPower>\S*)\s*\w*\s\/\s(?P<TxdBPower>[\-\.\w\d]*).*Receiver\ssignal\saverage\s'
                           r'optical\spower\s*:\s*(?P<RxmWPower>\S*)\smW\s\/\s(?P<RxdBPower>\S*)\sdBm')
JUNIPER_XFP_RE = ('xfp_re', r'Laser\sbias\scurrent\s*:\s*(?P<current>[\d\.]*)\s*mA.*?Laser\soutput\s*power\s*:\s*'
                            r'(?P<TxmWPower>\S*)\s*\w*\s\/\s(?P<TxdBPower>[\-\.\w\d]*).*Laser\srx\spower\s*:\s*'
                            r'(?P<RxmWPower>\S*)\smW\s\/\s(?P<RxdBPower>\S*)\sdBm')
CISCO_IOS_RE = ('ios_generic_ge', r'^\w{2}\d+\/\d+\s*[\S\.]*\s*\S*\s[\-\+]*\s*(?P<biasCurrent>\S*)\s[\-\+]*\s*'
                                  r'(?P<dBmTxPower>\S*)\s*[\-\+]*\s+(?P<dBmRxPower>\S*)[\-\+]*')

XR_SIMPLIFIED_PER_LANE = ('xr_simplified_per_lane', r'^\s*(?P<laneNum>\d)\s+\S+\s+(?P<dBmTxPower>[\d\.\-]*)\s+(?P<mWTxPower>'
                                           r'[\d\.\-]*)\s+(?P<dBmRxPower>[\d\.\-]+)\s*(?P<mWRxPower>[\d\.\-]+)\s+'
                                           r'(?P<laserBias>[\d\.\-]{3,})')

XR_PRECISE_TOTAL_TX = ('xr_precise_total_tx',r'Total Tx power:\s(?P<mWTxPower>\S*)\s*\S*\s\(\s*(?P<dBmTxPower>[\-\d\.]*)\sdBm\)')
XR_PRECISE_TOTAL_RX = ('xr_precise_total_rx',r'Total Rx power:\s(?P<mWRxPower>\S*)\s*\S*\s\(\s*(?P<dBmRxPower>[\-\d\.]*)\sdBm\)')
XR_PRECISE_PER_LANE = ('xr_precise_per_lane', r'^\s*Lane\s(?P<laneNum>\d)\s(?P<direction>\S*)\spower:\s(?P<mWPower>\S*)\s'
                                              r'\S*\s*\(\s*(?P<dBmPower>[\d\.\-]*)\sdBm\)')

RE_PER_LANE_GROUP_KEY = 'per_lane'
RE_TOTAL_TX_GROUP_KEY = 'tx_total'
RE_TOTAL_RX_GROUP_KEY = 'rx_total'


XR_PRECISE_RE_ARRAY = {
    RE_PER_LANE_GROUP_KEY: XR_PRECISE_PER_LANE,
    RE_TOTAL_TX_GROUP_KEY: XR_PRECISE_TOTAL_TX,
    RE_TOTAL_RX_GROUP_KEY: XR_PRECISE_TOTAL_RX}

XR_SIMPLIFIED_RE_ARRAY = {
    RE_PER_LANE_GROUP_KEY: XR_SIMPLIFIED_PER_LANE,
    RE_TOTAL_TX_GROUP_KEY: None,
    RE_TOTAL_RX_GROUP_KEY: None}

IOS_GENERIC_RE_ARRAY = [{
    RE_PER_LANE_GROUP_KEY: CISCO_IOS_RE,
    RE_TOTAL_TX_GROUP_KEY: None,
    RE_TOTAL_RX_GROUP_KEY: None}]

JUNIPER = {
    RE_PER_LANE_GROUP_KEY: CISCO_IOS_RE,
    RE_TOTAL_TX_GROUP_KEY: None,
    RE_TOTAL_RX_GROUP_KEY: None}

JUNIPER_GENERIC_RES = [JUNIPER_CFP_RE, JUNIPER_QSFP_RE, JUNIPER_SFP_RE, JUNIPER_XFP_RE]
ATTENUATION_INCALCULABLE_INDICATOR = 'N/A'
DBM_KEY_NOTATION = 'dBm'
MW_KEY_NOTATION = 'mW'


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
        command = 'show controllers {}'.format(interface)
        controllers_data = self.walker.execute(host, command)
        return controllers_data


    def get_xrcontrollers_phy_details(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show controllers phy: {}'. format(host, interface))
        command = 'show controllers {} phy'.format(interface)
        controllers_data = self.walker.execute(host, command)
        return controllers_data


    def get_junos_disgnostics_details(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show command for interface: {}'.format(host, interface))
        command = 'show interfaces diagnostics optics {}'.format(interface)
        controllers_data = self.walker.execute(host, command)
        return controllers_data

    def get_ios_show_int_transciever(self, host: str, interface: str) -> str:
        logger.info('Preparing to perform a show command for interface: {}'.format(host, interface))
        command = 'show interfaces {} transciever'.format(interface)
        controllers_data = self.walker.execute(host, command)
        return controllers_data


    def perLane_transformer(self, data, direction: str) -> dict:
        logger.error('Extracting per lane power details in direction: {}'. format(direction))
        logger.error('Raw_data: {}'. format(data))
        if data:
            result = {}
            for line in iter(data):
                if line[1] == direction:
                    result[line[0]] = {
                             'dBm': line[3],
                             'mW': line[2]
                    }
            logger.debug('Transformed data: {}'. format(result))
        else:
            result = None
        return result


    def safe_re_getter(self, re_match_object, target_group):
        if re_match_object:
            try:
                return re_match_object.group(target_group)
            except:
                return None
        else:
            return None


    def gapfilling_getter(self, re_match_object, direction):

        logger.error('Troubleshooting now')
        logger.error('re_match_object')
        logger.error(re_match_object)
        if re_match_object:
            if direction == 'Tx':
                return {
                'dBm': self.safe_re_getter(re_match_object, 'dBmTxPower'),
                'mW': self.safe_re_getter(re_match_object, 'mWTxPower')}
            if direction == 'Rx':
                return {
                    'dBm': self.safe_re_getter(re_match_object, 'dBmRxPower'),
                    'mW': self.safe_re_getter(re_match_object, 'mWRxPower')}
        else:
            return None


    def _simplified_power_summariser(self, data: list, direction: str) -> dict:
        import math
        logger.info('Landed in a simplified power summariser')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'. format(direction))
        lane_mW_data = []
        if not data:
            return None
        else:
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


    def _junos_power_summariser(self, data: list, direction: str) -> dict:
        import math
        logger.info('Landed in a junos power summariser')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'. format(direction))
        lane_mW_data = []
        for line in iter(data):
            if direction == 'Tx':
                lane_mW_data.append(line.get('TxmWPower'))
            elif direction == 'Rx':
                lane_mW_data.append(line.get('RxmWPower'))
            else:
                raise Exception('Unknown direction: {}'. format(direction))
        if all(lane_mW_data):
            float_data = [float(x) for x in lane_mW_data]
            total_mW = sum(float_data)
            total_dBm = 10*math.log10(total_mW)
            return_total_mW = str(round(total_dBm, 2))
            return_total_dBm = str(round(total_mW, 4))
        else:
            return_total_mW = None
            return_total_dBm = None
        logger.debug('total_mW: {}'. format(return_total_mW))
        logger.debug('total_dBm: {}'. format(return_total_dBm))
        return {'dBm': return_total_mW,
                'mW': return_total_dBm}


    def lane_notation_mode_selector(self, lane_numbers: list) ->str:
        logger.error('Selecting optic lane notation mode, raw lane_numbers: {}'. format(lane_numbers))
        if lane_numbers == [None]:
            logger.info('Hit optics with a single lane')
            return 'unnotated'
        else:
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
        elif mode == 'unnotated':
            return '0'
        else:
            raise Exception('Bad mode: {}'.format(mode))


    def _simplified_perLane_transformer(self, data: list, direction: str) -> dict:
        logger.info('Started the per lane power transformer')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'.format(direction))
        result = {}
        if data:
            lane_numbers = [x[0] for x in data]
            lane_notation_mode = self.lane_notation_mode_selector(lane_numbers)
            for line in data:
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
        else:
            return None


    def _junos_perLane_transformer(self, data: list, direction: str):
        logger.info('Started the per lane power transformer')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'.format(direction))
        result = {}
        lane_numbers = [x.get('laneNum') for x in iter(data)]

        logger.error(data)
        lane_notation_mode = self.lane_notation_mode_selector(lane_numbers)
        for line in data:
            # we count lanes from 0. Some software is inconsistent. Normalizing now.
            lane_num = self.lane_num_equaliser(line.get('laneNum'), lane_notation_mode)
            result[lane_num] = {}
            if direction == 'Tx':
                result[lane_num] = {
                    'dBm': line.get('TxdBPower'),
                    'mW': line.get('TxmWPower')
                }
            elif direction == 'Rx':
                result[lane_num] = {
                    'dBm': line.get('RxdBPower'),
                    'mW': line.get('RxmWPower')
                }
            else:
                raise Exception('unknown direction: {}'.format(direction))
        logger.debug('Transformed_result: {}'.format(result))
        return result


    def xr_precise_controllers_parsing(self, data: str) -> dict:
        logger.error('Starting a precise parsing process')
        logger.error('raw data:{}'. format(data))
        txTotal_data = re.search(XR_PRECISE_TOTAL_TX[1], data, re.MULTILINE)
        rxTotal_data = re.search(XR_PRECISE_TOTAL_RX[1], data, re.MULTILINE)
        perLane_data = re.findall(XR_PRECISE_PER_LANE[1], data, re.MULTILINE)
        transformed_data = {
            'Tx':
                {'total': self.gapfilling_getter(txTotal_data, 'Tx'),
                'per_lane': self.perLane_transformer(perLane_data, 'Tx')},
            'Rx':
                {'total': self.gapfilling_getter(rxTotal_data, 'Rx'),
            'per_lane': self.perLane_transformer(perLane_data, 'Rx')}
        }
        return transformed_data


    def xr_simplified_controllers_parsing(self, data) -> dict:
        logger.debug('Starting a simplified parsing process')
        logger.debug('raw data:{}'. format(data))
        perLane_data = re.findall(XR_SIMPLIFIED_PER_LANE[1], data, re.MULTILINE)
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


    def generic_lane_normalizer(self, data: list, direction: str):
        logger.info('Started the per lane power normaliser')
        logger.debug('raw data: {}'.format(data))
        logger.debug('direction: {}'.format(direction))
        result = {}
        lane_numbers = [x.get('laneNum') for x in iter(data)]
        logger.error(data)

        if not data:
            return None
        else:
            lane_notation_mode = self.lane_notation_mode_selector(lane_numbers)

            for line in data:
                # we count lanes from 0. Some software is inconsistent. Normalizing now.
                lane_num = self.lane_num_equaliser(line.get('laneNum'), lane_notation_mode)

                lane_direction = line.get('direction')
                logger.debug('Looking at lane: {}'. format(lane_num))
                logger.debug('Assessed line: {}'.format(line))
                logger.debug('Assessed direction: {}'. format(direction))
                logger.debug('Detected lane direction: {}'.format(lane_direction))
                if not result.get(lane_num):
                    result[lane_num] = {}
                logger.debug('Interim data storage: {}'. format(result))
                if direction == 'Tx':
                    logger.debug('Hopped in the Tx part')

                    #todo - move that logic outside
                    if line.get('dBmTxPower'):
                        dBm = line.get('dBmTxPower')
                        logger.debug('Lane has dBmTxPower, value: {}'. format(dBm))
                        result[lane_num][DBM_KEY_NOTATION] = dBm
                    if line.get('dBmPower') and (line.get('direction') == 'Tx'):
                        dBm = line.get('dBmPower')
                        logger.debug('Lane has dBmPower AND direction is TX, value: {}'. format(dBm))
                        result[lane_num][DBM_KEY_NOTATION] = dBm
                    else:
                        pass

                    if line.get('mWTxPower'):
                        mW = line.get('mWTxPower')
                        logger.debug('Lane has mWTxPower, value: {}'. format(mW))
                        result[lane_num][MW_KEY_NOTATION] = mW
                    if line.get('mWPower') and (line.get('direction') == 'Tx'):
                        mW = line.get('mWPower')
                        logger.debug('Lane has mWPower AND direction is TX, value: {}'. format(mW))
                        result[lane_num][MW_KEY_NOTATION] = mW

                    if not result[lane_num].get(MW_KEY_NOTATION):
                        result[lane_num][MW_KEY_NOTATION] = None
                    if not result[lane_num].get(DBM_KEY_NOTATION):
                        result[lane_num][DBM_KEY_NOTATION] = None


                elif direction == 'Rx':
                    logger.debug('Hopped in the Rx part')
                    if line.get('dBmRxPower'):
                        dBm = line.get('dBmRxPower')
                        logger.debug('Lane has dBmRxPower, value: {}'. format(dBm))
                        result[lane_num][DBM_KEY_NOTATION] = dBm
                    if line.get('dBmPower') and (line.get('direction') == 'Rx'):
                        dBm = line.get('dBmPower')
                        logger.debug('Lane has dBmPower AND direction is RX, value: {}'. format(dBm))
                        result[lane_num][DBM_KEY_NOTATION] = dBm


                    if line.get('mWRxPower'):
                        mW = line.get('mWRxPower')
                        logger.debug('Lane has mWRxPower, value: {}'. format(mW))
                        result[lane_num][MW_KEY_NOTATION] = mW
                    if line.get('mWPower') and (line.get('direction') == 'Rx'):
                        mW = line.get('mWPower')
                        logger.debug('Lane has mWPower AND direction is RX, value: {}'. format(mW))
                        result[lane_num][MW_KEY_NOTATION] = mW

                    if not result[lane_num].get(MW_KEY_NOTATION):
                        result[lane_num][MW_KEY_NOTATION] = None
                    if not result[lane_num].get(DBM_KEY_NOTATION):
                        result[lane_num][DBM_KEY_NOTATION] = None

                else:
                    raise Exception('unknown direction: {}'.format(direction))
            logger.debug('Direction is {}'. format(direction))
            logger.debug('Transformed_result: {}'.format(result))
            return result


    def directional_power_summariser(self, data, direction):
        logger.error('Looking at data while summarizing: {}'. format(data))
        values = {DBM_KEY_NOTATION: [],
                  MW_KEY_NOTATION: []}

        if not data.get(direction):
            return None
        logger.debug('Extracting dbm and mw data, direction = {}'. format(direction))
        if data[direction]['per_lane']:
            for lane in data.get(direction)['per_lane']:
                logger.debug('looking at lane: {}'.format(lane))
                logger.error(data.get(direction))
                for metric in data[direction]['per_lane'][lane].keys():
                    logger.error('Summarizing power, direction = {}, metric = {}, lane = {}'.format(direction, metric, lane))
                    values[metric].append(data[direction]['per_lane'][lane][metric])
            logger.error('Extracted raw_data: {}'. format(values))
            # assessing which notation is used - mw or dbm
            logger.debug('values for summarising: {}'. format(values))

            if all(values[MW_KEY_NOTATION]):
                logger.error('Finally got sum data in db: {}'.format(
                power_handling_functions.return_sum_of_dbm_from_mw(values[MW_KEY_NOTATION])))
                return {DBM_KEY_NOTATION: power_handling_functions.return_sum_of_dbm_from_mw(values[MW_KEY_NOTATION],
                                                                                         mode='as_string'),
                    MW_KEY_NOTATION: power_handling_functions.return_sum_of_mw(values[MW_KEY_NOTATION],
                                                                               mode='as_string')}
            elif all(values[DBM_KEY_NOTATION]):
                return {DBM_KEY_NOTATION: power_handling_functions.return_sum_of_dbm(values[DBM_KEY_NOTATION], mode='as_string'),
                       MW_KEY_NOTATION: power_handling_functions.return_sum_of_mW_from_dbm(values[DBM_KEY_NOTATION], mode='as_string')}
            else:
                raise Exception('Inconsistent lane power notation')
        else:
            return None


    def ios_show_interface_transciever_parsing(self, data) -> dict:
        logger.debug('Starting a parsing process')
        logger.debug('raw data:{}'. format(data))
        extract = re.finditer(CISCO_IOS_RE[1], data, re.MULTILINE | re.DOTALL)
        extracted_data= self.iterator_to_dict(extract)
        transformed_data = {'Tx': {'per_lane': self.generic_lane_normalizer(extracted_data, 'Tx')},
                            'Rx': {'per_lane': self.generic_lane_normalizer(extracted_data, 'Rx')}}
        logger.error('Extracted data: {}'. format(transformed_data))
        if transformed_data:
            transformed_data['Tx']['total'] = self.directional_power_summariser(transformed_data, 'Tx')
            transformed_data['Rx']['total'] = self.directional_power_summariser(transformed_data, 'Rx')
        logger.error('final_data: {}'.format(transformed_data))
        return transformed_data


    def dict_assessor(self, ddict):
        logger.debug('raw data: {}'.format(ddict))
        result = [bool(ddict[kkey]) for kkey in ddict.keys()]
        logger.debug('result of array assessment: {}'.format(result))
        return result


    def re_selector(self, match_data, re_array_list):
        # selecting an item with most matches in match_data
        # returning a correcsponding item from the re_array_list
        # you'd rather use numpy for that. this function is terrible
        # todo simplify
        logger.debug('Hit the re_selector function')
        logger.error(match_data)
        logger.error(re_array_list)
        _ = {}
        logger.debug('match_data = {}'.format(match_data))
        logger.debug('re_array_list = {}'.format(re_array_list))
        for num, item in enumerate(match_data):
            print(num)
            print(item)
            print(match_data[item])
            length = len(match_data[item][0])
            num_trues = sum(match_data[item][0])
            logger.debug('num_trues: {}'. format(num_trues))
            logger.debug('total length of match entity: {}'. format(length))
            _[num] = num_trues/length
        match_scores = {}
        logger.debug('Our transformed data storage: {}'. format(_))
        logger.debug('Starting the match score assessment')
        for key in _.keys():
            match_rating = _[key]
            if not match_rating in match_scores:
                match_scores[match_rating] = key
            else:
                raise Exception('duplicate match ratings, best RE cannot be determined')
        logger.debug('Match ratings: {}'. format(match_scores))
        ratings_sorted = [x for x in match_scores.keys()]
        ratings_sorted.sort(reverse=True)
        logger.debug('Unsorted rating: {}'. format(ratings_sorted))
        result = re_array_list[match_scores[ratings_sorted[0]]]
        logger.debug('Result of selecting an RE with the most hits on re matched data: {}'.format(result))
        return result


    def generic_data_parser(self, data: str,
                            re_data,
                            lane_normalizer=generic_lane_normalizer,
                            power_summarizer=directional_power_summariser):
        logger.debug('Starting a generic parsing process')
        logger.debug('raw data:{}'. format(data))
        match_data = {}
        if isinstance(re_data, list):
            for num, re_array_item in enumerate(re_data):
                logger.debug('re_array_list : {}'. format(re_data))
                raw_extracts = {}
                for key in re_array_item.keys():
                    if re_array_item.get(key):
                        print('looking at re: {}'. format(re_array_item.get(key)[1]))
                        temp_extract = re.finditer(re_array_item.get(key)[1], data, re.MULTILINE | re.DOTALL)
                        raw_extracts[key] = self.iterator_to_dict(temp_extract)
                        logger.error(raw_extracts[key])
                    else:
                        raw_extracts[key] = None
                assessment = self.dict_assessor(raw_extracts)
                match_data[num] = (assessment, raw_extracts)
            extracts, re_array = self.re_selector(match_data, re_data)
        else:

            extracts = {}
            re_array = re_data
            for key in re_data.keys():
                if re_data.get(key):
                    print('looking at re: {}'.format(re_data.get(key)[1]))
                    temp_extract = re.finditer(re_data.get(key)[1], data, re.MULTILINE | re.DOTALL)
                    extracts[key] = self.iterator_to_dict(temp_extract)

                    logger.error(extracts[key])
                else:
                    extracts[key] = None

        logger.error(extracts)
        logger.error('Normalizing lane data: {}'.format(extracts[RE_PER_LANE_GROUP_KEY]))
        transformed_data = {'Tx': {'per_lane': lane_normalizer(self, data=extracts[RE_PER_LANE_GROUP_KEY], direction='Tx')},
                            'Rx': {'per_lane': lane_normalizer(self, data=extracts[RE_PER_LANE_GROUP_KEY], direction='Rx')}}
        logger.info('Here\'s our RE array data: {}'.format(re_array))
        logger.info('Here\'s our interim transformed data: {}'.format(transformed_data))
        if re_array.get(RE_TOTAL_TX_GROUP_KEY):
            logger.info('The groups has a total tx key defined. processing now')
            tx_total_raw = re.search(re_array[RE_TOTAL_TX_GROUP_KEY][1], data, re.MULTILINE)
            tx_total = self.gapfilling_getter(tx_total_raw, 'Tx')
        else:
            logger.info('The groups does not have a total tx key defined. summarizing now')
            tx_total = power_summarizer(self, transformed_data, 'Tx')

        if re_array.get(RE_TOTAL_RX_GROUP_KEY):
            logger.info('The groups has a total rx key defined. processing now')
            rx_total_raw = re.search(re_array[RE_TOTAL_RX_GROUP_KEY][1], data, re.MULTILINE)
            rx_total = self.gapfilling_getter(rx_total_raw, 'Rx')
        else:
            logger.info('The groups does not have a total rx key defined. summarizing now')
            rx_total = power_summarizer(self, transformed_data, 'Rx')

        transformed_data['Rx']['total'] = rx_total
        transformed_data['Tx']['total'] = tx_total
        logger.error(transformed_data)
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
            transformed_data = {
                'Tx':
                    {'total': self._junos_power_summariser(extracted_data[element_num], 'Tx'),
                     'per_lane': self._junos_perLane_transformer(extracted_data[element_num], 'Tx')},
                'Rx':
                    {'total': self._junos_power_summariser(extracted_data[element_num], 'Rx'),
                     'per_lane': self._junos_perLane_transformer(extracted_data[element_num], 'Rx')}
            }
            logger.debug('final_data: {}'.format(transformed_data))
            return transformed_data
        elif not any(re_match_array):
            logger.error('Junos diagnostics output didn\'t match any regexes')
            transformed_data = {'Tx': {'total': None, 'per_lane': None},
                     'Rx': {'total': None, 'per_lane': None}}
            logger.debug('final_data: {}'.format(transformed_data))
            return transformed_data
        else:
            logger.error(re_match_array)
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

    def _generic_ios_power_extractor(self, device: str, interface: str) -> dict:
        ddata = self.get_ios_show_int_transciever(device, interface)
        power_data = self.ios_show_interface_transciever_parsing(ddata)
        return power_data



    def interface_processor_selector(self, device_trait: str):
        local_function_register = {
            'xrsimplified': self._simplified_xr_power_extractor,
            'xrprecise': self._precise_xr_power_extractor,
            'junos_generic': self._generic_junos_power_extractor,
            'cisco_ios': self._generic_ios_power_extractor,
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


    def safe_power_delta_calculator(self, Tx: str, Rx: str, accuracy=2) -> str:
        if Tx and Rx:
            attenuation = str(round(float(Tx) - float(Rx), accuracy))
        else:
            attenuation = ATTENUATION_INCALCULABLE_INDICATOR
        return attenuation


    def _unidirectional_attenuation_calculator(self, Tx_data: dict, Rx_data: dict) -> dict:
        assert bool(Tx_data['total']) == bool(Rx_data['total'])
        assert len(Tx_data['per_lane']) == len(Rx_data['per_lane'])
        logger.debug('Calculating attenuation')
        logger.error('Tx_data: {}'. format(Tx_data))
        logger.error('Rx_data: {}'. format(Rx_data))
        total_attenuation_dB = self.safe_power_delta_calculator(Tx_data['total']['dBm'], Rx_data['total']['dBm'], 2)
        total_attenuation_mW = self.safe_power_delta_calculator(Tx_data['total']['mW'], Rx_data['total']['mW'], 4)

        per_lane_attenuation = {}
        for laneNum in Tx_data['per_lane'].keys():
            per_lane_attenuation_dBm = self.safe_power_delta_calculator(
                Tx_data['per_lane'][laneNum]['dBm'],
                Rx_data['per_lane'][laneNum]['dBm'],
                2)

            per_lane_attenuation_mW = self.safe_power_delta_calculator(
                Tx_data['per_lane'][laneNum]['mW'],
                Rx_data['per_lane'][laneNum]['mW'],
                4
            )
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
