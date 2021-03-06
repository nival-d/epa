import pytest
import power_analyser
import power_handling_functions
import os
import re


SAMPLE_DATA_DIR = 'sample_data'


@pytest.fixture()
def wrapper():
    wrapper = power_analyser.endpointRegister()
    yield wrapper


def test_update_link_register(wrapper):
    data = ('routerA', 'ifaceA', 'routerB', 'ifaceB')
    wrapper.update_link_register(*data)
    assert wrapper.link_register == [{'nodeA': 'routerA', 'ifaceA': 'ifaceA', 'nodeB': 'routerB', 'ifaceB': 'ifaceB'}]


def test_update_link_register_aux_data(wrapper):
    data = {'nodeA': 'routerA', 'ifaceA': 'ifaceA', 'nodeB': 'routerB', 'ifaceB': 'ifaceB', 'link_name':'link_name'}
    wrapper.update_link_register(**data)
    assert wrapper.link_register == [{'nodeA': 'routerA', 'ifaceA': 'ifaceA', 'nodeB': 'routerB',
                                      'ifaceB': 'ifaceB', 'link_name':'link_name'}]


def test_update_interface_register(wrapper):
    data = {'device': 'routerA', 'interface': 'ifaceA'}
    wrapper.update_interface_register(**data)
    print(wrapper.interface_register)
    assert wrapper.interface_register == {'routerA': {'ifaceA': {'ifname': 'ifaceA'}}}


def test_update_interface_register2(wrapper):
    data1 = {'device': 'routerA', 'interface': 'ifaceA'}
    data2 = {'device': 'routerA', 'interface': 'ifaceB'}
    data3 = {'device': 'routerB', 'interface': 'ifaceC'}
    wrapper.update_interface_register(**data1)
    wrapper.update_interface_register(**data2)
    wrapper.update_interface_register(**data3)
    print(wrapper.interface_register)
    assert wrapper.interface_register == {'routerA': {'ifaceA': {'ifname': 'ifaceA'},
                                                      'ifaceB': {'ifname': 'ifaceB'}},
                                          'routerB': {'ifaceC': {'ifname': 'ifaceC'}}}


def test_update_interface_register_duplicate(wrapper):
    data1 = {'device': 'routerA', 'interface': 'ifaceA'}
    data2 = {'device': 'routerA', 'interface': 'ifaceA'}
    wrapper.update_interface_register(**data1)
    with pytest.raises(Exception):
        wrapper.update_interface_register(**data2)


