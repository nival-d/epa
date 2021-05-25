import pytest
import power_analyser
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

    assert str(round(result['Tx']['total']['mW'], 4)) == '6.7216'
    assert str(round(result['Rx']['total']['mW'], 4)) == '1.1335'

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
    test_re = power_analyser.JUNIPER_CFP_RE
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
    test_re = power_analyser.JUNIPER_CFP_RE
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