def test_xr_precise_controllers_parsing(wrapper):
    data= '''
Total Tx power: 2.91 mW (  4.65 dBm)
  Lane 0 Tx power: 0.74 mW ( -1.30 dBm)
  Lane 1 Tx power: 0.70 mW ( -1.54 dBm)
  Lane 2 Tx power: 0.73 mW ( -1.34 dBm)
  Lane 3 Tx power: 0.74 mW ( -1.31 dBm)
Total Rx power: 4.11 mW (  6.14 dBm)
  Lane 0 Rx power: 1.28 mW (  1.06 dBm)
  Lane 1 Rx power: 1.04 mW (  0.19 dBm)
  Lane 2 Rx power: 1.08 mW (  0.32 dBm)
  Lane 3 Rx power: 0.71 mW ( -1.48 dBm)'''
    result = wrapper.xr_precise_controllers_parsing(data)
    assert result['Tx']['total']['dBm'] == '4.65'
    assert result['Tx']['total']['mW'] == '2.91'
    assert result['Rx']['total']['dBm'] == '6.14'
    assert result['Rx']['total']['mW'] == '4.11'
    # a physically painful section
    assert result['Tx']['per_lane']['0']['dBm'] == '-1.30'
    assert result['Tx']['per_lane']['0']['mW'] == '0.74'
    assert result['Tx']['per_lane']['1']['dBm'] == '-1.54'
    assert result['Tx']['per_lane']['1']['mW'] == '0.70'
    assert result['Tx']['per_lane']['2']['dBm'] == '-1.34'
    assert result['Tx']['per_lane']['2']['mW'] == '0.73'
    assert result['Tx']['per_lane']['3']['dBm'] == '-1.31'
    assert result['Tx']['per_lane']['3']['mW'] == '0.74'
    assert len(result['Tx']['per_lane'].keys()) == 4

    assert result['Rx']['per_lane']['0']['dBm'] == '1.06'
    assert result['Rx']['per_lane']['0']['mW'] == '1.28'
    assert result['Rx']['per_lane']['1']['dBm'] == '0.19'
    assert result['Rx']['per_lane']['1']['mW'] == '1.04'
    assert result['Rx']['per_lane']['2']['dBm'] == '0.32'
    assert result['Rx']['per_lane']['2']['mW'] == '1.08'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.48'
    assert result['Rx']['per_lane']['3']['mW'] == '0.71'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_xr_simplified_controllers_parsing(wrapper):
    data = '''           Wavelength    Tx Power          Rx Power      Laser Bias
        Lane  (nm)    (dBm)    (mW)     (dBm)     (mW)      (mA)
        --   -----   ------   ------    ------   ------    ------
        1    0     2.2   1.6769     -1.1   0.2738     176.624
        2    0     1.4   1.3649     -3.3   0.0770     176.624
        3    0     2.5   1.7848     -3.5   0.1120     176.624
        4    0     2.8   1.8950     -6.2   0.6707     176.624'''

    result = wrapper.xr_simplified_controllers_parsing(data)

    assert result['Tx']['total']['mW'] == '6.7216'
    assert result['Rx']['total']['mW'] == '1.1335'

    # a physically painful section
    assert result['Tx']['per_lane']['0']['dBm'] == '2.2'
    assert result['Tx']['per_lane']['0']['mW'] == '1.6769'
    assert result['Tx']['per_lane']['1']['dBm'] == '1.4'
    assert result['Tx']['per_lane']['1']['mW'] == '1.3649'
    assert result['Tx']['per_lane']['2']['dBm'] == '2.5'
    assert result['Tx']['per_lane']['2']['mW'] == '1.7848'
    assert result['Tx']['per_lane']['3']['dBm'] == '2.8'
    assert result['Tx']['per_lane']['3']['mW'] == '1.8950'
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-1.1'
    assert result['Rx']['per_lane']['0']['mW'] == '0.2738'
    assert result['Rx']['per_lane']['1']['dBm'] == '-3.3'
    assert result['Rx']['per_lane']['1']['mW'] == '0.0770'
    assert result['Rx']['per_lane']['2']['dBm'] == '-3.5'
    assert result['Rx']['per_lane']['2']['mW'] == '0.1120'
    assert result['Rx']['per_lane']['3']['dBm'] == '-6.2'
    assert result['Rx']['per_lane']['3']['mW'] == '0.6707'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_parsing_sample_output_simple_power_sample1(wrapper):
    test_file = 'power_sample1'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.xr_precise_controllers_parsing(data)
        # a physically painful section
        assert result['Tx']['total']['dBm'] == '4.65'
        assert result['Tx']['total']['mW'] == '2.91'
        assert result['Rx']['total']['dBm'] == '6.14'
        assert result['Rx']['total']['mW'] == '4.11'

        assert result['Tx']['per_lane']['0']['dBm'] == '-1.30'
        assert result['Tx']['per_lane']['0']['mW'] == '0.74'
        assert result['Tx']['per_lane']['3']['dBm'] == '-1.31'
        assert result['Tx']['per_lane']['3']['mW'] == '0.74'
        assert len(result['Tx']['per_lane'].keys()) == 4
        assert result['Rx']['per_lane']['0']['dBm'] == '1.06'
        assert result['Rx']['per_lane']['0']['mW'] == '1.28'
        assert result['Rx']['per_lane']['3']['dBm'] == '-1.48'
        assert result['Rx']['per_lane']['3']['mW'] == '0.71'
        assert len(result['Rx']['per_lane'].keys()) == 4


def test_parsing_sample_output_simple_power_sample2(wrapper):
    test_file = 'power_sample2'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.xr_precise_controllers_parsing(data)
        # a physically painful section
        assert result['Tx']['per_lane']['0']['dBm'] == '1.86'
        assert result['Tx']['per_lane']['0']['mW'] == '1.54'
        assert result['Tx']['per_lane']['3']['dBm'] == '2.57'
        assert result['Tx']['per_lane']['3']['mW'] == '1.81'
        assert len(result['Tx']['per_lane'].keys()) == 4
        assert result['Rx']['per_lane']['0']['dBm'] == '-0.24'
        assert result['Rx']['per_lane']['0']['mW'] == '0.95'
        assert result['Rx']['per_lane']['3']['dBm'] == '1.14'
        assert result['Rx']['per_lane']['3']['mW'] == '1.30'
        assert len(result['Rx']['per_lane'].keys()) == 4


def test_parsing_sample_output_simple_power_sample3(wrapper):
    test_file = 'power_sample3'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.xr_simplified_controllers_parsing(data)
        # a physically painful section
        assert result['Tx']['per_lane']['0']['dBm'] == '2.2'
        assert result['Tx']['per_lane']['0']['mW'] == '1.6769'
        assert result['Tx']['per_lane']['3']['dBm'] == '2.8'
        assert result['Tx']['per_lane']['3']['mW'] == '1.8950'
        assert len(result['Tx']['per_lane'].keys()) == 4
        assert result['Rx']['per_lane']['0']['dBm'] == '-1.1'
        assert result['Rx']['per_lane']['0']['mW'] == '0.2738'
        assert result['Rx']['per_lane']['3']['dBm'] == '-6.2'
        assert result['Rx']['per_lane']['3']['mW'] == '0.6707'
        assert len(result['Rx']['per_lane'].keys()) == 4


def test_juniper_cfp_output(wrapper):
    test_re = power_analyser.JUNIPER_CFP_RE[1]
    test_file = 'juniper_cfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        matched_data = re.findall(test_re, data, flags=re.DOTALL|re.MULTILINE)
    assert len(matched_data) == 4
    assert matched_data[0][0] == '0'
    assert matched_data[0][1] == '131.684'
    assert matched_data[0][2] == '1.002'
    assert matched_data[0][3] == '0.01'
    assert matched_data[0][4] == '0.497'
    assert matched_data[0][5] == '-3.03'


def test_juniper_qsfp_output(wrapper):
    test_re = power_analyser.JUNIPER_CFP_RE[1]
    test_file = 'juniper_cfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        matched_data = re.findall(test_re, data, flags=re.DOTALL|re.MULTILINE)
    assert len(matched_data) == 4
    assert matched_data[0][0] == '0'
    assert matched_data[0][1] == '131.684'
    assert matched_data[0][2] == '1.002'
    assert matched_data[0][3] == '0.01'
    assert matched_data[0][4] == '0.497'
    assert matched_data[0][5] == '-3.03'


def test_lane_notation_mode_selector_1(wrapper):
    import random
    test_data = ['0', '1', '2', '3']
    mode = wrapper.lane_notation_mode_selector(test_data)
    assert mode == 'from_zero'
    for _ in range(10):
        random.shuffle(test_data)
        mode = wrapper.lane_notation_mode_selector(test_data)
        assert mode == 'from_zero'


def test_lane_notation_mode_selector_2(wrapper):
    import random
    test_data = ['1', '8', '2', '3']
    mode = wrapper.lane_notation_mode_selector(test_data)
    assert mode == 'from_one'
    for _ in range(10):
        random.shuffle(test_data)
        mode = wrapper.lane_notation_mode_selector(test_data)
        assert mode == 'from_one'


def test_lane_notation_mode_selector_3(wrapper):
    import random
    test_data = ['8', '3', '2', '3']
    for _ in range(10):
        random.shuffle(test_data)
        with pytest.raises(Exception):
            mode = wrapper.lane_notation_mode_selector(test_data)


def test_lane_num_equaliser1(wrapper):
    test_data = ['0', '1', '2', '3']
    mode = wrapper.lane_notation_mode_selector(test_data)
    assert mode == 'from_zero'
    new_lane_array = []
    for lane in test_data:
        new_lane_array.append(wrapper.lane_num_equaliser(lane, mode))
    assert new_lane_array == ['0', '1', '2', '3']


def test_lane_num_equaliser2(wrapper):
    test_data = ['1', '2', '3', '4']
    mode = wrapper.lane_notation_mode_selector(test_data)
    assert mode == 'from_one'
    new_lane_array = []
    for lane in test_data:
        new_lane_array.append(wrapper.lane_num_equaliser(lane, mode))
    assert new_lane_array == ['0', '1', '2', '3']


def test_attenutation_calculation_1(wrapper):
    file1 = 'power_sample1'
    file2 = 'power_sample2'
    test_file_path1 = os.path.join('tests', SAMPLE_DATA_DIR, file1)
    test_file_path2 = os.path.join('tests', SAMPLE_DATA_DIR, file2)
    with open(test_file_path1, 'r') as fh:
        data = fh.read()
        power_dataA = wrapper.xr_precise_controllers_parsing(data)
    with open(test_file_path2, 'r') as fh:
        data = fh.read()
        power_dataB = wrapper.xr_precise_controllers_parsing(data)
    AtoB = wrapper._unidirectional_attenuation_calculator(power_dataA['Tx'], power_dataB['Rx'])
    # assessment against manual calculations
    assert AtoB['total']['dB'] == '-1.81' # that happens with synthetic data
    assert AtoB['total']['mW'] == '-1.52' # that happens with synthetic data
    assert AtoB['per_lane']['0']['dB'] == '-1.06' # that happens with synthetic data
    assert AtoB['per_lane']['0']['mW'] == '-0.21' # that happens with synthetic data
    assert AtoB['per_lane']['3']['dB'] == '-2.45' # that happens with synthetic data
    assert AtoB['per_lane']['3']['mW'] == '-0.56' # that happens with synthetic data
    BtoA = wrapper._unidirectional_attenuation_calculator(power_dataB['Tx'], power_dataA['Rx'])
    # assessment against manual calculations
    assert BtoA['total']['dB'] == '2.18'
    assert BtoA['total']['mW'] == '2.68'
    assert BtoA['per_lane']['0']['dB'] == '0.8'
    assert BtoA['per_lane']['0']['mW'] == '0.26'
    assert BtoA['per_lane']['3']['dB'] == '4.05'
    assert BtoA['per_lane']['3']['mW'] == '1.1'


def test_attenutation_calculation_2(wrapper):
    file1 = 'power_sample1'
    file2 = 'power_sample3'
    test_file_path1 = os.path.join('tests', SAMPLE_DATA_DIR, file1)
    test_file_path2 = os.path.join('tests', SAMPLE_DATA_DIR, file2)
    with open(test_file_path1, 'r') as fh:
        data = fh.read()
        power_dataA = wrapper.xr_precise_controllers_parsing(data)
    with open(test_file_path2, 'r') as fh:
        data = fh.read()
        power_dataB = wrapper.xr_simplified_controllers_parsing(data)
    AtoB = wrapper._unidirectional_attenuation_calculator(power_dataA['Tx'], power_dataB['Rx'])
    #assessment against manual calculations
    print(power_dataB['Tx'])
    print(power_dataA['Rx'])
    assert AtoB['total']['dB'] == '4.11'
    assert AtoB['total']['mW'] == '1.7765'
    assert AtoB['per_lane']['0']['dB'] == '-0.2'
    assert AtoB['per_lane']['0']['mW'] == '0.4662'
    assert AtoB['per_lane']['3']['dB'] == '4.89'
    assert AtoB['per_lane']['3']['mW'] == '0.0693'
    BtoA = wrapper._unidirectional_attenuation_calculator(power_dataB['Tx'], power_dataA['Rx'])
    # assessment against manual calculations
    assert BtoA['total']['dB'] == '2.13'
    assert BtoA['total']['mW'] == '2.6116'
    assert BtoA['per_lane']['0']['dB'] == '1.14'
    assert BtoA['per_lane']['0']['mW'] == '0.3969'
    assert BtoA['per_lane']['3']['dB'] == '4.28'
    assert BtoA['per_lane']['3']['mW'] == '1.185'


def test_junos_generic_diagnostics_optics_parsing1(wrapper):
    file1 = 'juniper_qsfp_plus'
    test_file_path1 = os.path.join('tests', SAMPLE_DATA_DIR, file1)
    with open(test_file_path1, 'r') as fh:
        data = fh.read()
    result = wrapper.junos_generic_diagnostics_optics_parsing(data)
    assert result['Tx']['per_lane']['0']['dBm'] == None
    assert result['Tx']['per_lane']['0']['mW'] == None
    assert result['Tx']['per_lane']['3']['dBm'] == None
    assert result['Tx']['per_lane']['3']['mW'] == None
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-1.29'
    assert result['Rx']['per_lane']['0']['mW'] == '0.743'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.15'
    assert result['Rx']['per_lane']['3']['mW'] == '0.768'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_junos_generic_diagnostics_optics_parsing2(wrapper):
    file1 = 'juniper_cfp'
    test_file_path1 = os.path.join('tests', SAMPLE_DATA_DIR, file1)
    with open(test_file_path1, 'r') as fh:
        data = fh.read()
    result = wrapper.junos_generic_diagnostics_optics_parsing(data)
    assert result['Tx']['per_lane']['0']['dBm'] == '0.01'
    assert result['Tx']['per_lane']['0']['mW'] == '1.002'
    assert result['Tx']['per_lane']['3']['dBm'] == '0.01'
    assert result['Tx']['per_lane']['3']['mW'] == '1.002'
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-3.03'
    assert result['Rx']['per_lane']['0']['mW'] == '0.497'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.96'
    assert result['Rx']['per_lane']['3']['mW'] == '0.637'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_attenutation_calculation_3(wrapper):
    file1 = 'power_sample1'
    file2 = 'juniper_cfp'
    test_file_path1 = os.path.join('tests', SAMPLE_DATA_DIR, file1)
    test_file_path2 = os.path.join('tests', SAMPLE_DATA_DIR, file2)
    with open(test_file_path1, 'r') as fh:
        data = fh.read()
        power_dataA = wrapper.xr_precise_controllers_parsing(data)
    with open(test_file_path2, 'r') as fh:
        data = fh.read()
        power_dataB = wrapper.junos_generic_diagnostics_optics_parsing(data)
    AtoB = wrapper._unidirectional_attenuation_calculator(power_dataA['Tx'], power_dataB['Rx'])
    #assessment against manual calculations
    print(power_dataB['Tx'])
    print(power_dataA['Rx'])
    assert AtoB['total']['dB'] == '1.06'
    assert AtoB['total']['mW'] == '0.625'
    assert AtoB['per_lane']['0']['dB'] == '1.73'
    assert AtoB['per_lane']['0']['mW'] == '0.243'
    assert AtoB['per_lane']['3']['dB'] == '0.65'
    assert AtoB['per_lane']['3']['mW'] == '0.103'
    BtoA = wrapper._unidirectional_attenuation_calculator(power_dataB['Tx'], power_dataA['Rx'])
    # assessment against manual calculations
    assert BtoA['total']['dB'] == '-0.11'
    assert BtoA['total']['mW'] == '-0.104'
    assert BtoA['per_lane']['0']['dB'] == '-1.05'
    assert BtoA['per_lane']['0']['mW'] == '-0.278'
    assert BtoA['per_lane']['3']['dB'] == '1.49'
    assert BtoA['per_lane']['3']['mW'] == '0.292'


def test_attenutation_calculation_4(wrapper):
    file1 = 'power_sample1'
    file2 = 'juniper_qsfp_plus'
    test_file_path1 = os.path.join('tests', SAMPLE_DATA_DIR, file1)
    test_file_path2 = os.path.join('tests', SAMPLE_DATA_DIR, file2)
    with open(test_file_path1, 'r') as fh:
        data = fh.read()
        power_dataA = wrapper.xr_precise_controllers_parsing(data)
    with open(test_file_path2, 'r') as fh:
        data = fh.read()
        power_dataB = wrapper.junos_generic_diagnostics_optics_parsing(data)
    AtoB = wrapper._unidirectional_attenuation_calculator(power_dataA['Tx'], power_dataB['Rx'])
    # assessment against manual calculations
    assert AtoB['total']['dB'] == '-0.2'
    assert AtoB['total']['mW'] == '-0.143'
    assert AtoB['per_lane']['0']['dB'] == '-0.01'
    assert AtoB['per_lane']['0']['mW'] == '-0.003'
    assert AtoB['per_lane']['3']['dB'] == '-0.16'
    assert AtoB['per_lane']['3']['mW'] == '-0.028'
    BtoA = wrapper._unidirectional_attenuation_calculator(power_dataB['Tx'], power_dataA['Rx'])
    # assessment against manual calculations
    assert BtoA['total']['dB'] == power_analyser.ATTENUATION_INCALCULABLE_INDICATOR
    assert BtoA['total']['mW'] == power_analyser.ATTENUATION_INCALCULABLE_INDICATOR
    assert BtoA['per_lane']['0']['dB'] == power_analyser.ATTENUATION_INCALCULABLE_INDICATOR
    assert BtoA['per_lane']['0']['mW'] == power_analyser.ATTENUATION_INCALCULABLE_INDICATOR
    assert BtoA['per_lane']['3']['dB'] == power_analyser.ATTENUATION_INCALCULABLE_INDICATOR
    assert BtoA['per_lane']['3']['mW'] == power_analyser.ATTENUATION_INCALCULABLE_INDICATOR


def test_safe_power_delta_calculator_1(wrapper):
    powerA = ('0.05','0.002',None,'0.008')
    powerB = ('0.04','0.005','0.2', None)
    result = ('0.01',
              '-0.003',
              power_analyser.ATTENUATION_INCALCULABLE_INDICATOR,
              power_analyser.ATTENUATION_INCALCULABLE_INDICATOR)
    accuracy = (2, 4, 2, 2)
    for sample in zip(powerA, powerB, result, accuracy):
        assert  wrapper.safe_power_delta_calculator(sample[0], sample[1], sample[3]) == sample[2]


def test_juniper_sfp_data(wrapper):
    test_file = 'juniper_sfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.junos_generic_diagnostics_optics_parsing(data)
        assert result['Tx']['per_lane']['0']['dBm'] == '-6.56'
        assert result['Tx']['per_lane']['0']['mW'] == '0.2210'
        assert len(result['Tx']['per_lane'].keys()) == 1
        assert result['Rx']['per_lane']['0']['dBm'] == '-6.15'
        assert result['Rx']['per_lane']['0']['mW'] == '0.2429'
        assert len(result['Rx']['per_lane'].keys()) == 1


def test_juniperxsfp_data(wrapper):
    test_file = 'juniper_xfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.junos_generic_diagnostics_optics_parsing(data)
        assert result['Tx']['per_lane']['0']['dBm'] == '-2.49'
        assert result['Tx']['per_lane']['0']['mW'] == '0.5640'
        assert len(result['Tx']['per_lane'].keys()) == 1
        assert result['Rx']['per_lane']['0']['dBm'] == '-10.74'
        assert result['Rx']['per_lane']['0']['mW'] == '0.0844'
        assert len(result['Rx']['per_lane'].keys()) == 1


def test_dBtomWStr():
    dbs = ['1', '10', '0', '-10']
    mW = ['1.2589', '10.0', '1.0', '0.1']
    for i in zip(dbs, mW):
        assert i[1] == power_handling_functions.dBtomWStr(i[0])


def test_return_sum_of_mW(wrapper):
    mW_data = ['0.1', '0.2', '0.4', '10']
    assert power_handling_functions.return_sum_of_mw(mW_data, mode='as_string') == '10.7'
    mW_data = ['-0.1', '0.2', '0.4', '10']
    assert power_handling_functions.return_sum_of_mw(mW_data, mode='as_string') == '10.5'
    mW_data = [0.1, 0.2, 0.4, 10.0]
    assert power_handling_functions.return_sum_of_mw(mW_data, mode='as_string') == '10.7'
    mW_data = [-0.1, 0.2, 0.4, 10.0]
    assert power_handling_functions.return_sum_of_mw(mW_data, mode='as_string') == '10.5'
    mW_data = ['0.1', '0.2', '0.4', '10']
    assert power_handling_functions.return_sum_of_mw(mW_data) == 10.7000
    mW_data = ['-0.1', '0.2', '0.4', '10']
    assert power_handling_functions.return_sum_of_mw(mW_data) == 10.5000
    mW_data = [0.1, 0.2, 0.4, 10.0]
    assert power_handling_functions.return_sum_of_mw(mW_data) == 10.7000
    mW_data = [-0.1, 0.2, 0.4, 10.0]
    assert power_handling_functions.return_sum_of_mw(mW_data) == 10.5000


def test_cisco_ios_data(wrapper):
    test_file = 'ios_xenpak'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.ios_show_interface_transciever_parsing(data)
    assert result['Tx']['per_lane']['0']['dBm'] == '-1.4'
    assert result['Tx']['per_lane']['0']['mW'] == None
    assert result['Tx']['total']['dBm'] == '-1.4'
    assert result['Tx']['total']['mW'] == '0.7244'
    assert result['Rx']['per_lane']['0']['dBm'] == '-2.9'
    assert result['Rx']['per_lane']['0']['mW'] == None
    assert result['Rx']['total']['dBm'] == '-2.9'
    assert result['Rx']['total']['mW'] == '0.5129'


empty_data_output = {'Tx': {'total': None, 'per_lane': None},
                     'Rx': {'total': None, 'per_lane': None}}


def test_empty_data_cisco_ios(wrapper):
    data = '   \n   \n    \n'
    result = wrapper.ios_show_interface_transciever_parsing(data)
    assert result == empty_data_output


def test_empty_data_juniper(wrapper):
    data = '   \n   \n    \n'
    result = wrapper.junos_generic_diagnostics_optics_parsing(data)
    assert result == empty_data_output


def test_empty_data_xr_precise(wrapper):
    data = '   \n   \n    \n'
    result = wrapper.xr_precise_controllers_parsing(data)
    assert result == empty_data_output


def test_empty_data_xr_simplified(wrapper):
    data = '   \n   \n    \n'
    result = wrapper.xr_simplified_controllers_parsing(data)
    assert result == empty_data_output


def test_generic_data_parser(wrapper):
    data = '''
    Total Tx power: 2.91 mW (  4.65 dBm)
      Lane 0 Tx power: 0.74 mW ( -1.30 dBm)
      Lane 1 Tx power: 0.70 mW ( -1.54 dBm)
      Lane 2 Tx power: 0.73 mW ( -1.34 dBm)
      Lane 3 Tx power: 0.74 mW ( -1.31 dBm)
    Total Rx power: 4.11 mW (  6.14 dBm)
      Lane 0 Rx power: 1.28 mW (  1.06 dBm)
      Lane 1 Rx power: 1.04 mW (  0.19 dBm)
      Lane 2 Rx power: 1.08 mW (  0.32 dBm)
      Lane 3 Rx power: 0.71 mW ( -1.48 dBm)'''
    result = wrapper.generic_data_parser(data, power_analyser.XR_PRECISE_RE_ARRAY)
    assert result['Tx']['total']['dBm'] == '4.65'
    assert result['Tx']['total']['mW'] == '2.91'
    assert result['Rx']['total']['dBm'] == '6.14'
    assert result['Rx']['total']['mW'] == '4.11'
    # a physically painful sectionf
    assert result['Tx']['per_lane']['0']['dBm'] == '-1.30'
    assert result['Tx']['per_lane']['0']['mW'] == '0.74'
    assert result['Tx']['per_lane']['1']['dBm'] == '-1.54'
    assert result['Tx']['per_lane']['1']['mW'] == '0.70'
    assert result['Tx']['per_lane']['2']['dBm'] == '-1.34'
    assert result['Tx']['per_lane']['2']['mW'] == '0.73'
    assert result['Tx']['per_lane']['3']['dBm'] == '-1.31'
    assert result['Tx']['per_lane']['3']['mW'] == '0.74'
    assert len(result['Tx']['per_lane'].keys()) == 4


    assert result['Rx']['per_lane']['0']['dBm'] == '1.06'
    assert result['Rx']['per_lane']['0']['mW'] == '1.28'
    assert result['Rx']['per_lane']['1']['dBm'] == '0.19'
    assert result['Rx']['per_lane']['1']['mW'] == '1.04'
    assert result['Rx']['per_lane']['2']['dBm'] == '0.32'
    assert result['Rx']['per_lane']['2']['mW'] == '1.08'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.48'
    assert result['Rx']['per_lane']['3']['mW'] == '0.71'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_generic_data_parser2(wrapper):
    data = '''           Wavelength    Tx Power          Rx Power      Laser Bias
        Lane  (nm)    (dBm)    (mW)     (dBm)     (mW)      (mA)
        --   -----   ------   ------    ------   ------    ------
        1    0     2.2   1.6769     -1.1   0.2738     176.624
        2    0     1.4   1.3649     -3.3   0.0770     176.624
        3    0     2.5   1.7848     -3.5   0.1120     176.624
        4    0     2.8   1.8950     -6.2   0.6707     176.624'''

    result = wrapper.generic_data_parser(data, power_analyser.XR_SIMPLIFIED_RE_ARRAY)

    assert result['Tx']['total']['mW'] == '6.7216'
    assert result['Rx']['total']['mW'] == '1.1335'

    # a physically painful section
    assert result['Tx']['per_lane']['0']['dBm'] == '2.2'
    assert result['Tx']['per_lane']['0']['mW'] == '1.6769'
    assert result['Tx']['per_lane']['1']['dBm'] == '1.4'
    assert result['Tx']['per_lane']['1']['mW'] == '1.3649'
    assert result['Tx']['per_lane']['2']['dBm'] == '2.5'
    assert result['Tx']['per_lane']['2']['mW'] == '1.7848'
    assert result['Tx']['per_lane']['3']['dBm'] == '2.8'
    assert result['Tx']['per_lane']['3']['mW'] == '1.8950'
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-1.1'
    assert result['Rx']['per_lane']['0']['mW'] == '0.2738'
    assert result['Rx']['per_lane']['1']['dBm'] == '-3.3'
    assert result['Rx']['per_lane']['1']['mW'] == '0.0770'
    assert result['Rx']['per_lane']['2']['dBm'] == '-3.5'
    assert result['Rx']['per_lane']['2']['mW'] == '0.1120'
    assert result['Rx']['per_lane']['3']['dBm'] == '-6.2'
    assert result['Rx']['per_lane']['3']['mW'] == '0.6707'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_generic_data_parser3(wrapper):
    test_file = 'ios_xenpak'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.generic_data_parser(data, power_analyser.IOS_GENERIC_RE_ARRAY)
    print(result)
    assert result['Tx']['per_lane']['0']['dBm'] == '-1.4'
    assert result['Tx']['per_lane']['0']['mW'] == None
    assert result['Tx']['total']['dBm'] == '-1.4'
    assert result['Tx']['total']['mW'] == '0.7244'
    assert result['Rx']['per_lane']['0']['dBm'] == '-2.9'
    assert result['Rx']['per_lane']['0']['mW'] == None
    assert result['Rx']['total']['dBm'] == '-2.9'
    assert result['Rx']['total']['mW'] == '0.5129'

def test_dict_assessor(wrapper):
    re_array = [
        {'per_lane':
             ('ios_generic_ge',
              '^\\w{2}\\d+\\/\\d+\\s*[\\S\\.]*\\s*\\S*\\s[\\-\\+]*\\s*(?P<biasCurrent>\\S*)\\s[\\-\\+]*\\s*'
              '(?P<dBmTxPower>\\S*)\\s*[\\-\\+]*\\s+(?P<dBmRxPower>\\S*)[\\-\\+]*'), 'tx_total': None, 'rx_total': None}]

    match_data = {0: (
        [True, False, False],
        {'per_lane':
             [
                 {'biasCurrent': '39.2', 'dBmTxPower': '-1.4', 'dBmRxPower': '-2.9'}
             ],
            'tx_total': None,
            'rx_total': None})}
    result = wrapper.re_selector(match_data, re_array)
    assert result == (match_data[0][1], re_array[0])


def test_dict_assessor2(wrapper):
    re_array = [
        {'per_lane':
             ('ios_generic_ge',
              '^\\w{2}\\d+\\/\\d+\\s*[\\S\\.]*\\s*\\S*\\s[\\-\\+]*\\s*(?P<biasCurrent>\\S*)\\s[\\-\\+]*\\s*'
              '(?P<dBmTxPower>\\S*)\\s*[\\-\\+]*\\s+(?P<dBmRxPower>\\S*)[\\-\\+]*'), 'tx_total': None, 'rx_total': None},
        {'per_lane':
             ('ios_generic_ge2',
              '^\\w{2}\\d+\\/\\d+\\s*[\\S\\.]*\\s*\\S*\\s[\\-\\+]*\\s*(?P<biasCurrent>\\S*)\\s[\\-\\+]*\\s*'
              '(?P<dBmTxPower>\\S*)\\s*[\\-\\+]*\\s+(?P<dBmRxPower>\\S*)[\\-\\+]*'), 'tx_total': None, 'rx_total': None},
        {'per_lane':
             ('ios_generic_ge3',
              '^\\w{2}\\d+\\/\\d+\\s*[\\S\\.]*\\s*\\S*\\s[\\-\\+]*\\s*(?P<biasCurrent>\\S*)\\s[\\-\\+]*\\s*'
              '(?P<dBmTxPower>\\S*)\\s*[\\-\\+]*\\s+(?P<dBmRxPower>\\S*)[\\-\\+]*'), 'tx_total': None, 'rx_total': None}
    ]
    winning_output = {'per_lane':
             [
                 {'biasCurrent': '39.2', 'dBmTxPower': '-1.4', 'dBmRxPower': '-2.9'}
             ],
            'tx_total': None,
            'rx_total': None}

    losing_output = {'per_lane':
             [
                 {'biasCurrent': '39.2', 'dBmTxPower': '-1.4', 'dBmRxPower': '-2.9'}
             ],
            'tx_total': None,
            'rx_total': None}
    match_data = {
        0: ([True, False, False],losing_output),
        1: ([False, False, False], losing_output),
        2: ([True, False, True], winning_output)
    }
    result = wrapper.re_selector(match_data, re_array)
    assert result == (winning_output, re_array[2])


def test_generic_data_parser4(wrapper):
    test_file = 'juniper_cfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.generic_data_parser(data, power_analyser.JUNIPER_GENERIC_RE_ARRAY)
    assert result['Tx']['per_lane']['0']['dBm'] == '0.01'
    assert result['Tx']['per_lane']['0']['mW'] == '1.002'
    assert result['Tx']['per_lane']['3']['dBm'] == '0.01'
    assert result['Tx']['per_lane']['3']['mW'] == '1.002'
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-3.03'
    assert result['Rx']['per_lane']['0']['mW'] == '0.497'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.96'
    assert result['Rx']['per_lane']['3']['mW'] == '0.637'
    assert len(result['Rx']['per_lane'].keys()) == 4



def test_generic_data_parser5(wrapper):
    test_file = 'juniper_qsfp_plus'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.generic_data_parser(data, power_analyser.JUNIPER_GENERIC_RE_ARRAY)
    assert result['Tx']['per_lane']['0']['dBm'] == None
    assert result['Tx']['per_lane']['0']['mW'] == None
    assert result['Tx']['per_lane']['3']['dBm'] == None
    assert result['Tx']['per_lane']['3']['mW'] == None
    assert len(result['Tx']['per_lane'].keys()) == 4
    assert result['Rx']['per_lane']['0']['dBm'] == '-1.29'
    assert result['Rx']['per_lane']['0']['mW'] == '0.743'
    assert result['Rx']['per_lane']['3']['dBm'] == '-1.15'
    assert result['Rx']['per_lane']['3']['mW'] == '0.768'
    assert len(result['Rx']['per_lane'].keys()) == 4


def test_generic_data_parser6(wrapper):
    test_file = 'juniper_sfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.generic_data_parser(data, power_analyser.JUNIPER_GENERIC_RE_ARRAY)
    assert result['Tx']['per_lane']['0']['dBm'] == '-6.56'
    assert result['Tx']['per_lane']['0']['mW'] == '0.2210'
    assert len(result['Tx']['per_lane'].keys()) == 1
    assert result['Rx']['per_lane']['0']['dBm'] == '-6.15'
    assert result['Rx']['per_lane']['0']['mW'] == '0.2429'
    assert len(result['Rx']['per_lane'].keys()) == 1


def test_generic_data_parser7(wrapper):
    test_file = 'juniper_xfp'
    test_file_path = os.path.join('tests', SAMPLE_DATA_DIR, test_file)
    with open(test_file_path, 'r') as fh:
        data = fh.read()
        result = wrapper.generic_data_parser(data, power_analyser.JUNIPER_GENERIC_RE_ARRAY)
    assert result['Tx']['per_lane']['0']['dBm'] == '-2.49'
    assert result['Tx']['per_lane']['0']['mW'] == '0.5640'
    assert len(result['Tx']['per_lane'].keys()) == 1
    assert result['Rx']['per_lane']['0']['dBm'] == '-10.74'
    assert result['Rx']['per_lane']['0']['mW'] == '0.0844'
    assert len(result['Rx']['per_lane'].keys()) == 1

